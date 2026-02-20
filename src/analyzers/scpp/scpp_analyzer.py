import ast
import os
from typing import Dict, List, Set, Tuple, Any, Optional
from collections import defaultdict
from core.analysis_context import AnalysisContext
from core.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer
from analyzers.common.package_utils import find_connected_groups
from analyzers.common.variable_detection import is_likely_global_variable, get_files_accessed
from analyzers.common.ast_utils import get_attribute_path
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
        tree_metadata=self.context.get_tree_metadata()
        results = {
            'packages': {},
            'summary': {
                'total_packages': 0,
                'very_high': 0, 'high': 0, 'medium': 0, 'low': 0, 'very_low': 0,
                'average_scpp': 0.0
            }
        }
        self._get_packages_scpp_metrics(tree_metadata,results=results)
        if results["packages"]:
            results['summary']['average_scpp'] =round( sum(results["packages"][package_path]["scpp"] if results["packages"][package_path]["valid"] else 0 for package_path in results["packages"]) / len(results["packages"]),3)
            final_score = round(results['summary']['average_scpp'] * 10,3)
            results["packages"]=dict(reversed(list(results["packages"].items())))
        else:
            final_score = 0.0
        messages=self._generate_messages(results)
        return self._create_result(
            score=final_score,
            messages=messages,
            module_count=len(results["packages"]),
            details=results,
            group_key='by_package'
        )
        
    def _get_packages_scpp_metrics(self,node,current_path="",results=None):
        """
        Recursively traverses the AST to find packages and compute SCPP metrics.
        
        Args:
            node: Current node in the AST
            current_path: Path to the current node
            results: Dictionary to store the results
        
        Returns:
            List of package file paths
        """
        if node["type"]=="file"  and node["name"].endswith(".py") and node["name"]!="__init__.py":
            return node["path"].replace("/","",1)
        packages_file_path=[]  
        if "children" in node:
            for child in node["children"]:
                module=self._get_packages_scpp_metrics(child,node["path"],results)
                if isinstance(module,list):
                    packages_file_path.extend(module)
                else:
                    packages_file_path.append(module)
        if node["path"] !="/" and node["type"]=="directory":
              graph_data = self._analyze_package_graph(packages_file_path)
              if graph_data['valid']:
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
                results['packages'][node["path"].replace("/","",1)] = package_result 
                if scpp_value >= 0.8:
                    results['summary']['very_high'] += 1
                    results["packages"][node["path"].replace("/","",1)]["cohesion_level"] = "very_high"
                elif scpp_value >= 0.6: 
                    results['summary']['high'] += 1
                    results["packages"][node["path"].replace("/","",1)]["cohesion_level"] = "high"
                elif scpp_value >= 0.4: 
                    results['summary']['medium'] += 1
                    results["packages"][node["path"].replace("/","",1)]["cohesion_level"] = "medium"
                elif scpp_value >= 0.2: 
                    results['summary']['low'] += 1
                    results["packages"][node["path"].replace("/","",1)]["cohesion_level"] = "low"
                else: 
                    results['summary']['very_low'] += 1
                    results["packages"][node["path"].replace("/","",1)]["cohesion_level"] = "very_low"
                results['summary']['total_packages'] += 1
              else:
                package_result={
                    **graph_data,
                    "scpp":None,
                    "cohesion_level":"not_applicable"

                }
                results['packages'][node["path"].replace("/","",1)] = package_result 
                results['summary']['total_packages'] += 1
        return packages_file_path
    def _generate_messages(self, results: Dict) -> List[Dict[str, Any]]:
        messages = []
        for pkg_path, data in results['packages'].items():

            msg = self.evaluator.evaluate_package(pkg_path, data)
            if msg:
                messages.append(msg)
        return messages
    def _analyze_package_graph(self, nodes: List[str]) -> Dict[str, Any]:
        """Builds resources graph for the package."""
        m = len(nodes)
        if m < 2:
            return {'valid': False, 'n_nodes': m,"connections":[],"groups":[],"isolated_nodes":[],"nodes": nodes,"n_pairs":0,"n_shared":0}
        node_resources = {}
        for node_path in nodes:
            resources = self._extract_file_resources(node_path)
            node_resources[node_path] = resources
        connections = []
        connected_nodes = set()
        node_list = list(nodes)
        # Build Adjacency Matrix using Indices for standardization with package_utils
        adj_indices = defaultdict(set)
        for i in range(len(node_list)):
             node_a_res = node_resources[node_list[i]]
             for j in range(i + 1, len(node_list)):
                  node_b_res = node_resources[node_list[j]]
                  intersection = node_a_res.intersection(node_b_res)
                  
                  if intersection:
                        connections.append({
                            'node_a': node_list[i],
                            'node_b': node_list[j],
                            'shared_resources': list(intersection)[:5]
                        })
                        adj_indices[i].add(j)
                        adj_indices[j].add(i)

        # Find Groups and Isolated Nodes logic decoupled to package_utils
        groups, isolated_nodes = find_connected_groups(node_list, adj_indices)
        return {
            'valid': True,
            'n_nodes': m,
            'connections': connections,
            'groups': groups,
            'isolated_nodes': isolated_nodes,
            'nodes': nodes,
            'n_pairs': (m * (m - 1)) // 2,
            'n_shared': len(connections)
        }
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




