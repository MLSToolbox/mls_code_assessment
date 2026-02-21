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

        scoped_files = sorted(set(self.context.get_python_files()))
        package_dirs = self._discover_scoped_packages(scoped_files)

        scpp_scores: List[float] = []
        for package_path in package_dirs:
            graph_data = self._analyze_package_graph(package_path, scoped_files)
            if not graph_data["valid"]:
                continue

            groups = graph_data["groups"]
            indirect_shared_pairs = 0
            for group in groups:
                group_size = len(group)
                if group_size > 1:
                    indirect_shared_pairs += (group_size * (group_size - 1)) // 2

            node_count = graph_data["n_nodes"]
            total_pairs = graph_data["n_pairs"]
            scpp_value = (
                (2 * indirect_shared_pairs) / (node_count * (node_count - 1))
                if total_pairs > 0
                else 0
            )

            results["packages"][package_path] = {
                "scpp": round(scpp_value, 3),
                **graph_data,
            }
            scpp_scores.append(scpp_value)

            if scpp_value >= 0.8:
                results["summary"]["very_high"] += 1
            elif scpp_value >= 0.6:
                results["summary"]["high"] += 1
            elif scpp_value >= 0.4:
                results["summary"]["medium"] += 1
            elif scpp_value >= 0.2:
                results["summary"]["low"] += 1
            else:
                results["summary"]["very_low"] += 1

        results["summary"]["total_packages"] = len(scpp_scores)
        if scpp_scores:
            results["summary"]["average_scpp"] = sum(scpp_scores) / len(scpp_scores)
            final_score = results["summary"]["average_scpp"] * 10
        else:
            final_score = 0.0

        return self._create_result(
            score=round(final_score, 2),
            messages=self._generate_messages(results),
            module_count=len(scpp_scores),
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

    def _discover_scoped_packages(self, scoped_files: List[str]) -> List[str]:
        packages: Set[str] = set()
        for file_path in scoped_files:
            current = os.path.dirname(file_path).replace("\\", "/") or "."
            while True:
                packages.add(current)
                if current in ("", "."):
                    break
                current = os.path.dirname(current).replace("\\", "/") or "."
        return sorted(packages)

    def _analyze_package_graph(self, package_path: str, scoped_files: List[str]) -> Dict[str, Any]:
        nodes = self._get_package_nodes(package_path, scoped_files)
        node_keys = [node["path"] for node in nodes]
        node_count = len(node_keys)
        if node_count < 2:
            return {
                "valid": False,
                "n_nodes": node_count,
                "nodes": [node["name"] for node in nodes],
            }

        node_resources: Dict[str, Set[str]] = {}
        for node in nodes:
            if node["type"] == "package":
                node_resources[node["path"]] = self._get_subpackage_resources(
                    node["path"], scoped_files
                )
            else:
                node_resources[node["path"]] = self._extract_file_resources(node["path"])

        connections: List[Dict[str, Any]] = []
        adjacency = defaultdict(set)

        for i in range(len(node_keys)):
            node_a = node_keys[i]
            resources_a = node_resources[node_a]
            for j in range(i + 1, len(node_keys)):
                node_b = node_keys[j]
                resources_b = node_resources[node_b]
                shared = resources_a.intersection(resources_b)
                if shared:
                    connections.append(
                        {
                            "node_a": os.path.basename(node_a),
                            "node_b": os.path.basename(node_b),
                            "shared_resources": sorted(shared)[:5],
                        }
                    )
                    adjacency[i].add(j)
                    adjacency[j].add(i)

        groups, isolated_nodes = find_connected_groups(node_keys, adjacency)
        return {
            "valid": True,
            "n_nodes": node_count,
            "connections": connections,
            "groups": groups,
            "isolated_nodes": isolated_nodes,
            "nodes": [node["name"] for node in nodes],
            "n_pairs": (node_count * (node_count - 1)) // 2,
            "n_shared": len(connections),
        }

    def _get_package_nodes(self, package_path: str, scoped_files: List[str]) -> List[Dict[str, str]]:
        direct_modules: Set[str] = set()
        direct_subpackages: Set[str] = set()
        prefix = "" if package_path == "." else f"{package_path}/"

        for file_path in scoped_files:
            normalized = file_path.replace("\\", "/")
            if prefix and not normalized.startswith(prefix):
                continue

            relative = normalized[len(prefix):] if prefix else normalized
            if not relative:
                continue

            parts = relative.split("/")
            if len(parts) == 1:
                file_name = parts[0]
                if (
                    file_name.endswith(".py")
                    and file_name not in {"__init__.py", "__main__.py", "conftest.py", "setup.py"}
                ):
                    direct_modules.add(normalized)
            else:
                subpackage = f"{package_path}/{parts[0]}" if package_path != "." else parts[0]
                direct_subpackages.add(subpackage.replace("\\", "/"))

        nodes: List[Dict[str, str]] = []
        for module in sorted(direct_modules):
            nodes.append({"path": module, "type": "module", "name": os.path.basename(module)})
        for package in sorted(direct_subpackages):
            nodes.append({"path": package, "type": "package", "name": os.path.basename(package)})
        return nodes

    def _get_subpackage_resources(self, subpackage_path: str, scoped_files: List[str]) -> Set[str]:
        resources: Set[str] = set()
        prefix = f"{subpackage_path}/"
        for file_path in scoped_files:
            normalized = file_path.replace("\\", "/")
            if normalized.startswith(prefix):
                resources.update(self._extract_file_resources(normalized))
        return resources

    def _extract_file_resources(self, file_path: str) -> Set[str]:
        resources: Set[str] = set()
        tree = self.context.get_file_ast(file_path)
        if not tree:
            return resources

        resources.update(get_files_accessed(tree))

        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                attr_path = get_attribute_path(node)
                if attr_path and attr_path.startswith("self."):
                    resources.add(attr_path)
            elif isinstance(node, ast.Name):
                if is_likely_global_variable(node.id):
                    resources.add(node.id)

            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if is_likely_global_variable(node.value):
                    resources.add(node.value)

        return resources
