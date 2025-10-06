import os
from typing import List
import re
from analyzers.factory import AnalyzerFactory

def validate_file_path(path: str) -> bool:
    """Validate file path exists and is accessible."""
    return os.path.exists(path) and os.access(path, os.R_OK)

def validate_session_id(session_id: str) -> bool:
    """Validate session ID format (accepts UUID format with hyphens)."""
    if not validate_uuid(session_id):
        raise ValueError("Invalid session ID format (expected UUID)")

def validate_analyzer_types(analyzer_types: List[str]) -> bool:
    """Validate analyzer types are supported."""
    available = AnalyzerFactory.get_available_analyzers()
    return all(atype.lower() in available for atype in analyzer_types)

def validate_uuid(uuid: str) -> bool:
    """Validate if a string is a valid UUID."""
    uuid_pattern = r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'
    return bool(re.match(uuid_pattern, uuid.lower()))