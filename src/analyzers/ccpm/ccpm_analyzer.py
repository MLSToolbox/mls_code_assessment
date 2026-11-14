import ast
from typing import Dict, List, Set

from core.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer
from analyzers.ml_content import MLContentAnalyzer
from analyzers.ccpm.nloc_calculator import NLOCCalculator
from analyzers.ccpm.ccpm_evaluator import CCPMEvaluator
from analyzers.common import calculate_ccp
from analyzers.pipeline.pipeline_schema import get_pipeline_schema
from config.settings import settings


class CCPMAnalyzer(BaseAnalyzer):
    """
    Conceptual Cohesion of Pipeline Modules (CCPM) Analyzer.

    Evaluates conceptual cohesion using the paper's formula:
        CCP_i(C) = 5 - MP(C) - MS(C) - 2 * MPC(C)
    where MP = spans multiple phases, MS = spans multiple stages, and
    MPC = mixes ML pipeline code with non-pipeline code (web API, UI,
    logs, utilities, ...). See analyzers.common.ccp_calculator.

    Analyzes:
    1. ML pipeline stage/phase cohesion (via pipeline_stages.json)
    2. Responsibility mixing detection (single vs multiple stages/phases)
    3. ML content presence (via MLContentAnalyzer)
    4. NLOC (Non-comment Lines of Code) - reported as an informational
       note only; it does not affect the CCP_i level, per the paper.

    Cohesion Levels (CCP_i, 1-5):
    - Very High (5): Single stage, single phase, ML content only
    - High (4): Single phase, multiple stages, ML content only
    - Medium (3): Either (single phase, multiple stages, mixed content)
      or (multiple phases, multiple stages, ML content only)
    - Low (2): Single phase, multiple stages, mixed content
    - Very Low (1): Multiple phases, multiple stages, mixed content
    """
    
    def __init__(self, session_id: str, local_path: str, context=None):
        super().__init__(session_id, local_path, context)
        self.schema = get_pipeline_schema()
        self.config = self.schema.raw_config
        self.stage_to_phase = dict(self.schema.stage_to_phase)
        
        self.ml_content_analyzer = MLContentAnalyzer(
            session_id=session_id,
            local_path=local_path,
            context=context
        )
        
        nloc_threshold = settings.ANALYZER_CONFIG.get('ccpm', {}).get('nloc_threshold', 30)
        self.nloc_calculator = NLOCCalculator(threshold=nloc_threshold)
        
        # Initialize CCPM evaluator for rule-based diagnosis/recommendations
        self.evaluator = CCPMEvaluator()
    
    @property
    def analyzer_id(self) -> str:
        return "ccpm"
    
    def analyze(self) -> AnalysisResult:
        """
        Run CCPM analysis on Python files.
        
        The files to analyze are determined by the AnalysisContext configuration:
        - Uses pipeline-detected scope
        - Includes manual stage assignments when provided
        
        Returns:
            AnalysisResult with CCPM score based on ML pipeline cohesion, 
            ML content, and NLOC analysis.
        """

        results = {
            'files': {},
            'summary': {
                'total_files': 0,
                'very_high_cohesion': 0,
                'high_cohesion': 0,
                'medium_cohesion': 0,
                'low_cohesion': 0,
                'very_low_cohesion': 0,
                'non_ml_files': 0,
                'not_applicable': 0,
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

            self.context.set_file_metric(py_file, 'ccpm', file_result)
            
            # Use evaluator to generate diagnosis/recommendation message
            evaluation = self.evaluator.evaluate_file(py_file, file_result)
            if evaluation:
                messages_list.append(evaluation)
            
            # Update summary counters (for scoring)
            cohesion_level = file_result['cohesion_level']
            if cohesion_level == 'non_ml_file':
                results['summary']['non_ml_files'] += 1
            elif cohesion_level == 'not_applicable':
                results['summary']['not_applicable'] += 1
            elif cohesion_level == 'very_high':
                results['summary']['very_high_cohesion'] += 1
            elif cohesion_level == 'high':
                results['summary']['high_cohesion'] += 1
            elif cohesion_level == 'medium':
                results['summary']['medium_cohesion'] += 1
            elif cohesion_level == 'low':
                results['summary']['low_cohesion'] += 1
            elif cohesion_level == 'very_low':
                results['summary']['very_low_cohesion'] += 1
            
            # Track small files separately
            if not file_result['above_nloc_threshold'] and cohesion_level not in ['non_ml_file', 'not_applicable']:
                results['summary']['small_files'] += 1
        
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
        Analyze a single file for CCPM (Conceptual Cohesion of Pipeline Modules).
        
        Evaluates:
        1. Pipeline stage/phase cohesion
        2. ML content presence
        3. NLOC (file size)
        """
        # Calculate NLOC using NLOCCalculator
        nloc = self.nloc_calculator.calculate_nloc(source)
        above_nloc_threshold = self.nloc_calculator.is_above_threshold(nloc)
        
        # Detect ML vs non-ML content using MLContentAnalyzer
        ml_result = self.ml_content_analyzer.analyze_file(file_path)
        # Note: has_no_ml_content=True means "contains non-ML code"
        has_non_ml_content = ml_result['has_no_ml_content']
        non_ml_keywords = ml_result['non_ml_keywords_found']
        
        # ml_content_only=True means "all content is ML-related" (no non-ML code)
        # ml_content_only=False means "has non-ML code mixed in"
        ml_content_only = not has_non_ml_content
        
        functions = self._extract_functions(tree)
        file_stages_from_pipeline = self._get_file_stages_from_pipeline(file_path)
        
        function_stages = {}
        is_script_file = '<module_script>' in functions
        
        for func_name in functions.keys():
            stages = file_stages_from_pipeline
            function_stages[func_name] = list(stages)
        
        all_stages = set()
        for stages in function_stages.values():
            all_stages.update(stages)
        
        unique_stages = len(all_stages)
        all_phases = {self.stage_to_phase.get(stage, 'unknown') for stage in all_stages}
        all_phases.discard('unknown')
        unique_phases = len(all_phases)
        
        has_mixed_content = not ml_content_only

        # Exclusion categories don't get a CCP_i level: no pipeline stage was
        # detected at all, so "spans multiple phases/stages" is meaningless.
        if unique_stages == 0 and has_mixed_content:
            cohesion_level = 'non_ml_file'
            ccp_fields = {'mp': None, 'ms': None, 'mpc': None, 'ccp_level': None}
        elif unique_stages == 0:
            cohesion_level = 'not_applicable'
            ccp_fields = {'mp': None, 'ms': None, 'mpc': None, 'ccp_level': None}
        else:
            ccp = calculate_ccp(unique_phases, unique_stages, has_mixed_content)
            cohesion_level = ccp['cohesion_level']
            ccp_fields = {
                'mp': ccp['mp'],
                'ms': ccp['ms'],
                'mpc': ccp['mpc'],
                'ccp_level': ccp['ccp_level'],
            }

        result = {
            'unique_stages': unique_stages,
            'unique_phases': unique_phases,
            'stages_detected': list(all_stages),
            'phases_detected': list(all_phases),
            'cohesion_level': cohesion_level,
            **ccp_fields,
            'function_stages': function_stages,
            'source': 'pipeline_metadata_strict',
            'ml_content_only': ml_content_only,
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

        file_stages = pipeline_metadata.get("file_stages", {})
        stages = file_stages.get(file_path, [])
        return {
            stage
            for stage in stages
            if stage in self.schema.valid_stages
        }

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
    
    def _calculate_cohesion_score(self, results: Dict) -> float:
        """
        Calculate the project-wide CCPM score as the average CCP_i level
        (1-5, per the paper's formula) across all files that got a level.

        Files classified as 'non_ml_file' or 'not_applicable' have no
        CCP_i level (spanning phases/stages is meaningless without a
        detected pipeline stage) and are excluded from the average.

        Args:
            results: Analysis results dictionary

        Returns:
            Score in [1.0, 5.0], or 0 if no file could be scored.
        """
        total_level = 0
        counted_files = 0

        for file_data in results['files'].values():
            ccp_level = file_data.get('ccp_level')

            if ccp_level is not None:
                total_level += ccp_level
                counted_files += 1

        if counted_files > 0:
            return round(total_level / counted_files, 2)
        return 0
