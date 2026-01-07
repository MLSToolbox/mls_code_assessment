import ast
import os
import json
from typing import Dict, List, Set, Tuple, Any, Optional
from collections import defaultdict
import logging
from core.analysis_context import AnalysisContext
from core.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer
from analyzers.pipeline_graph_base import PipelineGraphBaseAnalyzer
logger = logging.getLogger(__name__)
class SCPPAnalyzer(PipelineGraphBaseAnalyzer):
    """
    Analyzer for SCPP (Structural Coupling Package Pipeline) metric.
    
    Measures the structural coupling of a package based on shared pipeline resources
    (datasets, models, configurations) between its modules and subpackages.
    
    Formula:
    SCPP(P) = (2 * sum(Q_ij)) / (m * (m - 1))
    
    Where:
    - m: Number of direct nodes (files or subpackages) in the package.
    - Q_ij: 1 if node i and node j share at least one pipeline resource, 0 otherwise.
    """
    @property
    def analyzer_id(self) -> str:
        return "scpp"

    def analyze(self) -> AnalysisResult:
        """
        Analyze SCPP cohesion for all Python packages.
        """
        results = {
            'packages': {},
            'summary': {
                'total_packages': 0,
                'very_high': 0,      # 0.8-1.0
                'high': 0,      # 0.6-0.79
                'medium': 0,  # 0.4-0.59
                'low': 0,       # 0.2-0.39
                'very_low': 0,  # 0.0-0.19
                'average_scpp': 0.0
            }
        }
        package_dirs = set()
        for root, dirs, files in os.walk(self.local_path):
            if self._is_package(root):
                package_dirs.add(root)
        scpp_scores = []
        for package_path in package_dirs:
            graph_data = self._analyze_package_graph(package_path)
            # Only record if meaningful (m >= 2)
            if graph_data['valid']:
                # Calculate SCPP score based on Indirect Connections (Transitivity)
                # Formal definition: Q_ij = 1 if linked directly OR indirectly.
                # This means Q_ij = 1 for ALL pairs within the same connected component.
                groups = graph_data['groups']
                indirect_shared_pairs = 0
                for group in groups:
                    k = len(group)
                    # Pairs in a fully connected sub-graph of size k: k*(k-1)/2
                    if k > 1:
                        indirect_shared_pairs += (k * (k - 1)) // 2
                # Formula: (2 * Sum(Q_ij)) / (m * (m - 1))
                # Sum(Q_ij) is now indirect_shared_pairs
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
                if scpp_value >= 0.8: results['summary']['very_high'] += 1
                elif scpp_value >= 0.6: results['summary']['high'] += 1
                elif scpp_value >= 0.4: results['summary']['medium'] += 1
                elif scpp_value >= 0.2: results['summary']['low'] += 1
                else: results['summary']['very_low'] += 1
        results['summary']['total_packages'] = len(scpp_scores)
        if scpp_scores:
            results['summary']['average_scpp'] = sum(scpp_scores) / len(scpp_scores)
            final_score = results['summary']['average_scpp'] * 10 # Scale 0-10 for final result
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
            scpp = data.get('scpp')
            if scpp is not None:
                category = self._get_category(scpp)
                isolated_nodes = data.get('isolated_nodes', [])
                diagnosis_text = f"Category: {category}."
                if isolated_nodes:
                    node_list_str = ", ".join(isolated_nodes)
                    diagnosis_text += f" The {{{node_list_str}}} modules/subpackages do not share datasets or models or configurations with any other module/subpackage of the same package."
                else:
                    if scpp < 1.0:
                         diagnosis_text += " Some modules share resources, but full cohesion is not reached."
                    else:
                         diagnosis_text += " All modules are interconnected."
                recommendations = []
                # Rec 1: Isolated nodes
                if isolated_nodes:
                    iso_str = ", ".join(isolated_nodes)
                    rec_1 = (
                        f"If the {{{iso_str}}} modules/subpackages do not invoke (directly or indirectly) "
                        "other functions within the same package (an indication of low functional cohesion) then, "
                        "to improve package structural cohesion, consider moving these modules/subpackages to "
                        "other packages that share datasets or models or configurations."
                    )
                    recommendations.append(rec_1)
                # Rec 2: Split Groups (P-LCOM integration)
                groups = data.get('groups', [])
                # Filter groups to only include those with actual content (size > 0)
                # Note: 'groups' from graph_base typically includes all components, even isolated ones of size 1.
                # The requirement implies looking for "groups of connected modules".
                # If we have 3 isolated files, we have 3 groups. SCPP is 0.
                # Should we recommend splitting a package of 3 isolated files into 3 subpackages? The prompt implies yes ("X groups... split into X").
                if len(groups) > 1:
                    group_strs = []
                    for g in groups:
                        g_str = "{" + ", ".join(g) + "}"
                        group_strs.append(g_str)
                    
                    groups_fmt = ", ".join(group_strs)
                    rec_2 = (
                        f"Additionally, as there are {len(groups)} groups of structural connected modules/subpackages "
                        f"{{{groups_fmt}}}, if these groups are not functional connected, to improve package "
                        f"structural cohesion, the package should be split into {len(groups)} smaller subpackages."
                    )
                    recommendations.append(rec_2)

                final_recommendation = " ".join(recommendations)
                # Rule ID logic
                rule_id = 'scpp_cohesion'
                if scpp >= 0.8:
                    rule_id = 'scpp_high_cohesion'
                
                messages.append({
                    'file': pkg_path,
                    'diagnosis': diagnosis_text,
                    'recommendation': final_recommendation,
                    'severity': 'medium' if scpp < 0.6 else 'low',
                    'rule_id': rule_id
                })
        return messages

    def _get_category(self, score: float) -> str:
        if score < 0.2: return "Very low"
        if score < 0.4: return "Low"
        if score < 0.6: return "Medium"
        if score < 0.8: return "High"
        return "Very high"
