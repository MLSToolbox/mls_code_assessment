# Diagrama de Flujo CCPM Migrado

## Arquitectura de Componentes

```
┌─────────────────────────────────────────────────────────────────┐
│                         CCPMAnalyzer                            │
│  (Conceptual Cohesion of Pipeline Modules)                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ usa
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Componentes Auxiliares                        │
├─────────────────────────────────────────────────────────────────┤
│  • pipeline_stages.json    → Clasificación de stages/phases    │
│  • MLContentAnalyzer       → Detecta contenido ML vs non-ML     │
│  • NLOCCalculator          → Calcula líneas de código          │
│  • CCPMEvaluator           → Genera diagnósticos/recomendaciones│
│  • ccpm_rules.json         → Reglas de evaluación              │
└─────────────────────────────────────────────────────────────────┘
```

## Flujo de Análisis Detallado

```
┌──────────────────────────────────────────────────────────────────┐
│ 1. INICIO: analyze()                                             │
│    Obtiene lista de archivos Python del contexto                 │
└──────────────────────────────────────────────────────────────────┘
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ 2. Por cada archivo: _analyze_file(tree, source, file_path)     │
└──────────────────────────────────────────────────────────────────┘
                              ▼
           ┌──────────────────┴──────────────────┐
           ▼                                      ▼
┌────────────────────────┐          ┌────────────────────────┐
│ 2a. NLOCCalculator     │          │ 2b. MLContentAnalyzer  │
│  calculate_nloc()      │          │  analyze_file()        │
│                        │          │                        │
│ Retorna:               │          │ Retorna:               │
│  • nloc: int           │          │  • has_no_ml_content   │
│  • above_threshold     │          │  • non_ml_keywords     │
└────────────────────────┘          └────────────────────────┘
           │                                      │
           └──────────────────┬──────────────────┘
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ 3. _extract_functions(tree)                                      │
│    Extrae todas las funciones/métodos del AST                    │
│    Si no hay funciones → Crea '<module_script>' (script-style)   │
└──────────────────────────────────────────────────────────────────┘
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ 4. Clasificación de Stages por Función                           │
└──────────────────────────────────────────────────────────────────┘
           ▼                                      ▼
┌────────────────────────┐          ┌────────────────────────┐
│ 4a. Pipeline Metadata  │          │ 4b. Heurística         │
│  (si disponible)       │          │  _detect_stages()      │
│                        │          │                        │
│ _get_file_stages_      │          │ Analiza:               │
│  from_pipeline()       │          │  • Filename patterns   │
│                        │          │  • Keywords en código  │
│ Retorna: Set[stages]   │          │  • Import statements   │
└────────────────────────┘          │                        │
                                    │ Retorna: Set[stages]   │
                                    └────────────────────────┘
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ 5. Agregación de Stages y Phases                                 │
│    • unique_stages = count(distinct stages)                      │
│    • unique_phases = count(distinct phases)                      │
│    • stages_detected = [lista de stages]                         │
│    • phases_detected = [lista de phases]                         │
└──────────────────────────────────────────────────────────────────┘
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ 6. _determine_cohesion_level()                                   │
│    Evalúa cohesión conceptual basada en mezcla de                │
│    responsabilidades del pipeline                                │
└──────────────────────────────────────────────────────────────────┘
                              ▼
        ┌─────────────────────┴─────────────────────┐
        │  Lógica de Decisión (Árbol de Decisión)   │
        └───────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
   ┌─────────┐          ┌─────────┐          ┌─────────┐
   │ Stage=1 │          │ Stage>1 │          │ Stage=0 │
   │ ML only │          │ Phase=1 │          │         │
   │ NLOC>T  │          │         │          │         │
   │         │          │         │          │         │
   │ VERY    │          │ MEDIUM  │          │ NON_ML  │
   │ HIGH    │          │         │          │ FILE    │
   └─────────┘          └─────────┘          └─────────┘
        │                     │                     │
        │                     ▼                     │
        │              ┌─────────────┐              │
        │              │  Phase>=2   │              │
        │              │  ML only    │              │
        │              │             │              │
        │              │    LOW      │              │
        │              └─────────────┘              │
        │                     │                     │
        │                     ▼                     │
        │              ┌─────────────┐              │
        │              │  Phase>=2   │              │
        │              │  + non-ML   │              │
        │              │             │              │
        │              │  VERY LOW   │              │
        │              └─────────────┘              │
        │                                           │
        └─────────────────────┬─────────────────────┘
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ 7. Retorna Métricas del Archivo                                  │
│    {                                                              │
│      'unique_stages': int,                                        │
│      'unique_phases': int,                                        │
│      'stages_detected': List[str],                                │
│      'phases_detected': List[str],                                │
│      'cohesion_level': 'very_high'|'high'|'medium'|'low'|...     │
│      'function_stages': Dict,                                     │
│      'ml_content': bool,                                          │
│      'has_no_ml_content': bool,                                   │
│      'nloc': int,                                                 │
│      'above_nloc_threshold': bool,                                │
│      ...                                                          │
│    }                                                              │
└──────────────────────────────────────────────────────────────────┘
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ 8. CCPMEvaluator.evaluate_file(file_path, metrics)              │
│    Hace matching de métricas contra ccpm_rules.json              │
└──────────────────────────────────────────────────────────────────┘
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ 9. Genera Evaluación                                             │
│    {                                                              │
│      'file': str,                                                 │
│      'diagnosis': str (dinámico según regla),                     │
│      'recommendation': str (dinámico según regla),                │
│      'severity': 'critical'|'high'|'medium'|'low'|'info',        │
│      'rule_id': int,                                              │
│      'metrics': Dict                                              │
│    }                                                              │
└──────────────────────────────────────────────────────────────────┘
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ 10. Agrega a messages_list y actualiza summary                   │
└──────────────────────────────────────────────────────────────────┘
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ 11. _calculate_cohesion_score(results)                           │
│     Calcula score agregado 0-10 basado en distribución           │
│     de categorías de cohesión                                    │
└──────────────────────────────────────────────────────────────────┘
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ 12. Retorna AnalysisResult                                       │
│     • score: float (0-10)                                         │
│     • messages: List[Dict] (diagnósticos/recomendaciones)         │
│     • details: Dict (métricas por archivo + summary)             │
└──────────────────────────────────────────────────────────────────┘
```

## Mapeo de Cohesión a Categorías

```
╔═══════════════════════════════════════════════════════════════════╗
║                  CATEGORÍAS DE COHESIÓN CCPM                      ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  VERY HIGH (10 pts) ┌─────────────────────────────────────────┐ ║
║  Perfect SRP        │ • 1 stage único                         │ ║
║                     │ • Solo contenido ML                     │ ║
║                     │ • NLOC > threshold                      │ ║
║                     └─────────────────────────────────────────┘ ║
║                                                                   ║
║  HIGH (8 pts)       ┌─────────────────────────────────────────┐ ║
║  Minor issues       │ • 1 stage único                         │ ║
║                     │ • Tiene código non-ML o NLOC < threshold│ ║
║                     └─────────────────────────────────────────┘ ║
║                                                                   ║
║  MEDIUM (5 pts)     ┌─────────────────────────────────────────┐ ║
║  Related tasks      │ • 1 phase única                         │ ║
║  mixed              │ • Múltiples stages (>1)                 │ ║
║                     │ • Tareas relacionadas pero mezcladas    │ ║
║                     └─────────────────────────────────────────┘ ║
║                                                                   ║
║  LOW (3 pts)        ┌─────────────────────────────────────────┐ ║
║  Unrelated tasks    │ • Múltiples phases (≥2)                 │ ║
║                     │ • Solo contenido ML                     │ ║
║                     │ • Mezcla Data Engineering + Model Dev   │ ║
║                     └─────────────────────────────────────────┘ ║
║                                                                   ║
║  VERY LOW (1 pt)    ┌─────────────────────────────────────────┐ ║
║  Worst case         │ • Múltiples phases (≥2)                 │ ║
║                     │ • Código non-ML presente                │ ║
║                     │ • Violación severa del SRP              │ ║
║                     └─────────────────────────────────────────┘ ║
║                                                                   ║
║  NON_ML_FILE        │ Archivo sin contenido ML (no contado)   │ ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
```

## Ejemplo de Análisis Completo

### Archivo: `data_model_processor.py`

```python
# Contiene funciones de data collection, model training y código auxiliar
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier

def load_data():  # Stage: data_collection
    return pd.read_csv('data.csv')

def train_model(X, y):  # Stage: model_training
    clf = RandomForestClassifier()
    return clf.fit(X, y)

def log_message(msg):  # Non-ML code
    print(f"[LOG] {msg}")
```

### Análisis CCPM:

```
1. _extract_functions() 
   → ['load_data', 'train_model', 'log_message']

2. _detect_stages() para cada función:
   → load_data: ['data_collection']
   → train_model: ['model_training']
   → log_message: []

3. Agregación:
   → unique_stages = 2 (data_collection, model_training)
   → unique_phases = 2 (data_engineering, model_development)
   → all_stages = ['data_collection', 'model_training']
   → all_phases = ['data_engineering', 'model_development']

4. MLContentAnalyzer:
   → has_no_ml_content = True (por log_message)

5. _determine_cohesion_level():
   → unique_phases >= 2 AND has_no_ml_content = True
   → Retorna: 'very_low'

6. CCPMEvaluator.evaluate_file():
   → Busca regla con: phases=2, ml_content_only=false
   → Encuentra Regla ID 3 (severity: critical)

7. Evaluación generada:
   {
     'diagnosis': 'The cohesion of the data_model_processor.py module 
                   is very low, as it combines code of two unrelated 
                   phases, Data Engineering and Model Development phases, 
                   and code not related to the pipeline.',
     'recommendation': 'The data_model_processor.py module should be 
                        split, at least, into three separate modules...',
     'severity': 'critical',
     'rule_id': 3
   }
```

## Beneficios de la Nueva Implementación

1. **Evaluación Más Granular**: 5 niveles vs 3 niveles anteriores
2. **Enfoque en SRP**: Detecta violaciones al Single Responsibility Principle
3. **Diagnósticos Precisos**: Generados dinámicamente según reglas
4. **Recomendaciones Específicas**: Basadas en el tipo de mezcla detectada
5. **Severidad Contextual**: critical, high, medium, low, info según impacto
6. **Conserva Toda la Lógica**: Detección de stages, script-style, ML content
