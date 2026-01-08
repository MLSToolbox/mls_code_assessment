import ast
import os
from typing import Dict, List, Set, Tuple, Optional, Any

from core.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer


class FCPMAnalyzer(BaseAnalyzer):
    """
    Analyzer for FCPM (Functional Cohesion of Pipeline Modules) metric.
    
    Measures functional connection via information flow:
    - Method invocations
    - Data flow (one method writes, another reads)
    """
    
    @property
    def analyzer_id(self) -> str:
        return "fcpm"
    
    def analyze(self) -> AnalysisResult:
        """
        Analyze FCPM cohesion for all Python files.
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
                'single_method_files': 0,
                'average_fcpm': 0.0
            }
        }
        
        python_files = self.context.get_python_files()
        results['summary']['total_files'] = len(python_files)
        
        scores = []
        
        for py_file in python_files:
            tree = self.context.get_file_ast(py_file)
            source = self.context.get_file_source(py_file)
            
            if tree is None or source is None:
                continue
            
            file_result = self._analyze_file(tree, py_file)
            results['files'][py_file] = file_result
            
            self.context.set_file_metric(py_file, 'fcpm', file_result)
            
            score = file_result['fcpm']
            if score is None:
                results['summary']['single_method_files'] += 1
            else:
                scores.append(score)
                if score >= 0.8: results['summary']['high_cohesion'] += 1
                elif score >= 0.6: results['summary']['good_cohesion'] += 1
                elif score >= 0.4: results['summary']['moderate_cohesion'] += 1
                elif score >= 0.2: results['summary']['low_cohesion'] += 1
                else: results['summary']['very_low_cohesion'] += 1
        
        if scores:
            results['summary']['average_fcpm'] = sum(scores) / len(scores)
            final_score = results['summary']['average_fcpm'] * 10
        else:
            final_score = 0
            
        messages = self._generate_messages(results)
        
        return self._create_result(
            score=round(final_score, 2),
            messages=messages,
            module_count=results['summary']['total_files'],
            details=results
        )
    
    def _analyze_file(self, tree: ast.Module, file_path: str) -> Dict:
        methods = self._extract_methods(tree)
        n_methods = len(methods)
        
        if n_methods <= 1:
            return {
                'fcpm': None,
                'n_methods': n_methods,
                'n_possible_pairs': 0,
                'n_connected_pairs': 0,
                'cohesion_level': 'not_applicable'
            }
            
        # Analyze usage for each method
        method_usage = {}
        for name, node in methods.items():
            method_usage[name] = {
                'calls': self._get_method_calls(node, methods),
                'reads': set(),
                'writes': set()
            }
            reads, writes = self._get_variable_usage(node)
            method_usage[name]['reads'] = reads
            method_usage[name]['writes'] = writes
            
        # Calculate connected pairs
        method_names = list(methods.keys())
        connected_pairs = 0
        total_pairs = (n_methods * (n_methods - 1)) // 2
        
        connected_pair_list = []
        
        for i, method_a in enumerate(method_names):
            for method_b in method_names[i+1:]:
                usage_a = method_usage[method_a]
                usage_b = method_usage[method_b]
                
                # Check invocation (A calls B or B calls A)
                invokes = (method_b in usage_a['calls']) or (method_a in usage_b['calls'])
                
                # Check data flow (A writes -> B reads OR B writes -> A reads)
                # We check intersection of Writes(A) and Reads(B)
                flow_a_to_b = bool(usage_a['writes'] & usage_b['reads'])
                flow_b_to_a = bool(usage_b['writes'] & usage_a['reads'])
                
                if invokes or flow_a_to_b or flow_b_to_a:
                    connected_pairs += 1
                    connected_pair_list.append((method_a, method_b))
                    
        fcpm = connected_pairs / total_pairs if total_pairs > 0 else 0
        
        return {
            'fcpm': round(fcpm, 3),
            'n_methods': n_methods,
            'n_possible_pairs': total_pairs,
            'n_connected_pairs': connected_pairs,
            'connected_pairs': connected_pair_list,
            'cohesion_level': self._categorize_cohesion(fcpm)
        }

    def _extract_methods(self, tree: ast.Module) -> Dict[str, ast.FunctionDef]:
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

    def _get_method_calls(self, method_node: ast.FunctionDef, all_methods: Dict[str, ast.FunctionDef]) -> Set[str]:
        calls = set()
        method_names = set(all_methods.keys())
        
        for node in ast.walk(method_node):
            if isinstance(node, ast.Call):
                func_name = self._get_function_name(node.func)
                if func_name in method_names:
                    calls.add(func_name)
                elif '.' in func_name:
                    parts = func_name.split('.')
                    if len(parts) >= 2:
                        for full_name in method_names:
                            if full_name.endswith('.' + parts[-1]):
                                calls.add(full_name)
        return calls

    def _get_function_name(self, func_node) -> str:
        if isinstance(func_node, ast.Name):
            return func_node.id
        elif isinstance(func_node, ast.Attribute):
            return self._get_attribute_path(func_node)
        return ''

    def _get_variable_usage(self, method_node: ast.FunctionDef) -> Tuple[Set[str], Set[str]]:
        """
        Identify variables read and written by the method.
        Returns (reads, writes).
        """
        reads = set()
        writes = set()
        params = {arg.arg for arg in method_node.args.args}
        
        for node in ast.walk(method_node):
            var_name = None
            is_read = False
            is_write = False
            
            if isinstance(node, ast.Attribute):
                attr_path = self._get_attribute_path(node)
                if attr_path and attr_path.startswith('self.'):
                    var_name = attr_path
                    if isinstance(node.ctx, ast.Load): is_read = True
                    elif isinstance(node.ctx, ast.Store): is_write = True
                    # Del is ignored
            
            elif isinstance(node, ast.Name):
                if node.id in params or node.id == 'self':
                    continue
                
                # Check for global/module-level variable heuristic
                if self._is_likely_global_variable(node.id):
                    var_name = f"global.{node.id}"
                    if isinstance(node.ctx, ast.Load): is_read = True
                    elif isinstance(node.ctx, ast.Store): is_write = True
            
            if var_name:
                if is_read: reads.add(var_name)
                if is_write: writes.add(var_name)
                
        return reads, writes

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
        builtins = {'list', 'dict', 'str', 'int', 'float', 'bool', 'len', 'print', 'range', 'enumerate', 'zip', 'set', 'min', 'max', 'sum', 'open'}
        common_imports = {'np', 'pd', 'plt', 'os', 'sys', 'json', 're', 'math'}
        
        if var_name in builtins or var_name in common_imports: return False
        
        ml_globals = {'data', 'df', 'model', 'config', 'X', 'y', 'X_train', 'y_train', 'scaler'}
        if var_name in ml_globals: return True
        if var_name.isupper(): return True
        if var_name.startswith('_'): return True
        if var_name[0].isupper(): return True
        
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
            'diagnosis': f"Analyzed {summary['total_files']} files. Average FCPM: {summary['average_fcpm']:.2f}",
            'recommendation': "Check individual files for details.",
            'severity': 'info'
        })
        
        for file_path, data in results['files'].items():
            if data.get('cohesion_level') in ['low', 'very_low']:
                score = data['fcpm']
                messages.append({
                    'file': file_path,
                    'diagnosis': f"Low functional cohesion (FCPM: {score:.2f}). Functions are not well connected by flow.",
                    'recommendation': "Ensure functions pass data to each other or use shared state effectively.",
                    'severity': 'medium' if data['cohesion_level'] == 'low' else 'high',
                    'rule_id': 'fcpm_cohesion'
                })
                
        return messages
