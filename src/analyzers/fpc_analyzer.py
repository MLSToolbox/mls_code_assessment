import ast
import os
import json
from typing import Dict, List, Set

from core.models.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer


class FPCAnalyzer(BaseAnalyzer):
    
    def __init__(self, session_id: str, local_path: str, context=None):
        super().__init__(session_id, local_path, context)
                
        pipeline_stages_json_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
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
    
    @property
    def analyzer_id(self) -> str:
        return "fpc"
    
    def analyze(self) -> AnalysisResult:
        """
        Run FPC analysis on Python files.

        This implementation analyzes all Python files available from the
        AnalysisContext (using get_all_python_files) and uses pipeline
        metadata (when present) as a hint per-file. Heuristic detection
        is used as a fallback for files without pipeline metadata.
        """

        results = {
            'files': {},
            'summary': {
                'total_files': 0,
                'high_cohesion': 0,
                'medium_cohesion': 0,
                'low_cohesion': 0,
                'scan_mode': self.context.get_scan_mode(),
                'by_pattern': {'functions_only': 0, 'classes_only': 0, 'mixed': 0}
            }
        }

        # Analyze all python files available in the context. Pipeline metadata
        # will be used as a hint when present for specific files.
        python_files = self.context.get_all_python_files()
        ml_files = self.context.get_all_ml_files()

        results['summary']['ml_files_only'] = bool(ml_files)
        results['summary']['uses_pipeline_metadata'] = bool(ml_files)
        results['summary']['total_files'] = len(python_files)

        for py_file in python_files:
            tree = self.context.get_file_ast(py_file)
            if tree is None:
                continue

            file_result = self._analyze_file(tree, py_file)
            results['files'][py_file] = file_result

            self.context.set_file_metric(py_file, 'fpc', file_result)

            cohesion_level = file_result['cohesion_level']
            if cohesion_level == 'high':
                results['summary']['high_cohesion'] += 1
            elif cohesion_level == 'medium':
                results['summary']['medium_cohesion'] += 1
            else:
                results['summary']['low_cohesion'] += 1

            # Count file pattern distribution (functions_only / classes_only / mixed)
            pattern = file_result.get('pattern', 'mixed')
            if pattern in results['summary']['by_pattern']:
                results['summary']['by_pattern'][pattern] += 1

        # Calculate score based ONLY on cohesion (no pattern weights)
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
    
    def _analyze_file(self, tree: ast.Module, file_path: str) -> Dict:
        """
        Analyze a single file for FPC (Functional Pipeline Cohesion).
        
        Evaluates how well functions within a file adhere to a single
        ML pipeline stage or phase.
        """
        functions = self._extract_functions(tree)
        # Classify file pattern: functions_only, classes_only, or mixed
        pattern = self._classify_file_pattern(tree)
        
        file_stages_from_pipeline = self._get_file_stages_from_pipeline(file_path)
        
        function_stages = {}
        for func_name, func_node in functions.items():
            if file_stages_from_pipeline:
                stages = file_stages_from_pipeline
            else:
                stages = self._detect_stages(func_node, file_path)
            
            function_stages[func_name] = list(stages)
        
        all_stages = set()
        for stages in function_stages.values():
            all_stages.update(stages)
        
        unique_stages = len(all_stages)
        all_phases = {self.stage_to_phase.get(stage, 'unknown') for stage in all_stages}
        all_phases.discard('unknown')
        unique_phases = len(all_phases)
        
        cohesion_level = self._determine_cohesion_level(unique_stages, unique_phases)
        
        result = {
            'unique_stages': unique_stages,
            'unique_phases': unique_phases,
            'stages_detected': list(all_stages),
            'phases_detected': list(all_phases),
            'cohesion_level': cohesion_level,
            'function_stages': function_stages,
            'source': 'pipeline_metadata' if file_stages_from_pipeline else 'heuristic',
            'pattern': pattern
        }
        
        return result
    
    def _extract_functions(self, tree: ast.Module) -> Dict[str, ast.FunctionDef]:
        """Extract all functions and methods from AST."""
        
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
                # file_info may be a dict or tuple depending on producer; handle both
                file_ref = None
                if isinstance(file_info, dict):
                    file_ref = file_info.get("file")
                elif isinstance(file_info, (list, tuple)) and len(file_info) > 0:
                    file_ref = file_info[0]
                else:
                    file_ref = None

                if file_ref == file_path:
                    file_stages.add(stage_name)
        
        return file_stages

    def _classify_file_pattern(self, tree: ast.Module) -> str:
        """Classify a file as 'functions_only', 'classes_only' or 'mixed'."""
        has_func = False
        has_class = False

        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                has_func = True
            elif isinstance(node, ast.ClassDef):
                has_class = True

            if has_func and has_class:
                return 'mixed'

        if has_func and not has_class:
            return 'functions_only'
        if has_class and not has_func:
            return 'classes_only'
        return 'functions_only'
    
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
            # Check keywords
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
    
    def _determine_cohesion_level(self, unique_stages: int, unique_phases: int) -> str:
        """
        Determine cohesion level based ONLY on stages and phases.
        
        Args:
            unique_stages: Number of unique ML pipeline stages
            unique_phases: Number of unique ML pipeline phases
            
        Returns:
            'high': Single stage (best cohesion)
            'medium': Single phase, multiple stages
            'low': Multiple phases (worst cohesion)
        """
        if unique_stages == 0:
            return 'high'
        elif unique_stages == 1:
            return 'high'
        elif unique_phases == 1:
            return 'medium'
        else:
            return 'low'
    
    def _calculate_cohesion_score(self, results: Dict) -> float:
        """
        Calculate weighted score based ONLY on ML pipeline cohesion.
        
        Pattern weights have been REMOVED - this now scores purely on cohesion.
        
        Cohesion scores:
        - high: 10 points (single stage)
        - medium: 6 points (single phase, multiple stages)
        - low: 3 points (multiple phases)
        
        Args:
            results: Analysis results dictionary
            
        Returns:
            Score from 0-10 based purely on cohesion levels
        """
        cohesion_scores = {
            'high': 10,
            'medium': 6,
            'low': 3
        }
        
        total_score = 0
        total_files = 0
        
        for file_data in results['files'].values():
            cohesion = file_data.get('cohesion_level', 'high')
            total_score += cohesion_scores.get(cohesion, 10)
            total_files += 1
        
        if total_files > 0:
            # Normalize to 0-10 scale
            return round((total_score / (total_files * 10)) * 10, 2)
        return 0
    
    def _generate_messages(self, results: Dict) -> List[str]:
        """Generate human-readable messages from the results summary."""
        messages: List[str] = []
        summary = results.get('summary', {})

        # Primary analysis context / scan mode information
        if summary.get('uses_pipeline_metadata'):
            messages.append(f"✓ Analyzed {summary.get('total_files', 0)} Python files (enhanced with pipeline metadata)")
        else:
            scan_mode_text = {
                'all_files': 'all Python files in project',
                'ml_only': 'ML pipeline files only',
                'all_files_fallback': 'all Python files (no pipeline detected)'
            }
            mode = summary.get('scan_mode', '')
            messages.append(f"Analyzed {summary.get('total_files', 0)} files ({scan_mode_text.get(mode, mode)})")

        # Pattern distribution (if available)
        by_pattern = summary.get('by_pattern', {})
        if any(by_pattern.values()):
            pattern_info = []
            if by_pattern.get('functions_only', 0) > 0:
                pattern_info.append(f"{by_pattern['functions_only']} functional")
            if by_pattern.get('classes_only', 0) > 0:
                pattern_info.append(f"{by_pattern['classes_only']} OOP")
            if by_pattern.get('mixed', 0) > 0:
                pattern_info.append(f"{by_pattern['mixed']} mixed")
            if pattern_info:
                messages.append(f"Pattern distribution: {', '.join(pattern_info)}")

        # Cohesion summary
        if summary.get('high_cohesion', 0) > 0:
            messages.append(f"✓ {summary['high_cohesion']} files have high cohesion (single stage/phase)")

        if summary.get('medium_cohesion', 0) > 0:
            messages.append(f"⚠ {summary['medium_cohesion']} files have medium cohesion (single phase, multiple stages)")

        if summary.get('low_cohesion', 0) > 0:
            messages.append(f"✗ {summary['low_cohesion']} files have low cohesion (multiple phases)")

            low_cohesion_files = [
                fp for fp, data in results.get('files', {}).items()
                if data.get('cohesion_level') == 'low'
            ]
            if low_cohesion_files:
                messages.append("Files needing cohesion refactoring:")
                for fp in low_cohesion_files:
                    file_data = results['files'].get(fp, {})
                    stages = ', '.join(file_data.get('stages_detected', []))
                    phases = ', '.join(file_data.get('phases_detected', []))
                    messages.append(f"  - {fp}")
                    messages.append(f"    Stages: {stages}")
                    messages.append(f"    Phases: {phases}")

        return messages
