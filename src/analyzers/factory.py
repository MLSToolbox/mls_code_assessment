from typing import Type, Optional, Dict

from analyzers.base_analyzer import BaseAnalyzer
from core.analysis_context import AnalysisContext


class AnalyzerFactory:
    """Factory for creating analyzer instances."""
    
    # Cache for lazy-loaded analyzers
    _analyzers: Dict[str, Type[BaseAnalyzer]] = {}
    
    @classmethod
    def _get_analyzers(cls) -> Dict[str, Type[BaseAnalyzer]]:
        """Lazy load analyzers to avoid circular imports."""
        if not cls._analyzers:
            from analyzers.pylint_analyzer import PyLintAnalyzer
            from analyzers.radon_cc_analyzer import RadonCCAnalyzer
            from analyzers.radon_mi_analyzer import RadonMIAnalyzer
            from analyzers.pipeline_analyzer import PipelineAnalyzer
            from analyzers.fpc_analyzer import FPCAnalyzer
            from analyzers.pfp_analyzer import PFPAnalyzer  
            
            cls._analyzers = {
                "pylint": PyLintAnalyzer,
                "radon_cc": RadonCCAnalyzer,
                "radon_mi": RadonMIAnalyzer,
                "pipeline": PipelineAnalyzer,
                "fpc": FPCAnalyzer,
                "pfp":PFPAnalyzer   
            }
        return cls._analyzers
    
    @classmethod
    def create_analyzer(
        cls, 
        analyzer_type: str, 
        session_id: str, 
        local_path: str,
        context: Optional[AnalysisContext] = None
    ) -> BaseAnalyzer:
        """Create analyzer instance by type."""
        analyzers = cls._get_analyzers()
        
        if analyzer_type.lower() not in analyzers:
            raise ValueError(f"Unknown analyzer type: {analyzer_type}")
        
        analyzer_class = analyzers[analyzer_type.lower()]
        return analyzer_class(session_id, local_path, context)
    
    @classmethod
    def get_available_analyzers(cls) -> list:
        """Get list of available analyzer types."""
        return list(cls._get_analyzers().keys())
    
    @classmethod
    def register_analyzer(cls, name: str, analyzer_class: Type[BaseAnalyzer]) -> None:
        """Register new analyzer type (for plugins/extensions)."""
        analyzers = cls._get_analyzers()
        analyzers[name.lower()] = analyzer_class
