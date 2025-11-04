from typing import Dict, Optional
import os
from ..base_evaluator import BaseEvaluator


class FPCEvaluator(BaseEvaluator):
    """
    Evaluator for FPC (Functional Pipeline Cohesion) metrics.
    Matches calculated metrics against predefined rules to generate
    diagnosis and recommendations.
    """
    
    def __init__(self):
        """
        Initialize FPC evaluator with rules from fpc_rules.json.
        """
        rules_path = os.path.join(
            os.path.dirname(__file__),
            'fpc_rules.json'
        )
        super().__init__(rules_path)
    
    def _match_rule(self, metrics: Dict) -> Optional[Dict]:
        """
        Match FPC metrics against evaluation rules.
        
        Args:
            metrics: Dictionary containing FPC metrics:
                - unique_phases (int): Number of unique phases
                - unique_stages (int): Number of unique stages  
                - has_no_ml_content (bool): True if non-ML content detected
                - nloc (int): Non-comment lines of code
                - above_nloc_threshold (bool): True if NLOC exceeds threshold
        
        Returns:
            Matched rule dict or None if no match found
        """
        unique_phases = metrics.get('unique_phases', 0)
        unique_stages = metrics.get('unique_stages', 0)
        has_no_ml_content = metrics.get('has_no_ml_content', False)
        above_nloc_threshold = metrics.get('above_nloc_threshold', False)
        
        # Convert has_no_ml_content to ml_content_only for matching
        # ml_content_only is True when there is NO non-ML content
        ml_content_only = not has_no_ml_content
        
        for rule in self.rules:
            conditions = rule['conditions']
            
            # Check phases condition
            phases_cond = conditions['phases']
            if phases_cond != unique_phases:
                continue
            
            # Check stages condition
            stages_cond = conditions['stages']
            if stages_cond == 1:
                if unique_stages != 1:
                    continue
            elif stages_cond == ">1":
                if unique_stages <= 1:
                    continue
            elif stages_cond == "any":
                # Any number of stages is acceptable
                pass
            else:
                # Unknown condition, skip rule
                continue
            
            # Check ml_content_only condition
            ml_cond = conditions['ml_content_only']
            if ml_cond != ml_content_only:
                continue
            
            # Check nloc_above_threshold condition (if present in rule)
            if 'nloc_above_threshold' in conditions:
                nloc_cond = conditions['nloc_above_threshold']
                if nloc_cond != above_nloc_threshold:
                    continue
            
            # All conditions matched, return this rule
            return rule
        
        # No rule matched
        return None
