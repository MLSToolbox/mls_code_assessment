from typing import Dict, Optional, Any
import os
from ..base_evaluator import BaseEvaluator


class CCPPEvaluator(BaseEvaluator):
    """
    Evaluator for CCPP (Conceptual Cohesion of Pipeline Packages) metrics.

    Mirrors CCPMEvaluator: matches the package's mp/ms/mpc binary
    indicators (already computed by CCPPAnalyzer via the shared
    calculate_ccp()) against the 6-row rule table in ccpp_rules.json.
    Packages with no CCP_i level ('non_ml_package') never match any rule,
    the same way CCPM stays silent for non-ML files - there's nothing to
    diagnose about conceptual cohesion without pipeline evidence.
    """

    def __init__(self):
        rules_path = os.path.join(
            os.path.dirname(__file__),
            'ccpp_rules.json'
        )
        super().__init__(rules_path)

    def _match_rule(self, metrics: Dict) -> Optional[Dict]:
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

    def evaluate_package(
        self,
        package_path: str,
        package_metrics: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluate a single package and generate diagnosis/recommendation.

        Args:
            package_path: Path to the package
            package_metrics: Dict produced by CCPPAnalyzer._analyze_package
                (includes mp/ms/mpc/ccp_level, or None for non_ml_package)

        Returns:
            Dict with the same shape as BaseEvaluator.evaluate_file
            ('file', 'diagnosis', 'recommendation', 'severity', 'rule_id',
            'metrics'), or None if the package has no CCP_i level.
        """
        matched_rule = self._match_rule(package_metrics)
        if not matched_rule:
            return None

        package_name = os.path.basename(package_path) or package_path
        template_vars = {
            'package_name': package_name,
            'ccp_level': package_metrics.get('ccp_level'),
        }

        diagnosis = matched_rule['diagnosis'].format(**template_vars)
        if package_metrics.get('phase_mapping_incomplete'):
            diagnosis = (
                f"{diagnosis} (Note: some detected stages aren't mapped to a "
                "pipeline phase in the configuration, so the multi-phase check "
                "for this package may be under-counted.)"
            )

        recommendation = matched_rule.get('recommendation')
        if recommendation:
            recommendation = recommendation.format(**template_vars)

        return {
            'file': package_path,
            'diagnosis': diagnosis,
            'recommendation': recommendation,
            'severity': matched_rule.get('severity', 'info'),
            'rule_id': matched_rule['id'],
            'metrics': package_metrics,
        }
