# Análisis de Cohesión de Código - LCCML

## Resumen Ejecutivo

Este documento explica cómo funciona el análisis de cohesión de módulos Python en proyectos de Machine Learning, específicamente la métrica **LCCML (Loose Class Cohesion Modified for ML)**.

---

## 1. ¿Qué es la Cohesión?

La **cohesión** mide qué tan relacionadas están las funciones dentro de un módulo de código. 

- **Cohesión Alta (0.8-1.0)**: Las funciones trabajan juntas y comparten recursos. Código bien organizado.
- **Cohesión Baja (0.0-0.4)**: Funciones desconectadas que hacen cosas no relacionadas. Indica que el módulo debería dividirse.

---

## 2. ¿Cómo Trata los Archivos Python?

### Estructura NO Basada en Clases

El análisis **NO considera la estructura de clases**. Trata todos los métodos y funciones como elementos individuales del módulo.

### Comportamiento según Tipo de Código

#### ✅ Archivo con Funciones Sueltas
```python
# modulo.py
def funcion_a(param1, param2):
    data = pd.read_csv('data.csv')
    return data

def funcion_b(param2, param3):
    result = np.array([1,2,3])
    return result
```
**Resultado**: Analiza ambas funciones. Si comparten parámetros (`param2`), se consideran conectadas.

#### ✅ Archivo con Clases
```python
# modulo.py
class MiClase:
    def __init__(self):
        self.data = None
    
    def metodo_a(self, param1):
        self.data = pd.read_csv('file.csv')
    
    def metodo_b(self):
        return self.data
```
**Resultado**: Analiza los métodos individualmente (`__init__`, `metodo_a`, `metodo_b`). Los conecta si comparten variables de instancia (`self.data`).

**⚠️ Limitación**: No sabe que pertenecen a la misma clase.

#### ❌ Archivo con Código Suelto (sin funciones)
```python
# script.py
import pandas as pd
data = pd.read_csv('data.csv')
print(data.head())
```
**Resultado**: **NO se analiza**. El código fuera de funciones se ignora completamente.

---

## 3. ¿Cómo Determina si Dos Métodos Están Conectados?

### Proceso en 4 Pasos

#### **Paso 1: Recolección de Elementos por Función**

Para cada función, identifica 3 tipos de elementos:

```python
{
    'funcion_a': [
        'self.model',      # ← Variables de instancia
        'data.csv',        # ← Archivos no-Python
        'pd.read_csv',     # ← Llamadas a librerías ML
        'sklearn.fit'
    ],
    'funcion_b': [
        'self.model',      # ← COMPARTEN self.model
        'config.json',
        'np.array'
    ]
}
```

#### **Paso 2: Construcción del Grafo**

Invierte el diccionario para identificar qué funciones usan cada elemento:

```python
parameter_to_functions = {
    'self.model':  {'funcion_a', 'funcion_b'},  # ← AMBAS lo usan
    'data.csv':    {'funcion_a'},
    'config.json': {'funcion_b'},
    'pd.read_csv': {'funcion_a'},
    'np.array':    {'funcion_b'}
}

# Conecta funciones que comparten AL MENOS 1 elemento
graph = {
    'funcion_a': {'funcion_b'},  # ← CONECTADAS por self.model
    'funcion_b': {'funcion_a'}
}
```

**Regla Clave**: Dos funciones están conectadas si comparten **al menos 1 elemento** (variable, archivo o librería).

#### **Paso 3: Búsqueda de Alcanzabilidad (DFS)**

Para cada función, encuentra todas las funciones alcanzables (directa o indirectamente):

```python
# Ejemplo: A ↔ B ↔ C    D (aislada)

reachable = {
    'A': ['A', 'B', 'C'],  # A alcanza C a través de B
    'B': ['B', 'A', 'C'],  
    'C': ['C', 'B', 'A'],
    'D': ['D']              # D solo se alcanza a sí misma
}
```

#### **Paso 4: Cálculo de Cohesión**

```python
# Cuenta pares de funciones que están conectadas
pares_conectados = 3  # (A,B), (A,C), (B,C)
pares_posibles = 6    # 4 funciones = 4×3/2 = 6 pares

Cohesión = pares_conectados / pares_posibles = 3/6 = 0.5
```

### Criterios de Conexión

✅ **Dos métodos SE conectan si comparten**:
1. La misma variable de instancia (`self.variable`)
2. El mismo archivo de datos (`'data.csv'`, `'model.pkl'`)
3. La misma librería ML (detectada por: `pd`, `np`, `sklearn`, `torch`, `tf`, etc.)

❌ **NO se conectan por**:
- Llamarse directamente entre sí
- Estar en la misma clase
- Usar variables locales con el mismo nombre
- Tener parámetros con nombres similares (sin relación real)

---

## 4. Ejemplo Completo

### Código de Entrada
```python
class ModelPipeline:
    def __init__(self):
        self.data = None      # ← Variable compartida 1
        self.scaler = None    # ← Variable compartida 2
    
    def load(self):
        self.data = pd.read_csv('x.csv')  # ← Usa: self.data, pd
    
    def preprocess(self):
        self.scaler = StandardScaler()    # ← Usa: self.scaler, sklearn
        self.data = self.scaler.fit(self.data)  # ← Usa: self.data, self.scaler
    
    def predict(self, x):
        return self.scaler.transform(x)   # ← Usa: self.scaler
```

### Análisis Paso a Paso

**1. Elementos por Función:**
```
__init__:     ['self.data', 'self.scaler']
load:         ['self.data', 'pd.read_csv']
preprocess:   ['self.scaler', 'self.data', 'StandardScaler']
predict:      ['self.scaler']
```

**2. Grafo de Conexiones:**
```
__init__ ↔ load        (comparten self.data)
__init__ ↔ preprocess  (comparten self.data y self.scaler)
__init__ ↔ predict     (comparten self.scaler)
load     ↔ preprocess  (comparten self.data)
preprocess ↔ predict   (comparten self.scaler)
```

**3. Alcanzabilidad:**
Todas las funciones son alcanzables entre sí (grafo completamente conectado).

**4. Resultado:**
- **Pares posibles**: 4 funciones = 6 pares
- **Pares conectados**: 6 (todos)
- **Cohesión**: 6/6 = **1.0** (máxima cohesión)

---

## 5. Nuestra Implementación LCCML vs Código Original

### Ventajas de Nuestra Implementación

| Aspecto | Código Original | Nuestra LCCML | Explicación de la Ventaja |
|---------|----------------|---------------|--------------------------|
| **Llamadas directas** | No detecta llamadas entre funciones (ej: `funcion_a()` llama a `funcion_b()`) | Detecta y registra como conexión (Mc) todas las llamadas directas entre métodos del módulo | Crítico para detectar flujo de ejecución en ML pipelines. Sin esto, funciones que forman un pipeline secuencial (load → preprocess → train) aparecen como desconectadas aunque sean parte del mismo flujo. |
| **Nivel de análisis** | Analiza funciones individuales sin considerar contexto de archivo | Analiza a nivel de módulo completo, considerando todas las funciones como parte de una unidad cohesiva | Más apropiado para evaluar organización de código. Un módulo debe tener funciones relacionadas trabajando juntas, no funciones aisladas. |
| **Falsos positivos** | Conecta funciones que tienen parámetros con el mismo nombre aunque sean objetos diferentes sin relación (ej: dos funciones con parámetro `model` que refieren a modelos distintos) | Reduce falsos positivos al analizar el contexto del módulo y enfocarse en variables de instancia compartidas (`self.x`) y llamadas explícitas | Mayor precisión en la detección de conexiones reales. Evita inflar artificialmente la cohesión por coincidencias de nombres. |
| **Adaptación ML** | Métrica genérica de cohesión sin consideración especial para patrones de Machine Learning | Específicamente diseñada para ML: prioriza detección de archivos de datos/modelos, uso de librerías ML (sklearn, tensorflow, pandas), y patrones de pipeline (ETL, entrenamiento, evaluación) | Mejor para nuestro dominio. Detecta patrones específicos de ML como carga de datasets, transformaciones de datos, entrenamiento de modelos, y serialización de artefactos. |
| **Archivos de modelos** | Trata todos los archivos por igual sin distinción | Diferencia entre archivos de datos (`data.csv`, `train.json`) y archivos de modelos (`model.pkl`, `weights.h5`), aplicando pesos diferentes según criticidad | Mayor precisión contextual. Los archivos de modelos compartidos indican mayor acoplamiento que archivos de datos genéricos, reflejando mejor la cohesión real del código ML. |

### Ejemplo Donde LCCML es Superior

```python
def load_data():
    return pd.read_csv('train.csv')  # ← Detectado: archivo

def preprocess():
    data = load_data()  # ← LCCML detecta esta llamada directa ✅
    return StandardScaler().fit(data)

def train():
    scaler = preprocess()  # ← LCCML detecta esta llamada directa ✅
    model = sklearn.LinearRegression()
    return model
```

**Código Original**: No detecta las llamadas directas `load_data()` y `preprocess()`.  
**Nuestra LCCML**: Detecta TODAS las conexiones (archivos + librerías + llamadas directas).

### Fórmula LCCML

```
LCCML = (Mv ∪ Mf ∪ Ml ∪ Mc) / (n(n-1)/2)

donde:
  n  = número de métodos en el archivo
  Mv = pares conectados por variables compartidas
  Mf = pares conectados por archivos compartidos (datos/modelos)
  Ml = pares conectados por librerías ML compartidas
  Mc = pares conectados por llamadas directas entre métodos
```

---

## 6. Interpretación de Resultados

### Rangos de Cohesión

| Rango | Interpretación | Acción Recomendada |
|-------|----------------|-------------------|
| **0.8 - 1.0** | Excelente - módulo altamente cohesivo | ✅ Mantener estructura |
| **0.6 - 0.79** | Bueno - cohesión razonable | Minor improvements posibles |
| **0.4 - 0.59** | Moderado - cohesión aceptable | Considerar refactorización |
| **0.2 - 0.39** | Bajo - módulo hace cosas no relacionadas | ⚠️ Dividir módulo |
| **0.0 - 0.19** | Muy bajo - sin cohesión | 🚨 Refactorización urgente |

### Ejemplo de Aplicación

**Proyecto**: Sistema de reconocimiento facial

**Resultados**:
- `data_acquisition.py`: Cohesión = 0.85 → ✅ Excelente
- `training_pipeline.py`: Cohesión = 0.72 → ✅ Bueno
- `utils.py`: Cohesión = 0.23 → ⚠️ Bajo (debería dividirse)

**Recomendación**: Dividir `utils.py` en módulos más específicos (ej: `data_utils.py`, `model_utils.py`, `visualization_utils.py`).

---

## 7. Limitaciones Conocidas

### ❌ No Detecta
- Código suelto fuera de funciones (scripts)
- Relaciones entre diferentes archivos
- Variables globales del módulo
- Herencia y composición entre clases

### ⚠️ Posibles Falsos Positivos
Parámetros con el mismo nombre en funciones diferentes pueden generar conexiones incorrectas:

```python
def train(model, data):  # parámetro "model"
    pass

def evaluate(model, test):  # parámetro "model" (DIFERENTE objeto)
    pass

# Se conectan aunque "model" sea diferente en cada función
```

**Nota**: Esto funciona bien para `self.variable` (siempre es la misma instancia), pero puede generar falsos positivos con parámetros.

---

## Conclusión

La métrica **LCCML** proporciona una medida objetiva de la calidad organizacional del código ML:

✅ **Identifica módulos bien estructurados** (alta cohesión)  
✅ **Detecta código que necesita refactorización** (baja cohesión)  
✅ **Adaptada específicamente para proyectos de Machine Learning**  
✅ **Incluye conexiones por llamadas directas** (mejora sobre implementaciones anteriores)

Esta métrica es especialmente valiosa para:
- **Code reviews**: Identificar módulos problemáticos
- **Refactorización**: Priorizar qué código mejorar primero
- **Calidad de código**: Monitorear la evolución del proyecto
- **Onboarding**: Entender la organización del código

---

**Documento preparado para**: Stakeholders  
**Fecha**: Noviembre 18, 2025  
**Proyecto**: MLS Toolbox - Code Assessment
