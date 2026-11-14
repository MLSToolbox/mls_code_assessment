from typing import Dict, List, Set, Any


class CCPPCalculator:
    """
    Aggregation helper for CCPP (Conceptual Cohesion of Pipeline Packages).

    The actual CCP_i level/MP/MS/MPC arithmetic lives in the shared
    analyzers.common.ccp_calculator.calculate_ccp(), used identically by
    CCPM (modules) and CCPP (packages) per the paper's formula. This class
    is responsible only for turning a package's modules into the inputs
    that function needs (unique phases/stages, mixed-content flag), plus
    a couple of presentation helpers.
    """

    def __init__(self, etapas_max: int = 5):
        self.etapas_max = etapas_max

    def aggregate_package_metrics(
        self,
        modules_ccpm_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Aggregate CCPM results from multiple modules into package-level metrics.

        Args:
            modules_ccpm_results: List of CCPM results for each module

        Returns:
            Dictionary with aggregated package metrics:
            - n_total: Total modules
            - n_ml: ML modules (modules with at least one detected stage)
            - all_stages: Set of unique stages
            - modules_info: Per-module details
        """
        n_total = len(modules_ccpm_results)
        n_ml = 0
        all_stages: Set[str] = set()
        modules_info: List[Dict[str, Any]] = []

        for ccpm_result in modules_ccpm_results:
            if ccpm_result and ccpm_result.get('stages_detected'):
                n_ml += 1
                all_stages.update(ccpm_result['stages_detected'])
                modules_info.append({
                    'path': ccpm_result.get('file_path', 'unknown'),
                    'stages': list(ccpm_result.get('stages_detected', [])),
                    'cohesion': ccpm_result.get('cohesion_level')
                })
            else:
                modules_info.append({
                    'path': ccpm_result.get('file_path', 'unknown') if ccpm_result else 'unknown',
                    'stages': [],
                    'cohesion': ccpm_result.get('cohesion_level')
                })

        return {
            'n_total': n_total,
            'n_ml': n_ml,
            'all_stages': all_stages,
            'modules_info': modules_info
        }

    def has_mixed_content(
        self,
        n_total: int,
        n_ml: int,
        modules_ccpm_results: List[Dict[str, Any]]
    ) -> bool:
        """
        MPC(package): True if the package mixes ML pipeline code with code
        foreign to the pipeline. This is true if either:
        - Not every module in the package belongs to the pipeline (n_ml < n_total), or
        - A pipeline module itself already mixes in non-pipeline code (its own MPC=True).
        """
        if n_ml < n_total:
            return True
        return any(
            ccpm_result.get('mpc') for ccpm_result in modules_ccpm_results
            if ccpm_result and ccpm_result.get('mpc') is not None
        )

    def get_overall_quality(self, average_ccp_level: float) -> str:
        """
        Determine overall project quality from the average CCP_i level (1-5).
        """
        if average_ccp_level >= 4.5:
            return "Excellent"
        if average_ccp_level >= 3.5:
            return "Good"
        if average_ccp_level >= 2.5:
            return "Fair"
        return "Critical"

    def get_etapas_max(self) -> int:
        return self.etapas_max
