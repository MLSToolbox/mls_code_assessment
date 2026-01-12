# Justificación Teórica: Ampliación de FCPP a "Uso de Símbolos"

## Contexto
La definición original de **FCPP (Functional Cohesion of Pipeline Packages)** se basa en la "invocación de funciones" ($m_i \to m_j$). Sin embargo, en la implementación práctica para Python, restringir la detección estrictamente a nodos `ast.Call` genera falsos negativos (Cohesión = 0) en casos de dependencia clara, como el uso de clases de configuración, decoradores o constantes.

## Decisión Técnica
Se ha ampliado la detección de conexiones en `FCPPAnalyzer` para incluir **todo uso de símbolos importados** (`ast.Name` context `Load`), no solo llamadas explícitas.

## Justificación
1.  **Naturaleza de Python**: En Python, muchas interacciones funcionales no son llamadas directas:
    *   **Instanciación**: `conf = Config()` (Es un Call, pero a veces se detecta ambiguamente).
    *   **Acceso a Atributos**: `conf.param` (Es dependencia funcional).
    *   **Tipado**: `def process(c: Config)` (El código depende de la definición de clase).
    *   **Decoradores**: `@registro` (Modifica el comportamiento funcional).

2.  **Cohesión Real vs. Teórica**:
    *   Si el módulo A *importa y usa* al módulo B, A no puede funcionar sin B. Existe un acoplamiento fuerte.
    *   Si FCPP ignora esto porque "no es una llamada ()", reportará que el paquete está fragmentado (FCPP=0), cuando en realidad es un bloque funcional sólido.

3.  **Diferenciación con SCPP**:
    *   **SCPP** mide recursos compartidos externos (datasets, archivos de modelos).
    *   **FCPP** debe medir la interdependencia del **código fuente**.
    *   `config.py` es código fuente. Su uso por otros módulos es competencia de FCPP.

## Conclusión
La métrica FCPP ahora interpreta "Invocación" como "Dependencia Funcional de Código (Code Dependency)", que es una métrica más robusta y realista para evaluar la cohesión de paquetes de software en Python.
