import json
import os
import warnings
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Mapping, Set


DEFAULT_REQUIRED_STAGES = {
    "data_collection",
    "model_training",
    "model_evaluation",
}


@dataclass(frozen=True)
class PipelineSchema:
    """Canonical schema for pipeline stages/phases loaded from JSON."""

    raw_config: Dict[str, Any]
    stages: Dict[str, Dict[str, List[str]]]
    phases: Dict[str, List[str]]
    required_stages: Set[str]
    valid_stages: Set[str]
    stage_to_phase: Dict[str, str]

    @classmethod
    def from_file(cls, config_path: str) -> "PipelineSchema":
        abs_path = os.path.abspath(config_path)
        return _load_pipeline_schema(abs_path)


def _default_config_path() -> str:
    return os.path.join(os.path.dirname(__file__), "pipeline_stages.json")


def get_pipeline_schema() -> PipelineSchema:
    """Load the default pipeline schema (cached)."""
    return _load_pipeline_schema(_default_config_path())


@lru_cache(maxsize=None)
def _load_pipeline_schema(config_path: str) -> PipelineSchema:
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Pipeline schema file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    if not isinstance(config, Mapping):
        raise ValueError("Pipeline schema must be a JSON object.")

    stages = _normalize_stages(config.get("stages"))
    phases = _normalize_phases(config.get("phases"), set(stages.keys()))
    required_stages = _normalize_required_stages(config.get("required_stages"), set(stages.keys()))
    stage_to_phase = _build_stage_to_phase(phases)

    normalized_config = dict(config)
    normalized_config["stages"] = stages
    normalized_config["phases"] = phases
    normalized_config["required_stages"] = sorted(required_stages)

    return PipelineSchema(
        raw_config=normalized_config,
        stages=stages,
        phases=phases,
        required_stages=required_stages,
        valid_stages=set(stages.keys()),
        stage_to_phase=stage_to_phase,
    )


def _normalize_stages(raw_stages: Any) -> Dict[str, Dict[str, List[str]]]:
    if not isinstance(raw_stages, Mapping) or not raw_stages:
        raise ValueError("Pipeline schema must define a non-empty 'stages' object.")

    normalized: Dict[str, Dict[str, List[str]]] = {}
    for stage_name, stage_config in raw_stages.items():
        if not isinstance(stage_name, str) or not stage_name.strip():
            raise ValueError("Stage names in pipeline schema must be non-empty strings.")
        if not isinstance(stage_config, Mapping):
            raise ValueError(f"Stage config for '{stage_name}' must be an object.")

        normalized[stage_name] = {
            "filename_patterns": _normalize_string_list(stage_config.get("filename_patterns", [])),
            "keywords": _normalize_string_list(stage_config.get("keywords", [])),
            "imports": _normalize_string_list(stage_config.get("imports", [])),
        }

    return dict(sorted(normalized.items()))


def _normalize_phases(raw_phases: Any, valid_stages: Set[str]) -> Dict[str, List[str]]:
    if raw_phases is None:
        return {}
    if not isinstance(raw_phases, Mapping):
        raise ValueError("'phases' in pipeline schema must be an object.")

    normalized: Dict[str, List[str]] = {}
    for phase_name, stage_list in raw_phases.items():
        if not isinstance(phase_name, str) or not phase_name.strip():
            raise ValueError("Phase names in pipeline schema must be non-empty strings.")
        phase_stages = _normalize_string_list(stage_list)

        invalid = [stage for stage in phase_stages if stage not in valid_stages]
        if invalid:
            raise ValueError(
                f"Phase '{phase_name}' references unknown stage(s): {', '.join(sorted(set(invalid)))}"
            )

        normalized[phase_name] = phase_stages

    return dict(sorted(normalized.items()))


def _normalize_required_stages(raw_required: Any, valid_stages: Set[str]) -> Set[str]:
    if raw_required is None:
        warnings.warn(
            "Pipeline schema missing 'required_stages'; using fallback defaults.",
            RuntimeWarning,
            stacklevel=2,
        )
        required = set(DEFAULT_REQUIRED_STAGES)
    else:
        required = set(_normalize_string_list(raw_required))

    invalid = [stage for stage in required if stage not in valid_stages]
    if invalid:
        raise ValueError(
            "Required stage(s) not defined in 'stages': "
            + ", ".join(sorted(set(invalid)))
        )

    return required


def _build_stage_to_phase(phases: Mapping[str, List[str]]) -> Dict[str, str]:
    stage_to_phase: Dict[str, str] = {}
    for phase_name, stage_list in phases.items():
        for stage_name in stage_list:
            stage_to_phase[stage_name] = phase_name
    return stage_to_phase


def _normalize_string_list(raw_values: Any) -> List[str]:
    if not isinstance(raw_values, list):
        raise ValueError("Expected a list of strings in pipeline schema.")

    normalized: List[str] = []
    for value in raw_values:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Pipeline schema lists must contain non-empty strings.")
        if value not in normalized:
            normalized.append(value)
    return normalized
