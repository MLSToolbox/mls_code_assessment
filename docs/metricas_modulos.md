# Métricas de Cohesión para Módulos - Implementación Final

## Objetivo / Contexto

Definición final de las métricas de cohesión para módulos Python en proyectos de Machine Learning, implementadas en el sistema de análisis de código.

## Arquitectura de Código Común

A partir de la refactorización post-migraciones, el código común compartido entre los analizadores de cohesión (CCPM, SCPM, FCPM) ha sido extraído al módulo `src/analyzers/common/`:

- **`common/ast_utils.py`**: Utilidades de manipulación AST
  - `extract_methods()`: Extrae métodos con nombres cualificados (ClassName.method)
  - `get_attribute_path()`: Obtiene rutas de atributos anidados

- **`common/lcom_analysis.py`**: Análisis LCOM (Lack of Cohesion of Methods)
  - `count_components()`: Cuenta componentes desconectados usando DFS
  - `identify_disconnected_methods()`: Identifica métodos sin conexiones

- **`common/variable_detection.py`**: Detección de variables, archivos y llamadas
  - `is_likely_global_variable()`: Detecta variables globales (excluye 40+ tipos ML como DataFrame, Tensor, etc.)
  - `get_files_accessed()`: Detecta acceso a 19 tipos de archivos (csv, pkl, h5, json, etc.)
  - `get_method_calls()`: Extrae llamadas a métodos dentro de un nodo AST

Esta refactorización eliminó ~476 líneas de código duplicado, mejorando la mantenibilidad y consistencia.

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

**Estado:** ✅ Implementado y Migrado

- **Tipo:** Estructural
- **Definición:** Mide cuánto están relacionadas las funciones de un módulo desde el punto de vista de los **datos y estructuras** que comparten. Enfoque exclusivamente estructural, sin considerar invocaciones funcionales.

- **Cálculo / Condición:** Detecta si las funciones comparten:
  - **Variables:**
    - Atributos de clase (`self.x`)
    - Variables globales del módulo (convención UPPERCASE o `_private`)
    - Constantes (UPPERCASE naming)
  - **Archivos:**
    - Datasets: `.csv`, `.json`, `.parquet`, `.xlsx`, `.tsv`, `.feather`, `.arrow`, etc.
    - Modelos ML: `.pkl`, `.joblib`, `.h5`, `.pt`, `.pth`, `.ckpt`, `.pb`, `.onnx`, etc.
    - Configuraciones: `.yaml`, `.yml`, `.ini`, `.cfg`, `.toml`, etc.

- **Fórmula:**
$$SCPM(M) = \frac{2 \times \sum_{i<j} P_{ij}}{n \times (n - 1)}$$

  Donde:
  - $P_{ij} = 1$ si las funciones $i$ y $j$ comparten al menos una **variable** O un **archivo**
  - $n$ = número de métodos/funciones en el módulo

- **Rangos de Diagnóstico (5 niveles granulares):**

| Rango | Nivel | Descripción |
| :--- | :--- | :--- |
| [0.8 - 1.0] | Very High | Casi todos los pares de métodos comparten datos |
| [0.6 - 0.8) | High | Fuerte compartición de datos entre métodos |
| [0.4 - 0.6) | Medium | Compartición moderada de datos |
| [0.2 - 0.4) | Low | Conexiones estructurales débiles |
| [0.0 - 0.2) | Very Low | Métodos operan independientemente |

- **Análisis LCOM (Lack of Cohesion of Methods):**
  - Detecta **grupos desconectados** de métodos mediante análisis de grafos (DFS)
  - Si `n_components > 1`: El módulo contiene X grupos independientes → Recomienda dividir en X módulos separados
  - **Identificación de métodos desconectados:** Lista específica {f1, ..., fn} de funciones sin conexiones

- **Sistema de Evaluación:**
  - **14 reglas** en `scpm_rules.json` para diagnóstico contextual
  - Considera: `cohesion_level`, `n_components`, `n_disconnected_methods`, `shared_variable_count`, `shared_file_count`, `shared_type`
  - Genera diagnósticos y recomendaciones específicas por archivo
  - **Recomendaciones cruzadas con FCPM:** Para métodos desconectados, sugiere verificar cohesión funcional

- **Interpretación:**
  - **Very High/High:** Excelente cohesión estructural, métodos bien conectados por datos compartidos
  - **Medium:** Cohesión aceptable, algunas oportunidades de mejora
  - **Low/Very Low:** Métodos operan independientemente, probable violación del SRP

- **Recomendaciones de Refactorización:**
  1. **LCOM > 1:** Dividir módulo en `n_components` módulos separados (uno por grupo conectado)
  2. **Métodos desconectados identificados:** Para cada función {f1, ..., fn} sin conexiones estructurales:
     - Verificar FCPM (cohesión funcional) para determinar si tienen relación conceptual
     - Si también tienen baja FCPM: mover a módulos más relacionados
  3. **Very Low sin componentes:** Mejorar compartición usando:
     - Atributos de instancia (`self.x`) en clases
     - Variables globales del módulo en código funcional
     - Pasar datos explícitamente como parámetros
  4. **Low cohesión:** Agrupar métodos que operan sobre los mismos datasets/modelos

- **Diferencias con otros analizadores:**
  - **SCPM:** Solo aspectos estructurales (variables + archivos)
  - **FCPM:** Solo aspectos funcionales (invocaciones directas + indirectas)
  - **Código común:** Ambos comparten utilidades del módulo `analyzers/common/`

- **Archivos:**
  - `src/analyzers/scpm_analyzer.py` - Analizador principal migrado
  - `src/analyzers/scpm/scpm_evaluator.py` - Evaluador basado en reglas
  - `src/analyzers/scpm/scpm_rules.json` - 14 reglas de diagnóstico

---

### **Functional Cohesion of Pipeline Modules - FCPM**

**Estado:** ✅ Migrado (Enero 2026)

- **Tipo:** Funcional
- **Definición:** Mide la cohesión funcional mediante patrones de invocación entre métodos, detectando relaciones directas e indirectas.

- **Fórmula:** 
$$FCPM = \frac{2 \times \sum_{i<j} F_{ij}}{n \times (n - 1)}$$

  Donde:
  - $n$ = número de funciones/métodos del módulo o clase
  - $F_{ij} = 1$ si se cumple alguna de estas condiciones:
    1. **Invocación directa:** $f_i \to f_j$ o $f_j \to f_i$
    2. **Invocación indirecta:** Ambas funciones ($f_i$ y $f_j$) invocan a una tercera función común $f_t$ del mismo módulo/clase

- **Rangos de Diagnóstico:**

| Rango       | Nivel     | Descripción |
| :---------- | :-------- | :---------- |
| [0.8 - 1.0] | Very High | Casi todos los pares se invocan |
| [0.6 - 0.8) | High      | Fuerte colaboración funcional |
| [0.4 - 0.6) | Medium    | Relaciones funcionales moderadas |
| [0.2 - 0.4) | Low       | Conexiones funcionales débiles |
| [0.0 - 0.2) | Very Low  | Métodos operan independientemente |

- **Análisis LCOM (Lack of Cohesion of Methods):**
  - Detecta **grupos desconectados funcionalmente** mediante análisis de grafos (DFS)
  - Si `n_components > 1`: El módulo contiene X flujos funcionales independientes → Dividir en X módulos
  - **Identificación de métodos desconectados:** Lista específica {f1, ..., fn} de funciones sin invocaciones

- **Sistema de Evaluación:**
  - **14 reglas** en `fcpm_rules.json` para diagnóstico contextual
  - Considera: `cohesion_level`, `n_components`, `n_disconnected_methods`, `breakdown` (invocaciones directas vs indirectas)
  - Genera diagnósticos y recomendaciones específicas por archivo
  - **Recomendaciones cruzadas con SCPM:** Para métodos desconectados, sugiere verificar cohesión estructural

- **Detección de Invocaciones:**
  - **Directas:** Análisis AST de nodos `ast.Call` para detectar `f_i()`, `self.f_j()`, `ClassName.method()`
  - **Indirectas:** Construcción de call graph, intersección de callees comunes:
    ```python
    common_callees = calls(f_i) ∩ calls(f_j) ∩ {métodos del mismo módulo}
    if common_callees ≠ ∅ → F_ij = 1
    ```
  - **Breakdown:** Conteo separado de invocaciones directas e indirectas para insights detallados

- **Interpretación:**
  - **Very High/High:** Excelente cohesión funcional, métodos colaboran intensivamente mediante invocaciones
  - **Medium:** Cohesión aceptable, algunas oportunidades de mejora
  - **Low/Very Low:** Métodos operan independientemente, probable violación del SRP

- **Recomendaciones de Refactorización:**
  1. **LCOM > 1:** Dividir módulo en `n_components` módulos (uno por flujo funcional)
  2. **Métodos desconectados identificados:** Para cada función {f1, ..., fn} sin invocaciones:
     - Verificar SCPM (cohesión estructural) para determinar si comparten datos
     - Si FCPM bajo Y SCPM bajo: mover a módulos más relacionados
     - Si FCPM bajo pero SCPM alto: mantener juntos, mejorar colaboración funcional
  3. **Very Low sin componentes:** Evaluar si los métodos realmente sirven el mismo propósito funcional
  4. **Low cohesión con invocaciones indirectas:** Buen uso de funciones helper, considerar si necesita más colaboración directa

- **Diferencias con LCCML (descontinuado):**
  - **FCPM:** Solo aspectos **funcionales** → Invocaciones directas + indirectas
  - **LCCML (eliminado):** Funcional + estructural → Invocaciones + Variables compartidas + Archivos + Funciones ML

- **Archivos:**
  - `src/analyzers/fcpm/fcpm_analyzer.py` - Analizador migrado con detección de invocaciones indirectas
  - `src/analyzers/fcpm/fcpm_evaluator.py` - Evaluador basado en reglas
  - `src/analyzers/fcpm/fcpm_rules.json` - 14 reglas de diagnóstico

---

## Métricas Descontinuadas

Las siguientes métricas han sido eliminadas del sistema:

**A nivel de paquetes:**
- ❌ **PFP** (Package Functional Purity)
- ❌ **PDSC** (Package Data Structure Cohesion)
- ❌ **PMCR** (Package Module Cohesion Ratio)
- ❌ **IFC-P** (Information Flow Cohesion - Package)
- ❌ **LPCML** (Loose Package Cohesion Modified for ML)

**Razón paquetes:** El enfoque actual se centra en métricas a nivel de **módulo/archivo**, no a nivel de paquete.

**A nivel de módulo:**
- ❌ **LCCML** (Logical Class Cohesion Modified for ML)

**Razón LCCML:** Funcionalidad redundante con SCPM y FCPM. LCCML combinaba aspectos estructurales (variables compartidas, archivos) y funcionales (invocaciones, funciones ML). Esta funcionalidad ahora está cubierta de forma más específica por:
  - **SCPM:** Cohesión estructural (variables compartidas, archivos de datos/modelos)
  - **FCPM:** Cohesión funcional (invocaciones directas e indirectas)
  
  El código común compartido entre CCPM, SCPM y FCPM ha sido refactorizado al módulo `analyzers/common/`.

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
  "analyzers": ["ccpm", "scpm", "fcpm"],
  "pipeline_overrides": {
    "file_stages": {"path/to/file.py": ["data_collection"]},
    "excluded_files": ["tests/"]
  }
}
```

El análisis requiere al menos un archivo con etapas asignadas (detectadas o manuales).

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
- **SCPM:** `docs/SCPM_Migration_Summary.md` - Resumen de migración de cohesión estructural
- **FCPM:** `docs/FCPM_Migration_Summary.md` - Resumen de migración de cohesión funcional
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



