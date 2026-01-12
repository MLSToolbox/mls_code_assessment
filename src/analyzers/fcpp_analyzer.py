import ast
import os
import logging
from typing import Dict, List, Set, Any, Tuple, Optional
from collections import defaultdict

from core.analysis_result import AnalysisResult
from analyzers.pipeline_graph_base import PipelineGraphBaseAnalyzer

logger = logging.getLogger(__name__)

class FCPPAnalyzer(PipelineGraphBaseAnalyzer):
    """
    Analyzer for FCPP (Functional Cohesion of Pipeline Packages).
    
    Measures how related the modules/subpackages of a package are, 
    from the point of view of the invocations they perform (Call Graph).
    """

    @property
    def analyzer_id(self) -> str:
        return "fcpp"

    def analyze(self) -> AnalysisResult:
        """
        Analyze FCPP cohesion for all packages.
        """
        results = {
            'packages': {},
            'summary': {
                'total_packages': 0,
                'very_high': 0,
                'high': 0,
                'medium': 0,
                'low': 0,
                'very_low': 0,
                'average_fcpp': 0.0
            }
        }
        
        # 1. Identify Packages
        package_dirs = set()
        for root, dirs, files in os.walk(self.local_path):
            if self._is_package(root):
                package_dirs.add(root)
        
        fcpp_scores = []

        # 2. Build Global Symbol Table (Function Definitions)
        # We need this to resolve calls. "utils.math.calc" -> defined in "src/utils/math.py"
        # We map: Qualified_Name -> Defining_File
        # Note: Ideally this should be done per-package context or globally. 
        # For simplicity and robustness, we'll scan the whole project once or lazily.
        # However, FCPP assesses 'same package' calls. So we focus on intra-package resolution mostly,
        # but valid resolution requires knowing about subpackages.
        
        for package_path in package_dirs:
            
            graph_data = self._analyze_functional_connectivity(package_path, package_dirs)
            
            if graph_data['valid']:
                m = graph_data['n_nodes']
                connections = graph_data['connections_count'] # sum(F_ij)
                
                # Formula: (2 * Sum(F_ij)) / (m * (m - 1))
                total_pairs = m * (m - 1)
                fcpp_value = (2.0 * connections) / total_pairs if total_pairs > 0 else 0.0
                
                package_result = {
                    **graph_data,
                    'fcpp': round(fcpp_value, 3),
                    'n_groups': graph_data['n_groups'], # Functional LCOM groups
                    'groups': graph_data['groups']
                }
                
                rel_pkg_path = os.path.relpath(package_path, self.local_path)
                results['packages'][rel_pkg_path] = package_result
                fcpp_scores.append(fcpp_value)
                
                # Update Summary
                cat = self._get_category(fcpp_value)
                results['summary'][cat.lower().replace(" ", "_")] += 1
        
        # Final Summary Stats
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

    def _analyze_functional_connectivity(self, package_path: str, all_packages: Set[str]) -> Dict[str, Any]:
        """
        Builds the functional call graph for the package and computes connectivity.
        """
        # 1. Nodes (Same as SCPP)
        nodes = self._get_package_nodes(package_path) # Absolute paths
        m = len(nodes)
        
        if m < 2:
            return {'valid': False, 'n_nodes': m, 'nodes': [os.path.basename(n) for n in nodes]}

        # Map: Node_Path -> Index
        node_to_idx = {n: i for i, n in enumerate(nodes)}
        
        # 2. Build Symbol Table for THIS Package (Who defines what?)
        # Map: Symbol_Name (e.g., 'process') -> Set[Node_Index]
        # Map: Subpackage_Exports -> Node_Index (for subpackage nodes)
        # We need to handle internal imports.
        # Let's simplify: 
        # We scan each node.
        # If node is file: extract defined functions/classes.
        # If node is subpackage: treat as a black box that might define things (harder).
        # Better approach: 
        # Scan ALL files in the package recursively. Map every file to its 'Owner Node'.
        # If file inside subpackage 'utils', owner is 'utils'.
        # If file in root, owner is itself.
        
        file_to_node_idx = {}
        definitions = defaultdict(list) # FuncName -> List[Node_Index]
        
        # 2.1 Map all internal files to their Node Owner
        for idx, node_path in enumerate(nodes):
            if os.path.isfile(node_path):
                file_to_node_idx[node_path] = idx
                # Extract defs
                files_to_scan = [node_path]
            else:
                # Subpackage
                files_to_scan = []
                for root, _, files in os.walk(node_path):
                    for f in files:
                        if f.endswith('.py'):
                            files_to_scan.append(os.path.join(root, f))
                            file_to_node_idx[os.path.join(root, f)] = idx
                            
            # 2.2 Scan definitions
            for f_path in files_to_scan:
                tree = self.context.get_file_ast(f_path)
                if tree:
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                            definitions[node.name].append(idx)

        # 3. Build Adjacency Matrix (Directed) with Reasons
        # adj[source][target] = {set of symbols used}
        adj = defaultdict(lambda: defaultdict(set))
        
        # We need to parse Calls and define Edges.
        # Edge i -> j exists if code in i calls a function defined in j.
        
        for f_path, owner_idx in file_to_node_idx.items():
            tree = self.context.get_file_ast(f_path)
            if not tree: continue
            
            # Simple Name Resolution Strategy
            # 1. Direct Imports: from .utils import calc -> calc is bound to utils node.
            # 2. Call Matching: calc() -> check if 'calc' is imported or defined in same file.
            
            # Extract Imports in this file
            imported_names = {} # Name -> Node_Index (if resolvable to a sibling node)
        
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    # Try to resolve imports to sibling nodes
                    # Enhanced with symbol definition lookup
                    targets = self._resolve_import(node, f_path, package_path, nodes, node_to_idx, definitions)
                    for alias, target_idx in targets.items():
                        imported_names[alias] = target_idx
            
            # Extract Calls & Usages
            for node in ast.walk(tree):
                used_name = None
                
                # Check 1: Explicit Calls
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        used_name = node.func.id
                    elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                         # e.g. utils.calc()
                         if node.func.value.id in imported_names:
                             used_name = node.func.value.id
                
                # Check 2: Variable Usage (any reference to imported name)
                elif isinstance(node, ast.Name):
                    if isinstance(node.ctx, ast.Load):
                        used_name = node.id

                if used_name and used_name in imported_names:
                     target = imported_names[used_name]
                     if target != owner_idx:
                         # Store symbol AND specific source file for better traceability
                         detail = f"{used_name} (in {os.path.basename(f_path)})"
                         adj[owner_idx][target].add(detail)
        
        # 4. Transitive Closure (Reachability)
        # R[i][j] = 1 if path i -> ... -> j exists
        R = [[False] * m for _ in range(m)]
        
        # Init R with direct edges
        for u in range(m):
            R[u][u] = True # Self-reachable
            for v in adj[u]:
                R[u][v] = True
                
        # Floyd-Warshall
        for k in range(m):
            for i in range(m):
                for j in range(m):
                    R[i][j] = R[i][j] or (R[i][k] and R[k][j])
                    
        # 5. Calculate Connectivity F_ij
        connections_count = 0
        groups_adj = defaultdict(set) # Undirected graph for LCOM groups
        
        connections_list = []
        
        for i in range(m):
            for j in range(i + 1, m):
                connected = False
                reason_str = "Unknown"
                
                # Condition 1: Direct/Indirect Invocation
                if R[i][j]:
                    connected = True
                    # Check if direct
                    if j in adj[i]:
                        symbols = list(adj[i][j])[:10] # Limit to 10 details
                        if len(adj[i][j]) > 10:
                            symbols.append("...")
                        reason_str = f"{os.path.basename(nodes[i])} uses {'; '.join(symbols)} defined in {os.path.basename(nodes[j])}"
                    else:
                        reason_str = f"Indirect: {os.path.basename(nodes[i])} -> ... -> {os.path.basename(nodes[j])}"
                
                elif R[j][i]:
                    connected = True
                    if i in adj[j]:
                         symbols = list(adj[j][i])[:10]
                         if len(adj[j][i]) > 10:
                            symbols.append("...")
                         reason_str = f"{os.path.basename(nodes[j])} uses {'; '.join(symbols)} defined in {os.path.basename(nodes[i])}"
                    else:
                        reason_str = f"Indirect: {os.path.basename(nodes[j])} -> ... -> {os.path.basename(nodes[i])}"
                
                # Condition 2: Shared Invocation (Third Party)
                if not connected:
                    for t in range(m):
                        if t == i or t == j: continue
                        if R[i][t] and R[j][t]:
                            connected = True
                            target_name = os.path.basename(nodes[t])
                            reason_str = f"Shared dependency on {target_name}"
                            break
                            
                if connected:
                    connections_count += 1
                    groups_adj[i].add(j)
                    groups_adj[j].add(i)
                    
                    connections_list.append({
                        'node_a': os.path.basename(nodes[i]),
                        'node_b': os.path.basename(nodes[j]),
                        'reason': reason_str
                    })

        # 6. Functional Groups (components in the undirected graph formed by F_ij)
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
        
        # Identify isolated nodes (Group of size 1 where Isolate=True)
        # In FCPP logic, 'Do not invoke...'. 
        # Isolated = Nodes present in no F_ij pair.
        connected_node_indices = set(groups_adj.keys())
        isolated_nodes = []
        for i in range(m):
            if i not in connected_node_indices:
                isolated_nodes.append(node_names[i])
        
        return {
            'valid': True,
            'fcpp': 0, # Placeholder, computed in caller
            'n_nodes': m,
            'nodes': node_names,
            'connections_count': connections_count,
            'n_groups': len(groups),
            'groups': groups,
            'isolated_nodes': isolated_nodes,
            'connections': connections_list
        }

    def _resolve_import(self, node: ast.AST, current_file: str, package_root: str, 
                       nodes: List[str], node_to_idx: Dict[str, int], definitions: Dict[str, List[int]] = None) -> Dict[str, int]:
        """
        Resolves imported names to sibling Root Nodes (modules or subpackages).
        Returns: Dict[Alias_Name -> Target_Node_Index]
        """
        resolved = {}
        
        # Extract target module and names
        module = node.module if hasattr(node, 'module') else None
        names = node.names
        level = node.level if hasattr(node, 'level') else 0
        
        # Heuristic Strategy to find the target Node Index
        def match_node_by_name(target_name: str) -> Optional[int]:
            # 1. Exact path match (if target_name is abs path)
            if target_name in node_to_idx:
                return node_to_idx[target_name]

            # 2. Filename match (robust check)
            # Check if any node's basename (without extension) matches target_name
            # e.g. target="data_cleaning", node=".../src/data_cleaning.py"
            for node_path, idx in node_to_idx.items():
                node_base = os.path.basename(node_path)
                if os.path.isfile(node_path):
                    # Remove .py for comparison
                    if node_base.replace('.py', '') == target_name:
                        return idx
                else: 
                    # Directory/Subpackage
                    if node_base == target_name:
                        return idx
            return None

        for alias in names:
            target_name = alias.name
            as_name = alias.asname or alias.name
            
            # Potential candidate names for the module being imported
            candidate_modules = []
            
            # Case A: From Import (from X import Y)
            if module:
                # 1. The module itself might be the neighbor (from sibling import func)
                # We care about 'module' being the neighbor.
                parts = module.split('.')
                candidate_modules.append(parts[-1]) # Last part (e.g. data_cleaning)
                candidate_modules.append(parts[0])  # First part (e.g. src) - Catch subpackage deps
                
                # 2. If valid relative import, module might be full path
                if level > 0:
                   # Simplification: we rely on name matching of the last segment
                   pass

            # Case B: Direct Import (import X) 
            else:
                # import sibling
                candidate_modules.append(target_name.split('.')[0]) # Top level?
                candidate_modules.append(target_name.split('.')[-1]) # Leaf?

            # Case C: "from . import sibling" (module is None, level > 0)
            if not module and level > 0:
                # This imports 'target_name' from current package
                candidate_modules.append(target_name)

            # TRY RESOLVE
            # We check if any candidate matches a known Sibling Node in this package
            found_idx = None
            
            # 1. Check Module-level match (e.g. from 'data_cleaning' import clean)
            # We want to link to 'data_cleaning.py' node.
            if module:
                 # Check if 'module' (e.g. 'src.data_cleaning') ends with a known node name
                 parts = module.split('.')
                 potential_node_name = parts[-1]
                 idx = match_node_by_name(potential_node_name)
                 if idx is not None:
                     found_idx = idx
                 
                 # Check first part for relative imports (e.g. from ..config)
                 if found_idx is None and len(parts) > 0:
                     idx = match_node_by_name(parts[0])
                     if idx is not None:
                         found_idx = idx
            
            # 2. Check Name-level match (e.g. import data_cleaning)
            if found_idx is None:
                for cand in candidate_modules:
                    idx = match_node_by_name(cand)
                    if idx is not None:
                        found_idx = idx
                        break
            
            # 3. Handle "from .sibling import func"
            if found_idx is None and not module and level > 0:
                 # e.g. from . import sibling
                 idx = match_node_by_name(target_name)
                 if idx is not None:
                     found_idx = idx

            # 4. Fallback: Symbol Definition Lookup (The "Magic" Step)
            # If we imported "Object" and "Object" is defined in one of our nodes, link to it.
            if found_idx is None and definitions:
                # We check the imported name (target_name)
                # e.g. from ... import Object -> target_name="Object"
                if target_name in definitions:
                    possible_nodes = definitions[target_name]
                    # We pick the first one. If multiple define same symbol, ambiguity exists, but usually OK.
                    if possible_nodes:
                        found_idx = possible_nodes[0]
            
            if found_idx is not None:
                # Prevent self-reference
                if node_to_idx.get(current_file) != found_idx:
                    resolved[as_name] = found_idx

        return resolved

    def _get_category(self, score: float) -> str:
        if score < 0.2: return "Very low"
        if score < 0.4: return "Low"
        if score < 0.6: return "Medium"
        if score < 0.8: return "High"
        return "Very high"

    def _generate_messages(self, results: Dict) -> List[Dict[str, Any]]:
        messages = []
        for pkg_path, data in results['packages'].items():
            fcpp = data.get('fcpp', 0)
            category = self._get_category(fcpp)
            
            isolated = data.get('isolated_nodes', [])
            
            diagnosis = f"Category: {category}."
            if isolated:
                diagnosis += f" The {{{', '.join(isolated)}}} modules/subpackages do not invoke (directly or indirectly) functions of other modules/subpackages of the same package."
                
            msg = {
                'file': pkg_path,
                'diagnosis': diagnosis,
                'recommendation': "", # To be filled
                'severity': 'medium' if fcpp < 0.6 else 'low',
                'rule_id': 'fcpp_functional_cohesion'
            }
            
            recs = []
            
            # Recommendation 1: Move Isolated
            if isolated:
                rec1 = (f"If the {{{', '.join(isolated)}}} modules/subpackages do not share datasets or models "
                        "or configurations with any other module/subpackage of the same package then, "
                        "to improve package functional cohesion, consider moving these modules/subpackages to "
                        "a package more functional related to them.")
                recs.append(rec1)
            
            # Recommendation 2: Split Groups
            groups = data.get('groups', [])
            if len(groups) > 1:
                group_strs = ["{" + ", ".join(g) + "}" for g in groups]
                groups_fmt = ", ".join(group_strs)
                
                rec2 = (f"Additionally, as there are {len(groups)} groups of functional connected modules/subpackages "
                        f"{{{groups_fmt}}}, if these groups are not structural connected, to improve package "
                        f"functional cohesion, the package should be split into {len(groups)} smaller subpackages.")
                recs.append(rec2)
                
            msg['recommendation'] = " ".join(recs)
            messages.append(msg)
            
        return messages
