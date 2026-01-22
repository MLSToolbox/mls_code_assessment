import json
import os
from typing import Dict, List, Any, Optional

class SCPPEvaluator:
    """
    Evaluator that matches SCPP metrics against rules to generate diagnoses.
    
    Uses scpp_rules.json to determine appropriate messages based on:
    - SCPP Score (float value 0.0-1.0)
    - Number of disconnected groups (n_groups)
    - Count of isolated nodes (isolated_nodes_count)
    """
    
    def __init__(self):
        # Load rules from same directory
        rules_path = os.path.join(os.path.dirname(__file__), 'scpp_rules.json')
        if not os.path.exists(rules_path):
            raise FileNotFoundError(f"SCPP rules file not found: {rules_path}")
        
        with open(rules_path, 'r') as f:
            data = json.load(f)
            self.rules = data.get('rules', [])

    def evaluate_package(self, package_path: str, metrics: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Evaluate SCPP metrics for a single package.
        """
        if metrics.get('scpp') is None:
            return None

        # Enhance metrics for easier rule matching
        eval_metrics = metrics.copy()
        
        # Count isolated nodes
        isolated = eval_metrics.get('isolated_nodes', [])
        eval_metrics['isolated_nodes_count'] = len(isolated)
        
        # Groups count
        groups = eval_metrics.get('groups', [])
        eval_metrics['n_groups'] = len(groups) if len(groups) > 0 else 1

        # Match rules (Priority order implicitly defined by JSON order)
        for rule in self.rules:
            if self._match_rule(rule, eval_metrics):
                return self._generate_message(rule, package_path, eval_metrics)
        
        return None

    def _match_rule(self, rule: Dict, metrics: Dict) -> bool:
        conditions = rule.get('conditions', {})
        for key, value in conditions.items():
            metric_val = metrics.get(key)
            if metric_val is None:
                return False
            
            # String comparison (commands)
            if isinstance(value, str):
                if value.startswith('>='):
                    if not (float(metric_val) >= float(value[2:])): return False
                elif value.startswith('<='):
                    if not (float(metric_val) <= float(value[2:])): return False
                elif value.startswith('>'):
                    if not (float(metric_val) > float(value[1:])): return False
                elif value.startswith('<'):
                    if not (float(metric_val) < float(value[1:])): return False
                elif value.startswith('=='):
                    if not (float(metric_val) == float(value[2:])): return False
            else:
                # Direct equality
                if metric_val != value: return False
                
        return True

    def _generate_message(self, rule: Dict, package_path: str, metrics: Dict) -> Dict[str, Any]:
        """Fill templates with metric data."""
        pkg_name = os.path.basename(package_path)

        
        # Format lists for display
        isolated = metrics.get('isolated_nodes', [])
        isolated_str = ", ".join(isolated)
        
        groups = metrics.get('groups', [])
        group_strs = ["{" + ", ".join(map(os.path.basename, g)) + "}" for g in groups]
        groups_str = ", ".join(group_strs)

        context = {
            'package_name': pkg_name,
            'scpp': metrics.get('scpp', 0.0),
            'isolated_nodes_str': isolated_str,
            'groups_str': groups_str,
            'n_groups': len(groups)
        }

        diagnosis = rule['diagnosis_template'].format(**context)
        recommendation = rule['recommendation_template'].format(**context)

        return {
            'file': package_path,
            'diagnosis': diagnosis,
            'recommendation': recommendation,
            'severity': rule.get('severity', 'info'),
            'rule_id': rule.get('id')
        }
