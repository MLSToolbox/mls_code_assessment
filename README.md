# MLS Toolbox Code Assessment

Microservicio para análisis automatizado de calidad de código Python, enfocada en proyectos de Machine Learning. Evalúa múltiples métricas: complejidad ciclomática, mantenibilidad, cohesión a nivel de módulos y paquetes, y detección de etapas del pipeline.

## Endpoints

### `POST /api/upload`
Sube código Python (ZIP o repositorio Git) y obtiene:
- `auto_detected_pipeline`: Etapas ML detectadas automáticamente
- `session_id`: Identificador de sesión
- `tree_structure`: Estructura de archivos

**Formato esperado (`multipart/form-data`):**
- `file`: archivo `.zip` con el código fuente
- `git_url`: URL `http(s)` de repositorio Git terminada en `.git`
- Enviar **solo uno** de los dos campos anteriores

### `POST /api/analyze/<session_id>`
Ejecuta analizadores sobre sesión existente:
```json
{
  "analyzers": ["pylint", "radon_cc", "pipeline", "fcpm"],
  "pipeline_overrides": {
    "file_stages": {"path/file.py": ["data_collection"]},
    "excluded_files": ["tests/"]
  }
}
```

Nota: el análisis requiere al menos un archivo con etapas asignadas (auto-detectadas o manuales).

**Analizadores disponibles:**
- `pylint` - Calidad de código (PEP 8)
- `radon_cc` - Complejidad ciclomática
- `radon_mi` - Índice de mantenibilidad
- `pipeline` - Detección de etapas ML
- `ccpm` - Cohesión Conceptual de Módulos Pipeline
- `scpm` - Cohesión Estructural de Módulos Pipeline
- `fcpm` - Cohesión Funcional de Módulos Pipeline
- `ccpp` - Cohesión Conceptual de Paquetes Pipeline
- `scpp` - Cohesión Estructural de Paquetes Pipeline
- `fcpp` - Cohesión Funcional de Paquetes Pipeline
- `file_structure` - Estructura de directorios
- `ml_content` - Detección de contenido ML/no-ML

## Arquitectura

```
src/
├── api/             # Capa HTTP (REST API)
├── analyzers/       # Analizadores de código
├── core/            # Modelos y lógica central
├── config/          # Configuración global
├── metrics/         # Metadatos de métricas
├── session/         # Gestión de sesiones temporales
└── server.py        # Entry point
```

### Descripción de carpetas

**`api/`** - Capa de presentación REST
- `routes.py` - Definición de endpoints (limpio, sin lógica)
- `services.py` - Lógica de negocio (upload, análisis)
- `validation.py` - Validación de requests HTTP
- `serializers.py` - Formato de respuestas JSON
- `error_handlers.py` - Manejo centralizado de errores
- `middleware.py` - CORS y logging

**`analyzers/`** - Motores de análisis de código
- `base_analyzer.py` - Clase abstracta base para analizadores
- `base_evaluator.py` - Clase base para evaluadores de reglas
- `factory.py` - Factory pattern para crear analizadores
- `pipeline/` - Analizador de pipeline ML (stages, overrides, config)
- `ccpm/` - Conceptual Cohesion of Pipeline Modules (migrado)
- `ml_content/` - Detección de contenido ML vs non-ML
- Analizadores individuales: `pylint_analyzer.py`, `radon_cc_analyzer.py`, `scpm_analyzer.py`, `fcpm_analyzer.py`, `lccml_analyzer.py`

**`core/`** - Componentes centrales reutilizables
- `analysis_result.py` - Modelo de resultado de análisis
- `analysis_context.py` - Contexto compartido entre analizadores
- `exceptions.py` - Jerarquía de excepciones custom
- `tree_generator.py` - Generador de árbol de archivos

**`config/`** - Configuración de la aplicación
- `settings.py` - Todas las settings (env vars, constantes, tipos válidos)

**`metrics/`** - Sistema de metadatos
- `registry.py` - Registro de métricas con documentación
- `metadata.py` - Modelo de metadatos (fórmula, rangos, referencias)

**`session/`** - Gestión de sesiones de análisis
- `session_manager.py` - CRUD de sesiones
- `session_storage.py` - Persistencia en filesystem
- `file_handler.py` - Manejo de ZIP files
- `cleanup_scheduler.py` - Limpieza automática de sesiones expiradas

## Principios de diseño aplicados

### **SOLID**
- **Single Responsibility**: Cada clase tiene una responsabilidad única
- **Dependency Inversion**: Inyección de dependencias, uso de interfaces

### **Clean Code**
- **DRY**: Sin duplicación de código
- **KISS**: Soluciones simples y directas
- **Separation of Concerns**: Capas bien definidas (API → Services → Analyzers)

### **Patrones aplicados**
- **Factory Pattern**: `AnalyzerFactory` para crear analizadores
- **Strategy Pattern**: Analizadores intercambiables
- **Repository Pattern**: `SessionStorage` para persistencia
- **Error Handler Pattern**: Manejo centralizado de excepciones

### **Arquitectura**
- **Layered Architecture**: API → Business Logic → Data Access
- **Service Layer**: Lógica de negocio separada de controllers
- **Config as Code**: JSON para configs complejas, env vars para runtime

### **Buenas prácticas**
- **Type Hints**: Tipado estático con Python typing
- **Pydantic**: Validación automática de schemas
- **Exception Hierarchy**: Excepciones específicas con status codes
- **Centralized Error Handling**: Error handlers globales en Flask
- **Logging**: Registro automático de errores y requests

## Stack técnico

- **Flask** - Framework web
- **Pydantic** - Validación de datos
- **Pylint/Radon** - Análisis estático
- **Waitress** - WSGI server (producción)

## Configuración

Variables de entorno en `.env`:
```bash
HOST=0.0.0.0
PORT=5060
DEBUG=False
SESSION_BASE_PATH=/tmp/mls_sessions
SESSION_TTL_MINUTES=60
CLEANUP_INTERVAL_MINUTES=30
```
