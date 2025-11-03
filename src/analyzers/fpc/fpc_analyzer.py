import ast
import os
import json
from typing import Dict, List, Set, Optional

from core.models.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer
from analyzers.ml_content_analyzer import MLContentAnalyzer
from analyzers.fpc.nloc_calculator import NLOCCalculator
from config.settings import settings


class FPCAnalyzer(BaseAnalyzer):
    """
    Functional Pipeline Cohesion Analyzer.
    
    Evaluates code organization by analyzing:
    1. ML pipeline stage/phase cohesion
    2. ML content presence (via MLContentAnalyzer)
    3. NLOC (Non-comment Lines of Code) to determine file size
    """
    
    def __init__(self, session_id: str, local_path: str, context=None):
        super().__init__(session_id, local_path, context)
        
        pipeline_stages_json_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'config',
            'pipeline_stages.json'
        )
        
        if os.path.exists(pipeline_stages_json_path):
            with open(pipeline_stages_json_path, 'r') as f:
                self.config = json.load(f)
        else:
            raise FileNotFoundError(
                f"Pipeline stages config not found at {pipeline_stages_json_path}"
            )

        self.stage_to_phase = {}
        for phase, stages in self.config.get('phases', {}).items():
            for stage in stages:
                self.stage_to_phase[stage] = phase
        
        self.ml_content_analyzer = MLContentAnalyzer(
            session_id=session_id,
            local_path=local_path,
            context=context
        )
        
        nloc_threshold = settings.ANALYZER_CONFIG.get('fpc', {}).get('nloc_threshold', 30)
        self.nloc_calculator = NLOCCalculator(threshold=nloc_threshold)
    
    @property
    def analyzer_id(self) -> str:
        return "fpc"
    
    def analyze(self) -> AnalysisResult:
        """
        Run FPC analysis on Python files.
        
        The files to analyze are determined by the AnalysisContext configuration:
        - If context.all_files=True: Analyzes ALL Python files
        - If context.all_files=False: Prefers ML pipeline files, falls back to all files
        
        Returns:
            AnalysisResult with FPC score based on ML pipeline cohesion, 
            ML content, and NLOC analysis.
        """
        results = {
            'files': {},
            'summary': {
                'total_files': 0,
                'high_cohesion': 0,
                'medium_cohesion': 0,
                'low_cohesion': 0,
                'non_ml_files': 0,
                'small_files': 0,
                'scan_mode': self.context.get_scan_mode(),
                'nloc_threshold': self.nloc_calculator.get_threshold()
            }
        }
        
        python_files = self.context.get_python_files()
        results['summary']['total_files'] = len(python_files)
        
        for py_file in python_files:
            tree = self.context.get_file_ast(py_file)
            source = self.context.get_file_source(py_file)
            
            if tree is None or source is None:
                continue
            
            file_result = self._analyze_file(tree, source, py_file)
            results['files'][py_file] = file_result
            
            self.context.set_file_metric(py_file, 'fpc', file_result)
            
            if not file_result['ml_content']:
                results['summary']['non_ml_files'] += 1
            elif not file_result['above_nloc_threshold']:
                results['summary']['small_files'] += 1
            else:
                cohesion_level = file_result['cohesion_level']
                if cohesion_level == 'high':
                    results['summary']['high_cohesion'] += 1
                elif cohesion_level == 'medium':
                    results['summary']['medium_cohesion'] += 1
                elif cohesion_level == 'low':
                    results['summary']['low_cohesion'] += 1
        
        if results['summary']['total_files'] > 0:
            score = self._calculate_cohesion_score(results)
        else:
            score = 0
        
        messages = self._generate_messages(results)
        
        return self._create_result(
            score=round(score, 2),
            message_count={'messages': messages},
            module_count=results['summary']['total_files'],
            details=results
        )
    
    def _analyze_file(self, tree: ast.Module, source: str, file_path: str) -> Dict:
        """
        Analyze a single file for FPC (Functional Pipeline Cohesion).
        
        Evaluates:
        1. Pipeline stage/phase cohesion
        2. ML content presence
        3. NLOC (file size)
        """
        nloc = self.nloc_calculator.calculate_nloc(source)
        above_nloc_threshold = self.nloc_calculator.is_above_threshold(nloc)
        
        ml_content = self.ml_content_analyzer.analyze_file(file_path)
        
        functions = self._extract_functions(tree)
        
        file_stages_from_pipeline = self._get_file_stages_from_pipeline(file_path)
        
        function_stages = {}
        is_script_file = '<module_script>' in functions
        
        for func_name, func_node in functions.items():
            if file_stages_from_pipeline:
                stages = file_stages_from_pipeline
            else:
                stages = self._detect_stages(func_node, file_path)
            
            function_stages[func_name] = stages
        
        all_stages = set()
        for stages in function_stages.values():
            all_stages.update(stages)
        
        unique_stages = len(all_stages)
        all_phases = {self.stage_to_phase.get(stage, 'unknown') for stage in all_stages}
        all_phases.discard('unknown')
        unique_phases = len(all_phases)
        
        cohesion_level = self._determine_cohesion_level(
            unique_stages, 
            unique_phases,
            ml_content,
            above_nloc_threshold
        )
        
        result = {
            'unique_stages': unique_stages,
            'unique_phases': unique_phases,
            'stages_detected': list(all_stages),
            'phases_detected': list(all_phases),
            'cohesion_level': cohesion_level,
            'function_stages': function_stages,
            'source': 'pipeline_metadata' if file_stages_from_pipeline else 'heuristic',
            'ml_content': ml_content,
            'nloc': nloc,
            'above_nloc_threshold': above_nloc_threshold,
            'is_script_file': is_script_file
        }
        
        return result
    
    def _extract_functions(self, tree: ast.Module) -> Dict[str, ast.FunctionDef]:
        """
        Extract all functions and methods from AST.
        
        If file has no functions/classes (script-style), creates a pseudo-function
        representing the loose code for cohesion analysis.
        """
        
        class FunctionVisitor(ast.NodeVisitor):
            def __init__(self):
                self.current_class = None
                self.functions = {}
            
            def visit_ClassDef(self, node):
                old_class = self.current_class
                self.current_class = node.name
                self.generic_visit(node)
                self.current_class = old_class
            
            def visit_FunctionDef(self, node):
                if self.current_class:
                    func_name = f"{self.current_class}.{node.name}"
                else:
                    func_name = node.name
                self.functions[func_name] = node
                self.generic_visit(node)
        
        visitor = FunctionVisitor()
        visitor.visit(tree)
        
        if not visitor.functions:
            visitor.functions['<module_script>'] = tree
        
        return visitor.functions
    
    def _get_file_stages_from_pipeline(self, file_path: str) -> Set[str]:
        """Get stages for a file from pipeline metadata."""
        pipeline_metadata = self.context.get_pipeline_metadata()
        if not pipeline_metadata:
            return set()
        
        detected_stages = pipeline_metadata.get("detected_stages", {})
        file_stages = set()
        
        for stage_name, file_list in detected_stages.items():
            for file_info in file_list:
                if file_info["file"] == file_path:
                    file_stages.add(stage_name)
        
        return file_stages
    
    def _detect_stages(self, func_node: ast.FunctionDef, file_path: str) -> Set[str]:
        """Detect ML pipeline stages in a function."""
        detected_stages = set()
        
        source = self.context.get_file_source(file_path)
        if source is None:
            return detected_stages
        
        try:
            func_source = ast.get_source_segment(source, func_node)
        except:
            func_source = None
        
        if func_source is None:
            return detected_stages
        
        func_source_lower = func_source.lower()
        
        for stage_name, stage_config in self.config['stages'].items():
            for keyword in stage_config.get('keywords', []):
                if keyword.lower() in func_source_lower:
                    detected_stages.add(stage_name)
                    break
            
            if stage_name in detected_stages:
                continue
            
            for node in ast.walk(func_node):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for import_pattern in stage_config.get('imports', []):
                            if import_pattern.lower() in alias.name.lower():
                                detected_stages.add(stage_name)
                                break
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        for import_pattern in stage_config.get('imports', []):
                            if import_pattern.lower() in node.module.lower():
                                detected_stages.add(stage_name)
                                break
                
                if stage_name in detected_stages:
                    break
        
        return detected_stages
    
    def _determine_cohesion_level(
        self, 
        unique_stages: int, 
        unique_phases: int,
        ml_content: bool,
        above_nloc_threshold: bool
    ) -> str:
        """
        Determine cohesion level based on stages, phases, ML content, and file size.
        
        Args:
            unique_stages: Number of unique ML pipeline stages
            unique_phases: Number of unique ML pipeline phases
            ml_content: Whether file contains ML content
            above_nloc_threshold: Whether file is above NLOC threshold
            
        Returns:
            'high': Single stage (best cohesion)
            'medium': Single phase, multiple stages
            'low': Multiple phases (worst cohesion)
            'non_ml_file': File doesn't contain ML content
            'too_small': File is below NLOC threshold (not counted as issue)
        """
        # Non-ML files don't count for cohesion
        if not ml_content:
            return 'non_ml_file'
        
        # No stages detected
        if unique_stages == 0:
            return 'non_ml_file'
        
        # Files below threshold are marked but not penalized
        if not above_nloc_threshold:
            if unique_stages == 1:
                return 'high'
            elif unique_phases == 1:
                return 'medium'
            else:
                return 'too_small'
        
        # Regular cohesion evaluation
        if unique_stages == 1:
            return 'high'
        elif unique_phases == 1:
            return 'medium'
        else:
            return 'low'
    
    def _calculate_cohesion_score(self, results: Dict) -> float:
        """
        Calculate weighted score based on ML pipeline cohesion.
        
        Only counts files that:
        - Have ML content
        - Are above NLOC threshold
        
        Cohesion scores:
        - high: 10 points (single stage)
        - medium: 6 points (single phase, multiple stages)
        - low: 3 points (multiple phases)
        
        Args:
            results: Analysis results dictionary
            
        Returns:
            Score from 0-10 based on cohesion levels
        """
        cohesion_scores = {
            'high': 10,
            'medium': 6,
            'low': 3
        }
        
        total_score = 0
        counted_files = 0
        
        for file_data in results['files'].values():
            cohesion = file_data.get('cohesion_level', 'high')
            
            # Only count ML files above threshold
            if cohesion in ['high', 'medium', 'low']:
                total_score += cohesion_scores.get(cohesion, 10)
                counted_files += 1
        
        if counted_files > 0:
            # Normalize to 0-10 scale
            return round((total_score / (counted_files * 10)) * 10, 2)
        return 0
    
    def _generate_messages(self, results: Dict) -> List[str]:
        """Generate human-readable messages."""
        messages = []
        summary = results['summary']
        
        # Scan mode info
        scan_mode_text = {
            'all_files': 'all Python files in project',
            'ml_only': 'ML pipeline files only',
            'all_files_fallback': 'all Python files (no pipeline detected)'
        }
        mode = summary['scan_mode']
        messages.append(
            f"Analyzed {summary['total_files']} files ({scan_mode_text.get(mode, mode)})"
        )
        
        # ML content summary
        if summary['non_ml_files'] > 0:
            messages.append(
                f"ℹ {summary['non_ml_files']} files without ML content (excluded from cohesion evaluation)"
            )
        
        # Small files summary
        if summary['small_files'] > 0:
            messages.append(
                f"ℹ {summary['small_files']} files below NLOC threshold "
                f"({summary['nloc_threshold']} lines) - marked but not penalized"
            )
        
        # Cohesion summary
        evaluated_files = (
            summary['high_cohesion'] + 
            summary['medium_cohesion'] + 
            summary['low_cohesion']
        )
        
        if evaluated_files > 0:
            messages.append(
                f"Evaluated {evaluated_files} ML files for cohesion:"
            )
        
        if summary['high_cohesion'] > 0:
            messages.append(
                f"  ✓ {summary['high_cohesion']} files have high cohesion (single stage/phase)"
            )
        
        if summary['medium_cohesion'] > 0:
            messages.append(
                f"  ⚠ {summary['medium_cohesion']} files have medium cohesion (single phase, multiple stages)"
            )
        
        if summary['low_cohesion'] > 0:
            messages.append(
                f"  ✗ {summary['low_cohesion']} files have low cohesion (multiple phases)"
            )
            
            # List problematic files
            low_cohesion_files = [
                (fp, data) for fp, data in results['files'].items()
                if data['cohesion_level'] == 'low'
            ]
            if low_cohesion_files:
                messages.append("Files needing cohesion refactoring:")
                for fp, file_data in low_cohesion_files:
                    stages = ', '.join(file_data.get('stages_detected', []))
                    phases = ', '.join(file_data.get('phases_detected', []))
                    nloc = file_data.get('nloc', 0)
                    messages.append(f"  - {fp}")
                    messages.append(f"    NLOC: {nloc} lines")
                    messages.append(f"    Stages: {stages}")
                    messages.append(f"    Phases: {phases}")
        
        return messages
