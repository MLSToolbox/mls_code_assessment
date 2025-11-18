from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

from config.settings import settings


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
        for filepath, stages in v.items():
            for stage in stages:
                if stage not in settings.VALID_PIPELINE_STAGES:
                    raise ValueError(
                        f"Invalid stage '{stage}' for file '{filepath}'. "
                        f"Valid stages: {', '.join(sorted(settings.VALID_PIPELINE_STAGES))}"
                    )
        return v


class AnalysisRequest(BaseModel):
    """
    Request model for analysis endpoint.
    
    Attributes:
        analyzers: List of analyzer types to execute
        pipeline_overrides: Optional pipeline overrides
        all_files: Whether to analyze all files or only ML-related files
    """
    analyzers: List[str] = Field(
        ..., 
        min_length=1,
        description="List of analyzer types to run"
    )
    pipeline_overrides: Optional[PipelineOverrides] = Field(
        None,
        description="Optional overrides for pipeline detection"
    )
    all_files: bool = Field(
        False,
        description="Analyze all files (True) or only ML-related files (False)"
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