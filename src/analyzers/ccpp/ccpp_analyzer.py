import os
import json
from typing import Dict, List, Set, Any
from collections import defaultdict
from core.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer
from analyzers.ccpp.ccpp_calculator import CCPPCalculator
from analyzers.ccpp.ccpp_evaluator import CCPPEvaluator
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
        pipeline_stages_json_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'pipeline',
            'pipeline_stages.json'
        )
        if os.path.exists(pipeline_stages_json_path):
            with open(pipeline_stages_json_path, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {"stages": {}}
            
        num_stages = len(self.config.get('stages', {}))
        max_stages = num_stages if num_stages > 0 else 5
        self.calculator = CCPPCalculator(etapas_max=max_stages)
        self.evaluator = CCPPEvaluator()
    def analyze(self) -> AnalysisResult:
        packages = self._discover_packages()
        package_results = {}
        total_ccpp_score = 0
        messages_list = []
        if not packages:
            return self._create_result(
                score=0, 
                messages=[],
                module_count=0,
                details={"message": "No Python packages found to analyze."}
            )
        for pkg_path, modules in packages.items():
            package_results[pkg_path] = self._analyze_package(pkg_path, modules)
            total_ccpp_score += package_results[pkg_path]['ccpp_score']
            evaluation = self.evaluator.evaluate_package(pkg_path, package_results[pkg_path])
            if evaluation:
                messages_list.append(evaluation)
        average_ccpp = total_ccpp_score / len(packages)
        final_score = round(average_ccpp * 10, 2)
        return self._create_result(
            score=final_score,
            messages=messages_list,  
            module_count=len(self.context.get_all_python_files()),
            details={
                "summary": {
                    "total_packages_analyzed": len(packages),
                    "average_ccpp_score": round(average_ccpp, 4),
                    "overall_quality": self.calculator.get_overall_quality(average_ccpp),
                    "packages_needing_attention": len([p for p in package_results.values() if p['ccpp_score'] < 0.6]),
                    "packages_with_good_purity": len([p for p in package_results.values() if p['ccpp_score'] >= 0.6]),
                    "etapas_max": self.calculator.get_etapas_max(),
                    "purity_summary": self._generate_summary(package_results)
                },
                "packages": self._format_package_results(package_results)
            },
            
        )
    def _analyze_package(self, pkg_path: str, modules: List[str]) -> Dict[str, Any]:
        """
        Calculates CCPP for a single package by reusing CCPM metrics.
        
        Args:
            pkg_path: Package directory path
            modules: List of module file paths in package
            
        Returns:
            Dictionary with package CCPP metrics, including:
            - ccpp_score: Final calculated score
            - purity_level: Qualitative assessment
            - unique_stages/phases: Counts used for calculation
        """
        ccpm_results = []
        for module_path in modules:
            ccpm_result = self.context.get_file_metric(module_path, 'ccpm')
            if ccpm_result:
                ccpm_result['file_path'] = module_path
                ccpm_results.append(ccpm_result)
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
        purity_level = self.calculator.get_purity_level(ccpp_score)
        return {
            "total_modules": n_total,
            "ml_modules": n_ml,
            "unique_stages_found": n_etapas,
            "stage_types": sorted(list(all_stages)),
            "phases_detected": sorted(list(all_phases)),
            "ccpp_score": ccpp_score,
            "purity_level": purity_level,
            "modules": modules_info
        }  
    def _discover_packages(self) -> Dict[str, List[str]]:
        """
        Identifies packages and their contained modules.
        A package is a directory containing Python files.
        """
        packages: Dict[str, List[str]] = defaultdict(list)
        python_files = self.context.get_all_python_files()

        for file_path in python_files:
            if file_path.endswith('__init__.py'):
                continue  
            package_path = os.path.dirname(file_path) or '.'
            packages[package_path].append(file_path) 
        return dict(packages)
    def _is_ccpm_data_available(self) -> bool:
        """Checks if any file has CCPM data in the context."""
        for py_file in self.context.get_all_python_files():
            if self.context.has_file_metric(py_file, 'ccpm'):
                return True
        return False
    def _format_package_results(self, results: Dict) -> Dict:
        """Formats package results with better structure."""
        formatted = {}
        for pkg_path, data in results.items():
            formatted[pkg_path] = {
                "metrics": {
                    "total_modules": data['total_modules'],
                    "ml_modules": data['ml_modules'],
                    "ccpp_score": data['ccpp_score'],
                    "purity_level": data['purity_level']
                },
                "phases_detected": data['phases_detected'],
                "stages_detected": data['stage_types'],
                "quality_indicators": {
                    "needs_refactoring": data['ccpp_score'] < 0.6,
                    "has_ml_content": data['ml_modules'] > 0,
                    "is_pure_package": data['ml_modules'] == data['total_modules'] and data['unique_stages_found'] == 1
                },
            }
        return formatted  
    def _generate_summary(self, results: Dict) -> Dict:
        summary = {"High": 0, "Moderate": 0, "Low": 0, "Very Low": 0}
        for data in results.values():
            level = data['purity_level']
            summary[level] += 1
        return summary
