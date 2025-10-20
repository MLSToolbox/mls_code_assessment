from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass(frozen=True)
class MetricMetadata:
    metric_id: str
    name: str
    description: str
    formula: Optional[str] = None
    ideal_range: Dict[str, Any] = field(default_factory=dict)
    interpretation: Dict[str, str] = field(default_factory=dict)
    references: List[str] = field(default_factory=list)
    category: str = "general"
    unit: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "name": self.name,
            "description": self.description,
            "formula": self.formula,
            "ideal_range": self.ideal_range,
            "interpretation": self.interpretation,
            "references": self.references,
            "category": self.category,
            "unit": self.unit
        }
