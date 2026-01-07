from typing import Dict, Any, List, Optional
import os
from core.analysis_result import AnalysisResult
from analyzers.pipeline_graph_base import PipelineGraphBaseAnalyzer

class PLCOMAnalyzer(PipelineGraphBaseAnalyzer):
    """
    Analyzer for P-LCOM (Package Lack of Cohesion of Modules) metric.
    
    Measures the lack of cohesion in a package by counting the number of 
    connected components (groups) of modules/subpackages that share pipeline resources.
    
    Formula:
    P-LCOM(P) = Number of Connected Components
    
    Interpretation:
    - 1: High Cohesion (All modules are connected)
    - >1: Low Cohesion (Fragmented groups)
    """
    @property
    def analyzer_id(self) -> str:
        return "p-lcom"
    def analyze(self) -> AnalysisResult:
        results = {
            'packages': {},
            'summary': {
                'total_packages': 0,
                'high_cohesion': 0,    
                'low_cohesion': 0,      
                'average_components': 0.0
            }
        }
        package_dirs = set()
        for root, dirs, files in os.walk(self.local_path):
            # Use improved package detection (recursively checks for .py files)
            # This aligns P-LCOM with SCPP to ensure they analyze the same set of packages.
            if self._is_package(root):
                package_dirs.add(root)
        component_counts = []
        for package_path in package_dirs:
            graph_data = self._analyze_package_graph(package_path)
            if graph_data['valid']:
                groups = graph_data['groups']
                n_components = len(groups)
                # If there are isolated nodes, they are treated as components of size 1 (groups list covers this)
                # Ensure _analyze_package_graph returns ALL components including isolated singular ones?
                # looking at previous logic: 
                # "groups" was constructed from "visited". If a node is isolated, it's a component of 1.
                # Yes, the loop `for i in range(m)` covers all nodes.
                package_result = {
                    'p-lcom': n_components,
                    'n_groups': n_components,
                    'groups': groups,
                    **graph_data
                }
                rel_pkg_path = os.path.relpath(package_path, self.local_path)
                results['packages'][rel_pkg_path] = package_result
                component_counts.append(n_components)
                if n_components == 1:
                    results['summary']['high_cohesion'] += 1
                else:
                    results['summary']['low_cohesion'] += 1
        results['summary']['total_packages'] = len(component_counts)
        if component_counts:
            results['summary']['average_components'] = sum(component_counts) / len(component_counts)
            # Score: Inverted. 1 is best. Higher is worse.
            # Normalize to 0-10? 
            # If avg=1 -> 10. If avg=5 -> 2.
            avg = results['summary']['average_components']
            final_score = (1.0 / avg) * 10 if avg > 0 else 0
        else:
            final_score = 0.0
        messages = self._generate_messages(results)
        return self._create_result(
            score=round(final_score, 2),
            messages=messages,
            module_count=len(component_counts),
            details=results
        )
    def _generate_messages(self, results: Dict) -> List[Dict[str, Any]]:
        messages = []
        for pkg_path, data in results['packages'].items():
            plcom = data.get('p-lcom')
            if plcom is not None and plcom > 1:
                groups = data.get('groups', [])
                diagnosis = f"Package Fragmented (P-LCOM={plcom}). Found {plcom} disconnected groups of modules."
                group_strs = []
                for g in groups:
                    group_strs.append("{" + ",".join(g) + "}")
                groups_fmt = ", ".join(group_strs)
                recommendation = (f"The package consists of distinct groups: {groups_fmt}. "
                                  "Consider splitting these into separate subpackages to improve cohesion.")
                messages.append({
                    'file': pkg_path,
                    'diagnosis': diagnosis,
                    'recommendation': recommendation,
                    'severity': 'medium',
                    'rule_id': 'plcom_fragmentation'
                })
        return messages
