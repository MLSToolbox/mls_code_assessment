from typing import Dict, Optional
import os
from ..base_evaluator import BaseEvaluator


class CCPMEvaluator(BaseEvaluator):
    """
    Evaluator for CCPM (Conceptual Cohesion of Pipeline Modules) metrics.
    Matches calculated metrics against predefined rules to generate
    diagnosis and recommendations.
    """
    
    def __init__(self):
        """
        Initialize CCPM evaluator with rules from ccpm_rules.json.
        """
        rules_path = os.path.join(
            os.path.dirname(__file__),
            'ccpm_rules.json'
        )
        super().__init__(rules_path)
    
    def _match_rule(self, metrics: Dict) -> Optional[Dict]:
        """
        Match CCPM metrics against evaluation rules.

        Rules are keyed directly on the paper's binary indicators, already
        computed by analyzers.common.ccp_calculator.calculate_ccp():
            - mp (bool): spans multiple pipeline phases
            - ms (bool): spans multiple pipeline stages
            - mpc (bool): mixes ML pipeline code with non-pipeline code

        Files with no CCP_i level (mp/ms/mpc are None - non_ml_file or
        not_applicable) never match any rule, which is intentional: there's
        nothing to diagnose for a file without pipeline evidence.

        Args:
            metrics: Per-file metrics dict from CCPMAnalyzer._analyze_file

        Returns:
            Matched rule dict or None if no match found
        """
        mp = metrics.get('mp')
        ms = metrics.get('ms')
        mpc = metrics.get('mpc')

        if mp is None or ms is None or mpc is None:
            return None

        for rule in self.rules:
            conditions = rule['conditions']
            if conditions['mp'] != mp:
                continue
            if conditions['ms'] != ms:
                continue
            if conditions['mpc'] != mpc:
                continue
            return rule

        return None
