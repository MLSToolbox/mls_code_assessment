from dataclasses import dataclass
from typing import Dict, Any, Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from core.metrics import MetricMetadata


@dataclass(frozen=True)
class AnalysisResult:
    analyzer_id: str
    score: float
    message_count: Dict[str, Any]
    module_count: int
    metric_metadata: 'MetricMetadata'
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            object.__setattr__(self, 'timestamp', datetime.now())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "analyzer_id": self.analyzer_id,
            "score": self.score,
            "message_count": self._serialize_value(self.message_count),
            "module_count": self.module_count,
            "details": self._serialize_value(self.details),
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "documentation": self.metric_metadata.to_dict()
        }
    
    def _serialize_value(self, value: Any) -> Any:
        """Convert non-JSON-serializable types to serializable ones."""
        if isinstance(value, set):
            return list(value)
        elif isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        elif isinstance(value, (list, tuple)):
            return [self._serialize_value(item) for item in value]
        elif isinstance(value, datetime):
            return value.isoformat()
        else:
            return value

@dataclass(frozen=True)
class SessionResult:
    """Complete session analysis results."""
    session_id: str
    results: Dict[str, AnalysisResult]
    total_modules: int
    total_lines: int