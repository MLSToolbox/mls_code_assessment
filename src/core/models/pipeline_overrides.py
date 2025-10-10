from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PipelineOverrides:
    """
    User-provided overrides for pipeline detection.
    
    Attributes:
        file_stages: Manual stage assignments per file
        excluded_files: Files/directories to exclude from analysis
    """
    file_stages: Dict[str, List[str]] = field(default_factory=dict)
    excluded_files: List[str] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'PipelineOverrides':
        """
        Create PipelineOverrides from dictionary.
        
        Args:
            data: Dictionary with overrides data
            
        Returns:
            PipelineOverrides instance
        """
        return cls(
            file_stages=data.get('file_stages', {}),
            excluded_files=data.get('excluded_files', [])
        )


@dataclass
class AnalysisRequest:
    """
    Request model for analysis endpoint.
    
    Attributes:
        analyzers: List of analyzer types to execute
        pipeline_overrides: Optional pipeline overrides
    """
    analyzers: List[str]
    pipeline_overrides: Optional[PipelineOverrides] = None
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AnalysisRequest':
        """
        Create AnalysisRequest from dictionary.
        
        Args:
            data: Dictionary with request data
            
        Returns:
            AnalysisRequest instance
        """
        overrides_data = data.get('pipeline_overrides')
        overrides = None
        
        if overrides_data:
            overrides = PipelineOverrides.from_dict(overrides_data)
        
        return cls(
            analyzers=data.get('analyzers', []),
            pipeline_overrides=overrides
        )