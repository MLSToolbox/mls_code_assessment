from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import json
import os


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
