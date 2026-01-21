import os
import json
from typing import Dict, List, Any


class FCPMEvaluator:
    """
    Evaluator for FCPM (Functional Cohesion of Pipeline Modules) metrics.
    
    Matches file-level metrics against contextual rules defined in fcpm_rules.json
    to generate specific diagnoses and recommendations.
    
    Rules consider:
    - cohesion_level: very_low | low | medium | high | very_high
    - n_components: Number of disconnected functional groups (LCOM)
    - n_disconnected_methods: Number of methods with no functional connections
    - breakdown: Direct vs indirect invocations
    """
    
    def __init__(self):
        rules_path = os.path.join(
            os.path.dirname(__file__),
            'fcpm_rules.json'
        )
        
        with open(rules_path, 'r') as f:
            self.rules = json.load(f)['rules']
    
    def evaluate_file(self, file_path: str, metrics: Dict) -> List[Dict[str, Any]]:
        """
        Evaluate FCPM metrics for a file and generate diagnostic messages.
        
        Args:
            file_path: Path to the file being evaluated
            metrics: Dictionary containing:
                - fcpm: Cohesion score [0-1]
                - cohesion_level: very_low|low|medium|high|very_high
                - n_methods: Number of methods
                - n_components: Number of disconnected functional groups
                - n_disconnected_methods: Number of methods with no connections
                - disconnected_methods: List of disconnected method names
                - breakdown: {direct_invocations, indirect_invocations}
        
        Returns:
            List of diagnostic messages
        """
        messages = []
        
        # Skip files with n/a cohesion
        if metrics.get('cohesion_level') == 'not_applicable':
            return messages
        
        # Find matching rules
        for rule in self.rules:
            if self._match_rule(rule, metrics):
                message = self._generate_message(rule, file_path, metrics)
                messages.append(message)
                break  # Only apply first matching rule
        
        return messages
    
    def _match_rule(self, rule: Dict, metrics: Dict) -> bool:
        """
        Check if a rule's conditions match the file's metrics.
        
        Conditions can include:
        - cohesion_level: exact match
        - n_components: comparison (">1", "=1", etc.)
        - n_disconnected_methods: comparison (">0", "=0", etc.)
        - direct_invocations: comparison
        - indirect_invocations: comparison
        """
        conditions = rule.get('conditions', {})
        
        for key, expected in conditions.items():
            if key == 'cohesion_level':
                if metrics.get('cohesion_level') != expected:
                    return False
            
            elif key == 'n_components':
                if not self._evaluate_comparison(metrics.get('n_components', 0), expected):
                    return False
            
            elif key == 'n_disconnected_methods':
                if not self._evaluate_comparison(metrics.get('n_disconnected_methods', 0), expected):
                    return False
            
            elif key == 'direct_invocations':
                value = metrics.get('breakdown', {}).get('direct_invocations', 0)
                if not self._evaluate_comparison(value, expected):
                    return False
            
            elif key == 'indirect_invocations':
                value = metrics.get('breakdown', {}).get('indirect_invocations', 0)
                if not self._evaluate_comparison(value, expected):
                    return False
        
        return True
    
    def _evaluate_comparison(self, value: float, condition: str) -> bool:
        """Evaluate comparison conditions like '>1', '>=0.8', '=1', etc."""
        if isinstance(condition, (int, float)):
            return value == condition
        
        if not isinstance(condition, str):
            return False
        
        if condition.startswith('>='):
            threshold = float(condition[2:])
            return value >= threshold
        elif condition.startswith('<='):
            threshold = float(condition[2:])
            return value <= threshold
        elif condition.startswith('>'):
            threshold = float(condition[1:])
            return value > threshold
        elif condition.startswith('<'):
            threshold = float(condition[1:])
            return value < threshold
        elif condition.startswith('='):
            threshold = float(condition[1:])
            return value == threshold
        
        return False
    
    def _generate_message(
        self, 
        rule: Dict, 
        file_path: str, 
        metrics: Dict
    ) -> Dict[str, Any]:
        """
        Generate diagnosis and recommendation messages from a rule template.
        
        Templates can use placeholders:
        - {module_name}: File name without extension
        - {fcpm}: FCPM score (formatted to 2 decimal places)
        - {n_methods}: Number of methods
        - {n_components}: Number of disconnected functional groups
        - {n_disconnected_methods}: Number of completely disconnected methods
        - {disconnected_methods_str}: Comma-separated list of disconnected methods
        - {direct_invocations}: Count of direct invocations
        - {indirect_invocations}: Count of indirect invocations
        - {total_invocations}: Total connected pairs
        """
        # Extract module name from file path
        module_name = os.path.splitext(os.path.basename(file_path))[0]
        
        # Format disconnected methods list
        disconnected_methods = metrics.get('disconnected_methods', [])
        if disconnected_methods:
            if len(disconnected_methods) == 1:
                disconnected_methods_str = disconnected_methods[0]
            elif len(disconnected_methods) == 2:
                disconnected_methods_str = f"{disconnected_methods[0]} and {disconnected_methods[1]}"
            else:
                disconnected_methods_str = ', '.join(disconnected_methods[:-1]) + f' and {disconnected_methods[-1]}'
        else:
            disconnected_methods_str = ''
        
        # Prepare template context
        breakdown = metrics.get('breakdown', {})
        context = {
            'module_name': module_name,
            'fcpm': metrics.get('fcpm', 0.0),
            'n_methods': metrics.get('n_methods', 0),
            'n_components': metrics.get('n_components', 1),
            'n_disconnected_methods': metrics.get('n_disconnected_methods', 0),
            'disconnected_methods_str': disconnected_methods_str,
            'direct_invocations': breakdown.get('direct_invocations', 0),
            'indirect_invocations': breakdown.get('indirect_invocations', 0),
            'total_invocations': metrics.get('n_connected_pairs', 0)
        }
        
        # Render templates
        diagnosis = rule['diagnosis_template'].format(**context)
        recommendation = rule.get('recommendation_template')
        
        if recommendation:
            recommendation = recommendation.format(**context)
        
        return {
            'file': file_path,
            'diagnosis': diagnosis,
            'recommendation': recommendation,
            'severity': rule.get('severity', 'info'),
            'rule_id': rule.get('id', 0)
        }
