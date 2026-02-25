from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict

from config.settings import settings
from analyzers.pipeline.pipeline_schema import get_pipeline_schema


class PipelineOverrides(BaseModel):
    """
    User-provided overrides for pipeline detection.
    
    Attributes:
        file_stages: Manual stage assignments per file
        excluded_files: Files/directories to exclude from analysis
    """
    file_stages: Dict[str, List[str]] = Field(default_factory=dict)
    excluded_files: List[str] = Field(default_factory=list)
    
    @field_validator('file_stages')
    @classmethod
    def validate_stages(cls, v: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """Validate that all stages are valid."""
        valid_stages = get_pipeline_schema().valid_stages
        for filepath, stages in v.items():
            for stage in stages:
                if stage not in valid_stages:
                    raise ValueError(
                        f"Invalid stage '{stage}' for file '{filepath}'. "
                        f"Valid stages: {', '.join(sorted(valid_stages))}"
                    )
        return v


class AnalysisRequest(BaseModel):
    """
    Request model for analysis endpoint.
    
    Attributes:
        analyzers: List of analyzer types to execute
        pipeline_overrides: Optional pipeline overrides
    """
    # Reject unknown fields in analyze payload
    model_config = ConfigDict(extra='forbid')

    analyzers: List[str] = Field(
        ..., 
        min_length=1,
        description="List of analyzer types to run"
    )
    pipeline_overrides: Optional[PipelineOverrides] = Field(
        None,
        description="Optional overrides for pipeline detection"
    )
    
    @field_validator('analyzers')
    @classmethod
    def validate_analyzers(cls, v: List[str]) -> List[str]:
        """Validate that all analyzer types are valid."""
        invalid = [a for a in v if a not in settings.VALID_ANALYZERS]
        if invalid:
            raise ValueError(
                f"Invalid analyzer(s): {', '.join(invalid)}. "
                f"Valid types: {', '.join(sorted(settings.VALID_ANALYZERS))}"
            )
        return v
