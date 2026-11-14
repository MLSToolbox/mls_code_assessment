import os
from typing import Any, Dict, List
from collections import defaultdict
from core.analysis_result import AnalysisResult
from analyzers.base_analyzer import BaseAnalyzer
from analyzers.ccpp.ccpp_calculator import CCPPCalculator
from analyzers.ccpp.ccpp_evaluator import CCPPEvaluator
from analyzers.common.package_utils import transverse_tree_to_get_packages_and_files
from analyzers.common import calculate_ccp
from analyzers.pipeline.pipeline_schema import get_pipeline_schema
class CCPPAnalyzer(BaseAnalyzer):
    """
    Conceptual Cohesion of Pipeline Packages (CCPP) Analyzer.

    Treats a package (directory) as the same kind of "software component"
    as a module, applying the same formula as CCPM:
        CCP_i(C) = 5 - MP(C) - MS(C) - 2 * MPC(C)
    where MP/MS are derived from the union of phases/stages across the
    package's modules, and MPC is true if the package contains any module
    outside the pipeline, or any pipeline module that itself mixes in
    non-pipeline code. See analyzers.common.ccp_calculator and
    CCPPCalculator.has_mixed_content().

    Packages with no detected pipeline stage anywhere inside them get no
    CCP_i level ('non_ml_package'), mirroring CCPM's non_ml_file/
    not_applicable exclusion, and are left out of the project-wide average.
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
        if not packages:
            return self._create_result(
                score=0,
                messages=[],
                module_count=0,
                details={"message": "No Python packages found to analyze."},
                group_key='by_package'
            )
        total_level = 0
        scored_packages = 0
        for pkg in packages:
            pkg["ccpp"]=self._analyze_package(pkg)
            ccp_level = pkg["ccpp"].get('ccp_level')
            if ccp_level is not None:
                total_level += ccp_level
                scored_packages += 1
            evaluation=self.evaluator.evaluate_package(pkg["path"], pkg["ccpp"])
            if evaluation:
                pkg["evaluation"] = evaluation
            else:
                pkg["evaluation"] = None
        average_ccp_level = round(total_level / scored_packages, 2) if scored_packages > 0 else 0
        return self._create_result(
            score=average_ccp_level,
            messages=[pkg["evaluation"] for pkg in packages if pkg["evaluation"]!=None],
            module_count=len(self.context.get_python_files()),
            details={
                "summary": {
                    "total_packages_analyzed": len(packages),
                    "scored_packages": scored_packages,
                    "average_ccp_level": average_ccp_level,
                    "overall_quality": (
                        self.calculator.get_overall_quality(average_ccp_level)
                        if scored_packages > 0 else "N/A"
                    ),
                    "packages_needing_attention": len([
                        p for p in packages
                        if p['ccpp'].get('ccp_level') is not None and p['ccpp']['ccp_level'] < 3
                    ]),
                    "packages_with_good_purity": len([
                        p for p in packages
                        if p['ccpp'].get('ccp_level') is not None and p['ccpp']['ccp_level'] >= 3
                    ]),
                    "etapas_max": self.calculator.get_etapas_max(),
                    "purity_summary": self._generate_summary(packages)
                },
                "packages": self._format_package_results(packages)
            },
            group_key='by_package'
        )
    def _analyze_package(self, pkg: Dict) -> Dict[str, Any]:
        """
        Calculates CCP_i for a single package by reusing per-module CCPM
        metrics and the shared calculate_ccp() formula.

        Args:
            pkg: Dict with 'path' (package directory) and 'modules' (list
                of python module file paths belonging to it)

        Returns:
            Dictionary with package CCP metrics: mp/ms/mpc/ccp_level,
            cohesion_level, and the raw stage/phase/module counts used.
        """
        ccpm_results = []
        for module_path in pkg["modules"]:
            ccpm_result = self.context.get_file_metric(module_path, 'ccpm')
            module_metric = dict(ccpm_result) if ccpm_result else {}
            module_metric['file_path'] = module_path
            module_metric.setdefault('stages_detected', [])
            module_metric.setdefault('phases_detected', [])
            module_metric.setdefault('cohesion_level', None)
            module_metric.setdefault('mpc', None)
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

        package_metrics = {
            'total_modules': n_total,
            'ml_modules': n_ml,
            'unique_stages_found': n_etapas,
            'stage_types': sorted(list(all_stages)),
            'phases_detected': sorted(list(all_phases)),
            'modules': modules_info
        }

        if n_etapas == 0:
            # No pipeline evidence anywhere in this package - CCP_i doesn't
            # apply, mirroring CCPM's non_ml_file/not_applicable exclusion.
            package_metrics.update({
                'cohesion_level': 'non_ml_package',
                'mp': None, 'ms': None, 'mpc': None, 'ccp_level': None,
                'phase_mapping_incomplete': False,
            })
            return package_metrics

        has_mixed_content = self.calculator.has_mixed_content(n_total, n_ml, ccpm_results)
        ccp = calculate_ccp(n_phases, n_etapas, has_mixed_content)
        package_metrics.update({
            'cohesion_level': ccp['cohesion_level'],
            'mp': ccp['mp'],
            'ms': ccp['ms'],
            'mpc': ccp['mpc'],
            'ccp_level': ccp['ccp_level'],
            # Stages were detected but none mapped to a known phase (a gap
            # in pipeline_stages.json's stage->phase config) - MP may be a
            # false negative here. Informational only, doesn't block scoring.
            'phase_mapping_incomplete': n_phases == 0,
        })
        return package_metrics

    def _format_package_results(self, results: Dict) -> Dict:
        """Formats package results with better structure."""
        formatted = {}
        for pkg in results:
            ccpp = pkg['ccpp']
            formatted[pkg["path"]] = {
                "metrics": {
                    "total_modules": ccpp['total_modules'],
                    "ml_modules": ccpp['ml_modules'],
                    "cohesion_level": ccpp['cohesion_level'],
                    "mp": ccpp.get('mp'),
                    "ms": ccpp.get('ms'),
                    "mpc": ccpp.get('mpc'),
                    "ccp_level": ccpp.get('ccp_level'),
                },
                "phases_detected": ccpp['phases_detected'],
                "stages_detected": ccpp['stage_types'],
                "quality_indicators": {
                    "needs_refactoring": ccpp.get('ccp_level') is not None and ccpp['ccp_level'] < 3,
                    "has_ml_content": ccpp['ml_modules'] > 0,
                    "is_pure_package": ccpp.get('mp') is False and ccpp.get('ms') is False and ccpp.get('mpc') is False
                },
            }
        return formatted
    def _generate_summary(self, results: List[Dict]) -> Dict:
        summary = {"very_high": 0, "high": 0, "medium": 0, "low": 0, "very_low": 0, "non_ml_package": 0}
        for pkg in results:
            level = pkg['ccpp']['cohesion_level']
            summary[level] = summary.get(level, 0) + 1
        return summary