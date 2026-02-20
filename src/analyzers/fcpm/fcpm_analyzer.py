import ast
import os
from typing import Dict, List, Set, Tuple, Optional, Any

from core.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer
from analyzers.fcpm.fcpm_evaluator import FCPMEvaluator
from analyzers.common.ast_utils import extract_methods, get_attribute_path
from analyzers.common.lcom_analysis import count_components, identify_disconnected_methods
from analyzers.common.variable_detection import get_method_calls


class FCPMAnalyzer(BaseAnalyzer):
    """
    Analyzer for FCPM (Functional Cohesion of Pipeline Modules) metric.
    
    FORMULA: FCPM = (2 × Σi<j F_ij) / (n × (n-1))
    
    where F_ij = 1 if any of:
    - Direct invocation: f_i → f_j or f_j → f_i
    - Indirect invocation: both f_i and f_j call a common third function f_t
      (where f_t is in the same module/class)
    
    Measures functional cohesion through method invocation patterns,
    detecting both direct and indirect functional relationships.
    """
    
    def __init__(self, session_id: str, local_path: str, context=None):
        super().__init__(session_id, local_path, context)
        self.evaluator = FCPMEvaluator()
    
    @property
    def analyzer_id(self) -> str:
        return "fcpm"
    
    @staticmethod
    def _is_special_method(method_name: str) -> bool:
        """
        Check if a method is a Python special/magic method that should be excluded
        from disconnection analysis.
        
        Special methods like __init__, __str__, etc. serve specific purposes and
        don't need functional connections to other methods.
        """
        # Extract just the method name (remove ClassName. prefix if present)
        simple_name = method_name.split('.')[-1]
        return simple_name.startswith('__') and simple_name.endswith('__')
    
    def analyze(self) -> AnalysisResult:
        """
        Analyze FCPM cohesion for all Python files.
        """
        results = {
            'files': {},
            'summary': {
                'total_files': 0,
                'very_high_cohesion': 0,  # 0.8-1.0
                'high_cohesion': 0,        # 0.6-0.8
                'moderate_cohesion': 0,    # 0.4-0.6
                'low_cohesion': 0,         # 0.2-0.4
                'very_low_cohesion': 0,    # 0.0-0.2
                'single_method_files': 0,
                'average_fcpm': 0.0
            }
        }
        
        python_files = self.context.get_python_files()
       
        results['summary']['total_files'] = len(python_files)
        
        scores = []
        all_messages = []
        
        for py_file in python_files:
            
            tree = self.context.get_file_ast(py_file)
            source = self.context.get_file_source(py_file)
            
            if tree is None or source is None:
                continue
            
            file_result = self._analyze_file(tree, py_file)
            results['files'][py_file] = file_result
            
            self.context.set_file_metric(py_file, 'fcpm', file_result)
            
            # Get evaluation messages
            messages = self.evaluator.evaluate_file(py_file, file_result)
            all_messages.extend(messages)
            
            score = file_result['fcpm']
            if score is None:
                results['summary']['single_method_files'] += 1
            else:
                scores.append(score)
                cohesion_level = file_result['cohesion_level']
                if cohesion_level == 'very_high':
                    results['summary']['very_high_cohesion'] += 1
                elif cohesion_level == 'high':
                    results['summary']['high_cohesion'] += 1
                elif cohesion_level == 'medium':
                    results['summary']['moderate_cohesion'] += 1
                elif cohesion_level == 'low':
                    results['summary']['low_cohesion'] += 1
                elif cohesion_level == 'very_low':
                    results['summary']['very_low_cohesion'] += 1
        
        if scores:
            results['summary']['average_fcpm'] = sum(scores) / len(scores)
            final_score = results['summary']['average_fcpm'] * 10
        else:
            final_score = 0
        
        return self._create_result(
            score=round(final_score, 2),
            messages=all_messages,
            module_count=results['summary']['total_files'],
            details=results
        )
    
    def _analyze_file(self, tree: ast.Module, file_path: str) -> Dict:
        """
        Analyze functional cohesion for a single file.
        
        Returns:
            Dictionary with FCPM metrics including:
            - fcpm: score [0-1]
            - cohesion_level: very_low|low|medium|high|very_high
            - n_methods: total methods
            - n_possible_pairs: n*(n-1)/2
            - n_connected_pairs: pairs with F_ij=1
            - call_graph: {method: [methods_called]}
            - connected_pairs: list of connected pairs
            - breakdown: {direct_invocations, indirect_invocations}
            - n_components: number of disconnected functional groups
            - n_disconnected_methods: methods with no functional connections
            - disconnected_methods: list of method names
        """
        methods = self._extract_methods(tree)
        n_methods = len(methods)
        
        if n_methods <= 1:
            return {
                'fcpm': None,
                'n_methods': n_methods,
                'n_possible_pairs': 0,
                'n_connected_pairs': 0,
                'cohesion_level': 'not_applicable',
                'call_graph': {},
                'connected_pairs': [],
                'breakdown': {'direct_invocations': 0, 'indirect_invocations': 0},
                'n_components': 0 if n_methods == 0 else 1,
                'n_disconnected_methods': n_methods,
                'disconnected_methods': list(methods.keys()) if n_methods == 1 else []
            }
        
        # Build call graph
        call_graph = self._build_call_graph(methods)
        
        # Calculate connected pairs
        method_names = list(methods.keys())
        connected_pairs = []
        direct_invocations = 0
        indirect_invocations = 0
        total_pairs = (n_methods * (n_methods - 1)) // 2
        
        # Build adjacency dict for LCOM analysis
        adjacency = {name: [] for name in method_names}
        
        for i, method_a in enumerate(method_names):
            for method_b in method_names[i+1:]:
                is_direct = False
                is_indirect = False
                
                # Check direct invocation: A calls B or B calls A
                if method_b in call_graph.get(method_a, []) or \
                   method_a in call_graph.get(method_b, []):
                    is_direct = True
                    direct_invocations += 1
                else:
                    # Check indirect: both call a common third function
                    calls_a = set(call_graph.get(method_a, []))
                    calls_b = set(call_graph.get(method_b, []))
                    common_callees = calls_a & calls_b
                    
                    # Filter to only methods in the same module
                    common_internal = common_callees & set(method_names)
                    
                    if common_internal:
                        is_indirect = True
                        indirect_invocations += 1
                
                if is_direct or is_indirect:
                    connected_pairs.append([method_a, method_b])
                    adjacency[method_a].append(method_b)
                    adjacency[method_b].append(method_a)
        
        n_connected_pairs = len(connected_pairs)
        fcpm = (2 * n_connected_pairs) / (n_methods * (n_methods - 1)) if n_methods > 1 else 0
        
        # LCOM analysis: count functional components (excluding special methods)
        # Special methods like __init__ shouldn't count as separate functional groups
        regular_methods = [m for m in method_names if not self._is_special_method(m)]
        n_components = self._count_components(adjacency, regular_methods) if regular_methods else 0
        
        # Identify disconnected methods (excluding special methods like __init__)
        all_disconnected = self._identify_disconnected_methods(adjacency, method_names)
        disconnected_methods = [m for m in all_disconnected if not self._is_special_method(m)]
        
        return {
            'fcpm': round(fcpm, 3),
            'n_methods': n_methods,
            'n_possible_pairs': total_pairs,
            'n_connected_pairs': n_connected_pairs,
            'connected_pairs': connected_pairs,
            'call_graph': call_graph,
            'breakdown': {
                'direct_invocations': direct_invocations,
                'indirect_invocations': indirect_invocations
            },
            'cohesion_level': self._categorize_cohesion(fcpm),
            'n_components': n_components,
            'n_disconnected_methods': len(disconnected_methods),
            'disconnected_methods': disconnected_methods
        }

    def _build_call_graph(self, methods: Dict[str, ast.FunctionDef]) -> Dict[str, List[str]]:
        """
        Build a call graph showing which methods call which other methods.
        
        Returns:
            {method_name: [list of methods it calls]}
        """
        call_graph = {}
        method_names = set(methods.keys())
        
        for method_name, method_node in methods.items():
            calls = self._get_method_calls(method_node, methods)
            call_graph[method_name] = list(calls)
        
        return call_graph
    
    def _extract_methods(self, tree: ast.Module) -> Dict[str, ast.FunctionDef]:
        """Extract all methods from the AST, with qualified names."""
        return extract_methods(tree)
    
    def _get_method_calls(
        self, 
        method_node: ast.FunctionDef,
        all_methods: Dict[str, ast.FunctionDef]
    ) -> Set[str]:
        """Extract which other methods this method calls."""
        return get_method_calls(method_node, all_methods)

    def _get_function_name(self, func_node) -> str:
        """Extract function name from Call node."""
        if isinstance(func_node, ast.Name):
            return func_node.id
        elif isinstance(func_node, ast.Attribute):
            return self._get_attribute_path(func_node)
        return ''


    def _get_attribute_path(self, node: ast.Attribute) -> str:
        """Extract attribute path like 'self.method' or 'obj.method'."""
        return get_attribute_path(node)


    def _count_components(self, adjacency: Dict[str, List[str]], methods: List[str]) -> int:
        """Count disconnected functional components using DFS."""
        return count_components(adjacency, methods)

    def _identify_disconnected_methods(
        self, 
        adjacency: Dict[str, List[str]], 
        methods: List[str]
    ) -> List[str]:
        """Identify methods that have no functional connections to any other method."""
        return identify_disconnected_methods(adjacency, methods)

    def _categorize_cohesion(self, score: float) -> str:
        """Map FCPM score to cohesion level."""
        if score >= 0.8:
            return 'very_high'
        elif score >= 0.6:
            return 'high'
        elif score >= 0.4:
            return 'medium'
        elif score >= 0.2:
            return 'low'
        else:
            return 'very_low'
