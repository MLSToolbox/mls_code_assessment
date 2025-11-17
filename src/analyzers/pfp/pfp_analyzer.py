import os
from typing import Dict, List, Set, Any
from collections import defaultdict

from core.models.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer
from analyzers.pfp.pfp_calculator import PFPCalculator
from analyzers.pfp.pfp_evaluator import PFPEvaluator
from core.exceptions import AnalyzerError

class PFPAnalyzer(BaseAnalyzer):
    """
    Analyzes Package Functional Purity (PFP).
    
    This metric measures how focused a package is on a specific ML pipeline function.
    It depends on the results of the FPCAnalyzer and reuses FPC metrics at package level.
    
    Architecture (modular approach like FPC):
    - PFPAnalyzer: Main analyzer, orchestrates analysis
    - PFPCalculator: Handles PFP score calculation
    - PFPEvaluator: Matches metrics against rules, generates diagnosis/recommendations
    """

    @property
    def analyzer_id(self) -> str:
        return "pfp"
    
    def __init__(self, session_id: str, local_path: str, context=None):
        super().__init__(session_id, local_path, context)
        
        # Initialize PFP calculator with updated ETAPAS_MAX = 6
        self.calculator = PFPCalculator(etapas_max=6)
        
        # Initialize PFP evaluator for rule-based diagnosis/recommendations
        self.evaluator = PFPEvaluator()

    def analyze(self) -> AnalysisResult:
        """
        Runs the PFP analysis for all packages in the project.

        It relies on the FPC analysis results being available in the context.
        Dependencies are automatically resolved by the @requires decorator.
        """

        packages = self._discover_packages()
        package_results = {}
        total_pfp_score = 0
        
        # List to store per-package messages (following FPC pattern)
        messages_list = []
        
        if not packages:
            return self._create_result(
                score=10.0, 
                messages=[],
                module_count=0,
                details={"message": "No Python packages found to analyze."}
            )

        for pkg_path, modules in packages.items():
            package_results[pkg_path] = self._analyze_package(pkg_path, modules)
            total_pfp_score += package_results[pkg_path]['pfp_score']
            
            # Use evaluator to generate diagnosis/recommendation message
            evaluation = self.evaluator.evaluate_package(pkg_path, package_results[pkg_path])
            if evaluation:
                messages_list.append(evaluation)

        average_pfp = total_pfp_score / len(packages)
        final_score = round(average_pfp * 10, 2)
        
        

        return self._create_result(
            score=final_score,
            messages=messages_list,  # Use list format like FPC
            module_count=len(self.context.get_all_python_files()),
            details={
                "summary": {
                    "total_packages_analyzed": len(packages),
                    "average_pfp_score": round(average_pfp, 4),
                    "overall_quality": self.calculator.get_overall_quality(average_pfp),
                    "packages_needing_attention": len([p for p in package_results.values() if p['pfp_score'] < 0.6]),
                    "packages_with_good_purity": len([p for p in package_results.values() if p['pfp_score'] >= 0.6]),
                    "etapas_max": self.calculator.get_etapas_max(),
                    "purity_summary": self._generate_summary(package_results)
                },
                "packages": self._format_package_results(package_results)
            }
        )

    def _analyze_package(self, pkg_path: str, modules: List[str]) -> Dict[str, Any]:
        """
        Calculates PFP for a single package by reusing FPC metrics.
        
        Args:
            pkg_path: Package directory path
            modules: List of module file paths in package
            
        Returns:
            Dictionary with package PFP metrics
        """
        # Collect FPC results for all modules in package
        fpc_results = []
        for module_path in modules:
            fpc_result = self.context.get_file_metric(module_path, 'fpc')
            if fpc_result:
                fpc_result['file_path'] = module_path
                fpc_results.append(fpc_result)
        
        # Aggregate FPC metrics to package level
        aggregated = self.calculator.aggregate_package_metrics(fpc_results)
        
        n_total = aggregated['n_total']
        n_ml = aggregated['n_ml']
        all_stages = aggregated['all_stages']
        modules_info = aggregated['modules_info']
        
        n_etapas = len(all_stages)
        
        # Get phases from FPC analysis (already calculated)
        all_phases = set()
        for fpc_result in fpc_results:
            all_phases.update(fpc_result.get('phases_detected', []))
        
        # Calculate PFP using calculator
        pfp_score = self.calculator.calculate_pfp(n_total, n_ml, n_etapas)
        purity_level = self.calculator.get_purity_level(pfp_score)
        
        return {
            "total_modules": n_total,
            "ml_modules": n_ml,
            "unique_stages_found": n_etapas,
            "stage_types": sorted(list(all_stages)),
            "phases_detected": sorted(list(all_phases)),
            "pfp_score": pfp_score,
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
                    "pfp_score": data['pfp_score'],
                    "purity_level": data['purity_level']
                },
                "phases_detected": data['phases_detected'],
                "stages_detected": data['stage_types'],
                "quality_indicators": {
                    "needs_refactoring": data['pfp_score'] < 0.6,
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
    
    def _get_stage_to_package_mapping(self) -> Dict[str, List[str]]:
        """Returns suggested package names for each ML pipeline stage."""
        return {
            'data_collection': ['data', 'data/collection', 'data/ingest'],
            'data_cleaning': ['data/preprocessing', 'data/cleaning', 'data/prep'],
            'data_labeling': ['data/labeling', 'data/annotation', 'labeling'],
            'feature_engineering': ['features', 'feature_engineering', 'features/processing'],
            'model_training': ['training', 'training/models', 'training/experiments'],
            'model_evaluation': ['evaluation', 'evaluation/metrics', 'validation']
        }
    
    def _classify_modules_by_stage(self, modules: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Groups module file paths by their detected pipeline stages."""
        files_by_stage: Dict[str, List[str]] = {}
        for module in modules:
            for stage in module.get('stages', []):
                files_by_stage.setdefault(stage, []).append(module['path'])
        return files_by_stage
    
    def _identify_dominant_stage(self, files_by_stage: Dict[str, List[str]]) -> str:
        """Returns the stage with the most files, or None if empty."""
        if not files_by_stage:
            return None
        stage_counts = {stage: len(files) for stage, files in files_by_stage.items()}
        return max(stage_counts, key=stage_counts.get)
    
    def _generate_file_move_suggestions(
        self, 
        files_by_stage: Dict[str, List[str]], 
        dominant_stage: str,
        stage_to_suggested_pkgs: Dict[str, List[str]]
    ) -> List[str]:
        """Generates concrete file move suggestions for minority stages."""
        moves: List[str] = []
        for stage, files in files_by_stage.items():
            if stage == dominant_stage:
                continue
            suggested_names = stage_to_suggested_pkgs.get(stage, [stage])
            suggested_pkg = suggested_names[0]
            example_files = files[:3]
            for file_path in example_files:
                fname = os.path.basename(file_path)
                new_path = os.path.join(suggested_pkg, fname)
                moves.append(f"Move '{file_path}' → '{new_path}' (belongs to stage '{stage}')")
        return moves
    
    def _detect_deployment_candidates(self, modules: List[Dict[str, Any]]) -> List[str]:
        """Identifies files likely related to deployment/registry by filename heuristics."""
        keywords = ('promote', 'deploy', 'registry', 'register', 'push_model', 'serve', 'inference')
        candidates = []
        for module in modules:
            path = module['path']
            if any(keyword in os.path.basename(path).lower() for keyword in keywords):
                candidates.append(path)
        return candidates
    
    def _generate_priority_message(
        self, 
        pfp_score: float, 
        package_path: str, 
        dominant_stage: str
    ) -> str:
        """Generates priority guidance message based on PFP score."""
        if pfp_score < 0.4:
            return f"HIGH PRIORITY: PFP {pfp_score:.2f} — split the package by responsibility and apply the suggested file moves above to achieve immediate gains."
        elif pfp_score < 0.6:
            return f"MEDIUM PRIORITY: PFP {pfp_score:.2f} — consider moving the listed files and consolidating ML logic into '{package_path}/{dominant_stage}' or suggested packages."
        return None
    
    