import ast
import os
import logging
from typing import Dict, List, Set, Any, Tuple, Optional
from collections import defaultdict

from core.analysis_context import AnalysisContext
from core.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer
from analyzers.common.package_utils import find_connected_groups
from analyzers.fcpp.fcpp_evaluator import FCPPEvaluator

class FCPPAnalyzer(BaseAnalyzer):
    """
    Analyzer for FCPP (Functional Cohesion of Pipeline Packages).
    
    Measures how much modules/subpackages within a package are related from the viewpoint of functional invocations.
    
    Let P be a package with m modules/subpackages.
    F_ij = 1 if there exists a function in mi that invokes (directly or indirectly) a function in mj:
    - Direct: mi -> mj OR mj -> mi
    - Indirect: mi -> ... -> mj (intermediate nodes must be in P)
    - Shared Target: mi -> mt AND mj -> mt (where mt is in P)
    
    Otherwise F_ij = 0.
    
    Formula: FCPP(P) = (2 * Sum_{i<j} F_ij) / (m * (m - 1))
    """

    def __init__(self, session_id: str, local_path: str, context: Optional[AnalysisContext] = None):
        super().__init__(session_id, local_path, context)
        self.evaluator = FCPPEvaluator()

    @property
    def analyzer_id(self) -> str:
        return "fcpp"

    def analyze(self) -> AnalysisResult:
        packages=self.context.get_packages_and_files()
        if not packages:
            return self._create_result(
                score=0.0,
                messages=[],
                module_count=0,
                details={},
                group_key="by_package",
            )
        results = {
            'packages': {},
            'summary': {
                'total_packages': 0,
                'very_high': 0, 'high': 0, 'medium': 0, 'low': 0, 'very_low': 0,
                'average_fcpp': 0.0
            }
        }
        for package in packages :
            graph_data=self._analyze_functional_connectivity(package["path"],package["modules"])
            if graph_data["valid"]:
                m=graph_data["n_nodes"]
                connections = graph_data['connections_count'] 
                total_pairs = m * (m - 1)
                fcpp_value = (2.0 * connections) / total_pairs if total_pairs > 0 else 0.0
                results["packages"][package["path"]]={
                    **graph_data,
                    'fcpp': round(fcpp_value, 3),
                }
                if fcpp_value >= 0.8: 
                    results["packages"][package["path"]]["cohesion_level"] = "very_high"
                    results['summary']['very_high'] += 1 
                elif fcpp_value >= 0.6: 
                    results["packages"][package["path"]]["cohesion_level"] = "high"
                    results['summary']['high'] += 1
                elif fcpp_value >= 0.4: 
                    results["packages"][package["path"]]["cohesion_level"] = "medium"
                    results['summary']['medium'] += 1
                elif fcpp_value >= 0.2: 
                    results["packages"][package["path"]]["cohesion_level"] = "low"
                    results['summary']['low'] += 1
                else: 
                    results["packages"][package["path"]]["cohesion_level"] = "very_low"
                    results['summary']['very_low'] += 1
                results["summary"]["total_packages"]+=1
            else:
                results["packages"][package["path"]]={
                    **graph_data,
                    "fcpp":None,
                    "cohesion_level":"not_applicable",
                }
                results["summary"]["total_packages"]+=1
        if results["packages"]:
            results['summary']['average_fcpp'] = round(sum([results["packages"][package_path]["fcpp"] if results["packages"][package_path]["valid"] else 0  for package_path in results["packages"]]) / len(results["packages"]),3)
            results["packages"]=dict(reversed(list(results["packages"].items())))
            final_score =round( results['summary']['average_fcpp'] * 10,3)
        else :
            final_score = 0.0
        messages=self._generate_messages(results)
        return self._create_result(
            score=final_score,
            messages=messages,
            module_count= len(results["packages"]),
            details=results,
            
            group_key='by_package'
        )
    def _analyze_functional_connectivity(self, package_path: str,nodes:List[str]) -> Dict[str, Any]:
        """
        Builds the functional call graph for the package and computes connectivity.
        """
        m = len(nodes)
        if m < 2:
            return {'valid': False, 'n_nodes': m, 'nodes': nodes,'connections_count':0,'n_groups':0,'groups':[],"isolated_nodes":[],"connections":[]}

        node_to_idx = {n: i for i, n in enumerate(nodes)}
        module_to_idx = {}
        for i, n in enumerate(nodes):
            name = os.path.basename(n)
            if name == "__init__.py":
                name = os.path.basename(os.path.dirname(n))
            else:
                name = os.path.splitext(name)[0]
            module_to_idx[name] = i
        file_to_node_idx = {}
        definitions = defaultdict(list)
        for idx, node_path in enumerate(nodes):
            file_to_node_idx[node_path] = idx
            features = self.context.get_file_features(node_path)
            if features:
                for def_name in features.definitions:
                    definitions[def_name].append(idx)

        adj = defaultdict(lambda: defaultdict(set))
        for f_path, owner_idx in file_to_node_idx.items():
            features = self.context.get_file_features(f_path)
            if not features: continue
            
            imported_names = {}
            # 1. Process Imports
            for node in features.imports:
                targets = self._resolve_import(node, f_path, package_path, nodes, node_to_idx, definitions, module_to_idx)
                for alias, target_idx in targets.items():
                    imported_names[alias] = target_idx
            
            # 2. Process Calls and Name usage
            potential_uses = features.calls + features.name_nodes
            for node in potential_uses:
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
                        detail = f"{used_name} (in {f_path})"
                        adj[owner_idx][target].add(detail)
        R = [[False] * m for _ in range(m)]
        for u in range(m):
            R[u][u] = True
            for v in adj[u]:
                R[u][v] = True
                
        for k in range(m):
            for i in range(m):
                for j in range(m):
                    R[i][j] = R[i][j] or (R[i][k] and R[k][j])
                    
        connections_count = 0
        groups_adj = defaultdict(set)
        connections_list = []
        
        for i in range(m):
            for j in range(i + 1, m):
                connected = False
                found_types = []
                found_reasons = []
                if R[i][j]:
                    connected = True
                    if j in adj[i]:
                        conn_type = "Direct"
                        raw_details = list(adj[i][j])
                        unique_symbols = sorted(list(set(d.split(' (')[0] for d in raw_details)))
                        symbols_str = ', '.join(unique_symbols[:3])
                        remaining = len(unique_symbols) - 3
                        if remaining > 0: symbols_str += f"... (+{remaining} more)"
                        reason_str = f"Uses: {symbols_str}"
                    else:
                        conn_type = "Indirect"
                        reason_str = "Indirect chain"
                    found_types.append(conn_type)
                    found_reasons.append(reason_str)
                if R[j][i]:
                    connected = True
                    if i in adj[j]:
                        conn_type = "Direct (Reverse)" if "Direct" in found_types else "Direct"
                        raw_details = list(adj[j][i])
                        unique_symbols = sorted(list(set(d.split(' (')[0] for d in raw_details)))
                        symbols_str = ', '.join(unique_symbols[:3])
                        remaining = len(unique_symbols) - 3
                        if remaining > 0: symbols_str += f"... (+{remaining} more)"
                        reason_str = f"Is Used By: {symbols_str}"
                    else:
                        conn_type = "Indirect"
                        reason_str = "Indirect chain (Reverse)"
                    if "Indirect" not in found_types or conn_type == "Direct": 
                         if conn_type not in found_types: found_types.append(conn_type)
                    found_reasons.append(reason_str)
                for t in range(m):
                    if t == i or t == j: continue
                    if R[i][t] and R[j][t]:
                        connected = True
                        if "Shared Dependency" not in found_types:
                             found_types.append("Shared Dependency")
                             found_reasons.append(f"Both use: {nodes[t]}")
                        break
                if connected:
                    connections_count += 1
                    groups_adj[i].add(j)
                    groups_adj[j].add(i)
                    
                    final_type = " + ".join(sorted(list(set(found_types))))
                    final_reason = "; ".join(found_reasons)
                        
                    connections_list.append({
                        'node_a': nodes[i],
                        'node_b':nodes[j],
                        'type': final_type,
                        'reason': final_reason
                    })
        groups, isolated = find_connected_groups(nodes, groups_adj)
        return {
            'valid': True,
            'n_nodes': m,
            'nodes': nodes,
            'connections_count': connections_count,
            'n_groups': len(groups),
            'groups': groups,
            'isolated_nodes': isolated,
            'connections': connections_list
        }    
    def _generate_messages(self, results: Dict) -> List[Dict[str, Any]]:
        messages = []
        for pkg_path, data in results['packages'].items():
            if data["valid"] == False:
                continue
            msg = self.evaluator.evaluate_package(pkg_path, data)
            if msg:
                messages.append(msg)
        return messages
    def _resolve_import(self, node: ast.AST, current_file: str, package_root: str, 
                       nodes: List[str], node_to_idx: Dict[str, int], 
                       definitions: Dict[str, List[int]], module_to_idx: Dict[str, int]) -> Dict[str, int]:
        """
        Resolves imported names to sibling Root Nodes using heuristic matching and definition lookup.
        """
        resolved = {}
        module = node.module if hasattr(node, 'module') else None
        names = node.names
        
        for alias in names:
            target = alias.name
            as_name = alias.asname or alias.name
            found_idx = None
            if module:
                parts = module.split('.')
                found_idx = module_to_idx.get(parts[-1])
                if found_idx is None and len(parts) > 0:
                    found_idx = module_to_idx.get(parts[0])
            if found_idx is None:
                found_idx = module_to_idx.get(target)
                if found_idx is None:
                    found_idx = module_to_idx.get(target.split('.')[0])
            if found_idx is None:
                if target in definitions:
                    candidates = definitions[target]
                    if candidates:
                        found_idx = candidates[0]
            if found_idx is not None and node_to_idx.get(current_file) != found_idx:
                resolved[as_name] = found_idx
        return resolved
