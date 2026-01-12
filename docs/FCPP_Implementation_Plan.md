# Plan de Implementación: Functional Cohesion of Pipeline Packages (FCPP)

Este documento detalla el análisis y diseño técnico para la nueva métrica FCPP, basándose en la especificación proporcionada.

## 1. Definición y Objetivo

**Métrica**: Functional Cohesion of Pipeline Packages (FCPP).
**Objetivo**: Medir la cohesión funcional de un paquete basándose en las **invocaciones de funciones** (Call Graph) entre sus módulos internos.

A diferencia de SCPP (que mide datos compartidos), FCPP mide **interacción lógica de código**.

## 2. Modelo Matemático

Sea $P$ un paquete con $m$ módulos (archivos `.py` o subpaquetes).
La métrica construye una matriz de conectividad $F_{ij}$ entre cada par de módulos $m_i, m_j$.

### Definición de Nodos (Consistencia con SCPP)
Los nodos $m_i$ del grafo son los **hijos directos** del paquete analizado:
1.  **Archivos**: `script.py` (nodo hoja).
2.  **Subpaquetes**: Directorio `utils/` (nodo agregado).
    *   *Regla de Agregación*: Si un archivo en la raíz llama a `utils/math.py`, se considera una arista hacia el nodo `utils`. Todas las llamadas internas o hacia adentro del subpaquete se colapsan en el nodo padre.

### Condición de Conexión ($F_{ij} = 1$)
Dos nodos están conectados si cumplen **cualquiera** de estas condiciones dentro del mismo paquete:

1.  **Invocación Directa o Indirecta (Cadena de Llamadas)**:
    *   $m_i$ llama a funciones de $m_j$ (directo).
    *   $m_i$ llama a $m_k$ que llama a $m_j$ (indirecto/transitivo).
    *   *Formalmente*: Existe un camino dirigido $m_i \to \dots \to m_j$ O $m_j \to \dots \to m_i$.

2.  **Uso Compartido de un Tercero (Shared Invocation)**:
    *   Ambos utilizan (invocan), directa o indirectamente, un módulo común $m_t$ del mismo paquete.
    *   **Regla**: Existe un camino $m_i \leadsto m_t$ Y existe un camino $m_j \leadsto m_t$.
    *   *Esto implica*: No basta ver las llamadas directas; necesitamos calcular la **Matriz de Alcanzabilidad (Reachability)** completa para verificar si ambos desembocan en la misma utilidad.

### Fórmula FCPP
Es la densidad de este grafo de conexiones funcionales:

$$ FCPP(P) = \frac{2 \times \sum_{i<j} F_{ij}}{m \times (m - 1)} $$

*   Rango: [0, 1].

## 3. LCOM Funcional (Diagnóstico)

Además del puntaje, calculamos el **LCOM de Paquete** basado en este grafo funcional.
Este valor es el número de **Componentes Conectados** en el grafo no dirigido formado por las aristas $F_{ij}$.

*   Si Grupos > 1: El paquete está funcionalmente fragmentado.

## 4. Estrategia de Implementación Técnica

Para implementar esto, necesitamos un analizador (`FCPPAnalyzer`) capaz de construir un **Grafo de Llamadas (Call Graph)** a nivel de archivo.

### Desafío Técnico: Resolución de Nombres
A diferencia de buscar nombres de variables (`df`), aquí debemos saber que cuando `file_a.py` llama a `process_data()`, esa función pertenece realmente a `file_b.py`.

**Algoritmo Propuesto:**

1.  **Paso 1: Tabla de Símbolos (Definiciones)**
    *   Escanear todo el paquete primero.
    *   Crear un mapa: `Function Name -> Defining File`.
    *   *Ejemplo*: `{'calculate_metric': 'src/utils/math.py'}`.

2.  **Paso 2: Análisis de Importaciones y Llamadas**
    *   Para cada archivo, analizar sus `import`.
    *   Analizar nodos `ast.Call`.
    *   Resolver el destino de la llamada:
        *   Si es `utils.calculate_metric()`, buscar `utils` en los imports y resolver ruta.
        *   Si es `calculate_metric()`, ver si fue importada.

3.  **Paso 3: Construcción del Grafo Dirigido ($G_{dir}$)**
    *   Nodos: Archivos.
    *   Aristas: $A \to B$ si A llama a función definida en B.

4.  **Paso 4: Cálculo de Matriz $F_{ij}$**
    *   Para cada par $(i, j)$:
        *   Check Reachability: ¿Existe camino $i \to \dots \to j$ en $G_{dir}$? (BFS/DFS).
        *   Check Reachability Inverso: ¿Existe camino $j \to \dots \to i$ en $G_{dir}$?
        *   Check Common Target: ¿Existe algún $t$ tal que $i \to t$ y $j \to t$?

5.  **Paso 5: Cálculo de Métricas**
    *   Aplicar fórmulas de FCPP y conteo de grupos LCOM.

## 5. Salida y Recomendaciones

El analizador generará mensajes similar a SCPP, pero enfocados en invocación:
*   *Diagnóstico*: "The {modules} do not invoke functions of other modules..."
*   *Recomendación 1 (Mover)*: Si están aislados Y (check SCPP) no comparten datos/modelos $\to$ Moverlos.
*   *Recomendación 2 (Dividir)*: Si hay > 1 grupo funcional que no está conectado estructuralmente $\to$ Dividir paquete.

---
**Siguiente Paso**: ¿Deseas que proceda con la creación del `FCPPAnalyzer` siguiendo esta estrategia?
