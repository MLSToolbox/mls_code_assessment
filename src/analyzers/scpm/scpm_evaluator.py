import json
import os
from typing import Dict, List, Any, Optional


class SCPMEvaluator:
    """
    Evaluator that matches SCPM metrics against rules to generate diagnoses.
    
    Uses scpm_rules.json to determine appropriate messages based on:
    - Cohesion level (very_low, low, medium, high, very_high, not_applicable)
    - Number of methods
    - Number of disconnected components (LCOM analysis)
    - Shared resource counts (variables, files)
    - Type of sharing (class_attributes, global_variables, files)
    """
    
    def __init__(self):
        """Load rules from scpm_rules.json."""
        rules_path = os.path.join(os.path.dirname(__file__), 'scpm_rules.json')
        
        if not os.path.exists(rules_path):
            raise FileNotFoundError(f"SCPM rules file not found: {rules_path}")
        
        with open(rules_path, 'r') as f:
            rules_data = json.load(f)
        
        self.rules = rules_data.get('rules', [])
    
    def evaluate_file(
        self, 
        file_path: str, 
        metrics: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluate a single file's SCPM metrics against rules.
        
        Args:
            file_path: Path to the file
            metrics: Dict containing:
                - scpm: float (0.0-1.0)
                - cohesion_level: str
                - n_methods: int
                - n_components: int (from LCOM analysis)
                - n_disconnected_methods: int (methods with no connections)
                - disconnected_methods: List[str] (names of disconnected methods)
                - shared_variable_count: int
                - shared_file_count: int
                - shared_type: str (class_attributes, global_variables, files, mixed)
                - shared_vars: List[str]
                - shared_files: List[str]
        
        Returns:
            Dict with diagnosis, recommendation, severity, rule_id or None
        """
        # Skip if SCPM is not applicable
        if metrics.get('scpm') is None:
            return None
        
        # Match against rules
        for rule in self.rules:
            if self._match_rule(rule, metrics):
                return self._generate_message(rule, file_path, metrics)
        
        # Fallback if no rule matches
        return None
    
    def _match_rule(self, rule: Dict, metrics: Dict) -> bool:
        """
        Check if a rule's conditions match the metrics.
        
        Conditions can be:
        - cohesion_level: exact match ("very_low", "low", etc.)
        - n_methods: comparison (">1", "==1", etc.)
        - n_components: comparison (">1", "==1", etc.)
        - n_disconnected_methods: comparison (">0", etc.)
        - shared_file_count: comparison (">0", etc.)
        - shared_variable_count: comparison (">0", etc.)
        - shared_type: exact match ("class_attributes", "global_variables", etc.)
        """
        conditions = rule.get('conditions', {})
        
        for condition_key, condition_value in conditions.items():
            metric_value = metrics.get(condition_key)
            
            # Handle None values
            if metric_value is None:
                return False
            
            # Exact match for string conditions
            if isinstance(condition_value, str) and not any(
                op in condition_value for op in ['>', '<', '==', '!=', '>=', '<=']
            ):
                if str(metric_value) != condition_value:
                    return False
            
            # Comparison operators for numeric conditions
            elif isinstance(condition_value, str):
                if not self._evaluate_comparison(metric_value, condition_value):
                    return False
            
            # Direct equality for other types
            elif metric_value != condition_value:
                return False
        
        return True
    
    def _evaluate_comparison(self, value: Any, condition: str) -> bool:
        """
        Evaluate a comparison condition.
        
        Examples:
            - ">1" checks if value > 1
            - ">=0.5" checks if value >= 0.5
            - "==0" checks if value == 0
        """
        try:
            if condition.startswith('>='):
                return value >= float(condition[2:])
            elif condition.startswith('<='):
                return value <= float(condition[2:])
            elif condition.startswith('>'):
                return value > float(condition[1:])
            elif condition.startswith('<'):
                return value < float(condition[1:])
            elif condition.startswith('=='):
                return value == float(condition[2:])
            elif condition.startswith('!='):
                return value != float(condition[2:])
            else:
                return False
        except (ValueError, TypeError):
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
        - {scpm}: SCPM score (formatted to 2 decimal places)
        - {n_methods}: Number of methods
        - {n_components}: Number of disconnected components
        - {n_disconnected_methods}: Number of completely disconnected methods
        - {disconnected_methods_str}: Comma-separated list of disconnected methods
        - {shared_variable_count}: Count of shared variables
        - {shared_file_count}: Count of shared files
        - {shared_vars_str}: Comma-separated list of shared variables
        - {shared_files_str}: Comma-separated list of shared files
        """
        # Extract module name from file path
        module_name = os.path.splitext(os.path.basename(file_path))[0]
        
        # Format disconnected methods list
        disconnected_methods = metrics.get('disconnected_methods', [])
        if disconnected_methods:
            # Format: "method1, method2 and method3" or just "method1"
            if len(disconnected_methods) == 1:
                disconnected_methods_str = disconnected_methods[0]
            elif len(disconnected_methods) == 2:
                disconnected_methods_str = f"{disconnected_methods[0]} and {disconnected_methods[1]}"
            else:
                disconnected_methods_str = ', '.join(disconnected_methods[:-1]) + f' and {disconnected_methods[-1]}'
        else:
            disconnected_methods_str = ''
        
        # Prepare template context
        context = {
            'module_name': module_name,
            'scpm': metrics.get('scpm', 0.0),
            'n_methods': metrics.get('n_methods', 0),
            'n_components': metrics.get('n_components', 1),
            'n_disconnected_methods': metrics.get('n_disconnected_methods', 0),
            'disconnected_methods_str': disconnected_methods_str,
            'shared_variable_count': metrics.get('shared_variable_count', 0),
            'shared_file_count': metrics.get('shared_file_count', 0),
            'shared_vars_str': ', '.join(metrics.get('shared_vars', [])[:3]),  # Show first 3
            'shared_files_str': ', '.join(metrics.get('shared_files', [])[:3])  # Show first 3
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
            'rule_id': rule.get('id')
        }
