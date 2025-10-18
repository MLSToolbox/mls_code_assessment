# Metric Metadata System

Sistema modular para documentación de métricas de análisis.

## Estructura

```
src/core/metrics/
├── __init__.py      # Exports
├── metadata.py      # MetricMetadata dataclass
└── registry.py      # METRICS_REGISTRY
```

## Uso en Analizadores

```python
from core.metrics import get_metric_metadata
from core.models.analysis_result import AnalysisResult

def analyze(self):
    return AnalysisResult(
        analyzer_id="My Analyzer",
        score=7.5,
        message_count={},
        module_count=10,
        metric_metadata=get_metric_metadata("metric_id"),
        details={}
    )
```

## Agregar Nueva Métrica

Editar `registry.py`:

```python
METRICS_REGISTRY = {
    "my_metric": MetricMetadata(
        metric_id="my_metric",
        name="My Metric",
        description="What it measures",
        formula="x + y",
        ideal_range={"min": 0, "max": 10},
        interpretation={"low": "Bad", "high": "Good"},
        references=["https://..."],
        category="quality",
        unit="score"
    ),
}
```

## Respuesta API

```json
{
  "success": true,
  "data": {
    "score": 7.5,
    "module_count": 10,
    "documentation": {
      "name": "Cyclomatic Complexity",
      "description": "...",
      "formula": "CC = E - N + 2P",
      "ideal_range": {"min": 1, "max": 10},
      "interpretation": {...},
      "references": [...]
    }
  }
}
```

## Métricas Disponibles

- `radon_cc` - Cyclomatic Complexity
- `radon_mi` - Maintainability Index
- `pylint_score` - Code Quality Score
- `fpc` - Functional Pipeline Cohesion
- `pipeline_detection` - ML Pipeline Detection
