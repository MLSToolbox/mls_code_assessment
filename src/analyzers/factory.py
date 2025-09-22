from typing import Dict, Type
from analyzers.base_analyzer import BaseAnalyzer
from analyzers.pylint_analyzer import PyLintAnalyzer
from analyzers.radon_cc_analyzer import RadonCCAnalyzer
from analyzers.radon_mi_analyzer import RadonMIAnalyzer

class AnalyzerFactory:
    """Factory for creating analyzer instances."""
    
    _analyzers: Dict[str, Type[BaseAnalyzer]] = {
        "pylint": PyLintAnalyzer,
        "radon_cc": RadonCCAnalyzer,
        "radon_mi": RadonMIAnalyzer,
    }
    
    @classmethod
    def create_analyzer(cls, analyzer_type: str, session_id: str, local_path: str) -> BaseAnalyzer:
        """Create analyzer instance by type."""
        if analyzer_type.lower() not in cls._analyzers:
            raise ValueError(f"Unknown analyzer type: {analyzer_type}")
        
        analyzer_class = cls._analyzers[analyzer_type.lower()]
        return analyzer_class(session_id, local_path)
    
    @classmethod
    def get_available_analyzers(cls) -> list:
        """Get list of available analyzer types."""
        return list(cls._analyzers.keys())
    
    @classmethod
    def register_analyzer(cls, name: str, analyzer_class: Type[BaseAnalyzer]):
        """Register new analyzer type."""
        cls._analyzers[name.lower()] = analyzer_class