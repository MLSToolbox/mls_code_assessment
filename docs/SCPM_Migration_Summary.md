# Migración de SCPM (Structural Cohesion of Pipeline Modules)

**Fecha:** 8 de enero de 2026  
**Estado:** ✅ Completada

## Resumen Ejecutivo

Se ha migrado exitosamente la métrica SCPM desde su implementación básica hacia una versión refinada con:
- Detección explícita de tipos de datos compartidos (variables, archivos)
- Análisis LCOM para detectar grupos desconectados
- Identificación específica de métodos desconectados {f1, ..., fn}
- Sistema de evaluación basado en reglas (14 reglas)
- Diagnóstico granular en 5 niveles con recomendaciones cruzadas a FCPM

## Objetivo de la Migración

Mantener la fórmula LDSC existente pero **refinar qué se considera "compartir datos"**, agregando:
1. Detección explícita de variables globales, constantes y atributos de clase
2. Detección de archivos compartidos (datasets, modelos, configs)
3. Análisis LCOM avanzado para recomendar divisiones de módulos
4. Identificación específica de métodos completamente desconectados
5. Sistema de diagnóstico contextual basado en reglas con recomendaciones cruzadas a FCPM

## Componentes Reutilizados de LCCML

La migración aprovechó componentes robustos del analizador LCCML:

### Métodos Reutilizados:
- ✅ `_is_likely_global_variable()` - Heurística avanzada para detectar variables globales
- ✅ `_get_attribute_path()` - Extrae rutas de atributos (self.x)
- ✅ `_get_files_accessed()` - Detección de archivos con extensiones ML
- ✅ `_extract_methods()` - Extracción de funciones y métodos del AST

### Diferencia Clave SCPM vs LCCML:
- **SCPM:** Solo aspectos **estructurales** → Variables (Mv) + Archivos (Mf)
- **LCCML:** Estructural + **funcional** → Variables + Archivos + Llamadas a métodos (Mc) + Funciones ML (Ml)

## Cambios Implementados

### 1. Nueva Estructura de Archivos

```
src/analyzers/scpm/
├── scpm_evaluator.py      # Evaluador basado en reglas (nuevo)
└── scpm_rules.json         # 12 reglas de diagnóstico (nuevo)
```

### 2. scpm_analyzer.py - Migración Completa

#### Detección de Variables Compartidas (Mejorada)
```python
def _get_variables_accessed(self, method_node: ast.FunctionDef) -> Set[str]:
    """
    Detecta:
    - self.x (atributos de clase)
    - global.VAR (variables globales módulo)
    - global.CONST (constantes UPPERCASE)
    """
```

**Heurísticas aplicadas:**
- UPPERCASE → Constante
- `_private` → Variable global privada
- `self.x` → Atributo de instancia
- Patrones ML comunes: `train_data`, `model_config`, `X_train`, etc.

#### Detección de Archivos Compartidos (Nueva)
```python
def _get_files_accessed(self, method_node: ast.FunctionDef) -> Set[str]:
    """
    Detecta archivos con extensiones ML:
    - Data: .csv, .json, .parquet, .xlsx, .feather, .arrow, etc.
    - Models: .pkl, .h5, .pt, .ckpt, .pb, .onnx, etc.
    - Configs: .yaml, .yml, .ini, .cfg, .toml, etc.
    """
```

Escanea string literals en el código AST y filtra por extensiones relevantes.

#### Análisis LCOM (Nuevo)
```python
def _count_components(self, adjacency: Dict, methods: List) -> int:
    """
    Usa DFS para encontrar componentes desconectados en el grafo de métodos.
    
    Si n_components > 1:
        Módulo contiene X grupos independientes
        → Recomendar dividir en X módulos separados
    """

def _identify_disconnected_methods(self, adjacency: Dict, methods: List) -> List[str]:
    """
    Identifica métodos sin conexiones a ningún otro método.
    
    Retorna lista específica {f1, ..., fn} de funciones desconectadas
    para diagnóstico preciso y recomendaciones dirigidas.
    """
```

#### Clasificación de Tipo de Compartición (Nueva)
```python
def _determine_shared_type(self, shared_vars: Set, shared_files: Set) -> str:
    """
    Retorna:
    - 'class_attributes': >50% son self.x
    - 'global_variables': >50% son variables globales
    - 'files': >50% son archivos
    - 'mixed': Combinación equilibrada
    """
```

### 3. scpm_evaluator.py - Evaluador Basado en Reglas

Similar al patrón de `CCPMEvaluator`:

```python
class SCPMEvaluator:
    """
    Evalúa métricas SCPM contra 14 reglas contextuales.
    
    Considera:
    - cohesion_level: very_low | low | medium | high | very_high
    - n_components: Número de grupos desconectados (LCOM)
    - n_disconnected_methods: Número de métodos sin conexiones
    - disconnected_methods: Lista específica de métodos desconectados
    - shared_variable_count: Conteo de variables compartidas
    - shared_file_count: Conteo de archivos compartidos
    - shared_type: class_attributes | global_variables | files | mixed
    """
```

### 4. scpm_rules.json - 14 Reglas de Diagnóstico

Ejemplos de reglas implementadas:

**Regla 1 - Crítica (n_components > 1):**
```json
{
  "conditions": {
    "cohesion_level": "very_low",
    "n_components": ">1"
  },
  "diagnosis_template": "Very low cohesion with {n_components} disconnected groups",
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
  "diagnosis_template": "Very low cohesion. {disconnected_methods_str} are completely disconnected",
  "recommendation_template": "Review FCPM for {disconnected_methods_str} to determine if they share functional purpose",
  "severity": "critical"
}
```

**Regla 8 - Información (OOP bien hecho):**
```json
{
  "conditions": {
    "cohesion_level": "high",
    "shared_type": "class_attributes"
  },
  "diagnosis_template": "High cohesion through class attributes",
  "recommendation_template": "Excellent OOP principles with shared instance state",
  "severity": "info"
}
```

### 5. Niveles de Cohesión Granulares (5 niveles)

| Rango | Nivel | Descripción |
|-------|-------|-------------|
| [0.8-1.0] | very_high | Casi todos los pares comparten datos |
| [0.6-0.8) | high | Fuerte compartición de datos |
| [0.4-0.6) | medium | Compartición moderada |
| [0.2-0.4) | low | Conexiones débiles |
| [0.0-0.2) | very_low | Métodos independientes |

### 6. Métricas Exportadas

```python
file_result = {
    "scpm": 0.75,                              # Cohesión estructural [0-1]
    "cohesion_level": "high",                  # very_low|low|medium|high|very_high
    "n_methods": 8,
    "n_components": 1,                         # Grupos desconectados (LCOM)
    "n_disconnected_methods": 0,               # Métodos sin conexiones
    "disconnected_methods": [],                # Lista específica de métodos desconectados
    "shared_variable_count": 5,
    "shared_file_count": 2,
    "shared_vars": ["self.model", "CONFIG"],
    "shared_files": ["train_data.csv"],
    "shared_type": "mixed"
}
```

```python
{
    'scpm': float,                     # Valor 0.0-1.0
    'n_methods': int,                  # Total de métodos
    'n_possible_pairs': int,           # n*(n-1)/2
    'n_shared_pairs': int,             # Pares que comparten datos
    'cohesion_level': str,             # very_low | low | medium | high | very_high
    'n_components': int,               # Grupos desconectados (LCOM)
    'shared_variable_count': int,      # Total de variables compartidas
    'shared_file_count': int,          # Total de archivos compartidos
    'shared_vars': List[str],          # Top 10 variables
    'shared_files': List[str],         # Top 10 archivos
    'shared_type': str,                # class_attributes | global_variables | files | mixed
    'breakdown': {
        'pairs_via_variables': int,
        'pairs_via_files': int
    }
}
```

## Documentación Actualizada

### registry.py
- ✅ Fórmula detallada con pasos de cálculo
- ✅ Explicación de qué se considera "compartir"
- ✅ Documentación de 5 niveles de cohesión
- ✅ Referencia al análisis LCOM

### metricas_modulos.md
- ✅ Sección SCPM completamente reescrita
- ✅ Tabla de 5 niveles granulares
- ✅ Explicación de análisis LCOM
- ✅ Diferenciación clara con LCCML
- ✅ Recomendaciones contextuales de refactorización

## Validación

### Consistencia con CCPM Migration Pattern

| Aspecto | CCPM | SCPM |
|---------|------|------|
| Evaluador basado en reglas | ✅ | ✅ |
| Archivo JSON de reglas | ✅ | ✅ |
| 5 niveles cualitativos | ✅ | ✅ |
| Métricas enriquecidas | ✅ | ✅ |
| Diagnósticos contextuales | ✅ | ✅ |
| Documentación detallada | ✅ | ✅ |

### Testing Recomendado

```bash
# Test básico de análisis
POST /api/analyze
{
  "analyzers": ["scpm"],
  "files": ["src/example_module.py"]
}

# Verificar métricas retornadas:
- scpm value (0.0-1.0)
- n_components (LCOM)
- shared_vars/shared_files
- Diagnóstico con severity y rule_id
```

## Beneficios de la Migración

1. **Detección Explícita:**
   - Claridad sobre qué tipos de datos se comparten
   - Distinción entre self.x, globals y archivos

2. **Análisis LCOM:**
   - Detecta módulos que deberían dividirse
   - Recomienda número exacto de módulos target

3. **Diagnósticos Contextuales:**
   - 12 reglas cubren todos los escenarios
   - Mensajes específicos según tipo de problema

4. **Granularidad Mejorada:**
   - 5 niveles vs 3 niveles anteriores
   - Mejor mapeo a acciones de refactorización

5. **Consistencia Arquitectónica:**
   - Mismo patrón que CCPM
   - Reutilización de código probado (LCCML)

## Próximos Pasos

- [x] ✅ Migración completada
- [x] ✅ Identificación de métodos desconectados implementada
- [x] ✅ Recomendaciones cruzadas con FCPM agregadas
- [ ] 🔄 Testing en código real de ML pipelines
- [ ] 📊 Validar heurísticas de detección de globales
- [ ] 🔍 Refinar reglas según feedback de uso

## Notas Técnicas

### Por qué SCPM ≠ LCCML

**SCPM (Structural):**
```
P_ij = 1 IF shared_vars OR shared_files
```

**LCCML (Structural + Functional):**
```
P_ij = 1 IF shared_vars OR shared_files OR method_calls OR ml_functions
```

SCPM es subset de LCCML, enfocado únicamente en cohesión de datos.

### Decisiones de Diseño

1. **¿Por qué detectar archivos?**
   - ML pipelines operan sobre datasets y modelos persistidos
   - Compartir `"train_data.csv"` es tan relevante como compartir `self.data`

2. **¿Por qué LCOM analysis?**
   - Detecta el anti-pattern de "Dios módulos" con grupos independientes
   - Proporciona recomendación accionable: dividir en X módulos

3. **¿Por qué 5 niveles?**
   - Mapeo más preciso a severidad de problemas
   - Alineación con CCPM (consistencia)

## Conclusión

La migración de SCPM fue exitosa, manteniendo la fórmula LDSC existente pero agregando:
- ✅ Detección explícita y robusta de datos compartidos
- ✅ Análisis LCOM para detectar anti-patterns
- ✅ Identificación específica de métodos desconectados {f1, ..., fn}
- ✅ Sistema de evaluación basado en 14 reglas
- ✅ Diagnóstico granular en 5 niveles
- ✅ Recomendaciones cruzadas con FCPM para métodos desconectados
- ✅ Documentación exhaustiva con ejemplos de cálculo
- ✅ Consistencia arquitectónica con CCPM

La métrica ahora proporciona insights accionables sobre la cohesión estructural de módulos ML, identificando específicamente qué métodos requieren revisión funcional mediante FCPM.
