import ast
import os
import json
from typing import Dict, List, Set, Tuple, Optional, Any
from collections import defaultdict

from core.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer


class PMCRAnalyzer(BaseAnalyzer):
    """
    Analyzer for PMCR (Package Module Cohesion Ratio) metric.
    
    Measures the proportion of interconnected modules in a package, considering
    both code dependencies and shared ML resources (datasets, models, APIs).
    
    PMCR(P) = Mc / (n * (n - 1) / 2)
    where Mc is the number of connected module pairs (direct or indirect).
    """
    
    def __init__(self, session_id: str, local_path: str, context=None):
        super().__init__(session_id, local_path, context)
        
        # Load pipeline stages config for ML library detection
        pipeline_stages_json_path = os.path.join(
            os.path.dirname(__file__),
            'pipeline',
            'pipeline_stages.json'
        )
        
        self.ml_libraries = set(['pandas', 'numpy', 'scipy', 'joblib', 'sklearn', 'tensorflow', 'keras', 'torch', 'matplotlib', 'seaborn'])
        
        if os.path.exists(pipeline_stages_json_path):
            try:
                with open(pipeline_stages_json_path, 'r') as f:
                    config = json.load(f)
                    for stage_config in config.get('stages', {}).values():
                        for import_lib in stage_config.get('imports', []):
                            self.ml_libraries.add(import_lib.split('.')[0])
            except Exception:
                pass # Fallback to default set if config fails
                
        self.data_extensions = {'.csv', '.parquet', '.feather', '.json', '.xml', '.sql'}
        self.model_extensions = {'.pkl', '.joblib', '.h5', '.hdf5', '.pt', '.pth', '.ckpt', '.model', '.onnx'}

    @property
    def analyzer_id(self) -> str:
        return "pmcr"
    
    def analyze(self) -> AnalysisResult:
        """Analyze PMCR for all packages."""
        results = {
            'packages': {},
            'summary': {
                'total_packages': 0,
                'average_pmcr': 0.0,
                'high_cohesion': 0,
                'good_cohesion': 0,
                'moderate_cohesion': 0,
                'low_cohesion': 0,
                'very_low_cohesion': 0
            }
        }
        
        python_files = self.context.get_all_python_files()
        packages = defaultdict(list)
        
        for file_path in python_files:
            if file_path.endswith('__init__.py'):
                continue
            package_path = os.path.dirname(file_path) or '.'
            packages[package_path].append(file_path)
            
        results['summary']['total_packages'] = len(packages)
        scores = []
        
        for package_name, files in packages.items():
            if len(files) < 2:
                continue
                
            package_result = self._analyze_package(files, package_name)
            results['packages'][package_name] = package_result
            
            score = package_result['pmcr']
            if score is not None:
                scores.append(score)
                if score >= 0.8: results['summary']['high_cohesion'] += 1
                elif score >= 0.6: results['summary']['good_cohesion'] += 1
                elif score >= 0.4: results['summary']['moderate_cohesion'] += 1
                elif score >= 0.2: results['summary']['low_cohesion'] += 1
                else: results['summary']['very_low_cohesion'] += 1
                
        if scores:
            results['summary']['average_pmcr'] = sum(scores) / len(scores)
            final_score = results['summary']['average_pmcr'] * 10
        else:
            final_score = 0
            
        messages = self._generate_messages(results)
        
        return self._create_result(
            score=round(final_score, 2),
            messages=messages,
            module_count=len(packages),
            details=results
        )
        
    def _analyze_package(self, files: List[str], package_path: str) -> Dict:
        n = len(files)
        if n <= 1:
            return {'pmcr': None, 'n_modules': n}
            
        # Extract module info
        module_info = {}
        module_map = {} # name -> path
        
        for f in files:
            basename = os.path.basename(f)
            module_name = os.path.splitext(basename)[0]
            module_map[module_name] = f
            
            tree = self.context.get_file_ast(f)
            if not tree:
                module_info[f] = {'imports': set(), 'literals': set(), 'api_calls': set()}
                continue
                

            imports = self._extract_imports(tree)
            
            # Build alias map for this file
            alias_map = {}
            for imp in imports:
                if imp['type'] == 'absolute':
                    if imp.get('alias'):
                        alias_map[imp['alias']] = imp['name']
                elif imp['type'] == 'from':
                    module = imp['module']
                    for name, alias in zip(imp['names'], imp['aliases']):
                        full_name = f"{module}.{name}" if module else name
                        if alias:
                            alias_map[alias] = full_name
                        else:
                            alias_map[name] = full_name

            module_info[f] = {
                'imports': imports,
                'literals': self._extract_literals(tree),
                'api_calls': self._extract_api_calls(tree, alias_map)
            }
            
        # Resolve imports to file paths
        resolved_deps = defaultdict(set)
        for f, info in module_info.items():
            resolved = self._resolve_imports(info['imports'], module_map, package_path)
            resolved_deps[f] = resolved
            
        # Build adjacency graph
        adj = defaultdict(set)
        file_list = list(files)
        
        connected_pairs_details = []
        
        for i, file_a in enumerate(file_list):
            for file_b in file_list[i+1:]:
                connected = False
                reasons = []
                
                info_a = module_info[file_a]
                info_b = module_info[file_b]
                
                # 1. Direct code dependency
                if file_b in resolved_deps[file_a] or file_a in resolved_deps[file_b]:
                    connected = True
                    reasons.append('import')
                    
                # 2. Shared dataset or model (literals)
                shared_literals = info_a['literals'] & info_b['literals']
                for lit in shared_literals:
                    if any(lit.endswith(ext) for ext in self.data_extensions):
                        connected = True
                        reasons.append(f'shared_data({lit})')
                    elif any(lit.endswith(ext) for ext in self.model_extensions):
                        connected = True
                        reasons.append(f'shared_model({lit})')
                        
                # 3. Shared ML API
                shared_apis = info_a['api_calls'] & info_b['api_calls']
                if shared_apis:
                    connected = True
                    reasons.append(f'shared_api({list(shared_apis)[0]}...)')
                    
                if connected:
                    adj[file_a].add(file_b)
                    adj[file_b].add(file_a)
                    connected_pairs_details.append({
                        'module_a': os.path.basename(file_a),
                        'module_b': os.path.basename(file_b),
                        'reasons': list(set(reasons)) # dedupe
                    })
                    
        # Calculate connected components (transitive closure)
        visited = set()
        components = []
        
        for f in files:
            if f not in visited:
                component = set()
                stack = [f]
                while stack:
                    node = stack.pop()
                    if node not in visited:
                        visited.add(node)
                        component.add(node)
                        stack.extend(adj[node] - visited)
                components.append(component)
                
        # Calculate Mc (pairs in connected components)
        mc = 0
        for comp in components:
            k = len(comp)
            if k > 1:
                mc += (k * (k - 1)) // 2
                
        total_pairs = (n * (n - 1)) // 2
        pmcr = mc / total_pairs if total_pairs > 0 else 0
        
        return {
            'pmcr': round(pmcr, 3),
            'n_modules': n,
            'n_possible_pairs': total_pairs,
            'n_connected_pairs': mc,
            'connected_components': len(components),
            'cohesion_level': self._categorize_cohesion(pmcr),
            'direct_connections': connected_pairs_details
        }

    def _extract_imports(self, tree: ast.Module) -> List[Dict]:
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({
                        'type': 'absolute', 
                        'name': alias.name,
                        'alias': alias.asname
                    })
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                level = node.level
                names = []
                aliases = []
                for n in node.names:
                    names.append(n.name)
                    aliases.append(n.asname)
                imports.append({
                    'type': 'from', 
                    'module': module, 
                    'level': level, 
                    'names': names,
                    'aliases': aliases
                })
        return imports

    def _resolve_imports(self, imports: List[Dict], module_map: Dict[str, str], package_path: str) -> Set[str]:
        resolved = set()
        package_name = os.path.basename(package_path)
        for imp in imports:
            if imp['type'] == 'absolute':
                parts = imp['name'].split('.')
                if parts[0] in module_map:
                    resolved.add(module_map[parts[0]])
                elif len(parts) > 1 and parts[-1] in module_map:
                    resolved.add(module_map[parts[-1]])
            elif imp['type'] == 'from':
                level = imp['level']
                module = imp['module']
                names = imp['names']
                if level > 0:
                    if module and module in module_map:
                        resolved.add(module_map[module])
                    else:
                        for name in names:
                            if name in module_map:
                                resolved.add(module_map[name])
                else:
                    if module:
                        parts = module.split('.')
                        if parts[-1] in module_map:
                            resolved.add(module_map[parts[-1]])
                        elif parts[-1] == package_name:
                            for name in names:
                                if name in module_map:
                                    resolved.add(module_map[name])
        return resolved

    def _extract_literals(self, tree: ast.Module) -> Set[str]:
        literals = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                literals.add(node.value)
        return literals

    def _extract_api_calls(self, tree: ast.Module, alias_map: Dict[str, str]) -> Set[str]:
        calls = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = self._get_func_name(node.func)
                if func_name:
                    root = func_name.split('.')[0]
                    # Resolve alias if present
                    resolved_root = alias_map.get(root, root)
                    
                    # Check if the root library is in our ML list
                    lib_name = resolved_root.split('.')[0]
                    if lib_name in self.ml_libraries:
                        # Reconstruct full name with resolved root
                        parts = func_name.split('.')
                        parts[0] = resolved_root
                        full_name = '.'.join(parts)
                        calls.add(full_name)
        return calls

    def _get_func_name(self, node) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            value = self._get_func_name(node.value)
            return f"{value}.{node.attr}" if value else node.attr
        return ""

    def _categorize_cohesion(self, score: float) -> str:
        if score >= 0.8: return 'excellent'
        if score >= 0.6: return 'good'
        if score >= 0.4: return 'moderate'
        if score >= 0.2: return 'low'
        return 'very_low'

    def _generate_messages(self, results: Dict) -> List[Dict[str, Any]]:
        messages = []
        for pkg_name, data in results['packages'].items():
            score = data['pmcr']
            if score is not None and score < 0.4:
                messages.append({
                    'file': pkg_name,
                    'diagnosis': f"Low package cohesion (PMCR: {score:.2f}). Modules are isolated.",
                    'recommendation': "Consider consolidating related modules or improving interactions via shared resources.",
                    'severity': 'medium',
                    'rule_id': 'pmcr_cohesion'
                })
        return messages
