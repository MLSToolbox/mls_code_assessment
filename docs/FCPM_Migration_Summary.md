# Migración de FCPM (Functional Cohesion of Pipeline Modules)

**Fecha:** 8 de enero de 2026  
**Estado:** ✅ Completada

## Resumen Ejecutivo

Se ha migrado exitosamente la métrica FCPM desde su implementación básica hacia una versión refinada con:
- Detección explícita de invocaciones directas e indirectas
- Análisis LCOM para detectar grupos funcionalmente desconectados
- Identificación específica de métodos desconectados {f1, ..., fn}
- Sistema de evaluación basado en reglas (14 reglas)
- Diagnóstico granular en 5 niveles con recomendaciones cruzadas a SCPM

## Objetivo de la Migración

Mantener la fórmula FCPM existente pero **formalizar la detección de invocaciones**, agregando:
1. Detección robusta de invocaciones directas mediante análisis AST
2. Detección de invocaciones indirectas (a través de tercero común)
3. Construcción de call graph completo del módulo
4. Análisis LCOM avanzado para recomendar divisiones de módulos
5. Identificación específica de métodos completamente desconectados
6. Sistema de diagnóstico contextual basado en reglas con recomendaciones cruzadas a SCPM

## Diferencia Clave: Implementación Anterior vs Migrada

### Implementación Anterior:
- Invocaciones directas: `f_i → f_j` o `f_j → f_i`
- Data flow (producer-consumer): `writes(f_i) ∩ reads(f_j) ≠ ∅`
- Fórmula: `connected_pairs / total_pairs`

### Implementación Migrada (Especificación):
- **Invocaciones directas:** `f_i → f_j` o `f_j → f_i` (mejorado)
- **Invocaciones indirectas:** Ambas funciones llaman a un tercero común `f_t` del mismo módulo
- **Fórmula formal:** `FCPM = (2 × Σi<j F_ij) / (n × (n-1))`
- **Eliminado:** Data flow producer-consumer (redundante con SCPM)
- **Agregado:** Call graph, LCOM funcional, métodos desconectados

## Componentes Reutilizados de LCCML

La migración aprovechó componentes robustos del analizador LCCML:

### Métodos Reutilizados:
- ✅ `_extract_methods()` - Extracción de funciones y métodos del AST
- ✅ `_get_method_calls()` - Base para detección de invocaciones directas
- ✅ `_get_function_name()` - Extracción de nombres de funciones en nodos Call
- ✅ `_get_attribute_path()` - Resolución de rutas como `self.method`

### Diferencia Clave FCPM vs LCCML:
- **FCPM:** Solo aspectos **funcionales** → Invocaciones directas + indirectas
- **LCCML:** Funcional + **estructural** → Invocaciones + Variables + Archivos + Funciones ML

## Cambios Implementados

### 1. Nueva Estructura de Archivos

```
src/analyzers/fcpm/
├── __init__.py             # Package initialization
├── fcpm_analyzer.py        # Analizador migrado (nuevo)
├── fcpm_evaluator.py       # Evaluador basado en reglas (nuevo)
└── fcpm_rules.json         # 14 reglas de diagnóstico (nuevo)
```

### 2. fcpm_analyzer.py - Migración Completa

#### Construcción de Call Graph (Nueva)
```python
def _build_call_graph(self, methods: Dict[str, ast.FunctionDef]) -> Dict[str, List[str]]:
    """
    Construye un grafo de invocaciones mostrando qué métodos llaman a cuáles.
    
    Retorna:
        {method_name: [lista de métodos que invoca]}
    """
```

**Detecta:**
- Llamadas directas: `my_function()`
- Llamadas a métodos: `self.my_method()`
- Llamadas cualificadas: `ClassName.method_name()`

#### Detección de Invocaciones Indirectas (Nueva)
```python
for (f_i, f_j) in all_pairs:
    # Directa
    if f_j in call_graph[f_i] or f_i in call_graph[f_j]:
        F_ij = 1
        direct_invocations += 1
    else:
        # Indirecta: ambas llaman a un tercero común del mismo módulo
        calls_a = set(call_graph[f_i])
        calls_b = set(call_graph[f_j])
        common_callees = calls_a & calls_b & set(method_names)
        
        if common_callees:
            F_ij = 1
            indirect_invocations += 1
```

**Restricción clave:** El tercero común `f_t` debe estar en el mismo módulo/clase.

#### Análisis LCOM Funcional (Nuevo)
```python
def _count_components(self, adjacency: Dict, methods: List) -> int:
    """
    Usa DFS para encontrar componentes funcionalmente desconectados.
    
    Si n_components > 1:
        Módulo contiene X flujos funcionales independientes
        → Recomendar dividir en X módulos separados
    """

def _identify_disconnected_methods(self, adjacency: Dict, methods: List) -> List[str]:
    """
    Identifica métodos sin conexiones funcionales.
    
    Retorna lista específica {f1, ..., fn} de funciones desconectadas
    para diagnóstico preciso y recomendaciones dirigidas.
    """
```

#### Breakdown de Invocaciones (Nuevo)
```python
'breakdown': {
    'direct_invocations': 7,      # f_i → f_j directamente
    'indirect_invocations': 3,    # ambas llaman a f_t común
}
```

Proporciona insights sobre patrones de invocación (uso de helpers vs colaboración directa).

### 3. fcpm_evaluator.py - Evaluador Basado en Reglas

Similar al patrón de `CCPMEvaluator` y `SCPMEvaluator`:

```python
class FCPMEvaluator:
    """
    Evalúa métricas FCPM contra 14 reglas contextuales.
    
    Considera:
    - cohesion_level: very_low | low | medium | high | very_high
    - n_components: Número de grupos funcionalmente desconectados (LCOM)
    - n_disconnected_methods: Número de métodos sin invocaciones
    - disconnected_methods: Lista específica de métodos desconectados
    - breakdown: {direct_invocations, indirect_invocations}
    """
```

### 4. fcpm_rules.json - 14 Reglas de Diagnóstico

Ejemplos de reglas implementadas:

**Regla 1 - Crítica (n_components > 1):**
```json
{
  "conditions": {
    "cohesion_level": "very_low",
    "n_components": ">1"
  },
  "diagnosis_template": "Critical - {n_components} disconnected functional groups",
  "recommendation_template": "Split into {n_components} separate modules",
  "severity": "critical"
}
```

**Regla 2 - Crítica con métodos desconectados (Nueva):**
```json
{
  "conditions": {
    "cohesion_level": "very_low",
    "n_disconnected_methods": ">0"
  },
  "diagnosis_template": "{disconnected_methods_str} are completely disconnected",
  "recommendation_template": "Review SCPM for {disconnected_methods_str} to determine if they share data",
  "severity": "critical"
}
```

**Regla 8 - Información (uso de helpers):**
```json
{
  "conditions": {
    "cohesion_level": "medium",
    "indirect_invocations": ">0"
  },
  "diagnosis_template": "Connected through {indirect_invocations} indirect invocations via helpers",
  "recommendation_template": "Good use of helper functions",
  "severity": "info"
}
```

### 5. Niveles de Cohesión Granulares (5 niveles)

| Rango | Nivel | Descripción |
|-------|-------|-------------|
| [0.8-1.0] | very_high | Casi todos los pares se invocan |
| [0.6-0.8) | high | Fuerte colaboración funcional |
| [0.4-0.6) | medium | Relaciones funcionales moderadas |
| [0.2-0.4) | low | Conexiones funcionales débiles |
| [0.0-0.2) | very_low | Métodos operan independientemente |

### 6. Métricas Exportadas

```python
file_result = {
    "fcpm": 0.65,                              # Cohesión funcional [0-1]
    "cohesion_level": "high",                  # very_low|low|medium|high|very_high
    "n_methods": 8,
    "n_possible_pairs": 28,
    "n_connected_pairs": 18,
    "n_components": 1,                         # Grupos funcionalmente desconectados (LCOM)
    "n_disconnected_methods": 0,               # Métodos sin invocaciones
    "disconnected_methods": [],                # Lista específica de métodos desconectados
    "call_graph": {
        "prepare_data": ["load_model", "preprocess"],
        "train_model": ["load_model", "evaluate"],
        "load_model": [],
        "preprocess": [],
        "evaluate": []
    },
    "connected_pairs": [
        ["prepare_data", "load_model"],
        ["prepare_data", "preprocess"],
        ["train_model", "load_model"],
        # ...
    ],
    "breakdown": {
        "direct_invocations": 15,              # Invocaciones directas f_i → f_j
        "indirect_invocations": 3              # Invocaciones indirectas vía f_t común
    }
}
```

## Ventajas de la Migración

1. **Detección Formalizada:**
   - Invocaciones directas e indirectas claramente definidas
   - Call graph explícito para análisis detallado
   - Restricción de tercero común al mismo módulo (evita false positives)

2. **Eliminación de Data Flow Producer-Consumer:**
   - Redundante con SCPM (que mide compartición de datos)
   - FCPM ahora es puramente funcional (invocaciones)
   - Separación clara de responsabilidades entre métricas

3. **Breakdown Detallado:**
   - Insights sobre patrones de diseño (helpers vs colaboración directa)
   - Facilita diagnósticos específicos

4. **LCOM Funcional:**
   - Detecta módulos con flujos funcionales independientes
   - Recomendaciones accionables (dividir en X módulos)

5. **Recomendaciones Cruzadas:**
   - FCPM ↔ SCPM: Distinguir cohesión funcional vs estructural
   - Si FCPM bajo Y SCPM bajo → mover métodos
   - Si FCPM bajo pero SCPM alto → mantener, mejorar colaboración

6. **Consistencia Arquitectónica:**
   - Mismo patrón que CCPM y SCPM
   - Sistema de reglas JSON reutilizable
   - 5 niveles de diagnóstico granular

## Próximos Pasos

- [x] ✅ Migración completada
- [x] ✅ Identificación de métodos desconectados implementada
- [x] ✅ Recomendaciones cruzadas con SCPM agregadas
- [x] ✅ Breakdown de invocaciones (directas vs indirectas)
- [ ] 🔄 Testing en código real de ML pipelines
- [ ] 📊 Validar heurísticas de detección de invocaciones
- [ ] 🔍 Refinar reglas según feedback de uso

## Notas Técnicas

### Por qué Eliminar Producer-Consumer

**Implementación anterior:**
```python
# Consideraba data flow como conexión funcional
writes_a & reads_b ≠ ∅  →  F_ij = 1
```

**Problema:** Redundancia con SCPM (que ya mide compartición de datos).

**Solución migrada:**
- FCPM: Solo invocaciones (funcional puro)
- SCPM: Solo datos compartidos (estructural puro)
- Separación clara de responsabilidades

### Por qué Invocaciones Indirectas

Detecta patrones de diseño comunes en ML:

```python
# Ambas funciones usan la misma función helper
def prepare_data():
    data = load_config()  # helper común
    # ...

def train_model():
    config = load_config()  # helper común
    # ...

# F_ij = 1 aunque no se llamen directamente
# Evidencia de propósito funcional compartido
```

### Decisiones de Diseño

1. **¿Por qué call graph explícito?**
   - Facilita análisis de invocaciones indirectas
   - Proporciona información valiosa para debugging
   - Permite extensiones futuras (análisis de flujo de control)

2. **¿Por qué LCOM funcional?**
   - Detecta "God modules" con flujos funcionales independientes
   - Proporciona recomendación accionable: dividir en X módulos

3. **¿Por qué restringir tercero común al mismo módulo?**
   - Evita false positives (invocaciones a librerías externas)
   - Garantiza que la conexión sea realmente local al módulo

4. **¿Por qué 5 niveles?**
   - Mapeo más preciso a severidad de problemas
   - Alineación con CCPM y SCPM (consistencia)

## Conclusión

La migración de FCPM fue exitosa, manteniendo la fórmula existente pero agregando:
- ✅ Detección formalizada de invocaciones directas e indirectas
- ✅ Construcción de call graph explícito
- ✅ Análisis LCOM funcional para detectar anti-patterns
- ✅ Identificación específica de métodos desconectados {f1, ..., fn}
- ✅ Sistema de evaluación basado en 14 reglas
- ✅ Diagnóstico granular en 5 niveles
- ✅ Recomendaciones cruzadas con SCPM para métodos desconectados
- ✅ Breakdown de invocaciones (directas vs indirectas)
- ✅ Eliminación de data flow producer-consumer (ahora en SCPM)
- ✅ Documentación exhaustiva con ejemplos de cálculo
- ✅ Consistencia arquitectónica con CCPM y SCPM

La métrica ahora proporciona insights accionables sobre la cohesión funcional de módulos ML, distinguiendo claramente entre colaboración directa e indirecta, e identificando específicamente qué métodos requieren revisión estructural mediante SCPM.
