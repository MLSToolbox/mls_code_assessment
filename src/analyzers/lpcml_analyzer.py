import ast
import os
import json
import logging
from typing import Dict, List, Set, Tuple, Optional, Any
from collections import defaultdict

from core.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer

logger = logging.getLogger(__name__)

class LPCMLAnalyzer(BaseAnalyzer):
    """
    Analyzer for LPCML (Loose Package Cohesion Modified for ML) metric.
    
    Measures the number of connected components within a package. A connected 
    component represents a group of modules related through dependencies, 
    shared data, model files, or ML library usage.
    
    Formula: LPCML(P) = |CC(G_P)|
    where G_P = (V, E) is the undirected dependency graph:
    - V = first-level elements (modules/subpackages) of package P
    - E = edges exist when elements share resources (non-empty intersection)
    """
    
    def __init__(self, session_id: str, local_path: str, context=None):
        super().__init__(session_id, local_path, context)
        
        # Load ML library configuration
        pipeline_stages_json_path = os.path.join(
            os.path.dirname(__file__),
            'pipeline',
            'pipeline_stages.json'
        )
        
        if os.path.exists(pipeline_stages_json_path):
            with open(pipeline_stages_json_path, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {}
        
        self.ml_libraries = self._extract_ml_libraries_from_config()
        
        self.ml_file_extensions = {
            '.csv', '.pkl', '.joblib', '.h5', '.hdf5', '.pt', '.pth',
            '.ckpt', '.model', '.json', '.parquet', '.feather', '.npy', '.npz'
        }
    
    def _extract_ml_libraries_from_config(self) -> Set[str]:
        """Extract all ML library names from pipeline_stages.json."""
        libraries = set()
        for stage_name, stage_config in self.config.get('stages', {}).items():
            for import_lib in stage_config.get('imports', []):
                base_lib = import_lib.split('.')[0]
                libraries.add(base_lib)
        libraries.update(['pandas', 'numpy', 'scipy', 'joblib', 'sklearn', 'tensorflow', 'torch', 'keras', 'matplotlib', 'seaborn'])
        return libraries
    
    @property
    def analyzer_id(self) -> str:
        return "lpcml"
    
    def analyze(self) -> AnalysisResult:
        results = {
            'packages': {},
            'summary': {
                'total_packages': 0,
                'excellent_cohesion': 0,
                'acceptable_cohesion': 0,
                'moderate_cohesion': 0,
                'poor_cohesion': 0,
                'average_components': 0.0,
                'average_cohesion_ratio': 0.0
            }
        }
        
        package_structure = defaultdict(lambda: {'files': [], 'subpackages': []})
        all_python_files = self.context.get_all_python_files()
        
        logger.info(f"LPCML: Found {len(all_python_files)} python files.")
        
        package_dirs = set()
        for i, file_path in enumerate(all_python_files):
            dir_path = os.path.dirname(file_path)
            init_path = os.path.join(self.local_path, dir_path, '__init__.py')
            
            if i < 3: # Debug log for first few files
                logger.info(f"LPCML Debug: Checking {file_path} -> Dir: {dir_path} -> Init: {init_path} -> Exists: {os.path.exists(init_path)}")
                
            if os.path.exists(init_path):
                abs_pkg_dir = os.path.join(self.local_path, dir_path)
                package_dirs.add(os.path.normpath(abs_pkg_dir))
        
        logger.info(f"LPCML: Identified {len(package_dirs)} package directories.")
        
        for pkg_dir in package_dirs:
            try:
                with os.scandir(pkg_dir) as it:
                    for entry in it:
                        entry_path = os.path.normpath(entry.path)
                        if entry.is_file() and entry.name.endswith('.py') and entry.name != '__init__.py':
                            package_structure[pkg_dir]['files'].append(entry_path)
                        elif entry.is_dir():
                            init_path = os.path.join(entry_path, '__init__.py')
                            if os.path.exists(init_path):
                                package_structure[pkg_dir]['subpackages'].append(entry_path)
            except OSError as e:
                logger.error(f"LPCML: Error scanning directory {pkg_dir}: {e}")
                continue

        results['summary']['total_packages'] = len(package_structure)
        component_counts = []
        cohesion_ratios = []
        
        for pkg_path, structure in package_structure.items():
            # Use os.path.relpath to get relative path
            # Do NOT replace separators with dots, keep OS separator (backslash on Windows)
            pkg_name = os.path.relpath(pkg_path, self.local_path)
            if pkg_name == '.': pkg_name = 'root'
                
            vertices = structure['files'] + structure['subpackages']
            if len(vertices) < 2: continue
                
            package_result = self._analyze_package(vertices, structure['files'], structure['subpackages'])
            results['packages'][pkg_name] = package_result
            
            lpcml = package_result['lpcml']
            if lpcml is not None:
                component_counts.append(lpcml)
                cohesion_ratio = 1.0 / lpcml if lpcml > 0 else 0
                cohesion_ratios.append(cohesion_ratio)
                
                if lpcml == 1: results['summary']['excellent_cohesion'] += 1
                elif lpcml <= 3: results['summary']['acceptable_cohesion'] += 1
                elif lpcml <= 5: results['summary']['moderate_cohesion'] += 1
                else: results['summary']['poor_cohesion'] += 1
        
        if component_counts:
            results['summary']['average_components'] = sum(component_counts) / len(component_counts)
            results['summary']['average_cohesion_ratio'] = sum(cohesion_ratios) / len(cohesion_ratios)
            score = results['summary']['average_cohesion_ratio'] * 10
        else:
            score = 0
        
        messages = self._generate_messages(results)
        return self._create_result(score=round(score, 2), messages=messages, module_count=len(package_structure), details=results)
    
    def _analyze_package(self, vertices: List[str], files: List[str], subpackages: List[str]) -> Dict:
        vertex_resources = {}
        for file_path in files:
            vertex_resources[file_path] = self._extract_resources_from_file(file_path)
        for subpkg_path in subpackages:
            vertex_resources[subpkg_path] = self._extract_resources_recursive(subpkg_path)
import ast
import os
import json
import logging
from typing import Dict, List, Set, Tuple, Optional, Any
from collections import defaultdict

from core.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer

logger = logging.getLogger(__name__)

class LPCMLAnalyzer(BaseAnalyzer):
    """
    Analyzer for LPCML (Loose Package Cohesion Modified for ML) metric.
    
    Measures the number of connected components within a package. A connected 
    component represents a group of modules related through dependencies, 
    shared data, model files, or ML library usage.
    
    Formula: LPCML(P) = |CC(G_P)|
    where G_P = (V, E) is the undirected dependency graph:
    - V = first-level elements (modules/subpackages) of package P
    - E = edges exist when elements share resources (non-empty intersection)
    """
    
    def __init__(self, session_id: str, local_path: str, context=None):
        super().__init__(session_id, local_path, context)
        
        # Load ML library configuration
        pipeline_stages_json_path = os.path.join(
            os.path.dirname(__file__),
            'pipeline',
            'pipeline_stages.json'
        )
        
        if os.path.exists(pipeline_stages_json_path):
            with open(pipeline_stages_json_path, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {}
        
        self.ml_libraries = self._extract_ml_libraries_from_config()
        
        self.ml_file_extensions = {
            '.csv', '.pkl', '.joblib', '.h5', '.hdf5', '.pt', '.pth',
            '.ckpt', '.model', '.json', '.parquet', '.feather', '.npy', '.npz'
        }
    
    def _extract_ml_libraries_from_config(self) -> Set[str]:
        """Extract all ML library names from pipeline_stages.json."""
        libraries = set()
        for stage_name, stage_config in self.config.get('stages', {}).items():
            for import_lib in stage_config.get('imports', []):
                base_lib = import_lib.split('.')[0]
                libraries.add(base_lib)
        libraries.update(['pandas', 'numpy', 'scipy', 'joblib', 'sklearn', 'tensorflow', 'torch', 'keras', 'matplotlib', 'seaborn'])
        return libraries
    
    @property
    def analyzer_id(self) -> str:
        return "lpcml"
    
    def analyze(self) -> AnalysisResult:
        results = {
            'packages': {},
            'summary': {
                'total_packages': 0,
                'excellent_cohesion': 0,
                'acceptable_cohesion': 0,
                'moderate_cohesion': 0,
                'poor_cohesion': 0,
                'average_components': 0.0,
                'average_cohesion_ratio': 0.0
            }
        }
        
        package_structure = defaultdict(lambda: {'files': [], 'subpackages': []})
        all_python_files = self.context.get_all_python_files()
        
        logger.info(f"LPCML: Found {len(all_python_files)} python files.")
        
        package_dirs = set()
        for i, file_path in enumerate(all_python_files):
            dir_path = os.path.dirname(file_path)
            init_path = os.path.join(self.local_path, dir_path, '__init__.py')
            
            if i < 3: # Debug log for first few files
                logger.info(f"LPCML Debug: Checking {file_path} -> Dir: {dir_path} -> Init: {init_path} -> Exists: {os.path.exists(init_path)}")
                
            if os.path.exists(init_path):
                abs_pkg_dir = os.path.join(self.local_path, dir_path)
                package_dirs.add(os.path.normpath(abs_pkg_dir))
        
        logger.info(f"LPCML: Identified {len(package_dirs)} package directories.")
        
        for pkg_dir in package_dirs:
            try:
                with os.scandir(pkg_dir) as it:
                    for entry in it:
                        entry_path = os.path.normpath(entry.path)
                        if entry.is_file() and entry.name.endswith('.py') and entry.name != '__init__.py':
                            package_structure[pkg_dir]['files'].append(entry_path)
                        elif entry.is_dir():
                            init_path = os.path.join(entry_path, '__init__.py')
                            if os.path.exists(init_path):
                                package_structure[pkg_dir]['subpackages'].append(entry_path)
            except OSError as e:
                logger.error(f"LPCML: Error scanning directory {pkg_dir}: {e}")
                continue

        results['summary']['total_packages'] = len(package_structure)
        component_counts = []
        cohesion_ratios = []
        
        for pkg_path, structure in package_structure.items():
            # Use os.path.relpath to get relative path
            # Do NOT replace separators with dots, keep OS separator (backslash on Windows)
            pkg_name = os.path.relpath(pkg_path, self.local_path)
            if pkg_name == '.': pkg_name = 'root'
                
            vertices = structure['files'] + structure['subpackages']
            if len(vertices) < 2: continue
                
            package_result = self._analyze_package(vertices, structure['files'], structure['subpackages'])
            results['packages'][pkg_name] = package_result
            
            lpcml = package_result['lpcml']
            if lpcml is not None:
                component_counts.append(lpcml)
                cohesion_ratio = 1.0 / lpcml if lpcml > 0 else 0
                cohesion_ratios.append(cohesion_ratio)
                
                if lpcml == 1: results['summary']['excellent_cohesion'] += 1
                elif lpcml <= 3: results['summary']['acceptable_cohesion'] += 1
                elif lpcml <= 5: results['summary']['moderate_cohesion'] += 1
                else: results['summary']['poor_cohesion'] += 1
        
        if component_counts:
            results['summary']['average_components'] = sum(component_counts) / len(component_counts)
            results['summary']['average_cohesion_ratio'] = sum(cohesion_ratios) / len(cohesion_ratios)
            score = results['summary']['average_cohesion_ratio'] * 10
        else:
            score = 0
        
        messages = self._generate_messages(results)
        return self._create_result(score=round(score, 2), messages=messages, module_count=len(package_structure), details=results)
    
    def _analyze_package(self, vertices: List[str], files: List[str], subpackages: List[str]) -> Dict:
        vertex_resources = {}
        for file_path in files:
            vertex_resources[file_path] = self._extract_resources_from_file(file_path)
        for subpkg_path in subpackages:
            vertex_resources[subpkg_path] = self._extract_resources_recursive(subpkg_path)
            
        graph = self._build_graph(vertex_resources)
        component_count, components = self._count_connected_components(graph)
        cohesion_ratio = 1.0 / component_count if component_count > 0 else 0
        
        cohesive_clusters = []
        isolated_elements = []
        
        # Sort components by size (descending)
        components.sort(key=len, reverse=True)
        
        for comp in components:
            comp_names = [os.path.basename(v) for v in comp]
            
            if len(comp) > 1:
                # Analyze shared resources for this cluster
                shared_res = self._identify_shared_resources(comp, vertex_resources)
                cohesive_clusters.append({
                    'members': comp_names,
                    'shared_resources': shared_res
                })
            else:
                isolated_elements.extend(comp_names)
            
        return {
            'lpcml': component_count,
            'n_elements': len(vertices),
            'n_components': component_count,
            'cohesion_ratio': round(cohesion_ratio, 3),
            'cohesive_clusters': cohesive_clusters,
            'isolated_elements': isolated_elements,
            'cohesion_level': self._categorize_cohesion(component_count)
        }
    
    def _identify_shared_resources(self, cluster_nodes: List[str], vertex_resources: Dict) -> Dict[str, List[str]]:
        """Identify resources shared by at least 2 nodes in the cluster."""
        resource_counts = defaultdict(int)
        
        # Count occurrences of each resource across all nodes in cluster
        for node in cluster_nodes:
            res = vertex_resources[node]
            # Combine all resource types for counting
            all_res = set()
            all_res.update(res['data_files'])
            all_res.update(res['model_files'])
            all_res.update(res['ml_functions'])
            all_res.update(res['global_vars'])
            all_res.update(res['used_ml_libraries'])
            all_res.update(res['imports'])  # Include all imports to show code dependencies
            
            for r in all_res:
                resource_counts[r] += 1
                
        # Filter for resources appearing > 1
        shared = [r for r, count in resource_counts.items() if count > 1]
        
        # Categorize them for display
        categorized = defaultdict(list)
        for r in shared:
            if any(r.endswith(ext) for ext in self.ml_file_extensions):
                categorized['files'].append(r)
            elif r in self.ml_libraries:
                categorized['libraries'].append(r)
            elif r in self._get_all_imports(cluster_nodes, vertex_resources):
                categorized['common_imports'].append(r)
            else:
                categorized['other'].append(r)
                
        return dict(categorized)

    def _get_all_imports(self, nodes: List[str], vertex_resources: Dict) -> Set[str]:
        imports = set()
        for n in nodes:
            imports.update(vertex_resources[n]['imports'])
        return imports

    def _extract_resources_from_file(self, file_path: str) -> Dict[str, Set[str]]:
        tree = self.context.get_file_ast(file_path)
        if not tree: return self._empty_resources()
        return self._visit_ast(tree)

    def _extract_resources_recursive(self, dir_path: str) -> Dict[str, Set[str]]:
        aggregated = self._empty_resources()
        for root, _, files in os.walk(dir_path):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    resources = self._extract_resources_from_file(file_path)
                    self._merge_resources(aggregated, resources)
        return aggregated

    def _empty_resources(self):
        return {
            'data_files': set(),
            'model_files': set(),
            'imports': set(),
            'ml_functions': set(),
            'global_vars': set(),
            'used_ml_libraries': set()
        }
        
    def _merge_resources(self, target: Dict, source: Dict):
        for key in target:
            target[key].update(source.get(key, set()))

    def _visit_ast(self, tree: ast.Module) -> Dict[str, Set[str]]:
        resources = self._empty_resources()
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                file_str = node.value
                if any(file_str.endswith(ext) for ext in self.ml_file_extensions):
                    if any(file_str.endswith(ext) for ext in ['.pt', '.pth', '.h5', '.hdf5', '.model', '.ckpt']):
                        resources['model_files'].add(file_str)
                    else:
                        resources['data_files'].add(file_str)
            
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        resources['imports'].add(alias.name)
                        base_lib = alias.name.split('.')[0]
                        if base_lib in self.ml_libraries:
                            resources['used_ml_libraries'].add(base_lib)
                            
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    if node.level > 0:
                        # Relative import: .module or ..module
                        prefix = '.' * node.level
                        full_import = f"{prefix}{module}"
                        resources['imports'].add(full_import)
                    else:
                        resources['imports'].add(module)
                        base_lib = module.split('.')[0]
                        if base_lib in self.ml_libraries:
                            resources['used_ml_libraries'].add(base_lib)
                            
                    for alias in node.names:
                        if node.level > 0:
                             resources['imports'].add(f"{prefix}{module}.{alias.name}")
            
            elif isinstance(node, ast.Call):
                func_name = self._get_function_name(node.func)
                if func_name:
                    base_lib = func_name.split('.')[0]
                    if base_lib in self.ml_libraries:
                        resources['ml_functions'].add(func_name)
                        resources['used_ml_libraries'].add(base_lib)
            
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if self._is_likely_global_variable(node.id):
                    resources['global_vars'].add(node.id)
                    
        return resources

    def _get_function_name(self, func_node) -> str:
        if isinstance(func_node, ast.Name): return func_node.id
        elif isinstance(func_node, ast.Attribute): return self._get_attribute_path(func_node)
        return ''
    
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
        if not var_name: return False
        # Simplified heuristic
        ml_globals = {'data', 'df', 'model', 'config', 'X', 'y', 'dataset', 'CONFIG', 'DATA', 'MODEL'}
        return var_name in ml_globals or (var_name.isupper() and len(var_name) > 1)

    def _build_graph(self, vertex_resources: Dict[str, Dict]) -> Dict[str, Set[str]]:
        graph = {v: set() for v in vertex_resources}
        vertices = list(vertex_resources.keys())
        
        for i, v_a in enumerate(vertices):
            for v_b in vertices[i+1:]:
                res_a = vertex_resources[v_a]
                res_b = vertex_resources[v_b]
                
                shared = False
                # 1. Shared Resources (Data, Model, Globals, ML Libraries)
                for key in ['data_files', 'model_files', 'global_vars', 'used_ml_libraries']:
                    if not res_a[key].isdisjoint(res_b[key]):
                        shared = True
                        break
                
                # 2. Dependencies (Imports)
                if not shared:
                     name_a = os.path.splitext(os.path.basename(v_a))[0]
                     name_b = os.path.splitext(os.path.basename(v_b))[0]
                     
                     # Check if A imports B (by name, or relative)
                     # Simple heuristic: if 'B' appears in A's imports
                     # or '.B' appears in A's imports
                     
                     # Check A imports B
                     for imp in res_a['imports']:
                         if imp.endswith(f".{name_b}") or imp == name_b or imp.endswith(f"/{name_b}"): # / is unlikely in python import but just in case
                             shared = True
                             break
                     
                     if not shared:
                         # Check B imports A
                         for imp in res_b['imports']:
                             if imp.endswith(f".{name_a}") or imp == name_a:
                                 shared = True
                                 break
                
                if shared:
                    graph[v_a].add(v_b)
                    graph[v_b].add(v_a)
                    
        return graph

    def _count_connected_components(self, graph: Dict[str, Set[str]]) -> Tuple[int, List[List[str]]]:
        visited = set()
        components = []
        for node in graph:
            if node not in visited:
                component = []
                stack = [node]
                visited.add(node)
                while stack:
                    curr = stack.pop()
                    component.append(curr)
                    for neighbor in graph[curr]:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            stack.append(neighbor)
                components.append(component)
        return len(components), components

    def _categorize_cohesion(self, count: int) -> str:
        if count == 1: return 'excellent'
        if count <= 3: return 'acceptable'
        if count <= 5: return 'moderate'
        return 'poor'

    def _generate_messages(self, results: Dict) -> List[Dict]:
        messages = []
        for pkg, data in results['packages'].items():
            if data['lpcml'] and data['lpcml'] > 3:
                isolated = data.get('isolated_elements', [])
                diagnosis = f"High fragmentation (LPCML={data['lpcml']})."
                
                if isolated:
                    diagnosis += f" Isolated modules: {', '.join(isolated)}."
                    recommendation = "Consider checking if these isolated modules belong in this package or if they are missing dependencies."
                else:
                    recommendation = "Refactor to improve cohesion by grouping related modules."
                    
                messages.append({
                    'file': pkg,
                    'diagnosis': diagnosis,
                    'recommendation': recommendation,
                    'severity': 'medium',
                    'rule_id': 'lpcml_fragmentation'
                })
        return messages
