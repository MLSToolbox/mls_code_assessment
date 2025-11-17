import ast
import os
import json
from typing import Dict, List, Set

from core.models.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer
from analyzers.ml_content import MLContentAnalyzer
from analyzers.fpc.nloc_calculator import NLOCCalculator
from analyzers.fpc.fpc_evaluator import FPCEvaluator
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
        
        # Initialize FPC evaluator for rule-based diagnosis/recommendations
        self.evaluator = FPCEvaluator()
    
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
        
        # List to store per-file messages (new format)
        messages_list = []
        
        # Track processed files to avoid duplicates
        processed_files = set()
        
        for py_file in python_files:
            # Skip if already processed (avoid duplicates)
            if py_file in processed_files:
                continue
            processed_files.add(py_file)
            
            tree = self.context.get_file_ast(py_file)
            source = self.context.get_file_source(py_file)
            
            if tree is None or source is None:
                continue
            
            file_result = self._analyze_file(tree, source, py_file)
            results['files'][py_file] = file_result

            self.context.set_file_metric(py_file, 'fpc', file_result)
            
            # Use evaluator to generate diagnosis/recommendation message
            evaluation = self.evaluator.evaluate_file(py_file, file_result)
            if evaluation:
                messages_list.append(evaluation)
            
            # Update summary counters (for scoring)
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
        
        return self._create_result(
            score=round(score, 2),
            messages=messages_list,  # Use new list format
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
        
        ml_result = self.ml_content_analyzer.analyze_file(file_path)
        has_no_ml_content = ml_result['has_no_ml_content']
        non_ml_keywords = ml_result['non_ml_keywords_found']
        
        ml_content = not has_no_ml_content
        
        functions = self._extract_functions(tree)
        # Classify file pattern: functions_only, classes_only, or mixed
        pattern = self._classify_file_pattern(tree)
        
        file_stages_from_pipeline = self._get_file_stages_from_pipeline(file_path)
        
        function_stages = {}
        is_script_file = '<module_script>' in functions
        
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
            'has_no_ml_content': has_no_ml_content,
            'non_ml_keywords_found': non_ml_keywords,
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
        
        # Extract filename without path and extension
        filename_lower = file_path.lower().replace('\\', '/').split('/')[-1].replace('.py', '')
        
        # Check for EXACT filename matches only (high confidence)
        exact_matches = []
        for stage_name, stage_config in self.config['stages'].items():
            for pattern in stage_config.get('filename_patterns', []):
                if filename_lower == pattern.lower():
                    exact_matches.append(stage_name)
                    break  # Only need one exact match per stage
        
        # If exactly one stage has an exact filename match, return it with high confidence
        if len(exact_matches) == 1:
            return {exact_matches[0]}
        
        # If multiple exact matches (rare), continue to code analysis for disambiguation
        # If no exact matches, continue to code analysis
        # This avoids false positives from partial matches like "train" in "encoder_train"
        
        source = self.context.get_file_source(file_path)
        if source is None:
            return detected_stages
        
        # Get module-level AST for import detection
        module_tree = self.context.get_file_ast(file_path)
        
        try:
            func_source = ast.get_source_segment(source, func_node)
        except:
            func_source = None
        
        if func_source is None:
            return detected_stages
        
        func_source_lower = func_source.lower()
        source_lower = source.lower()  # Full file source for broader keyword detection
        
        for stage_name, stage_config in self.config['stages'].items():
            for keyword in stage_config.get('keywords', []):
                if keyword.lower() in func_source_lower:
                    detected_stages.add(stage_name)
                    break
            
            # Also check keywords at module level (for class names, etc.)
            if stage_name not in detected_stages:
                for keyword in stage_config.get('keywords', []):
                    if keyword.lower() in source_lower:
                        detected_stages.add(stage_name)
                        break
            
            if stage_name in detected_stages:
                continue
            
            # Check imports at MODULE level (not just function level)
            if module_tree:
                for node in ast.walk(module_tree):
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
            
            if stage_name in detected_stages:
                continue
            
            # Also check imports at function level (for local imports)
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
