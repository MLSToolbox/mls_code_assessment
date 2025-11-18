import ast
import os
import json
from typing import Dict, List, Set, Tuple, Optional, Any

from core.models.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer


class LCCMLAnalyzer(BaseAnalyzer):
    """
    Analyzer for LCCML (Loose Class Cohesion Modified for ML) metric.
    
    Calculates module-level cohesion by measuring connectivity between methods
    through shared resources specific to ML pipelines.
    
    Reuses pipeline_stages.json configuration and AnalysisContext for consistency.
    """
    
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
        
        self.ml_libraries = self._extract_ml_libraries_from_config()
        
        self.ml_file_extensions = {
            '.csv', '.pkl', '.joblib', '.h5', '.hdf5', '.pt', '.pth',
            '.ckpt', '.model', '.json', '.parquet', '.feather', '.npy', '.npz'
        }
    
    def _extract_ml_libraries_from_config(self) -> Set[str]:
        """
        Extract all ML library names from pipeline_stages.json.
        
        Returns:
            Set of library name prefixes to match against imports
        """
        libraries = set()
        
        for stage_name, stage_config in self.config.get('stages', {}).items():
            # Get imports from each stage
            for import_lib in stage_config.get('imports', []):
                # Extract base library name (e.g., 'sklearn' from 'sklearn.preprocessing')
                base_lib = import_lib.split('.')[0]
                libraries.add(base_lib)
        
        # Add common data libraries that may not be in imports
        libraries.update(['pandas', 'numpy', 'scipy', 'joblib'])
        
        return libraries
    
    @property
    def analyzer_id(self) -> str:
        return "lccml"
    
    def analyze(self) -> AnalysisResult:
        """
        Analyze LCCML cohesion for all Python files.
        
        Returns:
            AnalysisResult with LCCML scores per file
        """
        results = {
            'files': {},
            'summary': {
                'total_files': 0,
                'high_cohesion': 0,     # >= 0.8
                'good_cohesion': 0,      # 0.6-0.79
                'moderate_cohesion': 0,  # 0.4-0.59
                'low_cohesion': 0,       # 0.2-0.39
                'very_low_cohesion': 0,  # < 0.2
                'single_method_files': 0, # Files with 0 or 1 method (LCCML = N/A)
                'average_lccml': 0.0
            }
        }
        
        # Reuse context's file list
        python_files = self.context.get_python_files()
        results['summary']['total_files'] = len(python_files)
        
        lccml_scores = []
        
        for py_file in python_files:
            # Reuse cached AST and source from context
            tree = self.context.get_file_ast(py_file)
            source = self.context.get_file_source(py_file)
            
            if tree is None or source is None:
                continue
            
            file_result = self._analyze_file(tree, source, py_file)
            results['files'][py_file] = file_result
            
            # Store in context for potential reuse by other analyzers
            self.context.set_file_metric(py_file, 'lccml', file_result)
            
            # Categorize based on LCCML score
            lccml = file_result['lccml']
            if lccml is None:
                results['summary']['single_method_files'] += 1
            else:
                lccml_scores.append(lccml)
                if lccml >= 0.8:
                    results['summary']['high_cohesion'] += 1
                elif lccml >= 0.6:
                    results['summary']['good_cohesion'] += 1
                elif lccml >= 0.4:
                    results['summary']['moderate_cohesion'] += 1
                elif lccml >= 0.2:
                    results['summary']['low_cohesion'] += 1
                else:
                    results['summary']['very_low_cohesion'] += 1
        
        # Calculate average LCCML
        if lccml_scores:
            results['summary']['average_lccml'] = sum(lccml_scores) / len(lccml_scores)
            score = results['summary']['average_lccml'] * 10  # Scale to 0-10
        else:
            score = 0
        
        # Generate file-level messages for files with cohesion issues
        messages = []
        for file_path, file_data in results['files'].items():
            if file_data['lccml'] is not None:
                cohesion_level = self._categorize_cohesion(file_data['lccml'])
                if cohesion_level in ['low', 'very_low']:
                    severity = 'high' if cohesion_level == 'very_low' else 'medium'
                    messages.append({
                        'file': file_path,
                        'diagnosis': f"Low cohesion detected (LCCML: {file_data['lccml']:.2f}). Methods are not well connected.",
                        'recommendation': f"Consider refactoring this module to improve method connectivity. {file_data['n_disconnected_pairs']} disconnected method pairs found.",
                        'severity': severity,
                        'rule_id': 1
                    })
        
        return self._create_result(
            score=round(score, 2),
            messages=messages,
            module_count=results['summary']['total_files'],
            details=results
        )
    
    def _analyze_file(self, tree: ast.Module, source: str, file_path: str) -> Dict:
        """
        Analyze LCCML for a single file.
        
        Args:
            tree: AST of the file
            source: Source code string
            file_path: Path to the file
            
        Returns:
            Dict with LCCML score and connection details
        """
        # Extract all methods (functions and class methods)
        methods = self._extract_methods(tree)
        n_methods = len(methods)
        
        # LCCML is not applicable for files with 0 or 1 method
        if n_methods <= 1:
            return {
                'lccml': None,
                'n_methods': n_methods,
                'n_possible_pairs': 0,
                'n_connected_pairs': 0,
                'connection_breakdown': {
                    'by_variables': 0,
                    'by_files': 0,
                    'by_ml_functions': 0,
                    'by_method_calls': 0
                },
                'cohesion_level': 'not_applicable'
            }
        
        # Calculate total possible pairs
        n_possible_pairs = (n_methods * (n_methods - 1)) // 2
        
        # Analyze connections between methods
        connections = self._analyze_connections(methods, tree, source)
        
        # Count connected pairs (union of all connection types)
        connected_pairs = (
            connections['by_variables'] |
            connections['by_files'] |
            connections['by_ml_functions'] |
            connections['by_method_calls']
        )
        n_connected_pairs = len(connected_pairs)
        
        # Calculate disconnected pairs
        all_possible_pairs = set()
        method_names = list(methods.keys())
        for i, method_a in enumerate(method_names):
            for method_b in method_names[i+1:]:
                all_possible_pairs.add((method_a, method_b))
        
        disconnected_pairs = all_possible_pairs - connected_pairs
        
        # Calculate LCCML
        lccml = n_connected_pairs / n_possible_pairs if n_possible_pairs > 0 else 0
        
        # Determine cohesion level
        cohesion_level = self._determine_cohesion_level(lccml)
        
        return {
            'lccml': round(lccml, 3),
            'n_methods': n_methods,
            'n_possible_pairs': n_possible_pairs,
            'n_connected_pairs': n_connected_pairs,
            'n_disconnected_pairs': len(disconnected_pairs),
            'disconnected_pairs': sorted(list(disconnected_pairs)),
            'connection_breakdown': {
                'by_variables': len(connections['by_variables']),
                'by_files': len(connections['by_files']),
                'by_ml_functions': len(connections['by_ml_functions']),
                'by_method_calls': len(connections['by_method_calls'])
            },
            'cohesion_level': cohesion_level
        }
    
    def _extract_methods(self, tree: ast.Module) -> Dict[str, ast.FunctionDef]:
        """
        Extract all methods (functions and class methods) from AST.
        
        Returns:
            Dict mapping method name to AST node
        """
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
    
    def _analyze_connections(
        self, 
        methods: Dict[str, ast.FunctionDef],
        tree: ast.Module,
        source: str
    ) -> Dict[str, Set[Tuple[str, str]]]:
        """
        Analyze all types of connections between methods.
        
        Returns:
            Dict with sets of connected pairs for each connection type
        """
        # Get usage data for each method
        method_usage = {}
        for method_name, method_node in methods.items():
            method_usage[method_name] = {
                'variables': self._get_variables_accessed(method_node),
                'files': self._get_files_accessed(method_node),
                'ml_functions': self._get_ml_functions_used(method_node),
                'calls': self._get_method_calls(method_node, methods)
            }
        
        # Find connected pairs
        connections = {
            'by_variables': set(),
            'by_files': set(),
            'by_ml_functions': set(),
            'by_method_calls': set()
        }
        
        method_names = list(methods.keys())
        for i, method_a in enumerate(method_names):
            for method_b in method_names[i+1:]:
                pair = (method_a, method_b)
                
                # Check variable sharing
                if method_usage[method_a]['variables'] & method_usage[method_b]['variables']:
                    connections['by_variables'].add(pair)
                
                # Check file sharing
                if method_usage[method_a]['files'] & method_usage[method_b]['files']:
                    connections['by_files'].add(pair)
                
                # Check ML function sharing
                if method_usage[method_a]['ml_functions'] & method_usage[method_b]['ml_functions']:
                    connections['by_ml_functions'].add(pair)
                
                # Check method calls (bidirectional)
                if (method_b in method_usage[method_a]['calls'] or 
                    method_a in method_usage[method_b]['calls']):
                    connections['by_method_calls'].add(pair)
        
        return connections
    
    def _get_variables_accessed(self, method_node: ast.FunctionDef) -> Set[str]:
        """Extract all variables accessed (read or written) in a method."""
        variables = set()
        
        for node in ast.walk(method_node):
            if isinstance(node, ast.Name):
                variables.add(node.id)
            elif isinstance(node, ast.Attribute):
                # Get full attribute path (e.g., self.x)
                attr_path = self._get_attribute_path(node)
                if attr_path:
                    variables.add(attr_path)
        
        return variables
    
    def _get_attribute_path(self, node: ast.Attribute) -> str:
        """Get full attribute path (e.g., 'self.x' or 'obj.attr')."""
        parts = []
        current = node
        
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        
        if isinstance(current, ast.Name):
            parts.append(current.id)
            return '.'.join(reversed(parts))
        
        return ''
    
    def _get_files_accessed(self, method_node: ast.FunctionDef) -> Set[str]:
        """Extract file paths accessed in a method (data/model files)."""
        files = set()
        
        for node in ast.walk(method_node):
            # Look for string literals that look like file paths
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                file_path = node.value
                # Check if it has ML-related file extension
                if any(file_path.endswith(ext) for ext in self.ml_file_extensions):
                    files.add(file_path)
        
        return files
    
    def _get_ml_functions_used(self, method_node: ast.FunctionDef) -> Set[str]:
        """Extract ML library functions called in a method."""
        ml_functions = set()
        
        for node in ast.walk(method_node):
            if isinstance(node, ast.Call):
                func_name = self._get_function_name(node.func)
                if func_name and self._is_ml_function(func_name):
                    ml_functions.add(func_name)
        
        return ml_functions
    
    def _get_function_name(self, func_node) -> str:
        """Get the full name of a function call."""
        if isinstance(func_node, ast.Name):
            return func_node.id
        elif isinstance(func_node, ast.Attribute):
            # Get full path like 'sklearn.preprocessing.StandardScaler'
            return self._get_attribute_path(func_node)
        return ''
    
    def _is_ml_function(self, func_name: str) -> bool:
        """Check if a function name belongs to an ML library (from config)."""
        for lib in self.ml_libraries:
            if func_name.startswith(lib):
                return True
        return False
    
    def _get_method_calls(
        self, 
        method_node: ast.FunctionDef,
        all_methods: Dict[str, ast.FunctionDef]
    ) -> Set[str]:
        """Extract which other methods this method calls."""
        calls = set()
        method_names = set(all_methods.keys())
        
        for node in ast.walk(method_node):
            if isinstance(node, ast.Call):
                func_name = self._get_function_name(node.func)
                
                # Check if it's a direct call to another method
                if func_name in method_names:
                    calls.add(func_name)
                # Check for self.method() calls
                elif '.' in func_name:
                    parts = func_name.split('.')
                    if len(parts) >= 2:
                        # Try to match ClassName.method_name
                        for full_name in method_names:
                            if full_name.endswith('.' + parts[-1]):
                                calls.add(full_name)
        
        return calls
    
    def _determine_cohesion_level(self, lccml: float) -> str:
        """Determine cohesion level from LCCML score."""
        if lccml >= 0.8:
            return 'excellent'
        elif lccml >= 0.6:
            return 'good'
        elif lccml >= 0.4:
            return 'moderate'
        elif lccml >= 0.2:
            return 'low'
        else:
            return 'very_low'
    
    def _generate_messages(self, results: Dict) -> List[str]:
        """Generate human-readable messages."""
        messages = []
        summary = results['summary']
        
        messages.append(f"Analyzed {summary['total_files']} Python files for LCCML cohesion")
        
        if summary['single_method_files'] > 0:
            messages.append(
                f"ℹ {summary['single_method_files']} files with ≤1 method "
                f"(LCCML not applicable)"
            )
        
        evaluated_files = (
            summary['high_cohesion'] +
            summary['good_cohesion'] +
            summary['moderate_cohesion'] +
            summary['low_cohesion'] +
            summary['very_low_cohesion']
        )
        
        if evaluated_files > 0:
            avg_lccml = summary['average_lccml']
            messages.append(f"Average LCCML: {avg_lccml:.3f}")
            messages.append(f"Evaluated {evaluated_files} files:")
            
            if summary['high_cohesion'] > 0:
                messages.append(f"  ✓ {summary['high_cohesion']} excellent (LCCML ≥ 0.8)")
            
            if summary['good_cohesion'] > 0:
                messages.append(f"  ✓ {summary['good_cohesion']} good (LCCML 0.6-0.79)")
            
            if summary['moderate_cohesion'] > 0:
                messages.append(f"  ⚠ {summary['moderate_cohesion']} moderate (LCCML 0.4-0.59)")
            
            if summary['low_cohesion'] > 0:
                messages.append(f"  ✗ {summary['low_cohesion']} low (LCCML 0.2-0.39)")
                
                # List files with low cohesion
                low_cohesion_files = [
                    (fp, data) for fp, data in results['files'].items()
                    if data.get('cohesion_level') == 'low'
                ]
                if low_cohesion_files:
                    messages.append("Files with low cohesion:")
                    for fp, file_data in low_cohesion_files[:3]:  # Show max 3
                        lccml = file_data.get('lccml', 0)
                        n_disconnected = file_data.get('n_disconnected_pairs', 0)
                        disconnected_pairs = file_data.get('disconnected_pairs', [])
                        
                        messages.append(f"  - {fp} (LCCML: {lccml:.3f})")
                        if disconnected_pairs and n_disconnected > 0:
                            messages.append(f"    Disconnected pairs ({n_disconnected}):")
                            for pair in disconnected_pairs[:5]:
                                messages.append(f"      • {pair[0]} ↔ {pair[1]}")
                            if len(disconnected_pairs) > 5:
                                remaining = len(disconnected_pairs) - 5
                                messages.append(f"      ... and {remaining} more")
            
            if summary['very_low_cohesion'] > 0:
                messages.append(f"  ✗ {summary['very_low_cohesion']} very low (LCCML < 0.2)")
                
                # List problematic files
                low_files = [
                    (fp, data) for fp, data in results['files'].items()
                    if data.get('cohesion_level') == 'very_low'
                ]
                if low_files:
                    messages.append("Files needing cohesion improvement:")
                    for fp, file_data in low_files[:5]:  # Show max 5
                        lccml = file_data.get('lccml', 0)
                        n_methods = file_data.get('n_methods', 0)
                        n_connected = file_data.get('n_connected_pairs', 0)
                        n_possible = file_data.get('n_possible_pairs', 1)
                        n_disconnected = file_data.get('n_disconnected_pairs', 0)
                        disconnected_pairs = file_data.get('disconnected_pairs', [])
                        
                        messages.append(f"  - {fp}")
                        messages.append(f"    LCCML: {lccml:.3f} ({n_connected}/{n_possible} pairs connected)")
                        messages.append(f"    Methods: {n_methods}")
                        
                        if disconnected_pairs and n_disconnected > 0:
                            messages.append(f"    Disconnected pairs ({n_disconnected}):")
                            # Show max 10 disconnected pairs per file
                            for pair in disconnected_pairs[:10]:
                                messages.append(f"      • {pair[0]} ↔ {pair[1]}")
                            if len(disconnected_pairs) > 10:
                                remaining = len(disconnected_pairs) - 10
                                messages.append(f"      ... and {remaining} more")
        
        return messages
