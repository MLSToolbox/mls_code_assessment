# Migración de CCPM: Resumen de Cambios

## Contexto de la Migración

Se ha migrado exitosamente la métrica **CCPM** (Class Cohesion Per Module) hacia la nueva implementación de **Conceptual Cohesion of Pipeline Modules**, enfocándose en la detección de violaciones al Single Responsibility Principle (SRP) en módulos de pipelines ML.

## Cambios Principales Realizados

### 1. Sistema de Evaluación Cualitativo

#### ANTES (Sistema de Puntuación Numérica)
```python
cohesion_scores = {
    'high': 10,      # Single stage
    'medium': 6,     # Single phase, multiple stages
    'low': 3         # Multiple phases
}
```

#### DESPUÉS (Evaluación Cualitativa)
```python
cohesion_scores = {
    'very_high': 10,  # Single stage, ML only (perfect SRP)
    'high': 8,        # Single stage with minor issues
    'medium': 5,      # Single phase, multiple stages
    'low': 3,         # Multiple phases, ML content
    'very_low': 1     # Multiple phases + non-ML content
}
```

### 2. Método `_determine_cohesion_level` Actualizado

**Propósito**: Evaluar si un módulo/clase mezcla responsabilidades de diferentes tareas o etapas del pipeline ML.

#### Lógica de Categorización

| Categoría | Condición | Descripción |
|-----------|-----------|-------------|
| **Very High** | 1 stage + ML only + NLOC > threshold | Perfecto SRP, una sola etapa del pipeline |
| **High** | 1 stage + (non-ML content OR NLOC < threshold) | Una etapa pero con código no-ML o archivo pequeño |
| **Medium** | 1 phase + >1 stages | Mezcla etapas relacionadas de la misma fase |
| **Low** | ≥2 phases + ML only | Mezcla fases no relacionadas del pipeline |
| **Very Low** | ≥2 phases + non-ML content | Peor caso: múltiples fases + código no-ML |
| **Non-ML File** | No ML content detected | Archivo sin contenido ML |

### 3. Actualización de Contadores en Summary

Se agregaron contadores para todas las categorías de cohesión:

```python
'summary': {
    'total_files': 0,
    'very_high_cohesion': 0,  # NUEVO
    'high_cohesion': 0,
    'medium_cohesion': 0,
    'low_cohesion': 0,
    'very_low_cohesion': 0,   # NUEVO
    'non_ml_files': 0,
    'small_files': 0,
    # ...
}
```

### 4. Documentación Actualizada

El docstring de la clase `CCPMAnalyzer` ahora refleja:
- Enfoque en detección de mezcla de responsabilidades
- Violaciones al Single Responsibility Principle
- Categorías cualitativas de cohesión conceptual

## Componentes CONSERVADOS (Crítico)

### ✅ Detección de Pipeline Stages
- Se mantiene la lógica completa de `_detect_stages()`
- Continúa usando `pipeline_stages.json` para clasificación
- Detecta stages mediante:
  - Filename patterns (exact match)
  - Keywords en código
  - Import statements
  - Pipeline metadata (si está disponible)

### ✅ Detección de Script-Style Files
- Se conserva la detección de archivos sin funciones
- Pseudo-función `<module_script>` para código suelto
- Análisis de cohesión a nivel de módulo completo

### ✅ Integración con MLContentAnalyzer
- Se mantiene la detección de contenido ML vs non-ML
- Usa `ml_content_only` (True=solo ML, False=contiene código no-ML)
- Integración con `non_ml_keywords` para identificar código no relacionado con pipeline

### ✅ Sistema de Reglas (ccpm_rules.json)
- Las reglas JSON ya estaban correctamente definidas
- No fue necesario modificarlas
- Mapean perfectamente a las nuevas categorías

### ✅ CCPMEvaluator
- No requirió cambios
- Continúa haciendo matching de métricas contra reglas
- Genera diagnósticos y recomendaciones dinámicamente

## Flujo de Análisis (Conservado)

```
1. analyze()
   ↓
2. _analyze_file() para cada archivo Python
   ↓
3. _extract_functions() → Detecta funciones/clases o script-style
   ↓
4. _get_file_stages_from_pipeline() → Intenta usar metadata del pipeline
   ↓
5. _detect_stages() → Clasifica cada función por etapa/fase
   ↓
6. _determine_cohesion_level() → [ACTUALIZADO] Categoriza cohesión
   ↓
7. CCPMEvaluator.evaluate_file() → Genera diagnóstico/recomendación
   ↓
8. _calculate_cohesion_score() → [ACTUALIZADO] Score cualitativo agregado
```

## Métricas Exportadas por Archivo

Cada archivo analizado retorna:

```python
{
    'unique_stages': int,              # Número de etapas únicas detectadas
    'unique_phases': int,              # Número de fases únicas detectadas
    'stages_detected': List[str],      # Lista de etapas detectadas
    'phases_detected': List[str],      # Lista de fases detectadas
    'cohesion_level': str,             # ACTUALIZADO: 'very_high' | 'high' | 'medium' | 'low' | 'very_low'
    'function_stages': Dict,           # Mapeo función → etapas
    'source': str,                     # 'pipeline_metadata' | 'heuristic'
    'ml_content_only': bool,           # True si todo es contenido ML, False si hay código non-ML
    'non_ml_keywords_found': List,     # Keywords non-ML encontrados (si ml_content_only=False)
    'nloc': int,                       # Non-comment Lines of Code
    'above_nloc_threshold': bool,      # True si NLOC > threshold
    'is_script_file': bool             # True si es archivo script-style
}
```

## Evaluación Dinámica con Reglas

El `CCPMEvaluator` usa las métricas anteriores para hacer matching con `ccpm_rules.json`:

### Ejemplo de Regla Aplicada

**Regla ID 1** (Low Cohesion):
```json
{
  "conditions": {
    "phases": 2,
    "stages": "any",
    "ml_content_only": true,
    "nloc_above_threshold": true
  },
  "diagnosis_template": "The cohesion of the {module_name} module is low, as it combines code of two unrelated phases...",
  "recommendation_template": "The {module_name} module should be split, at least, into two separate modules...",
  "severity": "high"
}
```

**Salida Generada**:
```python
{
    'file': 'data_processor.py',
    'diagnosis': 'The cohesion of the data_processor.py module is low, as it combines code of two unrelated phases...',
    'recommendation': 'The data_processor.py module should be split, at least, into two separate modules...',
    'severity': 'high',
    'rule_id': 1,
    'metrics': { ... }
}
```

## Resultado Final

### Datos Calculados por Archivo
- Métricas de stages y phases detectados
- Categoría de cohesión cualitativa
- Información de NLOC y ML content

### Diagnóstico y Recomendación Dinámica
- Generados automáticamente por el evaluator
- Basados en las reglas de `ccpm_rules.json`
- Incluyen severidad (critical, high, medium, low, info)

### Score Agregado
- Promedio normalizado 0-10
- Basado en distribución de categorías de cohesión
- Solo cuenta archivos con contenido ML

## Conclusión

La migración fue exitosa manteniendo:
- ✅ Toda la lógica de detección de stages/phases
- ✅ Análisis de archivos script-style
- ✅ Integración con MLContentAnalyzer
- ✅ Sistema de reglas y evaluación dinámica
- ✅ Cálculo de NLOC para recomendaciones

Y agregando:
- ✨ Evaluación cualitativa más granular (5 niveles)
- ✨ Mejor mapeo a conceptos de cohesión conceptual
- ✨ Enfoque claro en violaciones del SRP
- ✨ Diagnósticos más precisos por categoría
- ✨ API estandarizada con nomenclatura consistente (`ml_content_only`)

## Cambios en la API

### Nomenclatura Estandarizada
- ✅ **`ml_content_only`**: Nomenclatura consistente en toda la cadena (analyzer → evaluator → rules)
  - `ml_content_only = True`: Todo el contenido es ML (cohesión ML pura)
  - `ml_content_only = False`: Hay código no-ML mezclado (ver `non_ml_keywords_found`)

### Eliminadas
- ❌ `has_no_ml_content`: Eliminada por confusa (doble negación)
- ❌ `ml_content`: Reemplazada por `ml_content_only` para mayor claridad
