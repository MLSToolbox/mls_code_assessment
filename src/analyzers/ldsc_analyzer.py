import ast
import os
from typing import Dict, List, Set, Tuple, Optional, Any

from core.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer


class LDSCAnalyzer(BaseAnalyzer):
    """
    Analyzer for LDSC (Linked Data Structure Cohesion) metric.
    
    Measures how much functions within a module share data or structures.
    LDSC = (2 * sum(P_ij)) / (n * (n-1))
    where P_ij = 1 if functions i and j share at least one significant variable.
    """
    
    @property
    def analyzer_id(self) -> str:
        return "ldsc"
    
    def analyze(self) -> AnalysisResult:
        """
        Analyze LDSC cohesion for all Python files.
        
        Returns:
            AnalysisResult with LDSC scores per file
        """
        results = {
            'files': {},
            'summary': {
                'total_files': 0,
                'high_cohesion': 0,      # 0.8-1.0
                'good_cohesion': 0,      # 0.6-0.79
                'moderate_cohesion': 0,  # 0.4-0.59
                'low_cohesion': 0,       # 0.2-0.39
                'very_low_cohesion': 0,  # 0.0-0.19
                'single_method_files': 0, # Files with 0 or 1 method
                'average_ldsc': 0.0
            }
        }
        
        python_files = self.context.get_python_files()
        results['summary']['total_files'] = len(python_files)
        
        ldsc_scores = []
        
        for py_file in python_files:
            tree = self.context.get_file_ast(py_file)
            source = self.context.get_file_source(py_file)
            
            if tree is None or source is None:
                continue
            
            file_result = self._analyze_file(tree, py_file)
            results['files'][py_file] = file_result
            
            self.context.set_file_metric(py_file, 'ldsc', file_result)
            
            ldsc = file_result['ldsc']
            if ldsc is None:
                results['summary']['single_method_files'] += 1
            else:
                ldsc_scores.append(ldsc)
                if ldsc >= 0.8:
                    results['summary']['high_cohesion'] += 1
                elif ldsc >= 0.6:
                    results['summary']['good_cohesion'] += 1
                elif ldsc >= 0.4:
                    results['summary']['moderate_cohesion'] += 1
                elif ldsc >= 0.2:
                    results['summary']['low_cohesion'] += 1
                else:
                    results['summary']['very_low_cohesion'] += 1
        
        if ldsc_scores:
            results['summary']['average_ldsc'] = sum(ldsc_scores) / len(ldsc_scores)
            score = results['summary']['average_ldsc'] * 10  # Scale to 0-10
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
        """Analyze LDSC for a single file."""
        methods = self._extract_methods(tree)
        n_methods = len(methods)
        
        if n_methods <= 1:
            return {
                'ldsc': None,
                'n_methods': n_methods,
                'n_possible_pairs': 0,
                'n_shared_pairs': 0,
                'cohesion_level': 'not_applicable'
            }
            
        # Get variables accessed by each method
        method_vars = {}
        for name, node in methods.items():
            method_vars[name] = self._get_variables_accessed(node)
            
        # Calculate pairs sharing variables
        method_names = list(methods.keys())
        shared_pairs = 0
        total_pairs = (n_methods * (n_methods - 1)) // 2
        
        shared_pair_list = []
        
        for i, method_a in enumerate(method_names):
            for method_b in method_names[i+1:]:
                vars_a = method_vars[method_a]
                vars_b = method_vars[method_b]
                
                # P_ij = 1 if they share at least one significant variable
                if vars_a & vars_b:
                    shared_pairs += 1
                    shared_pair_list.append((method_a, method_b))
                    
        ldsc = shared_pairs / total_pairs if total_pairs > 0 else 0
        
        return {
            'ldsc': round(ldsc, 3),
            'n_methods': n_methods,
            'n_possible_pairs': total_pairs,
            'n_shared_pairs': shared_pairs,
            'shared_pairs': shared_pair_list,
            'cohesion_level': self._categorize_cohesion(ldsc)
        }

    def _extract_methods(self, tree: ast.Module) -> Dict[str, ast.FunctionDef]:
        """Extract all methods (functions and class methods) from AST."""
        class MethodVisitor(ast.NodeVisitor):
            def __init__(self):
                self.current_class = None
                self.methods = {}
            
            def visit_ClassDef(self, node):
                old_class = self.current_class
                self.current_class = node.name
                self.generic_visit(node)
                self.current_class = old_class
            
            def visit_FunctionDef(self, node):
                if self.current_class:
                    method_name = f"{self.current_class}.{node.name}"
                else:
                    method_name = node.name
                self.methods[method_name] = node
                self.generic_visit(node)
        
        visitor = MethodVisitor()
        visitor.visit(tree)
        return visitor.methods

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
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
            return '.'.join(reversed(parts))
        return ''

    def _is_likely_global_variable(self, var_name: str) -> bool:
        """Heuristic to determine if a variable is likely a global."""
        # Simplified version of LCCML's heuristic
        builtins = {'list', 'dict', 'str', 'int', 'float', 'bool', 'len', 'print', 'range', 'enumerate', 'zip', 'set', 'min', 'max', 'sum', 'open'}
        common_imports = {'np', 'pd', 'plt', 'os', 'sys', 'json', 're', 'math'}
        
        if var_name in builtins or var_name in common_imports:
            return False
            
        # Common ML globals
        ml_globals = {'data', 'df', 'model', 'config', 'X', 'y', 'X_train', 'y_train', 'scaler'}
        if var_name in ml_globals:
            return True
            
        # Uppercase (constants)
        if var_name.isupper():
            return True
            
        # Starts with underscore
        if var_name.startswith('_'):
            return True
            
        # MixedCase starting with upper
        if var_name[0].isupper():
            return True
            
        return False

    def _categorize_cohesion(self, score: float) -> str:
        if score >= 0.8: return 'excellent'
        if score >= 0.6: return 'good'
        if score >= 0.4: return 'moderate'
        if score >= 0.2: return 'low'
        return 'very_low'

    def _generate_messages(self, results: Dict) -> List[Dict[str, Any]]:
        messages = []
        summary = results['summary']
        messages.append({
            'diagnosis': f"Analyzed {summary['total_files']} files. Average LDSC: {summary['average_ldsc']:.2f}",
            'recommendation': "Check individual files for details.",
            'severity': 'info'
        })

        
        for file_path, data in results['files'].items():
            if data.get('cohesion_level') in ['low', 'very_low']:
                ldsc = data['ldsc']
                messages.append({
                    'file': file_path,
                    'diagnosis': f"Low structural cohesion (LDSC: {ldsc:.2f}). Functions share few data structures.",
                    'recommendation': "Consider grouping functions that operate on the same data or passing data explicitly.",
                    'severity': 'medium' if data['cohesion_level'] == 'low' else 'high',
                    'rule_id': 'ldsc_cohesion'
                })
                
        return messages
