import json
import os
from typing import Dict, List, Any, Optional

class FCPPEvaluator:
    """
    Evaluator that matches FCPP (Package-Level Functional) metrics against rules.
    
    It applies rules defined in 'fcpp_rules.json' to diagnose cohesion issues based on:
    1. FCPP Score (0.0 to 1.0)
    2. LCOM Analysis:
       - Isolated Nodes: Modules that do not call any other module.
       - Disconnected Groups: Sets of modules that interact within the group but not with other groups.
       
    Example Recommendation logic:
    - If n_groups > 1: "Package should be split into X smaller subpackages."
    """
    
    def __init__(self):
        rules_path = os.path.join(os.path.dirname(__file__), 'fcpp_rules.json')
        if not os.path.exists(rules_path):
            raise FileNotFoundError(f"FCPP rules file not found: {rules_path}")
        
        with open(rules_path, 'r') as f:
            data = json.load(f)
            self.rules = data.get('rules', [])

    def evaluate_package(self, package_path: str, metrics: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if metrics.get('fcpp') is None:
            return None
        eval_metrics = metrics.copy()
        isolated = eval_metrics.get('isolated_nodes', [])
        eval_metrics['isolated_nodes_count'] = len(isolated)
        groups = eval_metrics.get('groups', [])
        eval_metrics['n_groups'] = len(groups) if len(groups) > 0 else 1

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
                if metric_val != value: return False
                
        return True

    def _generate_message(self, rule: Dict, package_path: str, metrics: Dict) -> Dict[str, Any]:
        pkg_name = os.path.basename(package_path)
        
        isolated = metrics.get('isolated_nodes', [])
        isolated_str = ", ".join(isolated)
        
        groups = metrics.get('groups', [])
        group_strs = ["{" + ", ".join(map(os.path.basename, g)) + "}" for g in groups]
        groups_str = ", ".join(group_strs)

        context = {
            'package_name': pkg_name,
            'fcpp': metrics.get('fcpp', 0.0),
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
