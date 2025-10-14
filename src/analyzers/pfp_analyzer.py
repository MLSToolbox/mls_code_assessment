import os
from typing import Dict, List, Set, Any
from collections import defaultdict

from core.models.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer
from core.exceptions import AnalyzerError

class PFPAnalyzer(BaseAnalyzer):
    """
    Analyzes Package Functional Purity (PFP).
    This metric measures how focused a package is on a specific ML pipeline function.
    It depends on the results of the FPCAnalyzer.
    """

    
    ETAPAS_MAX = 5

    @property
    def analyzer_id(self) -> str:
        return "PFP"

    def analyze(self) -> AnalysisResult:
        """
        Runs the PFP analysis for all packages in the project.

        It relies on the FPC analysis results being available in the context.
        """
 
        if not self._is_fpc_data_available():
            raise AnalyzerError(
                "PFP analysis requires FPC analysis to be run first. "
                "Please include 'fpc' in the list of analyzers."
            )

        packages = self._discover_packages()
        package_results = {}
        total_pfp_score = 0
        
        if not packages:
            return AnalysisResult(
                analyzer_id=self.analyzer_id,
                score=10.0, 
                message_count={},
                module_count=0,
                details={"message": "No Python packages found to analyze."}
            )

        for pkg_path, modules in packages.items():
            
            package_results[pkg_path] = self._analyze_package(modules)
            total_pfp_score += package_results[pkg_path]['pfp_score']

        
        average_pfp = total_pfp_score / len(packages)
        final_score = round(average_pfp * 10, 2)

        return AnalysisResult(
            analyzer_id=self.analyzer_id,
            score=final_score,
            message_count=self._generate_summary(package_results),
            module_count=len(self.context.get_all_python_files()),
            details={"packages": package_results}
        )

    def _analyze_package(self, modules: List[str]) -> Dict[str, Any]:
        """Calculates PFP for a single package."""
        n_total = len(modules)
        n_ml = 0
        all_stages: Set[str] = set()

        for module_path in modules:
            fpc_result = self.context.get_file_metric(module_path, 'fpc')
            
            
            
           
            if fpc_result and fpc_result.get('stages_detected'):
                
                n_ml += 1
                all_stages.update(fpc_result['stages_detected'])

       
        n_etapas = len(all_stages)
        cf = 1.0
        if self.ETAPAS_MAX > 1 and n_etapas > 1:
            cf = 1 - ((n_etapas - 1) / (self.ETAPAS_MAX - 1))

       
        pfp_score = 0
        if n_total > 0:
            pfp_score = (n_ml / n_total) * cf
            
        return {
            "total_modules": n_total,
            "ml_modules": n_ml,
            "unique_stages_found": n_etapas,
            "concentration_factor": round(cf, 4),
            "pfp_score": round(pfp_score, 4),
            "purity_level": self._get_purity_level(pfp_score)
        }
        
    def _discover_packages(self) -> Dict[str, List[str]]:
        """
        Identifies packages and their contained modules.
        A package is a directory containing Python files.
        """
        packages: Dict[str, List[str]] = defaultdict(list)
        python_files = self.context.get_all_python_files()

        for file_path in python_files:
            
            package_path = os.path.dirname(file_path) or '.'
            packages[package_path].append(file_path)
            
        return dict(packages)
        
    def _is_fpc_data_available(self) -> bool:
        """Checks if any file has FPC data in the context."""
        for py_file in self.context.get_all_python_files():
            if self.context.has_file_metric(py_file, 'fpc'):
                return True
        return False
        
    def _get_purity_level(self, score: float) -> str:
        """Determines a qualitative purity level from a PFP score."""
        if score > 0.8:
            return "High"
        if score >= 0.6:
            return "Moderate"
        if score >= 0.4:
            return "Low"
        return "Very Low"
        
    def _generate_summary(self, results: Dict) -> Dict:
        """Creates a summary message count from analysis results."""
        summary = {"High": 0, "Moderate": 0, "Low": 0, "Very Low": 0}
        for data in results.values():
            level = data['purity_level']
            summary[level] += 1
        return summary