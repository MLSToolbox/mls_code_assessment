from dataclasses import dataclass
from typing import Dict, Any, Optional
from datetime import datetime

@dataclass(frozen=True)
class AnalysisResult:
    """Immutable result from code analysis."""
    analyzer_id: str
    score: float
    message_count: Dict[str, Any]
    module_count: int
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            object.__setattr__(self, 'timestamp', datetime.now())

@dataclass(frozen=True)
class SessionResult:
    """Complete session analysis results."""
    session_id: str
    results: Dict[str, AnalysisResult]
    total_modules: int
    total_lines: int