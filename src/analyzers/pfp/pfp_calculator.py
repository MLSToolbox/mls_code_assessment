from typing import Dict, List, Set, Any


class PFPCalculator:
    """
    Calculator for Package Functional Purity (PFP) metrics.
    
    Calculates PFP score based on:
    1. ML content ratio (n_ml / n_total)
    2. Stage diversity penalty (cohesion factor CF)
    """
    
    def __init__(self, etapas_max: int = 6):
        """
        Initialize PFP calculator.
        
        Args:
            etapas_max: Maximum number of pipeline stages (updated to 6 stages)
        """
        self.etapas_max = etapas_max
    
    def calculate_pfp(
        self, 
        n_total: int, 
        n_ml: int, 
        unique_stages: int
    ) -> float:
        """
        Calculate PFP score for a package.
        
        Formula: PFP = (n_ml / n_total) × CF
        where CF = 1 - ((n_stages - 1) / (ETAPAS_MAX - 1))
        
        Args:
            n_total: Total number of modules in package
            n_ml: Number of ML-related modules
            unique_stages: Number of unique pipeline stages detected
            
        Returns:
            PFP score between 0 and 1
        """
        if n_total == 0:
            return 0.0
        cf = 1.0
        if self.etapas_max > 1 and unique_stages > 1:
            cf = 1 - ((unique_stages - 1) / (self.etapas_max - 1))
        pfp_score = (n_ml / n_total) * cf
        
        return round(pfp_score, 4)
    
    def get_purity_level(self, pfp_score: float) -> str:
        """
        Determines qualitative purity level from PFP score.
        
        Args:
            pfp_score: PFP score (0-1)
            
        Returns:
            Purity level: "High", "Moderate", "Low", or "Very Low"
        """
        if pfp_score > 0.8:
            return "High"
        if pfp_score >= 0.6:
            return "Moderate"
        if pfp_score >= 0.4:
            return "Low"
        return "Very Low"
    
    def get_overall_quality(self, average_pfp: float) -> str:
        """
        Determines overall project quality based on average PFP.
        
        Args:
            average_pfp: Average PFP across all packages
            
        Returns:
            Quality level: "Excellent", "Good", "Fair", or "Critical"
        """
        if average_pfp > 0.8:
            return "Excellent"
        if average_pfp >= 0.6:
            return "Good"
        if average_pfp >= 0.4:
            return "Fair"
        return "Critical"
    
    def aggregate_package_metrics(
        self, 
        modules_fpc_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Aggregate FPC results from multiple modules into package-level metrics.
        
        Args:
            modules_fpc_results: List of FPC results for each module
            
        Returns:
            Dictionary with aggregated package metrics:
            - n_total: Total modules
            - n_ml: ML modules
            - all_stages: Set of unique stages
            - modules_info: Per-module details
        """
        n_total = len(modules_fpc_results)
        n_ml = 0
        all_stages: Set[str] = set()
        modules_info: List[Dict[str, Any]] = []
        
        for fpc_result in modules_fpc_results:
            if fpc_result and fpc_result.get('stages_detected'):
                n_ml += 1
                all_stages.update(fpc_result['stages_detected'])
                modules_info.append({
                    'path': fpc_result.get('file_path', 'unknown'),
                    'stages': list(fpc_result.get('stages_detected', [])),
                    'cohesion': fpc_result.get('cohesion_level')
                })
            else:
                modules_info.append({
                    'path': fpc_result.get('file_path', 'unknown') if fpc_result else 'unknown',
                    'stages': [],
                    'cohesion': None
                })
        
        return {
            'n_total': n_total,
            'n_ml': n_ml,
            'all_stages': all_stages,
            'modules_info': modules_info
        }
    
    def get_etapas_max(self) -> int:
        """Get maximum number of stages configured."""
        return self.etapas_max
