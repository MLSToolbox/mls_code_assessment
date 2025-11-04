from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Union
from core.models.analysis_result import AnalysisResult
from core.analysis_context import AnalysisContext
from core.exceptions import AnalyzerError
from core.metrics import get_metric_metadata
import os


class BaseAnalyzer(ABC):
    """Abstract base class for all analyzers."""
    
    def __init__(
        self, 
        session_id: str, 
        local_path: str, 
        context: Optional[AnalysisContext] = None,
        validate_path: bool = True
    ):
        """
        Initialize base analyzer.
        
        Args:
            session_id: Unique session identifier
            local_path: Path to extracted code
            context: Shared analysis context (optional)
            validate_path: Whether to validate path existence
        """
        self.session_id = session_id
        self.local_path = local_path
        self.context = context or AnalysisContext(session_id, local_path)
        
        if validate_path:
            self._validate_path()
    
    def _validate_path(self) -> None:
        """Validate that the path exists and is accessible."""
        if self.local_path and not os.path.exists(self.local_path):
            raise AnalyzerError(f"Path does not exist: {self.local_path}")
    
    def _get_python_files(self) -> list:
        """
        Get all Python files in the project directory.
        
        Returns:
            List of absolute paths to Python files
        """
        python_files = []
        for root, dirs, files in os.walk(self.local_path):
            for file in files:
                if file.endswith('.py'):
                    python_files.append(os.path.join(root, file))
        return python_files
    
    def _change_to_project_dir(self):
        """
        Context manager for changing to project directory.
        
        Usage:
            with self._change_to_project_dir():
                # do work in project directory
                pass
        """
        class DirChanger:
            def __init__(self, path):
                self.path = path
                self.original_path = os.getcwd()
            
            def __enter__(self):
                os.chdir(self.path)
                return self
            
            def __exit__(self, *args):
                os.chdir(self.original_path)
        
        return DirChanger(self.local_path)
    
    def _get_project_folders(self, target_path: str = None) -> list:
        """
        Get folders containing Python files.
        
        Args:
            target_path: Path to search (defaults to self.local_path)
            
        Returns:
            List of folder names containing Python files
        """
        target_path = target_path or self.local_path
        folders = []
        
        for item in os.listdir(target_path):
            item_path = os.path.join(target_path, item)
            if os.path.isdir(item_path):
                has_python = any(
                    f.endswith('.py') 
                    for f in os.listdir(item_path) 
                    if os.path.isfile(os.path.join(item_path, f))
                )
                if has_python:
                    folders.append(item)
        
        return folders or ['.']
    
    @property
    @abstractmethod
    def analyzer_id(self) -> str:
        pass
    
    def _create_result(
        self,
        score: float,
        messages: Union[Dict[str, Any], List[Dict[str, Any]]],
        module_count: int,
        details: Optional[Dict[str, Any]] = None
    ) -> AnalysisResult:
        """
        Create an AnalysisResult object.
        
        Args:
            score: Numeric score for the analysis
            messages: Either:
                - Dict (old format): {'total': int, 'by_file': {...}} for backward compatibility
                - List[Dict] (new format): List of message dicts with file, diagnosis, recommendation, etc.
            module_count: Number of modules analyzed
            details: Optional additional details
        
        Returns:
            AnalysisResult object
        """
        # Convert old format to new format if needed
        if isinstance(messages, list):
            # New format: list of detailed messages
            messages_dict = {
                'total': len(messages),
                'by_file': {},
                'details': messages
            }
        else:
            # Old format: dict with total and by_file
            messages_dict = messages
        
        return AnalysisResult(
            analyzer_id=self.analyzer_id,
            score=score,
            messages=messages_dict,
            module_count=module_count,
            metric_metadata=get_metric_metadata(self.analyzer_id),
            details=details
        )
    
    @abstractmethod
    def analyze(self) -> AnalysisResult:
        pass