import ast
import os
from typing import Dict, List, Set, Tuple, Any, Optional
from collections import defaultdict
import logging
from core.analysis_context import AnalysisContext
from core.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer
logger = logging.getLogger(__name__)
class PipelineGraphBaseAnalyzer(BaseAnalyzer):
    """
    Base class for constructing and extracting the dependency graph of pipeline resources.
    Identifies nodes (modules), extracts ML resources, and builds the connectivity graph.
    """
    def __init__(self, session_id: str, local_path: str, context: Optional[AnalysisContext] = None):
        super().__init__(session_id, local_path, context)
        # Fallback/Supplemental heuristics for ML variable names
        self.heuristic_vars = {
            'df', 'data', 'dataset', 'batch', 'loader', 'tensor', 'X', 'y', 'X_train', 'y_train',
            'model', 'clf', 'estimator', 'network', 'weights', 'pipeline',
            'config', 'params', 'settings', 'args', 'hyperparams'
        }
    @property
    def analyzer_id(self) -> str:
        raise NotImplementedError

    def analyze(self) -> AnalysisResult:
        raise NotImplementedError
    def _analyze_package_graph(self, package_path: str) -> Dict[str, Any]:
        """
        Analyze the graph structure of a package.
        Returns nodes, connections, groups, and isolated nodes.
        """
        # 1. Node Identification (Files and Subpackages)
        nodes = self._get_package_nodes(package_path)
        m = len(nodes)
        # Minimum validation: need at least 2 nodes to analyze coupling
        if m < 2:
            return {
                'valid': False,
                'n_nodes': m, 
                'nodes': [os.path.basename(n) for n in nodes],
                'reason': 'Insufficient nodes (< 2)'
            }
        # 2. Resource Extraction per Node (Fingerprinting)
        node_resources = {}
        for node_path in nodes:
            node_name = os.path.basename(node_path)
            if os.path.isdir(node_path):
                # It's a subpackage: Recursive Aggregation
                resources = self._get_subpackage_resources(node_path)
            else:
                # It's a file: Direct AST Extraction
                resources = self._extract_file_resources(node_path)
            node_resources[node_path] = resources
        # 3. Construction of Connectivity Matrix (Q)
        connections = []
        connected_nodes = set()
        node_list = list(nodes) # Consistent order for indexing
        # Pair-wise Switch Comparison (All-pairs comparison, O(m^2))
        for i in range(len(node_list)):
            for j in range(i + 1, len(node_list)):
                node_a_path = node_list[i]
                node_b_path = node_list[j]
                res_a = node_resources[node_a_path]
                res_b = node_resources[node_b_path]
                # Cohesion Criterion: Non-empty intersection of resources
                intersection = res_a.intersection(res_b)
                if intersection:
                    connections.append({
                        'node_a': os.path.basename(node_a_path),
                        'node_b': os.path.basename(node_b_path),
                        'shared_resources': list(intersection)[:5] # Limit for display
                    })
                    connected_nodes.add(node_a_path)
                    connected_nodes.add(node_b_path)
        
        # 4. Calculation of Connected Components (Groups) - Base Logic for P-LCOM
        # Map name to numeric index for graph algorithms
        name_to_idx = {name: i for i, name in enumerate([os.path.basename(n) for n in nodes])}
        adj = defaultdict(list)
        # Construction of adjacency list
        for conn in connections:
            u = name_to_idx[conn['node_a']]
            v = name_to_idx[conn['node_b']]
            adj[u].append(v)
            adj[v].append(u)
        # Depth First Search (DFS) to find islands
        visited = set()
        groups = []
        node_names = [os.path.basename(n) for n in nodes]
        for i in range(m):
            if i not in visited:
                component = []
                stack = [i]
                visited.add(i)
                while stack:
                    curr = stack.pop()
                    component.append(node_names[curr])
                    for neighbor in adj[curr]:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            stack.append(neighbor)
                groups.append(component)
        # 5. Identification of Isolated Nodes
        all_nodes_set = set(nodes)
        isolated_nodes = list(all_nodes_set - connected_nodes)
        total_pairs = (m * (m - 1)) // 2
        # Return complete structure for consumption by SCPP and P-LCOM
        return {
            'valid': True,
            'n_nodes': m,
            'connections': connections,
            'groups': groups,
            'isolated_nodes': [os.path.basename(n) for n in isolated_nodes],
            'nodes': node_names,
            'n_pairs': total_pairs,
            'n_shared': len(connections)
        }
    
    def _get_package_nodes(self, package_path: str) -> List[str]:
        nodes = []
        try:
            for item in os.listdir(package_path):
                if item in ["__pycache__","test","tests","examples",".pytest_cache","docs"]:
                    continue
                abs_path = os.path.join(package_path, item)
                if os.path.isfile(abs_path):
                    if item.endswith('.py') and item != '__init__.py':
                        nodes.append(abs_path)
                elif os.path.isdir(abs_path):
                    if self._is_package(abs_path):
                        nodes.append(abs_path)
        except (PermissionError, FileNotFoundError):
             pass
      
        return nodes
    def _is_package(self, dir_path: str) -> bool:
        for _,_,files in os.walk(dir_path):
            if any(f.endswith(".py") for f in files):
                return True
        return False
    def _get_subpackage_resources(self, subpackage_path: str) -> Set[str]:
        resources = set()
        for root, _, files in os.walk(subpackage_path):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    resources.update(self._extract_file_resources(file_path))
        return resources
    def _extract_file_resources(self, file_path: str) -> Set[str]:
        resources = set()
        tree = self.context.get_file_ast(file_path)
        if not tree: return resources

        # Helper to process potentail file/URI strings
        def _process_str_arg(val_str):
            # Helper for OS-agnostic basename (URIs often use /, while Windows uses \)
            def get_robust_basename(path_str):
                return path_str.replace('\\', '/').split('/')[-1]

            # 1. Extensions check
            if val_str.endswith(('.yaml', '.yml', '.json', '.csv', '.parquet', '.pkl', '.h5', '.pth', '.joblib')):
                return get_robust_basename(val_str)
            
            # 2. MLflow / URI check
            if 'mlruns' in val_str or val_str.startswith(('file:', 'sqlite:', 'postgresql:', 'http:', 'https:', 's3:', 'gs:')):
                # Normalize URI: remove prefix 'file:', 'sqlite:///'
                clean_val = val_str
                if ':' in val_str:
                    clean_val = val_str.split(':', 1)[1] # remove schema
                
                # Extract the final component reliably
                return get_robust_basename(clean_val)
            return None

        for node in ast.walk(tree):
            # 1. Direct Variables (e.g., global variables or specific usages)
            if isinstance(node, ast.Name):
                # FIX: 'df' and 'data' are very common as local variables.
                # We only accept them if they come from 'strong' contexts (args, return, self).
                # Here in ast.Name (generic usage), we ignore them to avoid false positives.
                if node.id in ['df', 'data']:
                    continue
                if self._is_pipeline_resource(node.id): 
                    resources.add(node.id)
            # 2. Object Attributes (e.g. self.model, config.params)
            if isinstance(node, ast.Attribute):
                if self._is_pipeline_resource(node.attr): resources.add(node.attr)
                if isinstance(node.value, ast.Name):
                    if self._is_pipeline_resource(node.value.id): resources.add(node.value.id)
            # 3. Imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if self._is_pipeline_resource(alias.name): resources.add(alias.name)
            if isinstance(node, ast.ImportFrom):
                # 1. Check the module source (e.g. 'sklearn.linear_model')
                if node.module and self._is_pipeline_resource(node.module): 
                    resources.add(node.module)
                # 2. Check the imported objects (e.g. 'LinearRegression')
                for alias in node.names:
                    if self._is_pipeline_resource(alias.name):
                        resources.add(alias.name)
            # 6. Definitions (Classes and Functions) & Contextual Usage (Args/Returns)
            if isinstance(node, ast.ClassDef):
                if self._is_pipeline_resource(node.name):
                    resources.add(node.name)
            if isinstance(node, ast.FunctionDef):
                # A. Is the function name a resource? (Definition)
                if self._is_pipeline_resource(node.name):
                    resources.add(node.name)
                
                # B. Function Arguments (Strong Context)
                # If a function asks for (df, model), it is an explicit dependency.
                for arg in node.args.args:
                    if self._is_pipeline_resource(arg.arg):
                        resources.add(arg.arg)

            if isinstance(node, ast.Return):
                # C. Function Return (Strong Context)
                # If it returns 'df', it is a data producer.
                if isinstance(node.value, ast.Name):
                    if self._is_pipeline_resource(node.value.id):
                        resources.add(node.value.id)
            
            # 5. Shared Configuration/Data Files (String Literals in calls) & Semantic Models
            # Detects: load("params.yaml"), read_csv("data.csv"), RandomForestClassifier()
            if isinstance(node, ast.Call):
                # 8. Semantic Model Detection (Instantiations & Loading)
                # A. Detect Model Instantiation (e.g. RandomForestClassifier())
                full_func_name = ""
                if isinstance(node.func, ast.Name):
                    full_func_name = node.func.id
                    # Case: Classifier()
                    if any(mc in node.func.id for mc in ['Classifier', 'Regressor', 'Model', 'Estimator', 'Network', 'Transformer']):
                         resources.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    full_func_name = node.func.attr # Just the attribute name for generic check
                    # Case: sklearn.ensemble.RandomForestClassifier() -> checks 'RandomForestClassifier'
                    if any(mc in node.func.attr for mc in ['Classifier', 'Regressor', 'Model', 'Estimator', 'Network', 'Transformer']):
                         resources.add(node.func.attr)
                    
                    # Better reconstruction for loading checks
                    if isinstance(node.func.value, ast.Name):
                        full_func_name = f"{node.func.value.id}.{node.func.attr}"

                # B. Detect Model Loading (specific functions)
                if full_func_name in ['load_model', 'joblib.load', 'pickle.load', 'torch.load', 'load_state_dict', 'load']:
                     if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                         # Extract filename robustly
                         val = node.args[0].value
                         base_name = val.replace('\\', '/').split('/')[-1]
                         resources.add(f"model:{base_name}")

                # Check positional arguments
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        res = _process_str_arg(arg.value)
                        if res: resources.add(res)
                
                # Check keyword arguments
                for keyword in node.keywords:
                    if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                         res = _process_str_arg(keyword.value.value)
                         if res: resources.add(res)
            
            # 7. String Constants (e.g. Dict keys 'model_path', or names passed as str, or variable assignments)
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                 # A. Is it a file path or URI?
                 res = _process_str_arg(node.value)
                 if res: 
                     resources.add(res)
                 # B. Is it a resource name? (e.g. 'train_data')
                 elif self._is_pipeline_resource(node.value):
                     resources.add(node.value)
        return resources
    def _is_pipeline_resource(self, name: str) -> bool:
        if len(name) < 2: 
            return False
        # Blacklist of generic methods/names that DO NOT contribute to structural cohesion
        # Note: 'df' and 'data' are kept allowed as they represent the main data flow
        blacklist = {'fillna', 'apply', 'fit', 'transform', 'predict', 'fit_transform', 
                     'score', 'get_data', 'set_data', 'join', 'concat', 'isnull', 'sum', 'mean'}
        if name in blacklist:
            return False
        # Exact check first
        if name in self.heuristic_vars:
            return True
        # For compound variables (X_train, y_test, etc.)
        lower_name = name.lower()
        ml_patterns = ['_train', '_test', '_val', '_pred', 'dataset', 'model', 'config']
        for pattern in ml_patterns:
            if pattern in lower_name:
                return True      
        # Check for common prefixes/suffixes
        if lower_name.startswith(('x_', 'y_', 'df_', 'model_', 'config_')):
            return True
        return False
