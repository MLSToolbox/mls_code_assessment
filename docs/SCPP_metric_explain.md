# Documentación de SCPP y P-LCOM

Este documento detalla la implementación técnica, las decisiones de diseño y la fundamentación académica para la métrica de cohesión **SCPP** (Structural Coupling Package Pipeline) y su métrica de apoyo **P-LCOM** (Package Level Lack of Cohesion of Modules).

**Nota Importante**: Aunque P-LCOM es una métrica por derecho propio, en este sistema se ha implementado principalmente como una **herramienta de diagnóstico para SCPP**. Su función es identificar grupos desconectados (fragmentación) para que SCPP pueda ofrecer recomendaciones precisas de refactorización (división de paquetes) cuando la cohesión estructural es baja.

## 1. Visión General: Análisis Basado en Recursos de Pipeline

Ambas métricas comparten un núcleo común: evalúan la estructura del código basándose en cómo se comparten los recursos críticos del pipeline de Machine Learning (ML). A diferencia de las métricas de acoplamiento tradicionales (llamadas a función), aquí nos enfocamos en el **Flujo de Datos**.

### ¿Qué se considera un "Recurso de Pipeline"?
Un recurso no es cualquier variable. Para que una métrica de ML sea relevante, nos enfocamos en:
*   **Datos**: DataFrames, tensores, batches, loaders (`df`, `X_train`, `loader`).
*   **Modelos**: Estimadores, redes neuronales, pesos (`model`, `clf`, `weights`, `RandomForestClassifier`).
*   **Configuración**: Hiperparámetros, settings globales (`config`, `params`, `mlruns`).
*   **Archivos**: Referencias físicas a datasets o artefactos (`data.csv`, `model.pkl`).

**Decisión de Diseño**: La detección de estos recursos se centralizó en una clase base abstracta (`PipelineGraphBaseAnalyzer`). Esto asegura el principio de "Single Source of Truth": tanto SCPP como P-LCOM operan sobre *exactamente* el mismo grafo de dependencias, garantizando la consistencia matemática de los resultados.

---

## 2. SCPP (Structural Coupling Package Pipeline)

### Propósito
Medir la **densidad cohesiva** dentro de un paquete. Responde a la pregunta: *"¿Qué tan fuertemente interconectados están los componentes de este paquete a través de sus datos?"*.

### Fórmula
Se basa en el **Cierre Transitivo**. Si A comparte datos con B, y B con C, se considera que $\{A, B, C\}$ forman un grupo cohesivo.

\[
SCPP(P) = \frac{2 \times \sum_{g \in Grupos} \frac{|g|(|g|-1)}{2}}{m(m-1)}
\]

Donde:
*   \(m\): Número total de nodos (archivos/subpaquetes).
*   \(Grupos\): Conjunto de componentes conectados.
*   \(|g|\): Tamaño de cada componente.
*   El numerador suma todos los pares posibles dentro de cada componente (tratándolos como cliques).

## 3. P-LCOM (Package Lack of Cohesion of Modules)

### Propósito
Actuar como métrica de **apoyo diagnóstico** para SCPP. Mientras SCPP nos dice *qué tan denso* es el grafo (0 a 1), P-LCOM nos dice *si el grafo está roto en pedazos* (conteo entero).

Esta distinción es crucial para la recomendación automática:
*   **P-LCOM = 1**: Alta cohesión (todos los nodos forman un único grupo conectado).
*   **P-LCOM > 1**: Baja cohesión (hay "islas" funcionales desconectadas). Se recomienda dividir el paquete.

### Definición
\[
P-LCOM(P) = \text{Número de Componentes Conectados en el Grafo}
\]

---

## 4. Decisión Clave de Arquitectura: ¿Por qué una Clase Base?

Una de las decisiones más importantes en este diseño fue la creación de `PipelineGraphBaseAnalyzer` como ancestro común, en lugar de duplicar lógica o usar composición simple. Esta relación de herencia (`SCPPAnalyzer` hereda de `PipelineGraphBaseAnalyzer`) se justifica por tres pilares de ingeniería:

1.  **Consistencia Garantizada (Single Source of Truth)**
    *   **Problema**: Si SCPP y P-LCOM usaran lógicas separadas para detectar recursos, podrían contradecirse (ej: SCPP dice que dos archivos están conectados, pero P-LCOM dice que son componentes distintos).
    *   **Solución**: Al heredar, ambas métricas ven *exactamente* el mismo grafo. Si actualizamos la detección para soportar archivos `.h5`, ambas métricas se benefician instantáneamente y permanecen sincronizadas matemáticamente.

2.  **Mantenibilidad y DRY (Don't Repeat Yourself)**
    *   La lógica de "Fingerprinting" (sección 5.2) es compleja: implica recorrer árboles sintácticos (AST), aplicar heurísticas de contexto, limpiar rutas de sistema de archivos y filtrar blacklists.
    *   Duplicar este código en varios analizadores sería un riesgo de deuda técnica inaceptable. La herencia centraliza la complejidad en un solo punto de fallo y mejora.

3.  **Optimización de Rendimiento**
    *   El análisis estático (leer disco, parsear AST) es la operación más costosa del sistema.
    *   Al centralizar la construcción del grafo, optimizamos el recorrido del sistema de archivos y la construcción de la matriz de adyacencia (operación \(O(m^2)\)) en una implementación altamente optimizada.

---

## 5. Detalles Técnicos (Código Real Implementado)

A continuación se expone la lógica crítica implementada en `src/analyzers/pipeline_graph_base.py`.

### 5.1 Construcción del Grafo (`_analyze_package_graph`)
Este método construye la matriz de adyacencia y calcula los componentes conectados usando DFS.

*Ubicación: `src/analyzers/pipeline_graph_base.py`*

```python
    def _analyze_package_graph(self, package_path: str) -> Dict[str, Any]:
        # 1. Identificación de Nodos (ignorando __pycache__, tests, etc.)
        nodes = self._get_package_nodes(package_path)
        m = len(nodes)
        
        # ... (Validación mínima m < 2) ...

        # 2. Extracción de Recursos ("Fingerprinting")
        node_resources = {}
        for node_path in nodes:
            if os.path.isdir(node_path):
                resources = self._get_subpackage_resources(node_path) # Recursivo
            else:
                resources = self._extract_file_resources(node_path)   # Análisis AST
            node_resources[node_path] = resources

        # 3. Construcción de Conexiones (Comparación Pares O(m^2))
        connections = []
        for i in range(len(node_list)):
            for j in range(i + 1, len(node_list)):
                # ...
                # Criterio: Intersección no vacía de recursos
                intersection = res_a.intersection(res_b)
                if intersection:
                    connections.append({...})

        # 4. Cálculo de Componentes Conectados (DFS)
        # ... (Algoritmo estándar de búsqueda en profundidad para encontrar 'islas') ...
        
        return { 'groups': groups, 'connections': connections, ... }
```

### 5.2 Extracción Inteligente de Recursos (`_extract_file_resources`)

Esta es la parte más sofisticada. No solo busca nombres, sino que analiza el **contexto** y la **semántica**.

*Ubicación: `src/analyzers/pipeline_graph_base.py`*

#### A. Filtrado de Contexto para `df` y `data`
Evitamos falsos positivos ignorando variables locales genéricas. Solo aceptamos si son parte de la "Interfaz" del código.

```python
            # 1. Direct Variables
            if isinstance(node, ast.Name):
                # FIX: 'df' and 'data' are very common as local variables.
                # We only accept them if they come from 'strong' contexts (args, return, self).
                if node.id in ['df', 'data']:
                    continue
                if self._is_pipeline_resource(node.id): 
                    resources.add(node.id)
```

#### B. Detección Semántica de Modelos
Detectamos instanciación y carga de modelos, no solo variables llamadas "model".

```python
                # 8. Semantic Model Detection (Instantiations & Loading)
                # A. Detect Model Instantiation (e.g. RandomForestClassifier())
                if isinstance(node.func, ast.Name):
                    if any(mc in node.func.id for mc in ['Classifier', 'Regressor', 'Model', ...]):
                         resources.add(node.func.id)

                # B. Detect Model Loading (specific functions like joblib.load)
                if full_func_name in ['load_model', 'joblib.load', ...]:
                     if node.args and isinstance(node.args[0], ast.Constant):
                         # Extract filename robustly
                         val = node.args[0].value
                         base_name = val.replace('\\', '/').split('/')[-1]
                         resources.add(f"model:{base_name}")
```

#### C. Artefactos y URIs (String Literals)
Detectamos referencias a archivos (`.csv`, `.pkl`) y URIs de MLflow (`mlruns`), normalizando rutas.

```python
                # Helper to process potentail file/URI strings
                def _process_str_arg(val_str):
                    # 1. Extensions check (.csv, .parquet, .pkl, .h5, .joblib)
                    if val_str.endswith(...): return get_robust_basename(val_str)
                    
                    # 2. MLflow / URI check (file:, s3:, mlruns)
                    if 'mlruns' in val_str or val_str.startswith(...):
                        return get_robust_basename(clean_val)
```

### 5.3 Agregación Recursiva de Paquetes
Para soportar arquitecturas complejas (ej: carpetas `src` que contienen lógica pero no `__init__.py` directo), la detección de nodos es recursiva.

```python
    def _is_package(self, dir_path: str) -> bool:
        # Un directorio es paquete si contiene algún .py en su árbol
        for _,_,files in os.walk(dir_path):
            if any(f.endswith(".py") for f in files):
                return True
        return False
```

---

## 6. Interpretación de Resultados

| Métrica | Valor | Interpretación | Acción Recomendada |
| :--- | :--- | :--- | :--- |
| **SCPP** | 0.8 - 1.0 | **Muy Alta**. Cohesión excelente. | Ninguna. Mantener estructura. |
| **SCPP** | < 0.4 | **Baja**. Fragmentación significativa. | Revisar P-LCOM para refactorizar. |
| **P-LCOM** | 1 | Paquete Unificado. | - |
| **P-LCOM** | > 1 | **Paquete Fragmentado**. | **Dividir el paquete**. Existen \(N\) grupos disjuntos que no comparten recursos. |

### Ejemplo de Salida Automática (Estructura Real JSON)
```json
{
    "packages": {
        "src\\training": {
            "connections": [
                {
                    "node_a": "promote_latest_model.py",
                    "node_b": "train.py",
                    "shared_resources": ["model_name", "mlruns"]
                }
            ],
            "groups": [
                ["promote_latest_model.py", "train.py"]
            ],
            "isolated_nodes": [],
            "n_nodes": 2,
            "n_pairs": 1,
            "n_shared": 1,
            "nodes": ["promote_latest_model.py", "train.py"],
            "scpp": 1.0,
            "valid": true
        }
    },
    "summary": {
        "average_scpp": 1.0,
        "very_high": 1,
        "total_packages": 1
    }
}
```
