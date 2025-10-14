# Implementación del Analizador PFP (Package Functional Purity)

## Descripción

Este Pull Request implementa el analizador PFP (Package Functional Purity), una métrica que evalúa la pureza funcional y cohesión de paquetes en proyectos de Machine Learning. El analizador mide qué tan enfocado está un paquete en una función específica del pipeline de ML, proporcionando scores cuantitativos y clasificaciones cualitativas.

## Problema o Contexto

El sistema de análisis de código requería una métrica para evaluar la cohesión funcional a nivel de paquete. Los problemas identificados incluían:

- Ausencia de métricas para medir la pureza funcional de paquetes
- Necesidad de identificar paquetes con múltiples responsabilidades
- Falta de evaluación de concentración funcional en proyectos ML
- Requerimiento de clasificación cualitativa de la calidad de diseño de paquetes

La implementación del PFP permite evaluar si los paquetes están bien diseñados con alta cohesión o si mezclan múltiples responsabilidades indicando baja cohesión.

## Cambios Realizados

### 1. Nuevo Módulo: pfp_analyzer.py

Se creó el módulo `src/analyzers/pfp_analyzer.py` que implementa la clase `PFPAnalyzer`:

```python
class PFPAnalyzer(BaseAnalyzer):
    """
    Analyzes Package Functional Purity (PFP).
    Formula: PFP = (n_ml / n_total) * CF
    """
```

Componentes principales:
- Cálculo de ratio de módulos ML por paquete
- Factor de concentración basado en etapas únicas detectadas
- Clasificación cualitativa (High, Moderate, Low, Very Low)
- Validación de dependencia con FPC analyzer

### 2. Integración en AnalyzerFactory

Actualización de `src/analyzers/factory.py`:

```python
from analyzers.pfp_analyzer import PFPAnalyzer

cls._analyzers = {
    "pylint": PyLintAnalyzer,
    "radon_cc": RadonCCAnalyzer,
    "radon_mi": RadonMIAnalyzer,
    "pipeline": PipelineAnalyzer,
    "fpc": FPCAnalyzer,
    "pfp": PFPAnalyzer
}
```

### 3. Actualización de Validadores

Modificación en `src/utils/validation.py`:

```python
valid_analyzers = {'pylint', 'radon_cc', 'radon_mi', 'pipeline', 'fpc', 'pfp'}
```

### 4. Implementación de AnalysisContext

Se implementó un sistema de contexto compartido entre analizadores para permitir que PFP acceda a los resultados de FPC:

```python
# src/core/analysis_context.py
class AnalysisContext:
    """
    Contexto compartido que almacena resultados de análisis entre analizadores.
    Permite que analizadores dependientes accedan a métricas calculadas previamente.
    """
    
    def set_file_metric(self, file_path: str, metric_name: str, data: Any):
        """Almacena métricas de un archivo específico."""
        
    def get_file_metric(self, file_path: str, metric_name: str) -> Optional[Any]:
        """Recupera métricas de un archivo específico."""
        
    def has_file_metric(self, file_path: str, metric_name: str) -> bool:
        """Verifica si existe una métrica para un archivo."""
```

Uso en PFP Analyzer:

```python
# El PFP utiliza el contexto para acceder a resultados de FPC
fpc_result = self.context.get_file_metric(module_path, 'fpc')
if fpc_result and fpc_result.get('stages_detected'):
    n_ml += 1
    all_stages.update(fpc_result['stages_detected'])
```

### 5. Actualización de pipeline_stages.json

Se actualizó el archivo de configuración con palabras clave más específicas y precisas para mejorar la detección de etapas del pipeline ML:

```json
{
  "stages": {
    "data_collection": {
      "keywords": [
        "pd.read_csv",
        "pd.read_excel",
        "pd.read_json",
        "pd.read_sql",
        "pd.read_parquet",
        "load_dataset",
        "load_iris",
        "fetch_data",
        "requests.get",
        "BeautifulSoup",
        "boto3.client"
      ],
      "imports": ["requests", "selenium", "scrapy", "boto3", "sklearn.datasets"]
    },
    "feature_engineering": {
      "keywords": [
        "fit_transform",
        ".transform(",
        "OneHotEncoder",
        "LabelEncoder",
        "StandardScaler",
        "MinMaxScaler",
        "PCA",
        "SelectKBest",
        "TfidfVectorizer"
      ]
    },
    "model_training": {
      "keywords": [
        ".fit(",
        ".train(",
        "model.compile",
        "GridSearchCV",
        "cross_val_score",
        "train_test_split"
      ]
    }
  }
}
```

Mejoras implementadas:
- Keywords más específicas para reducir falsos positivos
- Patrones de importación actualizados
- Cobertura de bibliotecas ML modernas (scikit-learn, pandas, TensorFlow, PyTorch)

### 6. Algoritmo de Cálculo Implementado

```python
def _analyze_package(self, modules: List[str]) -> Dict[str, Any]:
    n_total = len(modules)
    n_ml = 0
    all_stages = set()
    
    for module_path in modules:
        # Utiliza el contexto para acceder a resultados de FPC
        fpc_result = self.context.get_file_metric(module_path, 'fpc')
        if fpc_result and fpc_result.get('stages_detected'):
            n_ml += 1
            all_stages.update(fpc_result['stages_detected'])
    
    n_etapas = len(all_stages)
    cf = 1 - ((n_etapas - 1) / (ETAPAS_MAX - 1)) if ETAPAS_MAX > 1 else 1.0
    
    pfp_score = (n_ml / n_total) * cf if n_total > 0 else 0
    
    return {
        "total_modules": n_total,
        "ml_modules": n_ml,
        "unique_stages_found": n_etapas,
        "concentration_factor": round(cf, 4),
        "pfp_score": round(pfp_score, 4),
        "purity_level": self._get_purity_level(pfp_score)
    }
```





```

**Paso 3: Subir Proyecto para Análisis**

```bash
curl -X POST http://0.0.0.0:5060/api/upload \
  -F "file=@/ruta/al/proyecto.zip"
```

Respuesta esperada:
```json
{
  "session_id": "940c41b9-d391-4149-8069-55896cad7cd7"
}
```

**Paso 4: Ejecutar Análisis PFP**

```bash
curl -X POST http://0.0.0.0:5060/api/analyze/940c41b9-d391-4149-8069-55896cad7cd7 \
  -H "Content-Type: application/json" \
  -d '{
    "analyzers": ["fpc", "pfp"]
  }'
```

**Paso 5: Validar Dependencia de FPC**

```bash
curl -X POST http://0.0.0.0:5060/api/analyze/940c41b9-d391-4149-8069-55896cad7cd7 \
  -H "Content-Type: application/json" \
  -d '{
    "analyzers": ["pfp"]
  }'
```

Resultado esperado: Error indicando que FPC es requerido.

### Opción 2: Ejecución en Entorno Local

**Paso 1: Instalación de Dependencias**

```bash
pip install -r requirements.txt
```

**Paso 2: Iniciar Servidor**

```bash
cd src
python server.py
```

**Paso 3: Realizar Peticiones HTTP**

Utilizando Postman, cURL o herramienta similar:

1. Upload del proyecto:
   - Método: POST
   - URL: `http://0.0.0.0:5060/api/upload`
   - Body: form-data con campo "file" conteniendo el ZIP

2. Análisis con PFP:
   - Método: POST
   - URL: `http://0.0.0.0:5060/api/analyze/{session_id}`
   - Headers: `Content-Type: application/json`
   - Body: `{"analyzers": ["fpc", "pfp"]}`

### Casos de Prueba

| Escenario | Configuración | Score Esperado | Nivel Esperado |
|-----------|---------------|----------------|----------------|
| Paquete puro | 1 etapa, todos módulos ML | 9.0 - 10.0 | High |
| Paquete moderado | 2-3 etapas, mayoría ML | 6.0 - 8.0 | Moderate |
| Paquete mixto | 4+ etapas, algunos ML | 4.0 - 6.0 | Low |
| Sin dependencia FPC | Solo PFP sin FPC | N/A | Error |

## Evidencia

### Estructura de Respuesta Esperada

```json
{
  "analyzer_id": "PFP",
  "score": 7.85,
  "message_count": {
    "High": 2,
    "Moderate": 3,
    "Low": 1,
    "Very Low": 0
  },
  "module_count": 15,
  "details": {
    "packages": {
      "src/data": {
        "total_modules": 5,
        "ml_modules": 5,
        "unique_stages_found": 2,
        "concentration_factor": 0.75,
        "pfp_score": 0.75,
        "purity_level": "High"
      },
      "src/models": {
        "total_modules": 4,
        "ml_modules": 4,
        "unique_stages_found": 1,
        "concentration_factor": 1.0,
        "pfp_score": 1.0,
        "purity_level": "High"
      },
      "src/utils": {
        "total_modules": 6,
        "ml_modules": 3,
        "unique_stages_found": 4,
        "concentration_factor": 0.25,
        "pfp_score": 0.125,
        "purity_level": "Very Low"
      }
    }
  }
}
```

### Interpretación de Resultados

- **total_modules**: Cantidad total de módulos Python en el paquete
- **ml_modules**: Módulos identificados con funcionalidad ML (tienen etapas detectadas por FPC)
- **unique_stages_found**: Número de etapas únicas del pipeline ML presentes
- **concentration_factor**: Factor de penalización por dispersión (0.0 - 1.0)
- **pfp_score**: Score de pureza funcional (0.0 - 1.0)
- **purity_level**: Clasificación cualitativa

## Checklist

- [x] Código implementado y funcional
- [x] Pruebas locales ejecutadas exitosamente
- [x] Documentación técnica completa (docstrings)
- [x] Integración con sistema existente sin romper funcionalidades
- [x] Validación de dependencias implementada
- [x] Manejo de errores robusto
- [x] Adherencia a patrones de diseño del proyecto (BaseAnalyzer)

## Notas Adicionales

### Fundamentos Técnicos

**Fórmula de Cálculo:**

```
PFP = (n_ml / n_total) × CF
```

Donde:
- `n_ml`: Número de módulos con funcionalidad ML
- `n_total`: Total de módulos en el paquete
- `CF`: Factor de concentración

**Factor de Concentración:**

```
CF = 1 - ((n_etapas - 1) / (ETAPAS_MAX - 1))
```

Donde:
- `n_etapas`: Etapas únicas del pipeline detectadas
- `ETAPAS_MAX`: Constante = 5 (etapas totales del pipeline ML)

### Clasificación de Pureza

| Rango de Score | Clasificación | Interpretación |
|----------------|---------------|----------------|
| 0.80 - 1.00 | High | Alta cohesión funcional |
| 0.60 - 0.79 | Moderate | Cohesión aceptable |
| 0.40 - 0.59 | Low | Baja cohesión, revisar diseño |
| 0.00 - 0.39 | Very Low | Múltiples responsabilidades |

### Decisiones de Diseño

1. **Dependencia de FPC**: El analizador PFP requiere resultados previos del FPC analyzer para determinar qué módulos tienen funcionalidad ML. Esta validación se ejecuta en tiempo de análisis y genera error descriptivo si no se cumple.

2. **Constante ETAPAS_MAX = 5**: Basada en las cinco etapas del pipeline ML definidas en `pipeline_stages.json`:
   - data_collection
   - data_cleaning
   - feature_engineering
   - model_training
   - model_evaluation

3. **Escala de Score**: Se mantiene consistencia con otros analizadores multiplicando el score base (0-1) por 10 para obtener la escala final (0-10).

4. **Descubrimiento de Paquetes**: Se identifica un paquete como cualquier directorio que contenga archivos Python. Los módulos se agrupan por su directorio padre.

### Compatibilidad y Extensibilidad

- Compatible con ejecución individual o dentro de pipelines de análisis
- Respeta el patrón de diseño establecido (herencia de BaseAnalyzer)
- Utiliza AnalysisContext para compartir datos entre analizadores
- Preparado para futuras extensiones (configuración dinámica de ETAPAS_MAX)

### Mejoras Futuras Sugeridas

1. Configuración dinámica de ETAPAS_MAX por proyecto
2. Visualización gráfica de pureza por paquete
3. Métricas de cohesión adicionales (acoplamiento inter-paquetes)
4. Reportes comparativos entre versiones del proyecto
5. Integración con herramientas de CI/CD para validación automática
