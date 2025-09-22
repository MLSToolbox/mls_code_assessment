# Documentación de la Arquitectura MLSToolbox Code Assessment

## Visión General

La nueva arquitectura implementa **principios SOLID** y **patrones de diseño** para crear un sistema **mantenible**, **escalable** y **extensible**. Separa las responsabilidades en capas bien definidas y utiliza interfaces para desacoplar componentes.

## Estructura del Proyecto

```
src/
├── core/                    # Núcleo del sistema
├── analyzers/              # Analizadores de código
├── session/                # Gestión de sesiones
├── api/                    # Capa de presentación (REST API)
├── utils/                  # Utilidades transversales
├── config/                 # Configuración centralizada
├── requirements.txt
└── server.py               # Punto de entrada
```

---

## 📦 **core/** - Núcleo del Sistema

### `core/exceptions.py`
**Propósito**: Manejo centralizado de excepciones
- `MLSAnalysisError`: Excepción base del sistema
- `SessionError`: Errores de gestión de sesiones
- `AnalyzerError`: Errores durante análisis de código
- `ReportGenerationError`: Errores en generación de reportes

**Ventaja**: Manejo consistente de errores en toda la aplicación

### `core/models/analysis_result.py`
**Propósito**: Modelos de datos inmutables y tipados
- `AnalysisResult`: Resultado de un análisis individual
- `SessionResult`: Resultados completos de una sesión

**Características**:
- **Inmutable** (`@dataclass(frozen=True)`)
- **Tipado fuerte** con Type Hints
- **Timestamp automático**

### `core/interfaces/analyzer_interface.py`
**Propósito**: Contrato que deben cumplir todos los analizadores
- `IAnalyzer`: Interface con métodos `analyze()` y `generate_report()`

**Patrón**: Interface Segregation Principle (ISP)

---

## 🔍 **analyzers/** - Analizadores de Código

### `analyzers/base_analyzer.py`
**Propósito**: Clase abstracta con funcionalidad común
- Validación de rutas
- Cambio de directorios seguro
- Detección de archivos Python
- Métodos utilitarios comunes

**Patrón**: Template Method Pattern

### `analyzers/pylint_analyzer.py`
**Propósito**: Análisis de calidad con PyLint
- Ejecuta PyLint en modo JSON
- Procesa estadísticas de calidad
- Genera reportes detallados

### `analyzers/radon_cc_analyzer.py`
**Propósito**: Análisis de complejidad ciclomática
- Ejecuta Radon CC
- Calcula score inverso a la complejidad
- Cuenta bloques de código

### `analyzers/radon_mi_analyzer.py`
**Propósito**: Análisis de índice de mantenibilidad
- Ejecuta Radon MI
- Procesa rankings A/B/C
- Calcula promedios de mantenibilidad

### `analyzers/factory.py`
**Propósito**: Creación dinámica de analizadores
- **Factory Pattern** para instanciar analizadores
- Registro dinámico de nuevos analizadores
- Listado de analizadores disponibles

**Extensibilidad**: Agregar nuevos analizadores sin modificar código existente

---

## 🎯 **session/** - Gestión de Sesiones

### `session/session_manager.py`
**Propósito**: Orquestador principal del flujo de análisis
- Coordina múltiples analizadores
- Gestiona el ciclo de vida de sesiones
- Manejo robusto de errores
- Cache de resultados y reportes

**Responsabilidades**:
- Ejecutar análisis con todos los analizadores
- Generar reportes específicos
- Coordinar limpieza de recursos

### `session/file_handler.py`
**Propósito**: Operaciones específicas con archivos
- Creación de espacios de trabajo
- Extracción de archivos ZIP
- Limpieza en caso de error

**Principio**: Single Responsibility Principle (SRP)

### `session/cleanup_service.py`
**Propósito**: Limpieza automática de recursos
- Timer automático para limpieza periódica
- Gestión de sesiones activas
- Limpieza de sesiones expiradas

**Características**:
- **Thread-safe**
- **Cleanup automático**
- **Configuración por tiempo de vida**

---

## 🌐 **api/** - Capa de Presentación

### `api/routes.py`
**Propósito**: Definición de endpoints REST
- `/api/rate_app` - Análisis de código
- `/api/get_report` - Generación de reportes
- `/api/analyzers` - Lista de analizadores disponibles
- `/` - Health check

**Características**:
- Manejo centralizado de errores
- Validación de parámetros
- Respuestas consistentes

### `api/serializers.py`
**Propósito**: Serialización consistente de respuestas
- `ResponseSerializer.success()` - Respuestas exitosas
- `ResponseSerializer.error()` - Respuestas de error

**Formato estándar**:
```json
{
  "success": true/false,
  "data": {...} | "error": {...}
}
```

### `api/middleware.py`
**Propósito**: Funcionalidades transversales
- Configuración CORS
- Logging de requests/responses
- Validación de requests
- Medición de tiempos de respuesta

---

## 🔧 **utils/** - Utilidades

### `utils/validation.py`
**Propósito**: Funciones de validación reutilizables
- Validación de rutas de archivos
- Validación de IDs de sesión
- Validación de tipos de analizadores

**Características**: Funciones puras y testeable

---

## ⚙️ **config/** - Configuración

### `config/settings.py`
**Propósito**: Configuración centralizada
- Settings de aplicación (HOST, PORT, modo)
- Configuración de análisis (timeouts, límites)
- Configuración específica de analizadores

**Ventajas**:
- **Configuración por ambiente**
- **Settings centralizados**
- **Fácil modificación**

---

## 🚀 **server.py** - Punto de Entrada

**Propósito**: Bootstrap de la aplicación
- Configuración de logging
- Creación de app Flask
- Configuración de middleware y rutas
- Detección de modo producción/desarrollo

---

## Patrones de Diseño Implementados

### 1. **Factory Pattern** (`analyzers/factory.py`)
- Creación dinámica de analizadores
- Registro de nuevos tipos sin modificar código

### 2. **Strategy Pattern** (Analizadores)
- Diferentes estrategias de análisis intercambiables
- Interface común para todos los analizadores

### 3. **Template Method Pattern** (`base_analyzer.py`)
- Estructura común con puntos de extensión
- Reutilización de código común

### 4. **Dependency Injection** 
- SessionManager recibe configuración externa
- Analizadores son inyectados dinámicamente

---

## Principios SOLID Aplicados

### ✅ **Single Responsibility Principle (SRP)**
- Cada clase tiene una responsabilidad específica
- FileHandler solo maneja archivos
- CleanupService solo limpia recursos

### ✅ **Open/Closed Principle (OCP)**
- Extensible sin modificar código existente
- Nuevos analizadores heredan de BaseAnalyzer
- Factory registra automáticamente

### ✅ **Liskov Substitution Principle (LSP)**
- Analizadores son intercambiables
- Todos implementan la misma interface

### ✅ **Interface Segregation Principle (ISP)**
- Interfaces específicas y cohesivas
- IAnalyzer solo define lo necesario

### ✅ **Dependency Inversion Principle (DIP)**
- Dependencias hacia abstracciones
- SessionManager depende de IAnalyzer, no implementaciones concretas

---

## Ventajas de la Nueva Arquitectura

### 🔧 **Mantenibilidad**
- Código organizado y cohesivo
- Separación clara de responsabilidades
- Fácil debugging y testing

### 📈 **Escalabilidad**
- Componentes desacoplados
- Configuración externa
- Cleanup automático de recursos

### 🔌 **Extensibilidad**
- Agregar analizadores: heredar de `BaseAnalyzer`
- Nuevos formatos de reporte: implementar interface
- Configuración dinámica

### 🧪 **Testabilidad**
- Interfaces mockeable
- Funciones puras en utils
- Inyección de dependencias

---

## Cómo Agregar un Nuevo Analizador

```python
# 1. Crear nuevo archivo: analyzers/mi_analyzer.py
class MiAnalyzer(BaseAnalyzer):
    @property
    def analyzer_id(self) -> str:
        return "Mi Analyzer"
    
    def analyze(self, code_path: str = None) -> AnalysisResult:
        # Implementación específica
        pass
    
    def generate_report(self, code_path: str = None) -> bytes:
        # Implementación específica  
        pass

# 2. Registrar en factory.py
AnalyzerFactory.register_analyzer("mi_analyzer", MiAnalyzer)

# 3. ¡Listo! El sistema lo detecta automáticamente
```

La arquitectura está preparada para crecer de manera controlada y mantenible. 🚀