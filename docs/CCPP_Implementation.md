# Documentación de Implementación: Conceptual Cohesion of Pipeline Packages (CCPP)

Este documento detalla la implementación técnica, arquitectura y lógica matemática de la métrica **CCPP**, diseñada para evaluar la cohesión arquitectónica de paquetes en proyectos de Machine Learning.

## 1. Definición y Fundamentación Teórica

**Conceptual Cohesion of Pipeline Packages (CCPP)**: Mide lo mismo que la métrica **CCPM** (*Conceptual Cohesion of Pipeline Modules*), pero a nivel de paquete.

Es decir, calcula la cohesión conceptual de un paquete determinando si sus elementos (módulos y subpaquetes) mezclan responsabilidades de diferentes tareas o etapas del flujo de ejecución de una pipeline ML (ej. un mismo paquete con muchos módulos de la etapa *data collection* y muchos módulos de la etapa de *data cleaning*) o incluso funcionalidad que no es de la pipeline.

*Nota: Las recomendaciones en el caso de identificar una cohesión conceptual baja, se pueden encontrar configuradas en el fichero `src/analyzers/ccpp/ccpp_rules.json`.*

### Visión General del Sistema

La métrica CCPP evalúa la cohesión conceptual de un paquete verificando si los módulos contenidos en un paquete pertenecen a una única etapa (Stage) o fase (Phase) del ciclo de vida de ML.

### Ubicación del Código Fuente

*   **Analyzers**: `src/analyzers/ccpp/`
    *   `ccpp_analyzer.py`: Orquestador principal.
    *   `ccpp_calculator.py`: Motor matemático y lógica de agregación.
    *   `ccpp_evaluator.py`: Sistema de reglas y diagnóstico cualitativo.
*   **Configuración**: `src/analyzers/pipeline/pipeline_stages.json`

## 2. Arquitectura de Componentes

La implementación se divide en tres componentes especializados que interactúan secuencialmente:

```text
[ CCPPAnalyzer ] ──────────┐
      │                    │
      ▼                    ▼
[ CCPPCalculator ]     [ CCPPEvaluator ]
      ▲                    ▲
      │                    │
[ CCPM Results ]       [ Reglas & Umbrales ]
(Nivel Archivo)        (JSON Config)
```

### 2.1 CCPPAnalyzer
**Responsabilidad**: Orquestación y Recolección de Datos.
*   **Inicialización Dinámica**: Carga `pipeline_stages.json` al inicio para determinar dinámicamente el número máximo de etapas posibles (`max_stages`), asegurando que la métrica se adapte a cambios en la definición del pipeline.
*   **Análisis Recursivo**: Recorre el árbol de directorios identificando paquetes (carpetas con `__init__.py`).
*   **Delegación**: Para cada archivo dentro de un paquete, utiliza los resultados de **CCPM** (Conceptual Cohesion of Pipeline Modules) para identificar las etapas y fases a nivel de módulo individual.

### 2.2 CCPPCalculator
**Responsabilidad**: Lógica Matemática y Agregación.
Este componente contiene la "fórmula secreta" de la métrica, incluyendo el **Bono de Afinidad**.

#### Proceso de Agregación:
1.  **Suma de Módulos**: Cuenta total de módulos (`n_total`) y módulos relacionados con ML (`n_ml`).
2.  **Identificación de Componentes**: Recolecta el conjunto de todas las *Etapas Únicas* y *Fases Únicas* detectadas en el paquete.

#### Fórmula Matemática:

El score CCPP (0.0 a 1.0) se calcula como:

$$ CCPP = \text{ContentRatio} \times \text{CohesionFactor} $$

Donde:
*   **Content Ratio ($n_{ML} / n_{Total}$)**: Penaliza el "ruido" o archivos no relacionados con ML.
*   **Cohesion Factor (CF)**: Penaliza la mezcla de responsabilidades.

**Lógica del Cohesion Factor y el Bono de Afinidad:**

El cálculo de CF introduce una lógica condicional inteligente para diferenciar entre mezclas "graves" y "leves":

1.  **Penalización Base**:
    $$ P_{base} = \frac{UniqueStages - 1}{MaxStages - 1} $$

2.  **Ajuste por Afinidad (Phase Affinity)**:
    *   **Escenario A (Múltiples Fases)**: Si el paquete mezcla etapas de fases completamente diferentes (ej. *Data Engineering* y *Model Evaluation*), se aplica la penalización completa.
        $$ CF = 1 - P_{base} $$
    *   **Escenario B (Misma Fase - Bono)**: Si el paquete mezcla etapas pero todas pertenecen a la misma fase lógica (ej. mezcla *Data Collection* y *Data Cleaning*, ambas de *Data Engineering*), la penalización se reduce al 50%.
        $$ CF = 1 - (P_{base} \times 0.5) $$

### 2.3 CCPPEvaluator
**Responsabilidad**: Diagnóstico Cualitativo.
Transforma el score numérico en información accionable para el desarrollador.

*   **Mapping de Niveles**:
    *   **HIGH (0.8 - 1.0)**: Paquete altamente cohesivo, enfocado en una sola responsabilidad.
    *   **MODERATE (0.6 - 0.79)**: Cohesión aceptable, posiblemente con mezcla de etapas afines.
    *   **LOW (0.4 - 0.59)**: Cohesión pobre, mezcla responsabilidades dispares.
    *   **VERY LOW (< 0.4)**: "God Package", requiere refactorización inmediata.

*   **Generación de Recomendaciones**: Basado en reglas predefinidas, sugiere acciones específicas (ej. "Dividir el paquete en sub-paquetes por etapa").

## 3. Flujo de Ejecución

1.  **Setup**: `CCPPAnalyzer` lee la configuración y prepara el contexto.
2.  **Discovery**: Se identifica un paquete candidato (ej. `src/data`).
3.  **Module Analysis**: Se inspecciona cada archivo `.py` en el paquete para extraer sus metadatos (etapas detectadas).
4.  **Aggregation**: `CCPPCalculator` compila los metadatos de todos los archivos.
5.  **Calculation**: Se aplica la fórmula CCPP considerando el *Bono de Afinidad*.
6.  **Evaluation**: `CCPPEvaluator` clasifica el resultado y genera el reporte final.

## 4. Ejemplo Práctico

Para un paquete `src/preprocessing` con 5 etapas totales definidas en el sistema:

*   **Contenido**: 3 Scripts de *Data Cleaning* y 2 Scripts de *Feature Engineering*.
*   **Análisis**:
    *   `Unique Stages`: 2
    *   `Unique Phases`: 1 (Ambas son parte de la fase de preparación).
*   **Cálculo**:
    *   Debido a que comparten la misma fase, se activa el **Bono de Afinidad**.
    *   La penalización por tener 2 etapas se reduce a la mitad.
    *   Resultado: Un score **Moderate/High** en lugar de Low, reconociendo que la arquitectura no está fundamentalmente rota, solo ligeramente mezclada.
