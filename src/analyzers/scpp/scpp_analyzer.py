
import ast
import os

from typing import Dict, List, Set, Tuple, Any, Optional
from collections import defaultdict

from core.analysis_context import AnalysisContext
from core.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer
from analyzers.common.package_utils import get_package_nodes, is_package
from analyzers.common.variable_detection import is_likely_global_variable, get_files_accessed
from analyzers.common.ast_utils import get_attribute_path
from analyzers.common.lcom_analysis import identify_disconnected_methods

from analyzers.scpp.scpp_evaluator import SCPPEvaluator



class SCPPAnalyzer(BaseAnalyzer):
    """
    Analyzer for SCPP (Structural Coupling Package Pipeline) metric.

    Measures how much modules and/or subpackages within a package correspond 
    from the point of view of sharing pipeline data and models.

    Q_ij = 1 if modules/subpackages i and j share, directly or indirectly, at least one:
    - Model (e.g., .pkl, .h5)
    - Common Configuration (e.g., global constants, config files)
    - Dataset (e.g., .csv, .parquet)
    Otherwise Q_ij = 0.

    Formula: SCPP(P) = (2 * sum(Q_ij)) / (m * (m - 1))
    where m is the number of modules/subpackages in the package.
    """
    def __init__(self, session_id: str, local_path: str, context: Optional[AnalysisContext] = None):
        super().__init__(session_id, local_path, context)
        self.evaluator = SCPPEvaluator()

    @property
    def analyzer_id(self) -> str:
        return "scpp"

    def analyze(self) -> AnalysisResult:
        results = {
            'packages': {},
            'summary': {
                'total_packages': 0,
                'very_high': 0, 'high': 0, 'medium': 0, 'low': 0, 'very_low': 0,
                'average_scpp': 0.0
            }
        }
        
        # 1. Identify Packages using shared utility
        package_dirs = set()
        for root, dirs, files in os.walk(self.local_path):
            if is_package(root):
                package_dirs.add(root)

        scpp_scores = []
        for package_path in package_dirs:
            # Main analysis logic (ported from PipelineGraphBaseAnalyzer)
            graph_data = self._analyze_package_graph(package_path)
            
            if graph_data['valid']:
                # Formula calculation
                groups = graph_data['groups']
                indirect_shared_pairs = 0
                for group in groups:
                    k = len(group)
                    if k > 1:
                        indirect_shared_pairs += (k * (k - 1)) // 2
                
                m = graph_data['n_nodes']
                total_pairs = graph_data['n_pairs']
                scpp_value = (2 * indirect_shared_pairs) / (m * (m - 1)) if total_pairs > 0 else 0
                
                package_result = {
                    'scpp': round(scpp_value, 3),
                    **graph_data
                }
                
                rel_pkg_path = os.path.relpath(package_path, self.local_path)
                results['packages'][rel_pkg_path] = package_result 
                scpp_scores.append(scpp_value)
                
                # Stats update
                if scpp_value >= 0.8: results['summary']['very_high'] += 1
                elif scpp_value >= 0.6: results['summary']['high'] += 1
                elif scpp_value >= 0.4: results['summary']['medium'] += 1
                elif scpp_value >= 0.2: results['summary']['low'] += 1
                else: results['summary']['very_low'] += 1

        results['summary']['total_packages'] = len(scpp_scores)
        if scpp_scores:
            results['summary']['average_scpp'] = sum(scpp_scores) / len(scpp_scores)
            final_score = results['summary']['average_scpp'] * 10
        else:
            final_score = 0.0

        messages = self._generate_messages(results)
        
        return self._create_result(
            score=round(final_score, 2),
            messages=messages,
            module_count=len(scpp_scores),
            details=results
        )

    def _generate_messages(self, results: Dict) -> List[Dict[str, Any]]:
        messages = []
        for pkg_path, data in results['packages'].items():
            msg = self.evaluator.evaluate_package(pkg_path, data)
            if msg:
                messages.append(msg)
        return messages

    # --- Graph Analysis Logic (Previously inherited) ---

    def _analyze_package_graph(self, package_path: str) -> Dict[str, Any]:
        """Builds resources graph for the package."""
        nodes = get_package_nodes(package_path)
        m = len(nodes)
        
        if m < 2:
            return {'valid': False, 'n_nodes': m, 'nodes': [os.path.basename(n) for n in nodes]}

        # Resource Extraction
        node_resources = {}
        for node_path in nodes:
            if os.path.isdir(node_path):
                resources = self._get_subpackage_resources(node_path)
            else:
                resources = self._extract_file_resources(node_path)
            node_resources[node_path] = resources

        # Connectivity Matrix construction
        connections = []
        connected_nodes = set()
        node_list = list(nodes)
        
        for i in range(len(node_list)):
            for j in range(i + 1, len(node_list)):
                node_a = node_list[i]
                node_b = node_list[j]
                res_a = node_resources[node_a]
                res_b = node_resources[node_b]
                
                intersection = res_a.intersection(res_b)
                if intersection:
                    connections.append({
                        'node_a': os.path.basename(node_a),
                        'node_b': os.path.basename(node_b),
                        'shared_resources': list(intersection)[:5]
                    })
                    connected_nodes.add(node_a)
                    connected_nodes.add(node_b)

        # Graph Components (DFS)
        

            
        # Use common DFS
        # We need custom logic here slightly different from common LCOM because we need the actual GROUPS
        # So we adapt the DFS locally or improve common LCOM. Let's adapt locally for now to match exact SCPP requirement.
        
        # Build string-based adjacency list for compatibility with identify_disconnected_methods
        node_base_names = [os.path.basename(n) for n in nodes]
        adj = defaultdict(set)
        for conn in connections:
            adj[conn['node_a']].add(conn['node_b'])
            adj[conn['node_b']].add(conn['node_a'])

        # Calculate groups using DFS (String-based)
        visited = set()
        groups = []
        for node_name in node_base_names:
            if node_name not in visited:
                component = []
                stack = [node_name]
                visited.add(node_name)
                while stack:
                    curr = stack.pop()
                    component.append(curr)
                    for neighbor in adj[curr]:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            stack.append(neighbor)
                groups.append(component)

        # 2. Identify Isolated Nodes using common utility
        # Now correctly passes a dictionary with string keys to the utility
        isolated_nodes = identify_disconnected_methods(adj, node_base_names)
        
        return {
            'valid': True,
            'n_nodes': m,
            'connections': connections,
            'groups': groups,
            'isolated_nodes': isolated_nodes,
            'nodes': node_base_names,
            'n_pairs': (m * (m - 1)) // 2,
            'n_shared': len(connections)
        }

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

        # 1. Use shared utility to detect ML file paths
        resources.update(get_files_accessed(tree))

        # 2. AST Scanning for Global Variables AND Class Attributes
        for node in ast.walk(tree):
            # Detect Class Attributes (self.variable)
            # In package-level analysis, persistent state (self.data) counts as a shared resource within the module
            if isinstance(node, ast.Attribute):
                attr_path = get_attribute_path(node)
                if attr_path and attr_path.startswith('self.'):
                    # We store 'self.data' to match what SCPM does
                    resources.add(attr_path)

            # Detect Global Variables
            elif isinstance(node, ast.Name):
                if is_likely_global_variable(node.id): 
                    resources.add(node.id)
            
            # Check constants for potential file paths/resource names not caught above
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if is_likely_global_variable(node.value):
                        resources.add(node.value)
        
        return resources




