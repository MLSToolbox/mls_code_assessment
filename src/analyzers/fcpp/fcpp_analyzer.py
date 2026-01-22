
import ast
import os
import logging
from typing import Dict, List, Set, Any, Tuple, Optional
from collections import defaultdict

from core.analysis_context import AnalysisContext
from core.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer
from analyzers.common.package_utils import get_package_nodes, is_package
from analyzers.fcpp.fcpp_evaluator import FCPPEvaluator

logger = logging.getLogger(__name__)

class FCPPAnalyzer(BaseAnalyzer):
    """
    Analyzer for FCPP (Functional Cohesion of Pipeline Packages).
    """

    def __init__(self, session_id: str, local_path: str, context: Optional[AnalysisContext] = None):
        super().__init__(session_id, local_path, context)
        self.evaluator = FCPPEvaluator()

    @property
    def analyzer_id(self) -> str:
        return "fcpp"

    def analyze(self) -> AnalysisResult:
        results = {
            'packages': {},
            'summary': {
                'total_packages': 0,
                'very_high': 0, 'high': 0, 'medium': 0, 'low': 0, 'very_low': 0,
                'average_fcpp': 0.0
            }
        }
        
        # 1. Identify Packages
        package_dirs = set()
        for root, dirs, files in os.walk(self.local_path):
            if is_package(root):
                package_dirs.add(root)
        
        fcpp_scores = []
        possible_sibling_nodes = set()
        # Pre-scan for possible cross-package resolution could be done here if needed
        
        for package_path in package_dirs:
            graph_data = self._analyze_functional_connectivity(package_path)
            
            if graph_data['valid']:
                m = graph_data['n_nodes']
                connections = graph_data['connections_count'] # sum(F_ij)
                
                # Formula: (2 * Sum(F_ij)) / (m * (m - 1))
                total_pairs = m * (m - 1)
                fcpp_value = (2.0 * connections) / total_pairs if total_pairs > 0 else 0.0
                
                package_result = {
                    **graph_data,
                    'fcpp': round(fcpp_value, 3),
                    'n_groups': graph_data['n_groups'],
                    'groups': graph_data['groups']
                }
                
                rel_pkg_path = os.path.relpath(package_path, self.local_path)
                results['packages'][rel_pkg_path] = package_result
                fcpp_scores.append(fcpp_value)
                
                # Update Summary
                if fcpp_value >= 0.8: results['summary']['very_high'] += 1
                elif fcpp_value >= 0.6: results['summary']['high'] += 1
                elif fcpp_value >= 0.4: results['summary']['medium'] += 1
                elif fcpp_value >= 0.2: results['summary']['low'] += 1
                else: results['summary']['very_low'] += 1
        
        results['summary']['total_packages'] = len(fcpp_scores)
        if fcpp_scores:
            results['summary']['average_fcpp'] = sum(fcpp_scores) / len(fcpp_scores)
            final_score = results['summary']['average_fcpp'] * 10
        else:
            final_score = 0.0
            
        messages = self._generate_messages(results)
        
        return self._create_result(
            score=round(final_score, 2),
            messages=messages,
            module_count=len(fcpp_scores),
            details=results
        )

    def _generate_messages(self, results: Dict) -> List[Dict[str, Any]]:
        messages = []
        for pkg_path, data in results['packages'].items():
            msg = self.evaluator.evaluate_package(pkg_path, data)
            if msg:
                messages.append(msg)
        return messages

    def _analyze_functional_connectivity(self, package_path: str) -> Dict[str, Any]:
        """
        Builds the functional call graph for the package and computes connectivity.
        """
        nodes = get_package_nodes(package_path)
        m = len(nodes)
        
        if m < 2:
            return {'valid': False, 'n_nodes': m, 'nodes': [os.path.basename(n) for n in nodes]}

        node_to_idx = {n: i for i, n in enumerate(nodes)}
        
        # Build Symbol Table (File -> Node Index mapping + Definitions)
        file_to_node_idx = {}
        definitions = defaultdict(list) # FuncName -> List[Node_Index]
        
        # Map internal files to Node Owner & Scan Definitions
        for idx, node_path in enumerate(nodes):
            if os.path.isfile(node_path):
                file_to_node_idx[node_path] = idx
                files_to_scan = [node_path]
            else:
                files_to_scan = []
                for root, _, files in os.walk(node_path):
                    for f in files:
                        if f.endswith('.py'):
                            full_p = os.path.join(root, f)
                            files_to_scan.append(full_p)
                            file_to_node_idx[full_p] = idx
                            
            for f_path in files_to_scan:
                tree = self.context.get_file_ast(f_path)
                if tree:
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                            definitions[node.name].append(idx)

        # Build Adjacency Matrix (Directed)
        adj = defaultdict(lambda: defaultdict(set))
        
        for f_path, owner_idx in file_to_node_idx.items():
            tree = self.context.get_file_ast(f_path)
            if not tree: continue
            
            imported_names = {}
            # Pass definitions to resolve imports more accurately
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    targets = self._resolve_import(node, f_path, package_path, nodes, node_to_idx, definitions)
                    for alias, target_idx in targets.items():
                        imported_names[alias] = target_idx
            
            for node in ast.walk(tree):
                used_name = None
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        used_name = node.func.id
                    elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                         if node.func.value.id in imported_names:
                             used_name = node.func.value.id
                elif isinstance(node, ast.Name):
                    if isinstance(node.ctx, ast.Load):
                        used_name = node.id

                if used_name and used_name in imported_names:
                     target = imported_names[used_name]
                     if target != owner_idx:
                         detail = f"{used_name} (in {os.path.basename(f_path)})"
                         adj[owner_idx][target].add(detail)
        
        # Transitive Closure (Floyd-Warshall)
        R = [[False] * m for _ in range(m)]
        for u in range(m):
            R[u][u] = True
            for v in adj[u]:
                R[u][v] = True
                
        for k in range(m):
            for i in range(m):
                for j in range(m):
                    R[i][j] = R[i][j] or (R[i][k] and R[k][j])
                    
        # Calculate Connectivity F_ij & Groups
        connections_count = 0
        groups_adj = defaultdict(set)
        connections_list = []
        
        for i in range(m):
            for j in range(i + 1, m):
                connected = False
                reason = "Unknown"
                
                # Direct/Indirect
                if R[i][j]:
                    connected = True
                    if j in adj[i]:
                        symbols = list(adj[i][j])[:3]
                        reason = f"Uses {', '.join(symbols)}..."
                    else:
                        reason = "Indirect call chain"
                elif R[j][i]:
                    connected = True
                    if i in adj[j]:
                        symbols = list(adj[j][i])[:3]
                        reason = f"Uses {', '.join(symbols)}..."
                    else:
                        reason = "Indirect call chain"
                
                # Shared Dependency
                if not connected:
                    for t in range(m):
                        if t == i or t == j: continue
                        if R[i][t] and R[j][t]:
                            connected = True
                            reason = f"Both use {os.path.basename(nodes[t])}"
                            break
                            
                if connected:
                    connections_count += 1
                    groups_adj[i].add(j)
                    groups_adj[j].add(i)
                    connections_list.append({
                        'node_a': os.path.basename(nodes[i]),
                        'node_b': os.path.basename(nodes[j]),
                        'reason': reason
                    })

        # Find Groups (DFS)
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
                    for neighbor in groups_adj[curr]:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            stack.append(neighbor)
                groups.append(component)
        
        # Isolated Nodes
        connected_indices = set(groups_adj.keys())
        isolated = [node_names[i] for i in range(m) if i not in connected_indices]
        
        return {
            'valid': True,
            'n_nodes': m,
            'nodes': node_names,
            'connections_count': connections_count,
            'n_groups': len(groups),
            'groups': groups,
            'isolated_nodes': isolated,
            'connections': connections_list
        }

    def _resolve_import(self, node: ast.AST, current_file: str, package_root: str, 
                       nodes: List[str], node_to_idx: Dict[str, int], definitions: Dict[str, List[int]]) -> Dict[str, int]:
        """
        Resolves imported names to sibling Root Nodes using heuristic matching and definition lookup.
        """
        resolved = {}
        module = node.module if hasattr(node, 'module') else None
        names = node.names
        level = node.level if hasattr(node, 'level') else 0
        
        def match_node(name: str) -> Optional[int]:
            for path, idx in node_to_idx.items():
                base = os.path.basename(path)
                if os.path.isfile(path):
                    if base.replace('.py', '') == name: return idx
                else:
                    if base == name: return idx
            return None

        for alias in names:
            target = alias.name
            as_name = alias.asname or alias.name
            found_idx = None
            
            # Module-based resolution
            if module:
                parts = module.split('.')
                # Last part is usually the file/module name
                found_idx = match_node(parts[-1])
                if found_idx is None and len(parts) > 0:
                    found_idx = match_node(parts[0])
            
            # Direct name resolution
            if found_idx is None:
                found_idx = match_node(target)
                if found_idx is None:
                    # Try splitting (import sibling.func)
                    found_idx = match_node(target.split('.')[0])
            
            # Definition lookup (The "Magic" Step)
            if found_idx is None:
                if target in definitions:
                    candidates = definitions[target]
                    if candidates:
                        found_idx = candidates[0]
            
            if found_idx is not None and node_to_idx.get(current_file) != found_idx:
                resolved[as_name] = found_idx
                
        return resolved
