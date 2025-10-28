import os
from typing import Dict, List, Set, Any
from collections import defaultdict

from core.models.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer
from core.exceptions import AnalyzerError
from core.metrics import get_metric_metadata

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
                metric_metadata=get_metric_metadata("pfp"),
                details={"message": "No Python packages found to analyze."}
            )

        for pkg_path, modules in packages.items():
            
            package_results[pkg_path] = self._analyze_package(modules)
            total_pfp_score += package_results[pkg_path]['pfp_score']

        
        average_pfp = total_pfp_score / len(packages)
        final_score = round(average_pfp * 10, 2)
        
        purity_distribution = self._get_purity_distribution(package_results)

        return AnalysisResult(
            analyzer_id=self.analyzer_id,
            score=final_score,
            message_count=self._generate_summary(package_results),
            module_count=len(self.context.get_all_python_files()),
            metric_metadata=get_metric_metadata("pfp"),
            details={
                "summary": {
                    "total_packages_analyzed": len(packages),
                    "average_pfp_score": round(average_pfp, 4),
                    "overall_quality": self._get_overall_quality(average_pfp),
                    "packages_by_purity": purity_distribution,
                    "packages_needing_attention": len([p for p in package_results.values() if p['pfp_score'] < 0.6]),
                    "packages_with_good_purity": len([p for p in package_results.values() if p['pfp_score'] >= 0.6])
                },
                "packages": self._format_package_results(package_results)
            }
        )

    def _analyze_package(self, modules: List[str]) -> Dict[str, Any]:
        """Calculates PFP for a single package."""
        n_total = len(modules) 
        n_ml = 0
        all_stages: Set[str] = set()
        modules_info: List[Dict[str, Any]] = []


        for module_path in modules:
            fpc_result = self.context.get_file_metric(module_path, 'fpc')
            
            if fpc_result and fpc_result.get('stages_detected'):
                n_ml += 1
                all_stages.update(fpc_result['stages_detected'])
                modules_info.append({
                    'path': module_path,
                    'stages': list(fpc_result.get('stages_detected', [])),
                    'cohesion': fpc_result.get('cohesion_level')
                })
            else:
                modules_info.append({
                    'path': module_path,
                    'stages': [],
                    'cohesion': None
                })

       
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
            "stage_types": sorted(list(all_stages)),
            "pfp_score": round(pfp_score, 4),
            "purity_level": self._get_purity_level(pfp_score),
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
        
    def _get_purity_level(self, score: float) -> str:
        """Determines a qualitative purity level from a PFP score."""
        if score > 0.8:
            return "High"
        if score >= 0.6:
            return "Moderate"
        if score >= 0.4:
            return "Low"
        return "Very Low"
    
    def _get_overall_quality(self, average_pfp: float) -> str:
        """Determines overall project quality based on average PFP."""
        if average_pfp > 0.8:
            return "Excellent"
        if average_pfp >= 0.6:
            return "Good"
        if average_pfp >= 0.4:
            return "Fair"
       
        return "Critical"
    
    def _get_purity_distribution(self, results: Dict) -> Dict[str, int]:
        """Gets distribution of packages by purity level."""
        distribution = {"High": 0, "Moderate": 0, "Low": 0, "Very Low": 0}
        for data in results.values():
            level = data['purity_level']
            distribution[level] += 1
        return distribution
    
    def _format_package_results(self, results: Dict) -> Dict:
        """Formats package results with better structure."""
        formatted = {}
        for pkg_path, data in results.items():
            formatted[pkg_path] = {
                "metrics": {
                    "total_modules": data['total_modules'],
                    "ml_modules": data['ml_modules'],
                    "ml_ratio": round(data['ml_modules'] / data['total_modules'], 2) if data['total_modules'] > 0 else 0,
                    "pfp_score": data['pfp_score'],
                    "purity_level": data['purity_level']
                },
                "pipeline_stages": {
                    "detected_stages": data['stage_types'],
                    "stage_count": data['unique_stages_found'],
                    "is_focused": data['unique_stages_found'] <= 1
                },
                "quality_indicators": {
                    "needs_refactoring": data['pfp_score'] < 0.6,
                    "has_ml_content": data['ml_modules'] > 0,
                    "is_pure_package": data['ml_modules'] == data['total_modules'] and data['unique_stages_found'] == 1
                },
                "recommendations": self._generate_recommendations(pkg_path, data)
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
    
    def _generate_recommendations(self, package_path: str, package_data: Dict) -> List[str]:
        """Orchestrates generation of actionable recommendations for a package."""
        recommendations: List[str] = []

        pfp_score = package_data['pfp_score']
        n_ml = package_data['ml_modules']
        n_total = package_data['total_modules']
        n_stages = package_data['unique_stages_found']
        modules = package_data.get('modules', [])

        if n_ml == 0:
            recommendations.append(
                "This package contains no ML-related modules. Consider moving utility code "
                "to a dedicated utilities package or documenting its non-ML responsibility."
            )
            return recommendations

        if n_ml < max(1, int(n_total * 0.5)):
            recommendations.append(
                f"Only {n_ml}/{n_total} modules are ML-related. Move non-ML modules to a "
                f"separate package (e.g., '{package_path}/utils' or a top-level 'utils' package) "
                f"to increase purity."
            )

        if n_stages <= 1:
            if pfp_score < 0.6:
                recommendations.append(
                    f"Package '{package_path}' has low PFP ({pfp_score:.2f}) despite being focused; "
                    f"inspect non-ML modules or thin ML implementations and consolidate ML logic "
                    f"into fewer modules."
                )
            return recommendations

        stage_to_suggested_pkgs = self._get_stage_to_package_mapping()
        files_by_stage = self._classify_modules_by_stage(modules)
        dominant_stage = self._identify_dominant_stage(files_by_stage)

        moves = self._generate_file_move_suggestions(
            files_by_stage, 
            dominant_stage, 
            stage_to_suggested_pkgs
        )

        if moves:
            recommendations.append(
                f"Package '{package_path}' spans multiple pipeline stages "
                f"({', '.join(package_data['stage_types'])}). Suggested file moves to increase purity:"
            )
            recommendations.extend(moves[:5])

        deploy_candidates = self._detect_deployment_candidates(modules)
        if deploy_candidates:
            for file_path in deploy_candidates[:3]:
                recommendations.append(
                    f"Consider moving deployment/registry helper '{file_path}' to a dedicated "
                    f"package like 'deployment' or 'registry' (e.g., 'src/deployment/{os.path.basename(file_path)}') "
                    f"to improve separation of concerns."
                )

        priority_msg = self._generate_priority_message(pfp_score, package_path, dominant_stage)
        if priority_msg:
            recommendations.append(priority_msg)

        return recommendations