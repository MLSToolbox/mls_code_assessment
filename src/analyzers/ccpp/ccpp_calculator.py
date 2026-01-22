from typing import Dict, List, Set, Any


class CCPPCalculator:
    """
    Calculator for Package Functional Purity (CCPP) metrics.
    
    Calculates CCPP score based on:
    1. ML content ratio (n_ml / n_total)
    2. Stage diversity penalty (cohesion factor CF)
    """
    def __init__(self, etapas_max: int = 5):
        """
        Initialize CCPP calculator.
        
        Args:
            etapas_max: Maximum number of pipeline stages (dynamically sourced from config)
        """
        self.etapas_max = etapas_max
    def calculate_ccpp(
        self, 
        n_total: int, 
        n_ml: int, 
        unique_stages: int,
        unique_phases: int = 0
    ) -> float:
        """
        Calculate CCPP score for a package.
        Formula: CCPP = (n_ml / n_total) × CF
        The Cohesion Factor (CF) is calculated based on stage diversity:
        1. Single Stage: CF = 1.0 (Ideal)
        2. Multiple Stages:
           - Same Phase (Affinity Bonus): Penalty is halved. Mixing related stages (e.g., Collection & Cleaning) is less severe.
             CF = 1 - ((n_stages - 1) / (ETAPAS_MAX - 1)) * 0.5
           - Different Phases: Full penalty. Mixing unrelated stages (e.g., Cleaning & Training) reduces cohesion significantly.
             CF = 1 - ((n_stages - 1) / (ETAPAS_MAX - 1))
        
        Args:
            n_total: Total modules in package
            n_ml: Modules identified as part of the ML pipeline
            unique_stages: Count of distinct pipeline stages found
            unique_phases: Count of distinct pipeline phases (Data Engineering vs Model Development)
            
        Returns:
            CCPP score (0-1)
        """
        if n_total == 0:
            return 0.0
        cf = 1.0
        if self.etapas_max > 1 and unique_stages > 1:
            base_penalty = (unique_stages - 1) / (self.etapas_max - 1)
            # Affinity Bonus: If all stages belong to the same phase, halve the penalty
            if unique_phases == 1:
                cf = 1 - (base_penalty * 0.5)
            else:
                cf = 1 - base_penalty 
        ccpp_score = (n_ml / n_total) * cf
        return round(ccpp_score, 4)
    def get_purity_level(self, ccpp_score: float) -> str:
        """
        Determines qualitative purity level from CCPP score.
        Args:
            ccpp_score: CCPP score (0-1)  
        Returns:
            Purity level: "High", "Moderate", "Low", or "Very Low"
        """
        if ccpp_score > 0.8:
            return "High"
        if ccpp_score >= 0.6:
            return "Moderate"
        if ccpp_score >= 0.4:
            return "Low"
        return "Very Low"
    
    def get_overall_quality(self, average_ccpp: float) -> str:
        """
        Determines overall project quality based on average CCPP.
        
        Args:
            average_ccpp: Average CCPP across all packages
            
        Returns:
            Quality level: "Excellent", "Good", "Fair", or "Critical"
        """
        if average_ccpp > 0.8:
            return "Excellent"
        if average_ccpp >= 0.6:
            return "Good"
        if average_ccpp >= 0.4:
            return "Fair"
        return "Critical"
    
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
            - n_ml: ML modules
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
    def get_etapas_max(self) -> int:
        return self.etapas_max
