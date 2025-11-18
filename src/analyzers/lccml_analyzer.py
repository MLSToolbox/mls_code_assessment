import ast
import os
import json
from typing import Dict, List, Set, Tuple, Optional, Any

from core.analysis_result import AnalysisResult
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
            os.path.dirname(__file__),
            'pipeline',
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
        
        Handles both OOP and functional paradigms:
        - Class methods: ClassName.method_name
        - Module-level functions: function_name
        
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
                    # Module-level function
                    method_name = node.name
                self.methods[method_name] = node
                self.generic_visit(node)
        
        visitor = MethodVisitor()
        visitor.visit(tree)
        return visitor.methods
    
    def _extract_global_variables(self, tree: ast.Module) -> Set[str]:
        """
        Extract module-level global variables that could be shared between functions.
        
        Detects:
        - Module-level assignments (e.g., DATA = load_data())
        - Constants (e.g., CONFIG = {...})
        - Global declarations
        
        These variables can be shared between module-level functions,
        providing cohesion similar to self.x in classes.
        
        Args:
            tree: AST of the module
            
        Returns:
            Set of global variable names
        """
        globals_vars = set()
        
        for node in ast.iter_child_nodes(tree):
            # Direct module-level assignments
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        globals_vars.add(target.id)
            
            # Annotated assignments (e.g., DATA: pd.DataFrame = ...)
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    globals_vars.add(node.target.id)
        
        return globals_vars
    
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
        
        # Build adjacency graph for direct connections
        graph = self._build_adjacency_graph(method_usage, list(methods.keys()))
        
        # Apply DFS to find all reachable methods (transitive connections)
        reachable = self._get_reachable_methods(graph, list(methods.keys()))
        
        # Find connected pairs using reachability
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
                
                # Check if methods are reachable (directly or transitively)
                if method_b in reachable[method_a]:
                    # Determine which type of connection exists
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
    
    def _build_adjacency_graph(
        self, 
        method_usage: Dict[str, Dict[str, Set]],
        method_names: List[str]
    ) -> Dict[str, Set[str]]:
        """
        Build adjacency graph of direct connections between methods.
        
        Two methods are directly connected if they share:
        - Variables (especially self.x)
        - Files
        - ML library functions
        - Method calls
        
        Args:
            method_usage: Dict mapping method names to their usage data
            method_names: List of all method names
            
        Returns:
            Adjacency graph: Dict[method_name, Set[connected_method_names]]
        """
        graph = {method: set() for method in method_names}
        
        for i, method_a in enumerate(method_names):
            for method_b in method_names[i+1:]:
                # Check if methods share any resource
                shares_variables = bool(
                    method_usage[method_a]['variables'] & method_usage[method_b]['variables']
                )
                shares_files = bool(
                    method_usage[method_a]['files'] & method_usage[method_b]['files']
                )
                shares_ml_functions = bool(
                    method_usage[method_a]['ml_functions'] & method_usage[method_b]['ml_functions']
                )
                calls_each_other = (
                    method_b in method_usage[method_a]['calls'] or
                    method_a in method_usage[method_b]['calls']
                )
                
                # If any connection exists, add edge (bidirectional)
                if shares_variables or shares_files or shares_ml_functions or calls_each_other:
                    graph[method_a].add(method_b)
                    graph[method_b].add(method_a)
        
        return graph
    
    def _get_reachable_methods(
        self,
        graph: Dict[str, Set[str]],
        method_names: List[str]
    ) -> Dict[str, Set[str]]:
        """
        Find all reachable methods from each method using DFS.
        
        This implements transitive closure: if A connects to B and B connects to C,
        then A is considered connected to C even without direct connection.
        
        Args:
            graph: Adjacency graph of direct connections
            method_names: List of all method names
            
        Returns:
            Dict mapping each method to set of all reachable methods (including itself)
        """
        def dfs(node: str, visited: Set[str]) -> Set[str]:
            """Depth-first search to find all reachable nodes."""
            visited.add(node)
            reachable = {node}
            
            for neighbor in graph[node]:
                if neighbor not in visited:
                    reachable.update(dfs(neighbor, visited))
            
            return reachable
        
        reachable = {}
        for method in method_names:
            visited = set()
            reachable[method] = dfs(method, visited)
        
        return reachable
    
    def _get_variables_accessed(self, method_node: ast.FunctionDef) -> Set[str]:
        """
        Extract shared variables accessed in a method.
        
        Detects two types of shared variables:
        1. Instance variables (self.x) - for OOP code
        2. Module-level global variables - for functional/script-style code
        
        This handles both paradigms:
        - OOP: class with self.data shared between methods
        - Functional: module-level DATA variable shared between functions
        
        Examples of what IS detected:
            - self.data (instance variable)
            - self.model (instance variable)
            - GLOBAL_VAR (if defined at module level and used in function)
            
        Examples of what is NOT detected:
            - local_var (local variable)
            - param (function parameter)
            - np.array (module import)
        
        Args:
            method_node: AST node of the method/function
            
        Returns:
            Set of variable names (e.g., {'self.data', 'DATASET', 'CONFIG'})
        """
        variables = set()
        
        # Get function parameters to exclude them
        params = {arg.arg for arg in method_node.args.args}
        
        for node in ast.walk(method_node):
            if isinstance(node, ast.Attribute):
                # Get full attribute path (e.g., self.x)
                attr_path = self._get_attribute_path(node)
                # Include if it starts with 'self.' (instance variables)
                if attr_path and attr_path.startswith('self.'):
                    variables.add(attr_path)
            
            elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Load, ast.Store)):
                # Check if it's a global variable (not a parameter or local)
                var_name = node.id
                
                # Skip if it's a parameter
                if var_name in params:
                    continue
                
                # Skip if it's 'self'
                if var_name == 'self':
                    continue
                
                # Check if it looks like a global/module-level variable
                # Heuristic: UPPERCASE or starts with underscore (common conventions)
                # OR it's being loaded (read) which suggests it might be global
                if isinstance(node.ctx, ast.Load):
                    # Only add if it's likely a global (not a builtin or import)
                    if self._is_likely_global_variable(var_name):
                        variables.add(f"global.{var_name}")
        
        return variables
    
    def _is_likely_global_variable(self, var_name: str) -> bool:
        """
        Enhanced heuristic to determine if a variable name is likely a module-level global.
        
        Excludes:
        - Python builtins (list, dict, str, etc.)
        - Common imports (pd, np, os, etc.)
        - Common local variable names (result, temp, i, j, etc.)
        - Very short names (x, y, i) unless they're common ML variables
        
        Includes:
        - UPPERCASE names (DATA, CONFIG, MODEL_PATH)
        - UPPER_SNAKE_CASE (TRAIN_DATA, MAX_EPOCHS)
        - Names starting with underscore (_cache, _config)
        - Common ML global patterns (dataset, model, scaler, etc.)
        - MixedCase starting with uppercase (DataLoader, ModelConfig)
        
        Args:
            var_name: Variable name to check
            
        Returns:
            True if likely a global variable
        """
        # Python builtins to exclude
        builtins = {
            'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'bytearray', 'bytes',
            'callable', 'chr', 'classmethod', 'compile', 'complex', 'delattr',
            'dict', 'dir', 'divmod', 'enumerate', 'eval', 'exec', 'filter',
            'float', 'format', 'frozenset', 'getattr', 'globals', 'hasattr',
            'hash', 'help', 'hex', 'id', 'input', 'int', 'isinstance',
            'issubclass', 'iter', 'len', 'list', 'locals', 'map', 'max',
            'memoryview', 'min', 'next', 'object', 'oct', 'open', 'ord',
            'pow', 'print', 'property', 'range', 'repr', 'reversed', 'round',
            'set', 'setattr', 'slice', 'sorted', 'staticmethod', 'str', 'sum',
            'super', 'tuple', 'type', 'vars', 'zip', '__import__'
        }
        
        # Common library aliases to exclude
        common_imports = {
            'np', 'pd', 'plt', 'sns', 'tf', 'torch', 'os', 'sys', 'json',
            'cv2', 'sk', 'sklearn', 'scipy', 'sp', 'math', 're', 'time',
            'datetime', 'collections', 'itertools', 'functools', 'operator',
            'pathlib', 'logging', 'warnings', 'pickle', 'joblib'
        }
        
        # Common local variable names to exclude
        common_locals = {
            'result', 'results', 'output', 'temp', 'tmp', 'value', 'values',
            'item', 'items', 'elem', 'element', 'row', 'col', 'idx', 'index',
            'i', 'j', 'k', 'n', 'm', 'key', 'val', 'arg', 'args', 'kwargs',
            'self', 'cls', 'obj', 'func', 'fn', 'callback', 'handler'
        }
        
        # Common ML global variable names/patterns
        common_ml_globals = {
            # Data
            'data', 'dataset', 'datasets', 'df', 'dataframe',
            'X', 'Y', 'y', 'X_train', 'X_test', 'X_val',
            'y_train', 'y_test', 'y_val', 'train_data', 'test_data', 'val_data',
            'train_set', 'test_set', 'val_set', 'validation_data',
            # Models
            'model', 'models', 'net', 'network', 'estimator',
            'classifier', 'regressor', 'predictor',
            # Preprocessing
            'scaler', 'encoder', 'tokenizer', 'vectorizer',
            'transformer', 'preprocessor', 'normalizer',
            # Configuration
            'config', 'cfg', 'params', 'hyperparams', 'settings',
            'options', 'args', 'arguments',
            # Paths
            'data_path', 'model_path', 'output_path', 'input_path',
            # Other
            'features', 'labels', 'targets', 'predictions',
            'weights', 'bias', 'embeddings'
        }
        
        if var_name in builtins or var_name in common_imports:
            return False
        
        if var_name in common_locals:
            return False
        
        # Check if it's a common ML global
        if var_name in common_ml_globals:
            return True
        
        # UPPERCASE (including UPPER_SNAKE_CASE like TRAIN_DATA)
        # Check if all alphabetic characters are uppercase
        if var_name.replace('_', '').isalpha() and var_name.replace('_', '').isupper():
            return True
        
        # Starts with underscore (module-private variables)
        if var_name.startswith('_'):
            return True
        
        # MixedCase starting with uppercase (e.g., DataLoader, ModelConfig)
        if var_name[0].isupper() and not var_name.isupper():
            return True
        
        # Pattern matching for common ML naming conventions
        # e.g., train_dataset, test_model, validation_scaler
        ml_prefixes = {'train', 'test', 'val', 'validation', 'dev'}
        ml_suffixes = {
            'data', 'dataset', 'set', 'loader', 'model', 'scaler',
            'encoder', 'tokenizer', 'config', 'params', 'path'
        }
        
        if '_' in var_name:
            parts = var_name.split('_')
            if len(parts) >= 2:
                # Check prefix_suffix pattern (e.g., train_data)
                if parts[0] in ml_prefixes and parts[-1] in ml_suffixes:
                    return True
                # Check suffix pattern (e.g., model_config, data_path)
                if parts[-1] in ml_suffixes and len(var_name) > 6:
                    return True
        
        # Very short names (≤2 chars) are likely locals unless already caught above
        if len(var_name) <= 2:
            return False
        
        # Conservative: longer lowercase names without ML patterns are excluded
        # to avoid false positives
        return False
    
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
