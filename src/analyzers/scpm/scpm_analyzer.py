import ast
import os
import json
from typing import Dict, List, Set, Tuple, Optional, Any

from core.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer
from analyzers.scpm.scpm_evaluator import SCPMEvaluator
from analyzers.common import (
    extract_methods,
    get_attribute_path,
    count_components,
    identify_disconnected_methods,
    is_likely_global_variable,
    get_files_accessed
)


class SCPMAnalyzer(BaseAnalyzer):
    """
    Analyzer for SCPM (Structural Cohesion of Pipeline Modules) metric.
    
    Measures how much functions within a module share DATA or STRUCTURES:
    - Variables: self.x (class attributes), module-level globals, constants
    - Files: datasets (.csv, .parquet), models (.pkl, .h5), configs (.yaml, .json)
    
    Formula: SCPM = (2 * sum(P_ij)) / (n * (n-1))
    where P_ij = 1 if functions i and j share at least one of the above.
    
    Includes LCOM analysis to detect disconnected groups of methods.
    """
    
    def __init__(self, session_id: str, local_path: str, context=None):
        super().__init__(session_id, local_path, context)
        
        # ML-related file extensions for shared file detection
        self.ml_file_extensions = {
            # Data files
            '.csv', '.tsv', '.txt', '.json', '.xml', '.parquet', '.feather',
            '.xlsx', '.xls', '.orc', '.avro', '.arrow',
            # Model files
            '.pkl', '.pickle', '.joblib', '.h5', '.hdf5', '.pt', '.pth',
            '.ckpt', '.pb', '.model', '.weights', '.bin', '.onnx',
            # NumPy arrays
            '.npy', '.npz',
            # Config files
            '.yaml', '.yml', '.ini', '.cfg', '.conf', '.toml'
        }
        
        # Initialize evaluator for rule-based diagnostics
        self.evaluator = SCPMEvaluator()
    
    @property
    def analyzer_id(self) -> str:
        return "scpm"
    
    @staticmethod
    def _is_special_method(method_name: str) -> bool:
        """
        Check if a method is a Python special/magic method that should be excluded
        from disconnection analysis.
        
        Special methods like __init__, __str__, etc. serve specific purposes and
        don't need structural connections to other methods.
        """
        # Extract just the method name (remove ClassName. prefix if present)
        simple_name = method_name.split('.')[-1]
        return simple_name.startswith('__') and simple_name.endswith('__')
    
    def analyze(self) -> AnalysisResult:
        """
        Analyze SCPM cohesion for all Python files.
        
        Returns:
            AnalysisResult with SCPM scores per file
        """
        results = {
            'files': {},
            'summary': {
                'total_files': 0,
                'very_high_cohesion': 0,  # 0.8-1.0
                'high_cohesion': 0,       # 0.6-0.79
                'medium_cohesion': 0,     # 0.4-0.59
                'low_cohesion': 0,        # 0.2-0.39
                'very_low_cohesion': 0,   # 0.0-0.19
                'single_method_files': 0, # Files with 0 or 1 method
                'average_scpm': 0.0,
                'modules_with_multiple_components': 0  # LCOM analysis result
            }
        }
        
        python_files = self.context.get_python_files()
        results['summary']['total_files'] = len(python_files)
        
        scpm_scores = []
        
        for py_file in python_files:
            tree = self.context.get_file_ast(py_file)
            source = self.context.get_file_source(py_file)
            
            if tree is None or source is None:
                continue
            
            file_result = self._analyze_file(tree, py_file)
            results['files'][py_file] = file_result
            
            self.context.set_file_metric(py_file, 'scpm', file_result)
            
            scpm = file_result['scpm']
            if scpm is None:
                results['summary']['single_method_files'] += 1
            else:
                scpm_scores.append(scpm)
                cohesion_level = file_result['cohesion_level']
                
                # Categorize by cohesion level
                if cohesion_level == 'very_high':
                    results['summary']['very_high_cohesion'] += 1
                elif cohesion_level == 'high':
                    results['summary']['high_cohesion'] += 1
                elif cohesion_level == 'medium':
                    results['summary']['medium_cohesion'] += 1
                elif cohesion_level == 'low':
                    results['summary']['low_cohesion'] += 1
                elif cohesion_level == 'very_low':
                    results['summary']['very_low_cohesion'] += 1
                
                # Count modules with multiple disconnected components
                if file_result['n_components'] > 1:
                    results['summary']['modules_with_multiple_components'] += 1
        
        if scpm_scores:
            results['summary']['average_scpm'] = sum(scpm_scores) / len(scpm_scores)
            score = results['summary']['average_scpm'] * 10  # Scale to 0-10
        else:
            score = 0
            
        messages = self._generate_messages(results)
        
        return self._create_result(
            score=round(score, 2),
            messages=messages,
            module_count=results['summary']['total_files'],
            details=results,
           
        )
    
    def _analyze_file(self, tree: ast.Module, file_path: str) -> Dict:
        """
        Analyze SCPM for a single file with enhanced detection and LCOM analysis.
        
        Detects structural connections through:
        1. Class attributes (self.x)
        2. Module-level global variables
        3. Constants (UPPERCASE)
        4. Shared file access (datasets, models, configs)
        """
        methods = self._extract_methods(tree)
        n_methods = len(methods)
        
        if n_methods <= 1:
            return {
                'scpm': None,
                'n_methods': n_methods,
                'n_possible_pairs': 0,
                'n_shared_pairs': 0,
                'cohesion_level': 'not_applicable',
                'n_components': 0,
                'shared_variable_count': 0,
                'shared_file_count': 0,
                'shared_vars': [],
                'shared_files': [],
                'shared_type': None
            }
            
        # Get variables and files accessed by each method
        method_vars = {}
        method_files = {}
        for name, node in methods.items():
            method_vars[name] = self._get_variables_accessed(node)
            method_files[name] = self._get_files_accessed(node)
            
        # Calculate pairs sharing variables OR files (union)
        method_names = list(methods.keys())
        shared_pairs = 0
        total_pairs = (n_methods * (n_methods - 1)) // 2
        
        shared_pair_list = []
        shared_via_vars = set()
        shared_via_files = set()
        all_shared_vars = set()
        all_shared_files = set()
        
        # Build adjacency graph for LCOM analysis
        adjacency = {method: set() for method in method_names}
        
        for i, method_a in enumerate(method_names):
            for method_b in method_names[i+1:]:
                vars_a = method_vars[method_a]
                vars_b = method_vars[method_b]
                files_a = method_files[method_a]
                files_b = method_files[method_b]
                
                # Check if they share variables
                shared_vars = vars_a & vars_b
                # Check if they share files
                shared_files = files_a & files_b
                
                # P_ij = 1 if they share at least one variable OR file
                if shared_vars or shared_files:
                    shared_pairs += 1
                    shared_pair_list.append((method_a, method_b))
                    
                    # Add to adjacency graph (bidirectional)
                    adjacency[method_a].add(method_b)
                    adjacency[method_b].add(method_a)
                    
                    if shared_vars:
                        shared_via_vars.add((method_a, method_b))
                        all_shared_vars.update(shared_vars)
                    if shared_files:
                        shared_via_files.add((method_a, method_b))
                        all_shared_files.update(shared_files)
                    
        scpm = shared_pairs / total_pairs if total_pairs > 0 else 0
        
        # LCOM analysis: find disconnected components (excluding special methods)
        # Special methods like __init__ shouldn't count as separate structural groups
        regular_methods = [m for m in method_names if not self._is_special_method(m)]
        n_components = self._count_components(adjacency, regular_methods) if regular_methods else 0
        
        # Identify completely disconnected methods (excluding special methods like __init__)
        all_disconnected = self._identify_disconnected_methods(adjacency, method_names)
        disconnected_methods = [m for m in all_disconnected if not self._is_special_method(m)]
        
        # Determine type of sharing
        shared_type = self._determine_shared_type(all_shared_vars, all_shared_files)
        
        # Categorize cohesion level
        cohesion_level = self._categorize_cohesion(scpm)
        
        file_result = {
            'scpm': round(scpm, 3),
            'n_methods': n_methods,
            'n_possible_pairs': total_pairs,
            'n_shared_pairs': shared_pairs,
            'shared_pairs': shared_pair_list,
            'cohesion_level': cohesion_level,
            'n_components': n_components,
            'disconnected_methods': disconnected_methods,  # NEW: Methods with no connections
            'n_disconnected_methods': len(disconnected_methods),  # NEW: Count
            'shared_variable_count': len(all_shared_vars),
            'shared_file_count': len(all_shared_files),
            'shared_vars': sorted(list(all_shared_vars))[:10],  # Top 10 for reporting
            'shared_files': sorted(list(all_shared_files))[:10],  # Top 10 for reporting
            'shared_type': shared_type,
            'breakdown': {
                'pairs_via_variables': len(shared_via_vars),
                'pairs_via_files': len(shared_via_files)
            }
        }
        
        return file_result
    
    def _count_components(self, adjacency: Dict[str, Set[str]], methods: List[str]) -> int:
        """Count disconnected components using DFS (LCOM analysis)."""
        return count_components(adjacency, methods)
    
    def _identify_disconnected_methods(self, adjacency: Dict[str, Set[str]], methods: List[str]) -> List[str]:
        """Identify methods with no structural connections."""
        return identify_disconnected_methods(adjacency, methods)
        """
        Identify methods that are completely disconnected (share nothing with any other method).
        
        These are methods where adjacency[method] is empty (no edges in the graph).
        
        Args:
            adjacency: Graph where adjacency[method_a] = {method_b, method_c, ...}
            methods: List of all method names
            
        Returns:
            List of method names that don't share data/files with any other method
        """
        disconnected = []
        for method in methods:
            if len(adjacency[method]) == 0:
                disconnected.append(method)
        return disconnected
    
    def _determine_shared_type(self, shared_vars: Set[str], shared_files: Set[str]) -> str:
        """
        Determine the predominant type of data sharing.
        
        Returns:
            'class_attributes': Mostly self.x
            'global_variables': Mostly module-level globals
            'files': Mostly shared files
            'mixed': Combination of types
            None: No sharing detected
        """
        if not shared_vars and not shared_files:
            return None
        
        # Count types
        class_attrs = sum(1 for v in shared_vars if v.startswith('self.'))
        global_vars = sum(1 for v in shared_vars if v.startswith('global.'))
        files = len(shared_files)
        
        total = class_attrs + global_vars + files
        if total == 0:
            return None
        
        # Determine predominant type (>50%)
        if class_attrs / total > 0.5:
            return 'class_attributes'
        elif global_vars / total > 0.5:
            return 'global_variables'
        elif files / total > 0.5:
            return 'files'
        else:
            return 'mixed'
    
    def _get_files_accessed(self, method_node: ast.FunctionDef) -> Set[str]:
        """Detect file paths accessed by the method."""
        return get_files_accessed(method_node)

    def _extract_methods(self, tree: ast.Module) -> Dict[str, ast.FunctionDef]:
        """Extract all methods from the AST, with qualified names."""
        return extract_methods(tree)

    def _get_variables_accessed(self, method_node: ast.FunctionDef) -> Set[str]:
        """Extract shared variables accessed in a method."""
        variables = set()
        params = {arg.arg for arg in method_node.args.args}
        
        for node in ast.walk(method_node):
            if isinstance(node, ast.Attribute):
                attr_path = self._get_attribute_path(node)
                if attr_path and attr_path.startswith('self.'):
                    variables.add(attr_path)
            
            elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Load, ast.Store)):
                var_name = node.id
                if var_name in params or var_name == 'self':
                    continue
                
                if isinstance(node.ctx, ast.Load):
                    if self._is_likely_global_variable(var_name):
                        variables.add(f"global.{var_name}")
        
        return variables

    def _get_attribute_path(self, node: ast.Attribute) -> str:
        """Extract full attribute path."""
        return get_attribute_path(node)
    
    def _is_likely_global_variable(self, var_name: str) -> bool:
        """Determine if a variable is likely a global/module-level variable."""
        return is_likely_global_variable(var_name)

    def _categorize_cohesion(self, score: float) -> str:
        """
        Categorize SCPM score into 5 granular levels.
        
        Ranges match SCPM requirements:
        - [0.8-1.0]: very_high
        - [0.6-0.8): high  
        - [0.4-0.6): medium
        - [0.2-0.4): low
        - [0.0-0.2): very_low
        """
        if score >= 0.8: return 'very_high'
        if score >= 0.6: return 'high'
        if score >= 0.4: return 'medium'
        if score >= 0.2: return 'low'
        return 'very_low'

    def _generate_messages(self, results: Dict) -> List[Dict[str, Any]]:
        """
        Generate messages using rule-based evaluator (scpm_evaluator.py).
        
        Returns structured messages with file-level diagnoses and recommendations.
        """
        messages = []
        
        # Generate messages for each file using evaluator
        for file_path, file_data in results['files'].items():
            if file_data.get('scpm') is not None:
                message = self.evaluator.evaluate_file(file_path, file_data)
                if message:
                    messages.append(message)
        
        return messages
