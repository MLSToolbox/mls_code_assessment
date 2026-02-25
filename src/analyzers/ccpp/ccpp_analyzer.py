import os
from typing import Any, Dict, List
from collections import defaultdict
from core.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer
from analyzers.ccpp.ccpp_calculator import CCPPCalculator
from analyzers.ccpp.ccpp_evaluator import CCPPEvaluator
from analyzers.common.package_utils import transverse_tree_to_get_packages_and_files
from analyzers.pipeline.pipeline_schema import get_pipeline_schema
class CCPPAnalyzer(BaseAnalyzer):
    """
    Conceptual Cohesion of Pipeline Packages (CCPP) Analyzer.
    
    Evaluates conceptual cohesion at the package level by detecting if the package
    mixes responsibilities from different ML pipeline tasks or stages, violating 
    the package-level Single Responsibility Principle.
    
    Analyzes:
    1. ML pipeline stage/phase presence (aggregating CCPM metrics from modules)
    2. Responsibility mixing detection (single vs multiple stages in package)
    3. ML content presence (ratio of ML modules to total modules)
    4. Package Functional Purity (combining content ratio and stage focus)
    
    Cohesion Levels:
    - High: Single stage, high density of ML content (focused package)
    - Moderate: Mostly single stage but with some noise or non-ML files
    - Low: Distinct pipeline stages mixed together (e.g. Training + Deployment)
    - Very Low: Multiple phases/stages mixed with high ratio of non-ML content
    """
    @property
    def analyzer_id(self) -> str:
        return "ccpp"
    def __init__(self, session_id: str, local_path: str, context=None):
        super().__init__(session_id, local_path, context)
        self.schema = get_pipeline_schema()
        self.config = self.schema.raw_config
        num_stages = len(self.schema.valid_stages)
        max_stages = num_stages if num_stages > 0 else 1
        self.calculator = CCPPCalculator(etapas_max=max_stages)
        self.evaluator = CCPPEvaluator()
    def analyze(self) -> AnalysisResult:
        packages=self.context.get_packages_and_files()
        total_ccpp_score = 0
        if not packages:
            return self._create_result(
                score=0, 
                messages=[],
                module_count=0,
                details={"message": "No Python packages found to analyze."},
                group_key='by_package'
            )
        for pkg in packages:
            pkg["ccpp"]=self._analyze_package(pkg)
            total_ccpp_score += pkg["ccpp"]['ccpp_score']
            evaluation=self.evaluator.evaluate_package(pkg["path"], pkg["ccpp"])
            if evaluation:
                pkg["evaluation"] = evaluation
            else:
                pkg["evaluation"] = None
        average_ccpp = total_ccpp_score / len(packages)
        final_score = round(average_ccpp * 10, 2)
        return self._create_result(
            score=final_score,
            messages=[pkg["evaluation"] for pkg in packages if pkg["evaluation"]!=None],  
            module_count=len(self.context.get_python_files()),
            details={
                "summary": {
                    "total_packages_analyzed": len(packages),
                    "average_ccpp_score": round(average_ccpp, 4),
                    "overall_quality": self.calculator.get_overall_quality(average_ccpp),
                    "packages_needing_attention": len([p for p in packages if p['ccpp']['ccpp_score'] < 0.6]),
                    "packages_with_good_purity": len([p for p in packages if p['ccpp']['ccpp_score'] >= 0.6]),
                    "etapas_max": self.calculator.get_etapas_max(),
                    "purity_summary": self._generate_summary(packages)
                },
                "packages": self._format_package_results(packages)
            },
            group_key='by_package'
        )
    def _analyze_package(self, pkg: Dict) -> Dict[str, Any]:
        """
        Calculates CCPP for a single package by reusing CCPM metrics.
        
        Args:
            pkg_path: Package directory path
            modules: List of module file paths in package
            
        Returns:
            Dictionary with package CCPP metrics, including:
            - ccpp_score: Final calculated score
            - cohesion_level: Qualitative assessment
            - unique_stages/phases: Counts used for calculation
        """
        ccpm_results = []
        for module_path in pkg["modules"]:
            ccpm_result = self.context.get_file_metric(module_path, 'ccpm')
            module_metric = dict(ccpm_result) if ccpm_result else {}
            module_metric['file_path'] = module_path
            module_metric.setdefault('stages_detected', [])
            module_metric.setdefault('phases_detected', [])
            module_metric.setdefault('cohesion_level', None)
            ccpm_results.append(module_metric)
        aggregated = self.calculator.aggregate_package_metrics(ccpm_results)
        n_total = aggregated['n_total']
        n_ml = aggregated['n_ml']
        all_stages = aggregated['all_stages']

        modules_info = aggregated['modules_info']
        n_etapas = len(all_stages)
        all_phases = set()
        for ccpm_result in ccpm_results:
            all_phases.update(ccpm_result.get('phases_detected', []))
        n_phases = len(all_phases)
        ccpp_score = self.calculator.calculate_ccpp(n_total, n_ml, n_etapas, n_phases)
        package_metrics = {
            'total_modules': n_total,
            'ml_modules': n_ml,
            'unique_stages_found': n_etapas,
            'stage_types': sorted(list(all_stages)),
            'phases_detected': sorted(list(all_phases)),
            'ccpp_score': ccpp_score,
            'modules': modules_info
        }
        cohesion_level = self.calculator.get_cohesion_level(package_metrics)
        package_metrics['cohesion_level'] = cohesion_level
        return package_metrics
   
    def _format_package_results(self, results: Dict) -> Dict:
        """Formats package results with better structure."""
        formatted = {}
        for pkg in results:
            formatted[pkg["path"]] = {
                "metrics": {
                    "total_modules": pkg['ccpp']['total_modules'],
                    "ml_modules": pkg['ccpp']['ml_modules'],
                    "ccpp_score": pkg['ccpp']['ccpp_score'],
                    "cohesion_level": pkg['ccpp']['cohesion_level']
                },
                "phases_detected": pkg['ccpp']['phases_detected'],
                "stages_detected": pkg['ccpp']['stage_types'],
                "quality_indicators": {
                    "needs_refactoring": pkg['ccpp']['ccpp_score'] < 0.6,
                    "has_ml_content": pkg['ccpp']['ml_modules'] > 0,
                    "is_pure_package": pkg['ccpp']['ml_modules'] == pkg['ccpp']['total_modules'] and pkg['ccpp']['unique_stages_found'] == 1
                },
            }
        return formatted  
    def _generate_summary(self, results: List[Dict]) -> Dict:
        summary = {"very_high": 0, "high": 0, "medium": 0, "low": 0, "very_low": 0}
        for pkg in results:
            level = pkg['ccpp']['cohesion_level']
            summary[level] += 1
        return summary