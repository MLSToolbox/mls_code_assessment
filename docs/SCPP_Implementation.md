# Documentación de Implementación: Structural Coupling Package Pipeline (SCPP)

Este documento detalla la implementación técnica, arquitectura y lógica matemática de la métrica **SCPP**, diseñada para evaluar la cohesión estructural de paquetes en flujos de trabajo de Machine Learning.

## 1. Definición y Fundamentación Teórica

**Structural Coupling Package Pipeline (SCPP)**: Mide la cohesión estructural (*Structural Cohesion*) a nivel de paquete, evaluando cómo los diferentes módulos (archivos `.py`) dentro de un directorio se conectan entre sí a través de recursos compartidos.

A diferencia de métricas conceptuales como CCPP, **SCPP** es empírica y concreta: busca evidencia física de datos fluyendo entre módulos. Un paquete altamente cohesivo bajo SCPP es aquel donde los módulos colaboran estrechamente compartiendo archivos de datos, modelos o configuración global.

*Nota: Las recomendaciones en el caso de identificar una cohesión estructural baja, se pueden encontrar configuradas en el fichero `src/analyzers/scpp/scpp_rules.json`.*

### Visión General del Sistema

La métrica SCPP construye un grafo de dependencias de recursos para cada paquete y analiza la topología de este grafo para determinar si el paquete actúa como una unidad monolítica cohesiva o como un conjunto fragmentado de scripts independientes.

### Ubicación del Código Fuente

*   **Analyzers**: `src/analyzers/scpp/`
    *   `scpp_analyzer.py`: Orquestador principal y constructor del grafo.
    *   `scpp_evaluator.py`: Sistema de reglas y diagnóstico cualitativo.
*   **Reglas**: `src/analyzers/scpp/scpp_rules.json`

## 2. Arquitectura de Componentes

La implementación sigue el patrón de diseño de analizadores del sistema, dividiendo la responsabilidad entre extracción, cálculo grafo-teórico y evaluación.

```text
[ SCPPAnalyzer ] ──────────┐
      │                    │
      ▼                    ▼
[ Graph Builder ]      [ SCPPEvaluator ]
Constructs: G=(V, E)       ▲
      │                    │
      ▼                    │
[ Graph Metrics ]      [ Reglas & Umbrales ]
(Groups, Isolates)     (JSON Config)
```

### 2.1 SCPPAnalyzer
**Responsabilidad**: Análisis Estático y Teoría de Grafos.

*   **Identificación de Recursos**: Para cada archivo en un paquete, extrae los recursos que utiliza:
    *   **Archivos Físicos**: Strings literales que referencian datasets (`.csv`, `.parquet`), modelos (`.pkl`, `.h5`) o configs (`.json`, `.yaml`).
    *   **Variables Globales**: Constantes a nivel módulo.
    *   **Atributos de Clase (Opcional)**: Detección de `self.atributo` como proxy de estado compartido (sujeto a configuración de diseño, ver `scpp_analyzer.py`).

*   **Construcción del Grafo**:
    *   **Nodos (V)**: Cada archivo `.py` es un nodo.
    *   **Aristas (E)**: Existe una arista entre dos nodos si la intersección de sus conjuntos de recursos no es vacía ($R_i \cap R_j \neq \emptyset$).

*   **Análisis Topológico**:
    *   **Componentes Conectados (Grupos)**: Utiliza DFS (Depth First Search) para identificar subgrafos disjuntos.
    *   **Nodos Aislados**: Identifica archivos que no comparten recursos con ningún otro.

### 2.2 Relación con LCOM y Recomendaciones

La lógica de detección de fracturas implementa el concepto de **LCOM** a nivel de paquete. El análisis calcula el *number of groups of connected modules/subpackages* ($N_{groups}$).

*   **Condición de Conexión**: Los módulos se consideran conectados si comparten *datasets*, *models* o *configurations*.
*   **Resultados Posibles**: $N_{groups}$ puede ser 1 (cohesivo), >1 (fracturado) o 0 (aislado).

**Recomendación Específica ($N_{groups} > 1$):**
En el caso de detectar múltiples grupos desconectados, el sistema emite automáticamente la siguiente recomendación:

> "Additionally, as there are X groups of structural connected modules/subpackages {{m11,...,m1n}, …{mx1,...,mxs}}, if these groups are not functional connected, to improve package structural cohesion, the package should be split into X smaller subpackages."

### 2.3 Fórmulas Matemáticas

La métrica se basa formalmente en la siguiente definición teórica:

**Structural Cohesion of Pipeline Packages (SCPP)**: Mide cuánto están relacionados los módulos y/o subpaquetes de un paquete, desde el punto de vista de la compartición de los datos y modelos de la pipeline.

Supongamos un paquete con $m$ módulos y subpaquetes (nodos). Sea $Q_{ij} = 1$ si los módulos/subpaquetes $i$ y $j$ comparten, de forma directa o indirecta, al menos un/a:
*   Modelo
*   Configuración común
*   Dataset
En caso contrario $Q_{ij} = 0$.

Entonces, se propone la fórmula siguiente:

$$ \text{SCPP}(P) = \frac{2 \times \sum_{i<j} Q_{ij}}{m \times (m - 1)} $$

#### Implementación del Cálculo:

En el código (`scpp_analyzer.py`), optimizamos el cálculo de $\sum Q_{ij}$ utilizando teoría de grafos. En lugar de verificar cada par individualmente, identificamos los **Componentes Conectados** (grupos de nodos interconectados).

Si el grafo tiene $k$ componentes conectados ($C_1, C_2, ..., C_k$), y cada componente tiene tamaño $|C_i|$, la suma de pares conectados es:

$$ \sum_{i<j} Q_{ij} = \sum_{g=1}^{k} \frac{|C_g| \times (|C_g| - 1)}{2} $$

Esto produce el mismo resultado matemático que la definición teórica pero de manera computacionalmente más eficiente.

**Interpretación**:
*   **SCPP = 1.0**: Todos los archivos pertenecen a un único componente conectado (Grafo Conexo). Cualquier archivo puede alcanzar a cualquier otro a través de recursos compartidos.
*   **SCPP = 0.0**: Cada archivo es una isla. No hay recursos compartidos.
*   **SCPP intermedio**: El paquete está fragmentado en varios "clusters" de funcionalidad.

### 2.4 SCPPEvaluator
**Responsabilidad**: Diagnóstico Cualitativo.

Evalúa no solo el score numérico, sino la topología detectada:

*   **Reglas de Fragmentación**:
    *   Si `n_groups > 1`: El paquete está fracturado. Violación del Principio de Responsabilidad Única (SRP). Se recomienda dividir el paquete.
*   **Reglas de Aislamiento**:
    *   Si `isolated_nodes > 0`: Detecta "scripts huérfanos" que podrían ser utilidades mal ubicadas o código muerto.

## 3. Flujo de Ejecución

1.  **Discovery**: Se identifican los paquetes del proyecto.
2.  **Resource Extraction**: Se parsea el AST de cada módulo para encontrar accesos a recursos (`self.data`, `config.json`, `model.pkl`).
3.  **Graph Construction**: Se crea el grafo de adyacencia basado en recursos compartidos.
4.  **Topology Analysis**: Se calculan los componentes conectados y nodos aislados.
5.  **Scoring**: Se calcula el ratio de pares conectados sobre el total de pares posibles.
6.  **Reporting**: `SCPPEvaluator` utiliza `scpp_rules.json` para generar diagnósticos humanos (ej. "El paquete está fracturado en 3 grupos desconectados").

## 4. Ejemplo Práctico

Para un paquete `src/training` con 4 archivos:

*   `train_model_A.py` (Usa `data.csv`, `model_A.pkl`)
*   `eval_model_A.py`  (Usa `model_A.pkl`, `metrics.json`)
*   `train_model_B.py` (Usa `data_B.csv`)
*   `utils.py`         (No usa recursos externos)

**Análisis**:
1.  **Conexión A**: `train_model_A` y `eval_model_A` comparten `model_A.pkl`. Forman un grupo de tamaño 2.
2.  **Aislamiento B**: `train_model_B` usa recursos únicos. Grupo de tamaño 1 (Aislado).
3.  **Aislamiento Utils**: `utils.py` no usa recursos. Grupo de tamaño 1 (Aislado).

**Cálculo**:
*   **Grupos**: {A, A_eval}, {B}, {Utils}
*   **Pares Conectados**: 1 (Solo A-A_eval).
*   **Total Pares Posibles**: $4 \times 3 / 2 = 6$.
*   **SCPP**: $1 / 6 \approx 0.16$ (Baja Cohesión).

**Diagnóstico**:
"El paquete tiene baja cohesión estructural (0.16). Contiene 2 nodos aislados y 1 grupo conectado. Considere separar el entrenamiento del modelo B en su propio paquete."
