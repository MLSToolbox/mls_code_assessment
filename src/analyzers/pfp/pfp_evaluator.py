from typing import Dict, Optional, Any
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
            metrics: Dictionary containing PFP package metrics:
                - purity_level (str): "High", "Moderate", "Low", or "Very Low"
                - has_ml_content (bool): True if package has ML modules
                - stage_count (int): Number of unique pipeline stages
                - pfp_score (float): PFP score (0-1)
                - ml_modules (int): Number of ML modules
                - total_modules (int): Total number of modules
        
        Returns:
            Matched rule dict or None if no match found
        """
        purity_level = metrics.get('purity_level', 'Very Low')
        has_ml_content = metrics.get('has_ml_content', False)
        stage_count = metrics.get('stage_count', 0)
        
        for rule in self.rules:
            conditions = rule['conditions']
            
            # Check purity_level condition
            if conditions['purity_level'] != purity_level:
                continue
            
            # Check has_ml_content condition
            if conditions['has_ml_content'] != has_ml_content:
                continue
            
            # Check stage_count condition
            stage_cond = conditions['stage_count']
            if stage_cond == ">1":
                if stage_count <= 1:
                    continue
            elif stage_cond == 1:
                if stage_count != 1:
                    continue
            elif stage_cond == 0:
                if stage_count != 0:
                    continue
            else:
                # Unknown condition, skip rule
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
        # Prepare metrics for rule matching
        metrics_for_matching = {
            'purity_level': package_metrics.get('purity_level', 'Very Low'),
            'has_ml_content': package_metrics.get('ml_modules', 0) > 0,
            'stage_count': package_metrics.get('unique_stages_found', 0),
            'pfp_score': package_metrics.get('pfp_score', 0.0),
            'ml_modules': package_metrics.get('ml_modules', 0),
            'total_modules': package_metrics.get('total_modules', 0)
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
            'pfp_score': package_metrics.get('pfp_score', 0.0),
            'ml_modules': package_metrics.get('ml_modules', 0),
            'total_modules': package_metrics.get('total_modules', 0),
            'stage_count': package_metrics.get('unique_stages_found', 0),
            'stages_list': ', '.join(package_metrics.get('stage_types', [])),
            'non_ml_count': package_metrics.get('total_modules', 0) - package_metrics.get('ml_modules', 0),
            'dominant_stage': self._get_dominant_stage(package_metrics)
        }
        
        # Format diagnosis and recommendation
        diagnosis = matched_rule['diagnosis_template'].format(**template_vars)
        recommendation = matched_rule['recommendation_template'].format(**template_vars)
        
        return {
            'file': package_path,  # Use 'file' key to match BaseAnalyzer._create_result() expectations
            'severity': matched_rule['severity'],
            'diagnosis': diagnosis,
            'recommendation': recommendation,
            'rule_id': matched_rule['id']
        }
    
    def _get_dominant_stage(self, package_metrics: Dict) -> str:
        """
        Get the dominant stage in a package (stage with most files).
        
        Args:
            package_metrics: Package metrics dictionary
            
        Returns:
            Name of dominant stage or 'unknown'
        """
        modules = package_metrics.get('modules', [])
        if not modules:
            return 'unknown'
        
        # Count files per stage
        stage_counts: Dict[str, int] = {}
        for module in modules:
            for stage in module.get('stages', []):
                stage_counts[stage] = stage_counts.get(stage, 0) + 1
        
        if not stage_counts:
            return 'unknown'
        
        # Return stage with most files
        return max(stage_counts, key=stage_counts.get)
