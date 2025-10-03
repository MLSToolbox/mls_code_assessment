# Análisis Pre-Refactorización

## Archivos Actuales
- src/server.py: Inicializa Flask, aplica middleware y decide entre waitress y modo debug; mezcla configuración, arranque de servidor y creación de app, además de depender de implementaciones concretas (`setup_middleware`, `create_routes`).
- src/config/settings.py: Define clase `Settings` con atributos estáticos para configuración y un método que devuelve dicts de PyLint/Radon; acopla lógica de configuración a un objeto mutable global y mezcla estilos (atributos de clase y de instancia).
- src/config/__init__.py: Vacío, solo para compatibilidad de paquete.
- src/core/exceptions.py: Jerarquía sencilla de excepciones específicas; no añade metadatos ni códigos y se usa mezcladamente con excepciones genéricas.
- src/core/models/analysis_result.py: Define `AnalysisResult` y `SessionResult`; `AnalysisResult` ajusta `timestamp` manualmente en `__post_init__`, `SessionResult` no se utiliza en el flujo actual.
- src/core/__init__.py: Vacío.
- src/core/interfaces/analyzer_interface.py: Interface `IAnalyzer` con `analyzer_id`, `analyze`, `generate_report`; no documenta expectativas de errores ni precondiciones.
- src/analyzers/base_analyzer.py: Clase base que valida paths, cambia directorios y localiza archivos Python; expone utilidades genéricas pero deja duplicada parte de la lógica (p.ej. `_get_project_folders` es reimplementada en PyLint).
- src/analyzers/pylint_analyzer.py: Ejecuta PyLint y procesa JSON; captura todo `Exception`, reimplementa `_get_project_folders`, decide score/formato y mezcla preparación de comandos con parsing.
- src/analyzers/radon_cc_analyzer.py: Ejecuta `radon cc`; contiene lógica de parseo de stdout similar a otros analizadores y calcula un score inverso ad hoc.
- src/analyzers/radon_mi_analyzer.py: Ejecuta `radon mi`; comparte estructura de ejecución con PyLint/Radon CC, transforma JSON en agregados y mantiene diccionarios de resultados.
- src/analyzers/factory.py: Factory con diccionario estático e importación dura de cada analizador; registrar uno nuevo requiere tocar el archivo para importarlo y añadirlo al mapa.
- src/analyzers/__init__.py: Vacío.
- src/session/session_manager.py: Orquesta sesiones, crea workspace, instancia analizadores, captura resultados, maneja reports y cleanup; instancia internamente `FileHandler` y `CleanupService`, recrea analizadores para buscar por `analyzer_id` y devuelve dicts nativos en vez de modelos.
- src/session/file_handler.py: Crea directorio, escribe ZIP temporal, extrae y borra; en caso de error elimina todo el workspace; usa rutas relativas desde cwd y no valida que el ZIP sea seguro.
- src/session/cleanup_service.py: Arranca un `threading.Timer` por instancia para limpiar carpetas con nombres UUID en el cwd; mantiene `_active_sessions` sin sincronización y nunca se registra desde `SessionManager`.
- src/session/__init__.py: Vacío.
- src/api/routes.py: Define endpoints directamente sobre `Flask` y usa `SessionManager` de forma síncrona; parsea input binario manualmente, recrea sesión por request y mezcla respuesta binaria con JSON; carece de Blueprints y de separación entre request parsing y lógica.
- src/api/serializers.py: Serializa respuestas JSON simples; devuelve siempre `Flask Response` pero sin incluir códigos de error en el payload salvo mensaje.
- src/api/middleware.py: Configura CORS y logging usando decoradores `before_request/after_request`; duplica controles de cuerpo vacío con rutas; mezcla responsabilidades de CORS, logging y validación.
- src/api/__init__.py: Vacío.
- src/utils/validation.py: Valida paths, session ids y tipos de analizador; `validate_session_id` requiere `isalnum`, por lo que rechaza los UUID con guiones generados por `SessionManager`; depende directamente de `AnalyzerFactory`.
- src/utils/__init__.py: Vacío.

## Violaciones de SOLID
- SRP: `SessionManager` maneja creación de sesión, orquestación de analizadores, almacenamiento de resultados, generación de reportes y lifecycle de archivos/cleanup, mezclando varias responsabilidades.
- SRP: `CleanupService` combina registro de sesiones, borrado individual, programación periódica y descubrimiento de carpetas en el filesystem global.
- SRP: `FileHandler` mezcla creación de workspace, escritura de ZIP y limpieza automática en caso de error en lugar de delegar.
- OCP: Para agregar un analizador nuevo es necesario editar `analyzers/factory.py` para importarlo y registrarlo, modificando código existente.
- LSP: `AnalyzerFactory.create_analyzer` devuelve instancias que lanzan `AnalyzerError` en `__init__` si el path no existe; `SessionManager._find_analyzer_type` crea instancias con `""`, rompiendo la sustitución porque la construcción falla antes de usar la interface.
- ISP/DIP: `SessionManager` depende directamente de la implementación concreta `AnalyzerFactory` y de clases concretas (`FileHandler`, `CleanupService`), sin interfaces inyectables.
- DIP: `utils/validation.validate_analyzer_types` depende de `AnalyzerFactory` estático en vez de recibir una abstracción de registro.

## Acoplamiento Detectado
- `SessionManager` instancia directamente `FileHandler` y `CleanupService`, dificultando pruebas y sustitución por mocks.
- `SessionManager` acopla el flujo a `AnalyzerFactory` y crea instancias concretas de analizadores, imposibilitando inyección de estrategias.
- `utils/validation` importa `AnalyzerFactory`, creando dependencia cruzada entre utilidades y capa de dominio de analizadores.
- `api/routes` acopla la capa HTTP al constructor concreto de `SessionManager` y a la estructura de dicts devuelta, sin capa de servicio o DTOs.
- `CleanupService` rehúsa información de `settings` directamente y toca el cwd global (`os.listdir('.')`), acoplando la lógica de limpieza al layout del proyecto.

## Código Duplicado
- La lógica para descubrir carpetas de proyecto (`_get_project_folders`) existe tanto en `BaseAnalyzer` como en `PyLintAnalyzer` con implementaciones casi idénticas.
- El patrón de ejecutar un comando externo con `subprocess.run`, iterar carpetas y manejar stdout/stderr se repite en los tres analizadores concretos.
- La creación y arranque del timer en `CleanupService` se repite para cada instancia porque `SessionManager` crea una nueva copia, provocando hilos múltiples con comportamiento igual.
- Validaciones de request sin cuerpo se realizan tanto en `api/routes` como en `api/middleware`, duplicando la lógica de error.
- Manejo de timestamps y módulos totals se gestiona manualmente en cada analizador en lugar de centralizarlo en `AnalysisResult` o utilidades compartidas.
