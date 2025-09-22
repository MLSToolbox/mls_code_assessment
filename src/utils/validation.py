import os
from typing import List
from core.exceptions import MLSAnalysisError

def validate_file_path(path: str) -> bool:
    """Validate file path exists and is accessible."""
    return os.path.exists(path) and os.access(path, os.R_OK)

def validate_session_id(session_id: str) -> bool:
    """Validate session ID format."""
    return bool(session_id and len(session_id) > 0 and session_id.isalnum())

def validate_analyzer_types(analyzer_types: List[str]) -> bool:
    """Validate analyzer types are supported."""
    from analyzers.factory import AnalyzerFactory
    available = AnalyzerFactory.get_available_analyzers()
    return all(atype.lower() in available for atype in analyzer_types)