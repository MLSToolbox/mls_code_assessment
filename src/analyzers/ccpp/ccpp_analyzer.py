import os
from typing import Dict, List, Set, Any
from collections import defaultdict

from core.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer
from analyzers.ccpp.ccpp_calculator import CCPPCalculator
from analyzers.ccpp.ccpp_evaluator import CCPPEvaluator


class CCPPAnalyzer(BaseAnalyzer):
    """
    Analyzes Conceptual Cohesion of Pipeline Packages (CCPP).
    
    This metric measures how focused a package is on a specific ML pipeline function.
    It depends on the results of the CCPPAnalyzer and reuses CCPP metrics at package level.
    
    Architecture :
    - CCPPAnalyzer: Main analyzer, orchestrates analysis
    - CCPPCalculator: Handles CCPP score calculation
    - CCPPEvaluator: Matches metrics against rules, generates diagnosis/recommendations
    """

    @property
    def analyzer_id(self) -> str:
        return "ccpp"
    
    def __init__(self, session_id: str, local_path: str, context=None):
        super().__init__(session_id, local_path, context)
        self.calculator = CCPPCalculator(etapas_max=6)
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
        Calculates CCPP for a single package by reusing FPC metrics.
        
        Args:
            pkg_path: Package directory path
            modules: List of module file paths in package
            
        Returns:
            Dictionary with package CCPP metrics
        """
        fpc_results = []
        for module_path in modules:
            fpc_result = self.context.get_file_metric(module_path, 'fpc')
            if fpc_result:
                fpc_result['file_path'] = module_path
                fpc_results.append(fpc_result)
        
        
        aggregated = self.calculator.aggregate_package_metrics(fpc_results)
        
        n_total = aggregated['n_total']
        n_ml = aggregated['n_ml']
        all_stages = aggregated['all_stages']
        modules_info = aggregated['modules_info']
        
        n_etapas = len(all_stages)
        
        
        all_phases = set()
        for fpc_result in fpc_results:
            all_phases.update(fpc_result.get('phases_detected', []))
        
        
        ccpp_score = self.calculator.calculate_ccpp(n_total, n_ml, n_etapas)
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
        
    def _is_fpc_data_available(self) -> bool:
        """Checks if any file has FPC data in the context."""
        for py_file in self.context.get_all_python_files():
            if self.context.has_file_metric(py_file, 'fpc'):
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
