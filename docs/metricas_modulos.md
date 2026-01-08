# Métricas de Cohesión para Módulos - Implementación Final

## Objetivo / Contexto

Definición final de las métricas de cohesión para módulos Python en proyectos de Machine Learning, implementadas en el sistema de análisis de código.

## Estado de Implementación

### ✅ Métricas Implementadas

Las siguientes métricas están completamente implementadas y operativas:

---

## Definición de las Métricas

### **Conceptual Cohesion of Pipeline Modules - CCPM**

**Estado:** ✅ Implementado y Migrado

- **Tipo:** Conceptual
- **Definición:** Evalúa la cohesión conceptual detectando si módulos/clases mezclan responsabilidades de diferentes tareas o etapas del pipeline ML, violando el Single Responsibility Principle (SRP).
- **Cálculo / Condición:** 
  - Identifica si el módulo mezcla:
    - Múltiples fases del pipeline (Data Engineering vs Model Development)
    - Múltiples etapas dentro de una fase (data_collection + data_cleaning)
    - Código ML con código no relacionado al pipeline
  - Utiliza detección heurística mediante:
    - Análisis de imports
    - Keywords en código
    - Patrones en nombres de archivo
    - Metadata del pipeline (si está disponible)

- **Niveles de Cohesión:**
  - **Very High:** Single stage, ML content only, NLOC > threshold (perfecto SRP)
  - **High:** Single stage con minor issues (código non-ML o archivo pequeño)
  - **Medium:** Single phase, múltiples stages (tareas relacionadas mezcladas)
  - **Low:** Múltiples phases, ML content only (tareas no relacionadas)
  - **Very Low:** Múltiples phases + non-ML content (peor caso)

- **Score:** 0-10 normalizado, donde:
  - `very_high = 10 pts`
  - `high = 8 pts`
  - `medium = 5 pts`
  - `low = 3 pts`
  - `very_low = 1 pt`

- **Diagnóstico y Recomendaciones:** 
  - Generados dinámicamente mediante sistema de reglas (`ccpm_rules.json`)
  - 10 reglas que cubren todos los casos posibles
  - Incluyen severidad (critical, high, medium, low, info)
  - Recomendaciones específicas según combinación de:
    - Número de phases (1 o 2+)
    - Número de stages (1, >1, o any)
    - Contenido ML puro vs mixto
    - NLOC sobre/bajo threshold

- **Archivos:**
  - `src/analyzers/ccpm/ccpm_analyzer.py` - Analizador principal
  - `src/analyzers/ccpm/ccpm_evaluator.py` - Sistema de evaluación por reglas
  - `src/analyzers/ccpm/ccpm_rules.json` - 10 reglas de diagnóstico
  - `src/analyzers/ccpm/nloc_calculator.py` - Cálculo de líneas de código
  - `src/analyzers/pipeline/pipeline_stages.json` - Clasificación de stages/phases
  - `docs/CCPM_Migration_Summary.md` - Documentación completa de la migración
  - `docs/CCPM_Flow_Diagram.md` - Diagramas de flujo del análisis

---

### **Structural Cohesion of Pipeline Modules - SCPM**

**Estado:** ✅ Implementado

- **Tipo:** Estructural
- **Definición:** Mide cuánto están relacionadas las funciones de un módulo o clase desde el punto de vista de los datos y modelos del pipeline que comparten.
- **Cálculo / Condición:** Detecta si las funciones comparten:
  - Variables globales
  - Constantes
  - Atributos de clase
  - Datasets (archivos .csv, .parquet, etc.)
  - Modelos (archivos .pkl, .h5, .joblib, etc.)
  - Configuraciones

- **Fórmula:**
$$SCPM(M) = \frac{2 \times \sum_{i<j} P_{ij}}{n \times (n - 1)}$$

  Donde $P_{ij} = 1$ si las funciones $i$ y $j$ comparten al menos un recurso estructural.

- **Rangos de Diagnóstico:**

| Rango | Nivel |
| :--- | :--- |
| [0.8 - 1.0] | Very High |
| [0.6 - 0.8) | High |
| [0.4 - 0.6) | Medium |
| [0.2 - 0.4) | Low |
| [0.0 - 0.2) | Very Low |

- **Interpretación:**
  - **Very High/High:** Funciones están fuertemente acopladas por recursos compartidos (buena cohesión estructural)
  - **Medium:** Cohesión moderada, algunas funciones comparten recursos
  - **Low/Very Low:** Funciones operan independientemente, poca compartición de recursos

- **Recomendaciones de Refactorización:**
  1. **Caso General:** Si las funciones no se invocan entre sí (baja FCPM) pero tienen baja SCPM, considerar moverlas a otros módulos
  2. **Caso Avanzado (LCOM):** Si se detectan X grupos conectados estructuralmente pero no funcionalmente, dividir el módulo en X módulos más pequeños

- **Archivos:**
  - `src/analyzers/scpm_analyzer.py` - Analizador de cohesión estructural

---

### **Functional Cohesion of Pipeline Modules - FCPM**

**Estado:** ✅ Implementado

- **Tipo:** Funcional
- **Definición:** Mide cuánto están relacionadas las funciones de un módulo o clase desde el punto de vista de las invocaciones que realizan entre sí.
- **Cálculo / Condición:** Se define $F_{ij} = 1$ si las funciones $i$ y $j$ cumplen:
  1. **Invocación directa:** $f_i \to f_j$ o $f_j \to f_i$
  2. **Invocación a tercero común:** Ambas invocan a una tercera función $f_t$ del mismo módulo/clase

- **Fórmula:** 
$$FCPM = \frac{2 \times \sum_{i<j} F_{ij}}{n \times (n - 1)}$$

  Donde $n$ es el número de funciones del módulo/clase.

- **Rangos de Diagnóstico:**

| Rango       | Nivel     |
| :---------- | :-------- |
| [0.8 - 1.0] | Very High |
| [0.6 - 0.8) | High      |
| [0.4 - 0.6) | Medium    |
| [0.2 - 0.4) | Low       |
| [0.0 - 0.2) | Very Low  |

- **Interpretación:**
  - **Very High/High:** Funciones están fuertemente acopladas funcionalmente (se invocan frecuentemente)
  - **Medium:** Cohesión funcional moderada
  - **Low/Very Low:** Funciones operan independientemente, no colaboran funcionalmente

- **Recomendaciones de Refactorización:**
  1. **Caso General:** Si las funciones tienen baja SCPM (no comparten datos) y baja FCPM, moverlas a módulos más relacionados
  2. **Caso Avanzado (LCOM):** Si se detectan X grupos conectados funcionalmente pero no estructuralmente, dividir en X módulos

- **Archivos:**
  - `src/analyzers/fcpm_analyzer.py` - Analizador de cohesión funcional

---

### **Logical Class Cohesion Modified for ML - LCCML**

**Estado:** ✅ Implementado

- **Tipo:** Lógico
- **Definición:** Mide la cohesión lógica de clases en proyectos ML, considerando atributos compartidos y métodos que los utilizan.
- **Archivos:**
  - `src/analyzers/lccml_analyzer.py` - Analizador de cohesión lógica de clases
  - `docs/LCCML_Analysis.md` - Análisis detallado de la métrica

---

## Métricas Descontinuadas

Las siguientes métricas a nivel de **paquetes** han sido eliminadas del sistema:

- ❌ **PFP** (Package Functional Purity)
- ❌ **PDSC** (Package Data Structure Cohesion)
- ❌ **PMCR** (Package Module Cohesion Ratio)
- ❌ **IFC-P** (Information Flow Cohesion - Package)
- ❌ **LPCML** (Loose Package Cohesion Modified for ML)

**Razón:** El enfoque actual se centra en métricas a nivel de **módulo/archivo**, no a nivel de paquete.

---

## Infraestructura de Evaluación

### Sistema de Evaluadores Basado en Reglas

Los analizadores complejos (CCPM) utilizan un patrón de evaluación basado en reglas:

1. **BaseEvaluator** (`src/analyzers/base_evaluator.py`)
   - Clase base abstracta para evaluadores
   - Carga reglas desde JSON
   - Renderiza templates de diagnóstico/recomendación
   - Genera mensajes por archivo

2. **Archivos de Reglas** (JSON)
   - Definen condiciones de matching
   - Templates para diagnóstico y recomendación
   - Severidad de cada caso
   - Ejemplos: `ccpm_rules.json`

3. **Flujo de Evaluación:**
   ```
   Métricas calculadas → Match contra reglas → Template rendering → Mensaje final
   ```

### Configuración de Thresholds

Configurados en `src/config/settings.py`:

```python
ANALYZER_CONFIG = {
    "ccpm": {
        "nloc_threshold": 30  # Mínimo de líneas para evaluación
    }
}
```

---

## Uso de las Métricas

### Endpoint de Análisis

```bash
POST /api/analyze/<session_id>
Content-Type: application/json

{
  "analyzers": ["ccpm", "scpm", "fcpm", "lccml"],
  "all_files": false,
  "pipeline_overrides": {
    "file_stages": {"path/to/file.py": ["data_collection"]},
    "excluded_files": ["tests/"]
  }
}
```

### Respuesta Típica (CCPM)

```json
{
  "ccpm": {
    "analyzer_id": "ccpm",
    "score": 7.5,
    "messages": [
      {
        "file": "ml_pipeline.py",
        "diagnosis": "The cohesion of the ml_pipeline.py module is low, as it combines code of two unrelated phases...",
        "recommendation": "The ml_pipeline.py module should be split, at least, into two separate modules...",
        "severity": "high",
        "rule_id": 1,
        "metrics": {
          "unique_stages": 4,
          "unique_phases": 2,
          "ml_content": true,
          "nloc": 120,
          ...
        }
      }
    ],
    "module_count": 15,
    "details": {
      "files": { ... },
      "summary": {
        "total_files": 15,
        "very_high_cohesion": 5,
        "high_cohesion": 3,
        "medium_cohesion": 4,
        "low_cohesion": 2,
        "very_low_cohesion": 1
      }
    }
  }
}
```

---

## Documentación Adicional

- **CCPM:** `docs/CCPM_Migration_Summary.md` - Resumen completo de la migración
- **CCPM:** `docs/CCPM_Flow_Diagram.md` - Diagramas de flujo y casos de uso
- **LCCML:** `docs/LCCML_Analysis.md` - Análisis de cohesión lógica de clases
- **Implementación:** `docs/metrics_implementation.md` - Guía de implementación del sistema de evaluadores

---

## Notas Técnicas

### Detección de Pipeline Stages

El sistema usa `pipeline_stages.json` para clasificar código en etapas:

**Fases:**
- `data_engineering`: data_collection, data_cleaning
- `model_development`: feature_engineering, model_training, model_evaluation

**Métodos de Detección:**
1. Exact filename match (alta confianza)
2. Keywords en código fuente
3. Import statements
4. Pipeline metadata (si disponible)

### Archivos Script-Style

Archivos sin funciones definidas son detectados como `<module_script>` y analizados como una unidad única.

### Integración con MLContentAnalyzer

Todas las métricas conceptuales utilizan `MLContentAnalyzer` para distinguir código ML vs non-ML:
- `ml_content = True`: Todo el código es ML
- `ml_content = False`: Contiene código no relacionado con ML (utilidades, GUI, etc.)

---

## Acciones / Siguientes Pasos

- [x] Migrar CCPM de sistema de puntuación a evaluación cualitativa
- [x] Eliminar métricas de paquetes obsoletas
- [x] Simplificar API eliminando propiedades redundantes
- [x] Actualizar documentación
- [ ] Agregar tests unitarios para evaluadores
- [ ] Documentar casos de uso de SCPM y FCPM




