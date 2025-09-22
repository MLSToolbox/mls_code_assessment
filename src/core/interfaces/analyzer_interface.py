from abc import ABC, abstractmethod
from core.models.analysis_result import AnalysisResult

class IAnalyzer(ABC):
    """Interface for code analyzers."""
    
    @property
    @abstractmethod
    def analyzer_id(self) -> str:
        """Unique identifier for this analyzer."""
        pass
    
    @abstractmethod
    def analyze(self, code_path: str) -> AnalysisResult:
        """Analyze code at given path."""
        pass
    
    @abstractmethod
    def generate_report(self, code_path: str) -> bytes:
        """Generate detailed report."""
        pass