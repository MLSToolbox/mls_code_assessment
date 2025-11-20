from typing import Dict, Optional, Any, Set
import os
from ..base_evaluator import BaseEvaluator


class PFPEvaluator(BaseEvaluator):
    """
    Evaluator for PFP (Package Functional Purity) metrics.
    Matches calculated package-level metrics against predefined rules
    to generate diagnosis and recommendations.
    """
    
    def __init__(self):
        """
        Initialize PFP evaluator with rules from pfp_rules.json.
        """
        rules_path = os.path.join(
            os.path.dirname(__file__),
            'pfp_rules.json'
        )
        super().__init__(rules_path)
    
    def _match_rule(self, metrics: Dict) -> Optional[Dict]:
        """
        Match PFP package metrics against evaluation rules.
        
        Args:
            metrics: Dictionary containing PFP package metrics
        
        Returns:
            Matched rule dict or None if no match found
        """
        number_of_phases = metrics.get('number_of_phases', 0)
        number_of_stages = metrics.get('number_of_stages', 0)
        ml_ratio = metrics.get('ml_ratio', 0.0)
        average_elems_per_stage = metrics.get('average_elems_per_stage', 0.0)
        
        for rule in self.rules:
            conditions = rule['conditions']
            
            # Check number_of_phases condition
            if 'number_of_phases' in conditions:
                if conditions['number_of_phases'] != number_of_phases:
                    continue
            
            # Check number_of_stages condition
            if 'number_of_stages' in conditions:
                stage_cond = conditions['number_of_stages']
                if stage_cond == ">1":
                    if number_of_stages <= 1:
                        continue
                elif isinstance(stage_cond, int):
                    if stage_cond != number_of_stages:
                        continue
                else:
                    continue
            
            # Check ml_ratio condition
            if 'ml_ratio' in conditions:
                ml_ratio_cond = conditions['ml_ratio']
                if ml_ratio_cond == 1:
                    if ml_ratio < 1.0:
                        continue
                elif ml_ratio_cond == "<1":
                    if ml_ratio >= 1.0:
                        continue
                elif ml_ratio_cond == 0:
                    if ml_ratio != 0:
                        continue
                else:
                    continue
            
            # Check average_elems_per_stage condition
            if 'average_elems_per_stage' in conditions:
                avg_cond = conditions['average_elems_per_stage']
                if avg_cond == ">1":
                    if average_elems_per_stage <= 1:
                        continue
                elif avg_cond == 1:
                    if average_elems_per_stage != 1:
                        continue
                elif avg_cond == "<1":
                    if average_elems_per_stage >= 1:
                        continue
                else:
                    continue
            
            # All conditions matched
            return rule
        
        # No rule matched
        return None
    
    def evaluate_package(
        self, 
        package_path: str, 
        package_metrics: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluate a single package and generate diagnosis/recommendation.
        
        Args:
            package_path: Path to the package
            package_metrics: Dictionary with package PFP metrics
            
        Returns:
            Evaluation result dict with diagnosis, recommendation, and severity,
            or None if no issues found (High purity with good structure)
        """
        # Calculate number of phases (unique phases across all detected stages)
        phases_detected = set(package_metrics.get('phases_detected', []))
        number_of_phases = len(phases_detected)
        
        # Get number of stages
        number_of_stages = package_metrics.get('unique_stages_found', 0)
        
        # Calculate ml_ratio
        ml_modules = package_metrics.get('ml_modules', 0)
        total_modules = package_metrics.get('total_modules', 1)
        ml_ratio = ml_modules / total_modules if total_modules > 0 else 0
        
        # Calculate average elements per stage
        average_elems_per_stage = 0
        if number_of_stages > 0:
            modules = package_metrics.get('modules', [])
            stage_counts: Dict[str, int] = {}
            for module in modules:
                for stage in module.get('stages', []):
                    stage_counts[stage] = stage_counts.get(stage, 0) + 1
            
            if stage_counts:
                total_elems = sum(stage_counts.values())
                average_elems_per_stage = total_elems / len(stage_counts)
        
        # Prepare metrics for rule matching
        metrics_for_matching = {
            'number_of_phases': number_of_phases,
            'number_of_stages': number_of_stages,
            'ml_ratio': ml_ratio,
            'average_elems_per_stage': average_elems_per_stage,
            'pfp_score': package_metrics.get('pfp_score', 0.0),
            'ml_modules': ml_modules,
            'total_modules': total_modules
        }
        
        # Find matching rule
        matched_rule = self._match_rule(metrics_for_matching)
        
        if not matched_rule:
            return None
        
        # Skip "info" severity messages (high purity, no issues)
        if matched_rule.get('severity') == 'info':
            return None
        
        # Extract package name from path
        package_name = os.path.basename(package_path) or package_path
        
        # Prepare template variables
        template_vars = {
            'package_name': package_name,
            'pfp_score': package_metrics.get('pfp_score', 0.0)
        }
        
        # Format diagnosis and recommendation
        diagnosis = matched_rule['diagnosis'].format(**template_vars)
        recommendation = matched_rule['recommendation'].format(**template_vars)
        
        return {
            'file': package_path,
            'severity': matched_rule['severity'],
            'diagnosis': diagnosis,
            'recommendation': recommendation,
            'rule_id': matched_rule['id']
        }
