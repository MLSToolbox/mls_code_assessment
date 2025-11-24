# Sistema de Métricas con Evaluadores - Guía de Implementación

## 📋 Contexto

Actualmente FPC calcula correctamente las métricas (phases, stages, ML content, NLOC) pero necesita un sistema para evaluar esos valores contra una tabla de verdad (ver `fpc_metrics.csv`) y generar diagnósticos y recomendaciones personalizadas por archivo.

**Objetivo**: Crear un sistema de evaluadores opcional, mantenible y SOLID que permita a analizadores complejos (como FPC) generar mensajes detallados por archivo, mientras que analizadores simples (pylint, radon) sigan funcionando con mensajes generales.

## 🎯 Arquitectura Aprobada

### Estructura de Archivos

```
analyzers/
├── base_evaluator.py              # ← CREAR: Clase base para evaluadores
├── fpc/
│   ├── __init__.py
│   ├── fpc_analyzer.py            # MODIFICAR: Integrar evaluador
│   ├── nloc_calculator.py         # Sin cambios
│   ├── fpc_evaluator.py           # ← CREAR: Lógica de evaluación
│   └── fpc_rules.json             # ← CREAR: Tabla de verdad del CSV
├── ml_content/
│   └── ...                        # Sin cambios
└── ...

core/models/
└── analysis_result.py             # MODIFICAR: message_count → messages
```

## 📝 Paso 1: Crear `analyzers/base_evaluator.py`

Clase base abstracta para evaluadores con lógica genérica de matching y rendering de templates.

```python
"""
Base Evaluator for Complex Metrics

Provides a foundation for analyzers that need to evaluate files against
rule sets and generate diagnostic messages with recommendations.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import json
import re


class BaseEvaluator(ABC):
    """
    Base class for metric evaluators.
    
    Evaluators take calculated metrics and evaluate them against a rule set
    to generate diagnostic messages and recommendations for each file.
    """
    
    def __init__(self, rules_path: str):
        """
        Initialize evaluator with rules from JSON file.
        
        Args:
            rules_path: Absolute path to rules JSON file
        """
        self.rules = self._load_rules(rules_path)
    
    def _load_rules(self, rules_path: str) -> List[Dict]:
        """Load rules from JSON file."""
        with open(rules_path, 'r') as f:
            config = json.load(f)
        return config.get('rules', [])
    
    @abstractmethod
    def _match_rule(self, metrics: Dict) -> Optional[Dict]:
        """
        Find the rule that matches the given metrics.
        
        Must be implemented by subclasses with specific matching logic.
        
        Args:
            metrics: Calculated metrics for a file
            
        Returns:
            Matched rule dict or None if no match
        """
        pass
    
    def evaluate_file(self, file_path: str, metrics: Dict) -> Optional[Dict]:
        """
        Evaluate a file and generate diagnostic message.
        
        Args:
            file_path: Path to the file being evaluated
            metrics: Calculated metrics for the file
            
        Returns:
            Dict with diagnosis, recommendation, severity, rule_id
            or None if no issues found (perfect cohesion)
        """
        matched_rule = self._match_rule(metrics)
        
        if not matched_rule:
            return None
        
        # Check if recommendation is null (e.g., rule 9 - perfect cohesion)
        if not matched_rule.get('recommendation_template'):
            return {
                'file': file_path,
                'diagnosis': self._render_template(
                    matched_rule['diagnosis_template'],
                    file_path,
                    metrics
                ),
                'recommendation': None,
                'severity': matched_rule.get('severity', 'info'),
                'rule_id': matched_rule['id'],
                'metrics': metrics
            }
        
        return {
            'file': file_path,
            'diagnosis': self._render_template(
                matched_rule['diagnosis_template'],
                file_path,
                metrics
            ),
            'recommendation': self._render_template(
                matched_rule['recommendation_template'],
                file_path,
                metrics
            ),
            'severity': matched_rule.get('severity', 'info'),
            'rule_id': matched_rule['id'],
            'metrics': metrics
        }
    
    def _render_template(self, template: str, file_path: str, metrics: Dict) -> str:
        """
        Render a template string with file and metric values.
        
        Supports placeholders like:
        - {module_name}
        - {nloc}
        - {phase_name}
        - {stage_name_1}, {stage_name_2}, etc.
        
        Args:
            template: Template string with placeholders
            file_path: Path to file (for extracting module name)
            metrics: Metrics to substitute into template
            
        Returns:
            Rendered string
        """
        # Extract module name from file path
        import os
        module_name = os.path.basename(file_path)
        
        # Start with basic substitutions
        context = {
            'module_name': module_name,
            'nloc': metrics.get('nloc', 'N/A'),
            'phase_name': self._get_phase_name(metrics),
        }
        
        # Add stage names
        stages = metrics.get('stages_detected', [])
        for i, stage in enumerate(stages, 1):
            context[f'stage_name_{i}'] = stage
        
        # Render template
        result = template
        for key, value in context.items():
            result = result.replace(f'{{{key}}}', str(value))
        
        return result
    
    def _get_phase_name(self, metrics: Dict) -> str:
        """
        Get human-readable phase name from metrics.
        
        Args:
            metrics: File metrics
            
        Returns:
            Phase name or 'Unknown'
        """
        phases = metrics.get('phases_detected', [])
        if len(phases) == 1:
            return phases[0].replace('_', ' ').title()
        elif len(phases) > 1:
            return ', '.join(p.replace('_', ' ').title() for p in phases)
        return 'Unknown'
```

## 📝 Paso 2: Crear `analyzers/fpc/fpc_rules.json`

Convertir la tabla de verdad del CSV a JSON estructurado.

```json
{
  "rules": [
    {
      "id": 1,
      "conditions": {
        "phases": 2,
        "stages": "any",
        "ml_content_only": true,
        "nloc_above_threshold": true
      },
      "diagnosis_template": "The cohesion of the {module_name} module is low, as it combines code of two unrelated phases, Data Engineering and Model Development phases.",
      "recommendation_template": "The {module_name} module should be split, at least, into two separate modules, one containing the code of Data Engineering phase and the other containing the code of Model Development phase. If the resulting modules are too long, consider to split them into one module for each stage.",
      "severity": "high"
    },
    {
      "id": 2,
      "conditions": {
        "phases": 2,
        "stages": "any",
        "ml_content_only": true,
        "nloc_above_threshold": false
      },
      "diagnosis_template": "The cohesion of the {module_name} module is low, as it combines code of two unrelated phases, Data Engineering and Model Development phases.",
      "recommendation_template": "The {module_name} module is too small (NLOC = {nloc}) but to improve cohesion it should be split into two separate modules, one containing the code of Data Engineering phase and the other containing the code of Model Development phase.",
      "severity": "medium"
    },
    {
      "id": 3,
      "conditions": {
        "phases": 2,
        "stages": "any",
        "ml_content_only": false,
        "nloc_above_threshold": true
      },
      "diagnosis_template": "The cohesion of the {module_name} module is very low, as it combines code of two unrelated phases, Data Engineering and Model Development phases, and code not related to the pipeline.",
      "recommendation_template": "The {module_name} module should be split, at least, into three separate modules, one containing the code of Data Engineering phase, one containing the code of Model Development phase and other containing the code unrelated to the pipeline. If the resulting pipeline modules are too long, consider to split them into one module for each stage.",
      "severity": "critical"
    },
    {
      "id": 4,
      "conditions": {
        "phases": 2,
        "stages": "any",
        "ml_content_only": false,
        "nloc_above_threshold": false
      },
      "diagnosis_template": "The cohesion of the {module_name} module is very low, as it combines code of two unrelated phases, Data Engineering and Model Development phases, and code not related to the pipeline.",
      "recommendation_template": "The {module_name} module is too small (NLOC = {nloc}) but to improve cohesion, at least, it should be split into two separate modules, one containing the code of pipeline and other containing the code unrelated to the pipeline.",
      "severity": "high"
    },
    {
      "id": 5,
      "conditions": {
        "phases": 1,
        "stages": ">1",
        "ml_content_only": true,
        "nloc_above_threshold": true
      },
      "diagnosis_template": "The cohesion of the {module_name} module is high, as it combines code of {stage_name_1} stage, {stage_name_2} stage of the {phase_name} phase.",
      "recommendation_template": "The {module_name} module should be split into different modules, one for each stage.",
      "severity": "medium"
    },
    {
      "id": 6,
      "conditions": {
        "phases": 1,
        "stages": ">1",
        "ml_content_only": true,
        "nloc_above_threshold": false
      },
      "diagnosis_template": "The cohesion of the {module_name} module is high, as it combines code of {stage_name_1} stage, {stage_name_2} stage of the {phase_name} phase.",
      "recommendation_template": "The {module_name} module is too small (NLOC = {nloc}) but to improve cohesion it should be split into different modules, one for each stage.",
      "severity": "low"
    },
    {
      "id": 7,
      "conditions": {
        "phases": 1,
        "stages": ">1",
        "ml_content_only": false,
        "nloc_above_threshold": true
      },
      "diagnosis_template": "The cohesion of the {module_name} module is medium, as it combines code of {stage_name_1} stage, {stage_name_2} stage of the {phase_name} phase and code not related to the pipeline.",
      "recommendation_template": "The {module_name} module should be split into different modules, one for each stage and one for the code not related to the pipeline.",
      "severity": "medium"
    },
    {
      "id": 8,
      "conditions": {
        "phases": 1,
        "stages": ">1",
        "ml_content_only": false,
        "nloc_above_threshold": false
      },
      "diagnosis_template": "The cohesion of the {module_name} module is medium, as it combines code of {stage_name_1} stage, {stage_name_2} stage of the {phase_name} phase and code not related to the pipeline.",
      "recommendation_template": "The {module_name} module is too small (NLOC = {nloc}) but to improve cohesion, at least, it should be split into two different modules, on for the pipeline code and other for the code not related to the pipeline.",
      "severity": "low"
    },
    {
      "id": 9,
      "conditions": {
        "phases": 1,
        "stages": 1,
        "ml_content_only": true
      },
      "diagnosis_template": "The cohesion of the {module_name} module is very high.",
      "recommendation_template": null,
      "severity": "info"
    },
    {
      "id": 10,
      "conditions": {
        "phases": 1,
        "stages": 1,
        "ml_content_only": false
      },
      "diagnosis_template": "The cohesion of the {module_name} module is high, as it combines the code of {stage_name_1} stage and the code not related to the pipeline.",
      "recommendation_template": "The {module_name} module should be split into two separate modules, one containing the code of {stage_name_1} stage and other containing the code unrelated to the pipeline.",
      "severity": "low"
    }
  ]
}
```

## 📝 Paso 3: Crear `analyzers/fpc/fpc_evaluator.py`

Implementar la lógica específica de matching para FPC.

```python
"""
FPC Evaluator - Evaluates FPC metrics against rules.

Implements the matching logic for the 10 FPC cohesion rules.
"""

import os
from typing import Dict, Optional

from analyzers.base_evaluator import BaseEvaluator


class FPCEvaluator(BaseEvaluator):
    """
    Evaluator for FPC (Functional Pipeline Cohesion) metrics.
    
    Matches file metrics against the 10 FPC rules to generate
    diagnostic messages and recommendations.
    """
    
    def __init__(self):
        """Initialize FPC evaluator with rules from fpc_rules.json."""
        rules_path = os.path.join(
            os.path.dirname(__file__),
            'fpc_rules.json'
        )
        super().__init__(rules_path)
    
    def _match_rule(self, metrics: Dict) -> Optional[Dict]:
        """
        Find the FPC rule that matches the given metrics.
        
        Matches based on:
        - Number of phases
        - Number of stages (supports ">1" condition)
        - ML content only (true if no non-ML content detected)
        - NLOC above threshold (if applicable)
        
        Args:
            metrics: FPC metrics for a file
            
        Returns:
            Matched rule or None
        """
        phases = metrics.get('unique_phases', 0)
        stages = metrics.get('unique_stages', 0)
        ml_content_only = not metrics.get('has_no_ml_content', False)
        nloc_above_threshold = metrics.get('above_nloc_threshold', False)
        
        for rule in self.rules:
            conditions = rule['conditions']
            
            # Match phases
            if conditions['phases'] != phases:
                continue
            
            # Match stages (handle ">1" condition)
            stage_condition = conditions['stages']
            if stage_condition == "any":
                pass  # Any number of stages is OK
            elif stage_condition == ">1":
                if stages <= 1:
                    continue
            elif stage_condition != stages:
                continue
            
            # Match ML content only
            if conditions['ml_content_only'] != ml_content_only:
                continue
            
            # Match NLOC (if specified in conditions)
            if 'nloc_above_threshold' in conditions:
                if conditions['nloc_above_threshold'] != nloc_above_threshold:
                    continue
            
            # All conditions match!
            return rule
        
        return None
```

## 📝 Paso 4: Modificar `core/models/analysis_result.py`

Cambiar `message_count` por `messages` y soportar el nuevo formato.

**ANTES:**
```python
class AnalysisResult:
    def __init__(self, score, message_count, module_count, details):
        self.score = score
        self.message_count = message_count  # Dict con {"messages": [...]}
        self.module_count = module_count
        self.details = details
```

**DESPUÉS:**
```python
class AnalysisResult:
    def __init__(self, score, messages, module_count, details):
        self.score = score
        self.messages = messages  # List[Dict] o List[str] para backward compatibility
        self.module_count = module_count
        self.details = details
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'score': self.score,
            'messages': self.messages,
            'module_count': self.module_count,
            'details': self.details
        }
```

## 📝 Paso 5: Modificar `analyzers/base_analyzer.py`

Actualizar `_create_result` para aceptar el nuevo formato.

```python
def _create_result(
    self, 
    score: float, 
    messages,  # Puede ser List[str] o List[Dict]
    module_count: int, 
    details: Dict
) -> AnalysisResult:
    """
    Create analysis result with flexible message format.
    
    Args:
        score: Numeric score (0-10)
        messages: Either:
            - List[str]: Simple messages (backward compatible)
            - List[Dict]: Complex messages with diagnosis/recommendation
        module_count: Number of modules analyzed
        details: Detailed results
    
    Returns:
        AnalysisResult instance
    """
    # Normalize to new format if needed
    if isinstance(messages, list) and messages:
        if isinstance(messages[0], str):
            # Convert old format to new format
            messages = [
                {
                    'message': msg,
                    'severity': 'info',
                    'file': None
                }
                for msg in messages
            ]
    
    return AnalysisResult(
        score=score,
        messages=messages,
        module_count=module_count,
        details=details
    )
```

## 📝 Paso 6: Modificar `analyzers/fpc/fpc_analyzer.py`

Integrar el evaluador en el análisis de FPC.

**Cambios principales:**

1. Importar y crear instancia del evaluador
2. Usar evaluador para generar mensajes por archivo
3. Cambiar formato de respuesta

```python
# En __init__
from analyzers.fpc.fpc_evaluator import FPCEvaluator

def __init__(self, session_id: str, local_path: str, context=None):
    super().__init__(session_id, local_path, context)
    # ... código existente ...
    
    # Initialize evaluator
    self.evaluator = FPCEvaluator()

# En analyze() - después del bucle for que procesa archivos
def analyze(self) -> AnalysisResult:
    # ... código existente hasta el bucle for ...
    
    # Generate messages using evaluator
    messages = []
    for py_file, file_result in results['files'].items():
        evaluation = self.evaluator.evaluate_file(py_file, file_result)
        if evaluation:  # Only add if there's a diagnosis
            messages.append(evaluation)
    
    # Calculate score (código existente)
    if results['summary']['total_files'] > 0:
        score = self._calculate_cohesion_score(results)
    else:
        score = 0
    
    return self._create_result(
        score=round(score, 2),
        messages=messages,  # ← Cambio de message_count a messages
        module_count=results['summary']['total_files'],
        details=results
    )
```

## 📝 Paso 7: Actualizar otros analizadores (opcional)

Para analizadores simples que ya funcionan, simplemente cambiar:

```python
# ANTES
messages = ["✓ 5 files analyzed", "⚠ 3 issues found"]
return self._create_result(
    score=score,
    message_count={'messages': messages},  # ← Viejo formato
    module_count=count,
    details=details
)

# DESPUÉS
messages = ["✓ 5 files analyzed", "⚠ 3 issues found"]
return self._create_result(
    score=score,
    messages=messages,  # ← Nuevo formato (base_analyzer lo normaliza)
    module_count=count,
    details=details
)
```

## ✅ Checklist de Implementación

- [ ] **Paso 1**: Crear `analyzers/base_evaluator.py`
- [ ] **Paso 2**: Crear `analyzers/fpc/fpc_rules.json`
- [ ] **Paso 3**: Crear `analyzers/fpc/fpc_evaluator.py`
- [ ] **Paso 4**: Modificar `core/models/analysis_result.py`
- [ ] **Paso 5**: Modificar `analyzers/base_analyzer.py`
- [ ] **Paso 6**: Modificar `analyzers/fpc/fpc_analyzer.py`
- [ ] **Paso 7**: Actualizar otros analizadores (pylint, radon, etc.)
- [ ] **Paso 8**: Probar con archivos de ejemplo
- [ ] **Paso 9**: Verificar que todas las 10 reglas del CSV funcionen

## 🧪 Testing

Crear casos de prueba para cada regla del CSV:

```python
# Ejemplo para regla 1
def test_rule_1_two_phases_ml_only_above_threshold():
    metrics = {
        'unique_phases': 2,
        'unique_stages': 3,
        'has_no_ml_content': False,  # ML only
        'above_nloc_threshold': True,
        'nloc': 150,
        'stages_detected': ['data_collection', 'model_training', 'model_evaluation'],
        'phases_detected': ['data_engineering', 'model_development']
    }
    
    evaluator = FPCEvaluator()
    result = evaluator.evaluate_file('src/train.py', metrics)
    
    assert result['rule_id'] == 1
    assert result['severity'] == 'high'
    assert 'low' in result['diagnosis']
    assert 'split' in result['recommendation']
```

## 📊 Formato de Respuesta Final

```json
{
  "score": 6.5,
  "messages": [
    {
      "file": "src/train.py",
      "diagnosis": "The cohesion of the train.py module is low, as it combines code of two unrelated phases, Data Engineering and Model Development phases.",
      "recommendation": "The train.py module should be split, at least, into two separate modules...",
      "severity": "high",
      "rule_id": 1,
      "metrics": {
        "unique_phases": 2,
        "unique_stages": 3,
        "nloc": 150,
        "ml_content": true
      }
    },
    {
      "file": "src/utils.py",
      "diagnosis": "The cohesion of the utils.py module is very high.",
      "recommendation": null,
      "severity": "info",
      "rule_id": 9,
      "metrics": {
        "unique_phases": 1,
        "unique_stages": 1,
        "nloc": 45,
        "ml_content": true
      }
    }
  ],
  "module_count": 10,
  "details": {
    "summary": {
      "total_files": 10,
      "high_cohesion": 4,
      "medium_cohesion": 3,
      "low_cohesion": 3
    }
  }
}
```

## 🎯 Notas Importantes

1. **Backward Compatibility**: El sistema soporta ambos formatos (strings y dicts) para facilitar la migración gradual

2. **Template Rendering**: Los templates soportan múltiples stages dinámicamente (stage_name_1, stage_name_2, etc.)

3. **Severity Levels**: 
   - `critical`: Muy grave (múltiples phases + no ML content)
   - `high`: Grave (múltiples phases)
   - `medium`: Moderado (múltiples stages en misma phase)
   - `low`: Leve (archivo pequeño con issues)
   - `info`: Informativo (cohesión perfecta)

4. **Extensibilidad**: Para crear un nuevo evaluador complejo, simplemente:
   - Heredar de `BaseEvaluator`
   - Crear archivo `{analyzer}_rules.json`
   - Implementar `_match_rule()` con lógica específica
   - Integrar en el analyzer principal

5. **Métricas en Respuesta**: Incluir las métricas en cada mensaje permite al frontend mostrar detalles adicionales si lo necesita

---

**🚀 Con esta arquitectura, el sistema de métricas es:**
- ✅ Mantenible (reglas en JSON)
- ✅ Extensible (nuevos evaluadores fácilmente)
- ✅ SOLID (separación de responsabilidades)
- ✅ Flexible (opcional para analizadores)
- ✅ Testeable (cada componente aislado)
