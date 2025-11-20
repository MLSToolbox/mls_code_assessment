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
            from analyzers.pipeline.pipeline_analyzer import PipelineAnalyzer
            from analyzers.fpc import FPCAnalyzer
            from analyzers.file_structure_analyzer import FileStructureAnalyzer
            from analyzers.ml_content import MLContentAnalyzer
            from analyzers.lccml_analyzer import LCCMLAnalyzer
            from analyzers.ldsc_analyzer import LDSCAnalyzer
            from analyzers.ifc_m_analyzer import IFCMAnalyzer
            
            cls._analyzers = {
                "pylint": PyLintAnalyzer,
                "radon_cc": RadonCCAnalyzer,
                "radon_mi": RadonMIAnalyzer,
                "pipeline": PipelineAnalyzer,
                "fpc": FPCAnalyzer,
                "file_structure": FileStructureAnalyzer,
                "ml_content": MLContentAnalyzer,
                "lccml": LCCMLAnalyzer,
                "ldsc": LDSCAnalyzer,
                "ifc_m": IFCMAnalyzer,
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
        """
        Create analyzer instance by type.
        
        Args:
            analyzer_type: Type of analyzer (e.g., 'pylint', 'fpc', 'file_structure')
            session_id: Unique session identifier
            local_path: Path to extracted code
            context: Shared analysis context (optional)
            
        Returns:
            Initialized analyzer instance
            
        Raises:
            ValueError: If analyzer_type is not registered
        """
        analyzers = cls._get_analyzers()
        
        if analyzer_type.lower() not in analyzers:
            available = ', '.join(analyzers.keys())
            raise ValueError(
                f"Unknown analyzer type: '{analyzer_type}'. "
                f"Available analyzers: {available}"
            )
        
        analyzer_class = analyzers[analyzer_type.lower()]
        return analyzer_class(session_id, local_path, context)
    
    @classmethod
    def get_available_analyzers(cls) -> list:
        """
        Get list of available analyzer types.
        
        Returns:
            List of analyzer type names
        """
        return list(cls._get_analyzers().keys())
    
    @classmethod
    def register_analyzer(cls, name: str, analyzer_class: Type[BaseAnalyzer]) -> None:
        """
        Register new analyzer type (for plugins/extensions).
        
        Args:
            name: Analyzer identifier
            analyzer_class: Analyzer class (must inherit from BaseAnalyzer)
            
        Raises:
            TypeError: If analyzer_class doesn't inherit from BaseAnalyzer
        """
        if not issubclass(analyzer_class, BaseAnalyzer):
            raise TypeError(
                f"{analyzer_class.__name__} must inherit from BaseAnalyzer"
            )
        
        analyzers = cls._get_analyzers()
        analyzers[name.lower()] = analyzer_class