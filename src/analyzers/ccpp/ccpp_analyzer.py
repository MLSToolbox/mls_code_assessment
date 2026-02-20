import os
import json
from typing import Dict, List, Set, Any
import ast
from collections import defaultdict
from core.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer
from analyzers.ccpp.ccpp_calculator import CCPPCalculator
from core.tree_generator import TreeGenerator
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
        tree_metadata=self.context.get_tree_metadata()
        packages_result=[]
        messages_list = []
        self._get_packages_ccpp_metrics(tree_metadata,dir_list=packages_result,messages_list=messages_list)
        packages_result.reverse()
        messages_list.reverse()
        total_ccpp_score=sum([d["ccpp_result"]["ccpp_score"] for d in packages_result])
        average_ccpp=total_ccpp_score/len(packages_result)
        final_score = round(average_ccpp * 10, 2)
        if not packages_result:
            return self._create_result(
                score=0, 
                messages=[],
                module_count=0,
                details={"message": "No Python packages found to analyze."},
                group_key='by_package'
            )
        return self._create_result(
            score=final_score,
            messages=messages_list,  
            module_count=len(packages_result),
            details={
                "summary": {
                    "total_packages_analyzed": len(packages_result),
                    "average_ccpp_score": round(average_ccpp, 4),
                    "overall_quality": self.calculator.get_overall_quality(average_ccpp),
                    "packages_needing_attention": len([p for p in packages_result if p['ccpp_result']['ccpp_score'] < 0.6]),
                    "packages_with_good_purity": len([p for p in packages_result if p['ccpp_result']['ccpp_score'] >= 0.6]),
                    "etapas_max": self.calculator.get_etapas_max(),
                    "cohesion_summary": self._generate_summary(packages_result)
                },
                "packages": self._format_package_results(packages_result)
            },
            group_key='by_package'
        )
        
    def _get_packages_ccpp_metrics(self,node,current_path="",dir_list=None,messages_list=None):
        """
        Recursively traverses the directory tree to collect metrics from all packages.
        
        Args:
            node: The current node in the directory tree
            current_path: The current path in the directory tree
            dir_list: List to store directory metrics
            messages_list: List to store messages
        
        Returns:
            List of directory metrics
        """
        if node["type"]=="file" and node["name"].endswith(".py") and node["name"]!="__init__.py":
            return self.context.get_file_metric(node["path"].replace("/","",1), 'ccpm')
        ccpm_results:List[Dict[str,Any]]=[]
        if "children" in node:
            for child in node["children"]:
               
                ccpm=self._get_packages_ccpp_metrics(child,node["path"],dir_list,messages_list)
                if ccpm:
                    if isinstance(ccpm,dict):
                        ccpm:Dict[str,Any]=ccpm
                        ccpm["file_path"]=child["path"]
                        ccpm_results.append(ccpm)
                    else:
                        ccpm_results.extend(ccpm)
        
        if node["path"] != "/" and node["type"]=="directory":
            path=node["path"].replace("/","",1)
            ccpm_result=self._analyze_package(path,ccpm_results)
            evaluation=self.evaluator.evaluate_package(path,ccpm_result)
            if evaluation:
                messages_list.append(evaluation)
            dir_list.append({
            "name":node["name"],
            "path":path,
            "ccpp_result":ccpm_result
            })
        return ccpm_results
    def _analyze_package(self,pkg_path,ccpm_results:List[Any])->Dict[str,Any]:
        """
        Analyzes a package by aggregating metrics from its modules.
        
        Args:
            pkg_path: The path to the package
            ccpm_results: List of metrics from modules in the package
        
        Returns:
            Dictionary with package metrics
        """
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
        cohesion_level = self.calculator.get_cohesion_level(ccpp_score)
        return {
            "total_modules": n_total,
            "ml_modules": n_ml,
            "unique_stages_found": n_etapas,
            "stage_types": sorted(list(all_stages)),
            "phases_detected": sorted(list(all_phases)),
            "ccpp_score": ccpp_score,
            "cohesion_level": cohesion_level,
            "modules": modules_info
        } 
    def _format_package_results(self, results: List) -> Dict:
        """Formats package results with better structure."""
        formatted = {}
        for data in results:
            formatted[data["path"]] = {
                "metrics": {
                    "total_modules": data['ccpp_result']['total_modules'],
                    "ml_modules": data['ccpp_result']['ml_modules'],
                    "ccpp_score": data['ccpp_result']['ccpp_score'],
                    "cohesion_level": data['ccpp_result']['cohesion_level']
                },
                "phases_detected": data['ccpp_result']['phases_detected'],
                "stages_detected": data['ccpp_result']['stage_types'],
                "quality_indicators": {
                    "needs_refactoring": data['ccpp_result']['ccpp_score'] < 0.6,
                    "has_ml_content": data['ccpp_result']['ml_modules'] > 0,
                    "is_pure_package": data['ccpp_result']['ml_modules'] == data['ccpp_result']['total_modules'] and data['ccpp_result']['unique_stages_found'] == 1
                },
            }
        return formatted  
    def _generate_summary(self, results: List) -> Dict:
        summary = {"very_high": 0, "high": 0, "medium": 0, "low": 0, "very_low": 0}
        for data in results:
            level = data['ccpp_result']['cohesion_level']
            summary[level] += 1
        return summary
