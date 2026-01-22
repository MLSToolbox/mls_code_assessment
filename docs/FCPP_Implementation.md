# Documentación de Implementación: Functional Cohesion of Pipeline Packages (FCPP)

Este documento detalla la implementación técnica, arquitectura y lógica matemática de la métrica **FCPP**, diseñada para evaluar la cohesión funcional de paquetes en flujos de trabajo de Machine Learning.

## 1. Definición y Fundamentación Teórica

**Functional Cohesion of Pipeline Packages (FCPP)**: Mide cuánto están relacionados los módulos y/o subpaquetes de un paquete, desde el punto de vista de las **invocaciones** que realizan (llamadas a funciones o métodos, instanciación de clases, uso de variables importadas).

A diferencia de SCPP (que mide datos compartidos), **FCPP** se centra en la colaboración algorítmica. Un paquete altamente cohesivo bajo FCPP es aquel donde los módulos colaboran estrechamente invocándose entre sí para cumplir una tarea común.

*Nota: Las recomendaciones en el caso de identificar una cohesión funcional baja, se pueden encontrar configuradas en el fichero `src/analyzers/fcpp/fcpp_rules.json`.*

### Visión General del Sistema

La métrica FCPP construye un grafo de llamadas funcionales (*Call Graph*) para cada paquete y analiza la topología de este grafo para determinar si existe una fuerte interdependencia funcional entre sus componentes o si, por el contrario, el paquete actúa como un contenedor de utilidades desconectadas.

### Ubicación del Código Fuente

*   **Analyzers**: `src/analyzers/fcpp/`
    *   `fcpp_analyzer.py`: Orquestador principal y constructor del grafo de llamadas.
    *   `fcpp_evaluator.py`: Sistema de reglas y diagnóstico cualitativo.
*   **Reglas**: `src/analyzers/fcpp/fcpp_rules.json`
*   **Utilidades Comunes**: `src/analyzers/common/package_utils.py` (Lógica de grafo y descubrimiento de paquetes).

## 2. Arquitectura de Componentes

La implementación sigue el patrón de diseño de analizadores del sistema, dividiendo la responsabilidad entre extracción AST, cálculo grafo-teórico y evaluación.

```text
[ FCPPAnalyzer ] ──────────┐
      │                    │
      ▼                    ▼
[ Graph Builder ]      [ FCPPEvaluator ]
Constructs: G=(V, E)       ▲
      │                    │
      ▼                    │
[ Graph Metrics ]      [ Reglas & Umbrales ]
(Groups, Isolates)     (JSON Config)
```

### 2.1 FCPPAnalyzer
**Responsabilidad**: Análisis Estático y Teoría de Grafos.

*   **Análisis AST**: Para cada archivo en un paquete, analiza el Árbol de Sintaxis Abstracta para detectar:
    *   **Definiciones**: Funciones y clases que el módulo expone.
    *   **Invocaciones**: Llamadas (`Call`) y usos de nombres (`Name`) que corresponden a símbolos importados de otros módulos del **mismo paquete**.

*   **Construcción del Grafo**:
    *   **Nodos (V)**: Cada archivo `.py` válido (excluyendo infraestructura como `__init__.py`, `__main__.py`) es un nodo de índice $0 \dots m-1$.
    *   **Aristas (E)**: Se construye una matriz de adyacencia dirigida basada en las importaciones y llamadas detectadas.

*   **Análisis de Conectividad Avanzada**:
    *   **Clausura Transitiva**: Utiliza el algoritmo de **Floyd-Warshall** para detectar conexiones indirectas ($A \to B \to C$).
    *   **Dependencia Compartida**: Verifica si dos nodos desconectados dependen de un tercero común ($A \to C$ y $B \to C$).

### 2.2 Relación con LCOM y Recomendaciones

La lógica implementa una variante de **LCOM (Lack of Cohesion of Methods)** adaptada a nivel de paquete. El análisis calcula el *number of groups of functional connected modules/subpackages* ($N_{groups}$).

*   **Condición de Conexión**: Los módulos se consideran conectados si existe invocación directa, indirecta o dependencia compartida entre ellos.
*   **Resultados Posibles**: $N_{groups}$ puede ser 1 (cohesión ideal), >1 (fracturado) o N (totalmente disperso).

**Recomendación Específica ($N_{groups} > 1$):**
Al detectar múltiples grupos funcionales desconectados, el sistema emite la recomendación estandarizada:

> "Additionally, as there are X groups of functional connected modules/subpackages {{m11,...,m1n}, …{mx1,...,mxs}}, if these groups are not structural connected, to improve package functional cohesion, the package should be split into X smaller subpackages."

### 2.3 Fórmulas Matemáticas

La métrica se basa formalmente en la siguiente definición teórica:

Supongamos un paquete con $m$ módulos y subpaquetes. Sea $F_{ij} = 1$ si existe alguna función del módulo o subpaquete $m_i$ que realiza alguna de las invocaciones siguientes a alguna función del módulo o subpaquete $m_j$:

1.  **Directa**: $m_i \to m_j$ o $m_j \to m_i$.
2.  **Indirecta**: $m_i \to \dots \to m_j$ o $m_j \to \dots \to m_i$ (donde los intermedios pertenecen al mismo paquete).
3.  **Dependencia Compartida**: $m_i \to m_t$ y $m_j \to m_t$ (donde $m_t$ pertenece al mismo paquete).

En caso contrario $F_{ij} = 0$.

Entonces, la fórmula es:

$$ \text{FCPP}(P) = \frac{2 \times \sum_{i < j} F_{ij}}{m \times (m - 1)} $$

#### Implementación del Cálculo:

En `fcpp_analyzer.py`, la conectividad se determina mediante una matriz de alcanzabilidad $R$ (resultado de Floyd-Warshall).

*   Para cada par $i, j$:
    *   Se verifica $R[i][j]$ o $R[j][i]$ (Directa/Indirecta).
    *   Se verifica $\exists t : R[i][t] \land R[j][t]$ (Compartida).
    *   Si cualquiera es verdadero $\implies$ se incrementa el contador de conexiones y se registra el motivo detallado (ej. "Direct + Shared Dependency").

### 2.4 FCPPEvaluator
**Responsabilidad**: Diagnóstico Cualitativo.

Evalúa el score y la topología usando las reglas definidas en `fcpp_rules.json`:

*   **Identificación de Grupos**: Usa un algoritmo DFS (vía `package_utils.find_connected_groups`) para listar los clusters desconectados.
*   **Auditoría de Razones**: El reporte incluye el motivo exacto de la conexión (ej. `Uses: Task, Model... (+2 more)`).

## 3. Flujo de Ejecución

1.  **Discovery**: Identificación de paquetes y sus nodos constituyentes.
2.  **Symbol Table Construction**: Se mapean definiciones (funciones/clases) a sus archivos propietarios.
3.  **Dependency Scanning**: Se detectan importaciones y usos de símbolos para construir la matriz de adyacencia inicial.
4.  **Transitive Closure**: Se calcula la matriz de todos los caminos posibles (Floyd-Warshall).
5.  **Connectivity Analysis**: Se verifica conectividad directa, indirecta y compartida para cada par.
6.  **Scoring & Grouping**: Cálculo final de FCPP y detección de subgrupos aislados.
7.  **Reporting**: Generación de diagnósticos humanos con recomendaciones de refactorización si es necesario.

## 4. Ejemplo Práctico

Para un paquete `src/orchestration` con 3 archivos:

*   `pipeline.py` (Importa y usa `Task` de `task.py`)
*   `task.py` (Define la clase `Task`)
*   `config_loader.py` (Independiente, solo carga YAMLs)

**Análisis**:
1.  **Conexión Pipeline-Task**: `pipeline.py` $\to$ `task.py`. Es una conexión directa. $F_{pip, task} = 1$.
2.  **Aislamiento ConfigLoader**: No llama a nadie ni es llamado por nadie del paquete.

**Cálculo**:
*   $m=3$ nodos. Total pares posibles: $3 \times 2 = 6$.
*   Pares conectados ($F_{ij}=1$): 1 par ({pipeline, task}).
    *   Nota: La fórmula cuenta pares no ordenados, multiplicada por 2. En nuestra implementación sumamos conexiones únicas.
*   **FCPP**: $(2 \times 1) / 6 = 0.33$ (Baja Cohesión).

**Diagnóstico**:
"El paquete tiene baja cohesión funcional (0.33). Contiene 1 nodo aislado (`config_loader.py`) y 1 grupo conectado. Considere mover `config_loader.py` a un paquete de utilidades si no comparte lógica de negocio."
