import ast
import os
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from analyzers.base_analyzer import BaseAnalyzer
from analyzers.common.ast_utils import get_attribute_path
from analyzers.common.package_utils import find_connected_groups
from analyzers.common.variable_detection import get_files_accessed, is_likely_global_variable
from analyzers.scpp.scpp_evaluator import SCPPEvaluator
from core.analysis_context import AnalysisContext
from core.analysis_result import AnalysisResult


class SCPPAnalyzer(BaseAnalyzer):
    """
    Analyzer for SCPP (Structural Coupling Package Pipeline) metric.

    Scope is limited to pipeline files resolved by AnalysisContext (file_stages != []).
    """

    def __init__(self, session_id: str, local_path: str, context: Optional[AnalysisContext] = None):
        super().__init__(session_id, local_path, context)
        self.evaluator = SCPPEvaluator()

    @property
    def analyzer_id(self) -> str:
        return "scpp"

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
            "packages": {},
            "summary": {
                "total_packages": 0,
                "very_high": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "very_low": 0,
                "average_scpp": 0.0,
                "scan_mode": self.context.get_scan_mode(),
            },
        }
        for package in packages:
            graph_data = self._analyze_package_graph(package["modules"])
            if not graph_data["valid"] :
                results["packages"][package["path"]]={
                    **graph_data,
                    "scpp":None,
                    "cohesion_level":"not_applicable"
                }
            else :
                groups = graph_data["groups"]
                indirect_shared_pairs = 0
                for group in groups:
                    k = len(group)
                    if k > 1:
                        indirect_shared_pairs += (k * (k - 1)) // 2

                m = graph_data["n_nodes"]
                total_pairs = graph_data["n_pairs"]
                scpp_value = (
                    (2 * indirect_shared_pairs) / (m * (m - 1))
                    if total_pairs > 0
                    else 0
                )
                results["packages"][package["path"]] = {
                    "scpp": round(scpp_value, 3),
                    **graph_data,
                }
                if scpp_value >= 0.8:
                    cohesion_level="very_high"
                    results["summary"]["very_high"] += 1
                elif scpp_value >= 0.6:
                    cohesion_level="high"
                    results["summary"]["high"] += 1
                elif scpp_value >= 0.4:
                    cohesion_level="medium"
                    results["summary"]["medium"] += 1
                elif scpp_value >= 0.2:
                    cohesion_level="low"
                    results["summary"]["low"] += 1
                else:
                    cohesion_level="very_low"
                    results["summary"]["very_low"] += 1
                results["packages"][package["path"]]["cohesion_level"]=cohesion_level
        results["summary"]["total_packages"] = len(packages)
        if results["summary"]["total_packages"]>0:
            results["summary"]["average_scpp"] = sum(results["packages"][package["path"]]["scpp"] for package in packages if results["packages"][package["path"]]["scpp"] is not None) / results["summary"]["total_packages"]
            final_score = results["summary"]["average_scpp"] * 10
        else:
            final_score = 0.0

        return self._create_result(
            score=round(final_score, 2),
            messages=self._generate_messages(results),
            module_count=results["summary"]["total_packages"],
            details=results,
            group_key="by_package",
        )

    def _generate_messages(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = []
        for package_path, data in results["packages"].items():
            msg = self.evaluator.evaluate_package(package_path, data)
            if msg:
                messages.append(msg)
        return messages


    def _analyze_package_graph(self, nodes:List[str]) -> Dict[str, Any]:
        node_count = len(nodes)
        if node_count < 2:
            return {
                "valid": False,
                "n_nodes": node_count,
                "connections": [],
                "groups": [],
                "isolated_nodes": [],
                "nodes": nodes,
                "n_pairs": 0,
                "n_shared": 0,
            }
        node_resources: Dict[str, Set[str]] = {}
        for node_path in nodes:
            node_resources[node_path] = self._extract_file_resources(node_path)
        
        connections=[]
        adj_indices=defaultdict(set)
        for i in range(len(nodes)):
            node_a_res=node_resources[nodes[i]]
            for j in range(i+1,len(nodes)) :
                node_b_res=node_resources[nodes[j]]
                intersection=node_a_res.intersection(node_b_res)
                if intersection :
                    connections.append({
                        "node_a":nodes[i],
                        "node_b":nodes[j],
                        "shared_resources":list(intersection)[:5]
                    })
                    adj_indices[i].add(j)
                    adj_indices[j].add(i)

        groups, isolated_nodes = find_connected_groups(nodes,adj_indices)
        return {
            "valid": True,
            "n_nodes": node_count,
            "connections": connections,
            "groups": groups,
            "isolated_nodes": isolated_nodes,
            "nodes": nodes,
            "n_pairs": (node_count * (node_count - 1)) // 2,
            "n_shared": len(connections),
        }
    def _extract_file_resources(self, file_path: str) -> Set[str]:
        resources: Set[str] = set()
        features = self.context.get_file_features(file_path)
        if not features:
            return resources
            
        resources.update(features.files_accessed)
        resources.update(features.attributes)
        resources.update(features.names)
        resources.update(features.constants)
        return resources
