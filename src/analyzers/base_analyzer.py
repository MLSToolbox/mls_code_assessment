import os
from abc import ABC, abstractmethod
from core.interfaces.analyzer_interface import IAnalyzer
from core.models.analysis_result import AnalysisResult
from core.exceptions import AnalyzerError

class BaseAnalyzer(IAnalyzer, ABC):
    """Base class for all analyzers implementing common functionality."""
    
    def __init__(self, session_id: str, local_path: str):
        self.session_id = session_id
        self.local_path = local_path
        self._validate_path()
    
    def _validate_path(self):
        """Validate that the path exists and is accessible."""
        if not os.path.exists(self.local_path):
            raise AnalyzerError(f"Path does not exist: {self.local_path}")
    
    def _get_python_files(self) -> list:
        """Get all Python files in the project directory."""
        python_files = []
        for root, dirs, files in os.walk(self.local_path):
            for file in files:
                if file.endswith('.py'):
                    python_files.append(os.path.join(root, file))
        return python_files
    
    def _change_to_project_dir(self):
        """Context manager for changing to project directory."""
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
    
    def _get_project_folders(self, target_path: str) -> list:
        """Get folders containing Python files."""
        folders = []
        for item in os.listdir(target_path):
            item_path = os.path.join(target_path, item)
            if os.path.isdir(item_path):
                # Check if folder contains Python files
                has_python = any(
                    f.endswith('.py') 
                    for f in os.listdir(item_path) 
                    if os.path.isfile(os.path.join(item_path, f))
                )
                if has_python:
                    folders.append(item)
        
        return folders or ['.']  # Current directory if no folders found