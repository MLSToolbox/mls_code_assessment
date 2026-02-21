import ast
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from analyzers.pipeline.pipeline_schema import get_pipeline_schema


@dataclass
class FileAnalysisCache:
    """Cache for a single file analysis."""

    file_path: str
    ast_tree: Optional[ast.Module] = None
    source_code: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


class AnalysisContext:
    """
    Shared context for analyzers.

    - Caches AST/source/metric data per file.
    - Exposes pipeline-scoped file discovery from file_stages.
    """

    def __init__(
        self,
        session_id: str,
        local_path: str,
        pipeline_metadata: Optional[Dict[str, Any]] = None,
        manual_override_applied: bool = False,
    ):
        self.session_id = session_id
        self.local_path = local_path
        self._file_cache: Dict[str, FileAnalysisCache] = {}
        self._global_metrics: Dict[str, Any] = {}
        self._manual_override_applied = manual_override_applied
        self._python_files_cache: Optional[List[str]] = None
        self._schema = get_pipeline_schema()
        self._pipeline_metadata: Optional[Dict[str, Any]] = self._normalize_pipeline_metadata(
            pipeline_metadata
        )

    def get_file_ast(self, file_path: str) -> Optional[ast.Module]:
        normalized_path = self._normalize_file_path(file_path)
        if normalized_path not in self._file_cache:
            self._file_cache[normalized_path] = FileAnalysisCache(normalized_path)

        cache = self._file_cache[normalized_path]
        if cache.ast_tree is None:
            try:
                cache.source_code = self._read_file(normalized_path)
                cache.ast_tree = ast.parse(cache.source_code, filename=normalized_path)
            except (SyntaxError, FileNotFoundError, UnicodeDecodeError) as e:
                print(f"Warning: Could not parse {normalized_path}: {e}")
                return None

        return cache.ast_tree

    def get_file_source(self, file_path: str) -> Optional[str]:
        normalized_path = self._normalize_file_path(file_path)
        if normalized_path not in self._file_cache:
            self._file_cache[normalized_path] = FileAnalysisCache(normalized_path)

        cache = self._file_cache[normalized_path]
        if cache.source_code is None:
            try:
                cache.source_code = self._read_file(normalized_path)
            except (FileNotFoundError, UnicodeDecodeError) as e:
                print(f"Warning: Could not read {normalized_path}: {e}")
                return None

        return cache.source_code

    def set_file_metric(self, file_path: str, metric_name: str, value: Any) -> None:
        normalized_path = self._normalize_file_path(file_path)
        if normalized_path not in self._file_cache:
            self._file_cache[normalized_path] = FileAnalysisCache(normalized_path)

        self._file_cache[normalized_path].metrics[metric_name] = value

    def get_file_metric(self, file_path: str, metric_name: str) -> Optional[Any]:
        normalized_path = self._normalize_file_path(file_path)
        if normalized_path in self._file_cache:
            return self._file_cache[normalized_path].metrics.get(metric_name)
        return None

    def set_global_metric(self, metric_name: str, value: Any) -> None:
        self._global_metrics[metric_name] = value

    def get_global_metric(self, metric_name: str) -> Optional[Any]:
        return self._global_metrics.get(metric_name)

    def has_file_metric(self, file_path: str, metric_name: str) -> bool:
        normalized_path = self._normalize_file_path(file_path)
        if normalized_path in self._file_cache:
            return metric_name in self._file_cache[normalized_path].metrics
        return False

    def _read_file(self, file_path: str) -> str:
        full_path = file_path if os.path.isabs(file_path) else os.path.join(self.local_path, file_path)
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()

    def get_python_files(self) -> List[str]:
        """
        Get files inside ML pipeline scope.

        Scope rule: only files with at least one stage assignment in file_stages.
        """
        if self._python_files_cache is not None:
            return self._python_files_cache

        self._python_files_cache = self.get_all_ml_files()
        return self._python_files_cache

    def get_scan_mode(self) -> str:
        ml_files = self.get_all_ml_files()
        if not ml_files:
            return "empty_scope"
        if self._manual_override_applied:
            return "manual_override_scope"
        return "pipeline_scope"

    def _get_filtered_all_python_files(self) -> List[str]:
        excluded_patterns = [
            "__init__.py",
            "__pycache__",
            ".pyc",
            ".pyo",
            "venv/",
            ".venv/",
            "env/",
            "site-packages/",
            "dist/",
            "build/",
            ".pytest_cache/",
            ".tox/",
        ]

        python_files: List[str] = []
        for root, dirs, files in os.walk(self.local_path):
            dirs[:] = [d for d in dirs if not any(excl.rstrip("/") in d for excl in excluded_patterns)]

            for file in files:
                if not file.endswith(".py"):
                    continue
                if any(pattern in file or pattern in root for pattern in excluded_patterns):
                    continue

                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, self.local_path)
                python_files.append(self._normalize_file_path(rel_path))

        return sorted(set(python_files))

    def get_all_python_files(self) -> List[str]:
        return self._get_filtered_all_python_files()

    def clear_cache(self) -> None:
        self._file_cache.clear()
        self._global_metrics.clear()
        self._python_files_cache = None

    def get_pipeline_metadata(self) -> Optional[Dict[str, Any]]:
        return self._pipeline_metadata

    def get_stage_assignments(self) -> Dict[str, List[str]]:
        """
        Return normalized file->stages assignments from pipeline metadata.
        """
        if not self._pipeline_metadata:
            return {}

        file_stages = self._pipeline_metadata.get("file_stages", {})
        if not isinstance(file_stages, dict):
            return {}

        assignments: Dict[str, List[str]] = {}
        for file_path, stages in file_stages.items():
            normalized = self._normalize_file_path(file_path)
            if not normalized:
                continue
            stage_list = [stage for stage in stages if stage in self._schema.valid_stages]
            assignments[normalized] = list(stage_list)
        return dict(sorted(assignments.items()))

    def get_ml_files_by_stage(self, stage: Optional[str] = None) -> Dict[str, List[str]]:
        assignments = self.get_stage_assignments()
        if not assignments:
            return {}

        if stage:
            if stage not in self._schema.valid_stages:
                return {}
            files = sorted([file_path for file_path, stages in assignments.items() if stage in stages])
            return {stage: files} if files else {}

        grouped: Dict[str, List[str]] = {}
        for file_path, stages in assignments.items():
            for stage_name in stages:
                grouped.setdefault(stage_name, []).append(file_path)

        for stage_name in grouped:
            grouped[stage_name] = sorted(grouped[stage_name])
        return dict(sorted(grouped.items()))

    def get_all_ml_files(self) -> List[str]:
        assignments = self.get_stage_assignments()
        ml_files = [file_path for file_path, stages in assignments.items() if stages]
        return sorted(ml_files)

    def _normalize_file_path(self, file_path: str) -> str:
        if not isinstance(file_path, str) or not file_path:
            return ""

        normalized = file_path.replace("\\", "/")
        if os.path.isabs(normalized):
            normalized = os.path.relpath(normalized, self.local_path)

        normalized = os.path.normpath(normalized).replace("\\", "/")
        if normalized in (".", ""):
            return ""
        return normalized.lstrip("/")

    def _normalize_pipeline_metadata(
        self, pipeline_metadata: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        if not pipeline_metadata:
            return None

        metadata = dict(pipeline_metadata)
        valid_stages = self._schema.valid_stages

        detected_stages = metadata.get("detected_stages", {})
        evidence_lookup = self._build_evidence_lookup(detected_stages)

        raw_file_stages = metadata.get("file_stages")
        if not isinstance(raw_file_stages, dict):
            raw_file_stages = self._build_file_stages_from_detected(detected_stages)

        normalized_file_stages: Dict[str, List[str]] = {}
        for raw_path, stages in raw_file_stages.items():
            normalized_path = self._normalize_file_path(raw_path)
            if not normalized_path:
                continue

            if not isinstance(stages, list):
                raise ValueError(f"Invalid stage assignments for file '{raw_path}' in pipeline metadata.")

            deduped: List[str] = []
            for stage in stages:
                if stage not in valid_stages:
                    raise ValueError(
                        f"Invalid stage '{stage}' in pipeline metadata for file '{normalized_path}'."
                    )
                if stage not in deduped:
                    deduped.append(stage)
            normalized_file_stages[normalized_path] = deduped

        # Ensure stage evidence-only files are represented in file_stages too.
        for stage_name, file_map in evidence_lookup.items():
            for normalized_path in file_map.keys():
                normalized_file_stages.setdefault(normalized_path, [])
                if stage_name not in normalized_file_stages[normalized_path]:
                    normalized_file_stages[normalized_path].append(stage_name)

        for file_path in normalized_file_stages:
            normalized_file_stages[file_path] = sorted(normalized_file_stages[file_path])

        rebuilt_detected: Dict[str, List[Dict[str, Any]]] = {}
        for file_path in sorted(normalized_file_stages.keys()):
            for stage_name in normalized_file_stages[file_path]:
                evidences = evidence_lookup.get(stage_name, {}).get(file_path)
                if not evidences:
                    evidences = [{"method": "pipeline_metadata", "value": "file_stage_assignment"}]
                rebuilt_detected.setdefault(stage_name, []).append(
                    {"file": file_path, "evidences": evidences}
                )

        missing_stages = sorted(
            stage for stage in self._schema.required_stages if stage not in rebuilt_detected
        )

        metadata["detected_stages"] = dict(sorted(rebuilt_detected.items()))
        metadata["file_stages"] = dict(sorted(normalized_file_stages.items()))
        metadata["missing_stages"] = missing_stages
        metadata["is_valid_pipeline"] = len(missing_stages) == 0
        metadata["files_analyzed"] = len(normalized_file_stages)
        return metadata

    def _build_file_stages_from_detected(self, detected_stages: Any) -> Dict[str, List[str]]:
        if not isinstance(detected_stages, dict):
            return {}

        file_stages: Dict[str, List[str]] = {}
        for stage_name, files in detected_stages.items():
            if stage_name not in self._schema.valid_stages or not isinstance(files, list):
                continue
            for file_info in files:
                if not isinstance(file_info, dict):
                    continue
                normalized_path = self._normalize_file_path(file_info.get("file", ""))
                if not normalized_path:
                    continue
                file_stages.setdefault(normalized_path, [])
                if stage_name not in file_stages[normalized_path]:
                    file_stages[normalized_path].append(stage_name)

        for file_path in file_stages:
            file_stages[file_path] = sorted(file_stages[file_path])
        return dict(sorted(file_stages.items()))

    def _build_evidence_lookup(
        self, detected_stages: Any
    ) -> Dict[str, Dict[str, List[Dict[str, str]]]]:
        lookup: Dict[str, Dict[str, List[Dict[str, str]]]] = {}
        if not isinstance(detected_stages, dict):
            return lookup

        for stage_name, files in detected_stages.items():
            if stage_name not in self._schema.valid_stages or not isinstance(files, list):
                continue

            for file_info in files:
                if not isinstance(file_info, dict):
                    continue
                normalized_path = self._normalize_file_path(file_info.get("file", ""))
                if not normalized_path:
                    continue

                evidences: List[Dict[str, str]] = []
                raw_evidences = file_info.get("evidences", [])
                if isinstance(raw_evidences, list):
                    for evidence in raw_evidences:
                        if not isinstance(evidence, dict):
                            continue
                        evidences.append(
                            {
                                "method": str(evidence.get("method", "")),
                                "value": str(evidence.get("value", "")),
                            }
                        )

                lookup.setdefault(stage_name, {})[normalized_path] = evidences

        return lookup
