import os
import shutil
import uuid
from typing import Dict, List, Optional

from core.models.analysis_result import SessionResult
from core.exceptions import SessionError, AnalyzerError
from analyzers.factory import AnalyzerFactory
from session.file_handler import FileHandler
from session.cleanup_service import CleanupService
from utils.validation import validate_session_id

class SessionManager:
    """Manages analysis sessions with improved architecture."""
    
    def __init__(self, app_zip: bytes, analyzer_types: Optional[List[str]] = None):
        self.app_zip = app_zip
        self.session_id = self._generate_session_id()
        self.local_path = None
        self.file_handler = FileHandler()
        self.cleanup_service = CleanupService()
        
        # Default to all available analyzers
        self.analyzer_types = analyzer_types or ["pylint", "radon_mi", "radon_cc"]
        self._validate_analyzers()
        
        self.results: Dict[str, any] = {}
        self.reports: Dict[str, bytes] = {}
    
    def run_analysis(self) -> Dict[str, any]:
        """Execute analysis with all configured analyzers."""
        try:
            self.local_path = self._setup_session()
            
            for analyzer_type in self.analyzer_types:
                analyzer = AnalyzerFactory.create_analyzer(
                    analyzer_type, self.session_id, self.local_path
                )
                
                try:
                    result = analyzer.analyze()
                    self.results[analyzer.analyzer_id] = {
                        "score": result.score,
                        "message_count": result.message_count,
                        "module_count": result.module_count
                    }
                except AnalyzerError as e:
                    self.results[analyzer.analyzer_id] = {
                        "error": str(e),
                        "score": 0,
                        "message_count": {},
                        "module_count": 0
                    }
            
            return self.results
            
        except Exception as e:
            raise SessionError(f"Analysis failed: {str(e)}")
    
    def generate_report(self, analyzer_id: str) -> Optional[bytes]:
        """Generate detailed report for specific analyzer."""
        if self.local_path is None:
            self.local_path = self._setup_session()
        
        try:
            # Find analyzer type by ID
            analyzer_type = self._find_analyzer_type(analyzer_id)
            if not analyzer_type:
                return None
            
            analyzer = AnalyzerFactory.create_analyzer(
                analyzer_type, self.session_id, self.local_path
            )
            
            report = analyzer.generate_report()
            self.reports[analyzer_id] = report
            return report
            
        except AnalyzerError:
            return None
    
    def get_results(self) -> Dict[str, any]:
        """Get analysis results."""
        return self.results
    
    def get_report(self, analyzer_id: str) -> Optional[bytes]:
        """Get cached report."""
        return self.reports.get(analyzer_id)
    
    def cleanup(self):
        """Clean up session resources."""
        if self.local_path and os.path.exists(self.local_path):
            self.cleanup_service.cleanup_session(self.local_path)
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        return str(uuid.uuid4())
    
    def _validate_analyzers(self):
        """Validate requested analyzers are available."""
        available = AnalyzerFactory.get_available_analyzers()
        invalid = [a for a in self.analyzer_types if a.lower() not in available]
        if invalid:
            raise SessionError(f"Invalid analyzers: {invalid}")
    
    def _setup_session(self) -> str:
        """Set up session workspace."""
        try:
            local_path = self.file_handler.create_session_workspace(
                self.session_id, self.app_zip
            )
            return local_path
        except Exception as e:
            raise SessionError(f"Session setup failed: {str(e)}")
  
  
    def _find_analyzer_type(self, analyzer_id: str) -> Optional[str]:
        """Find analyzer type by ID."""
        analyzer_id_map = {
            "PyLint": "pylint",
            "Radon - Complexity": "radon_cc",
            "Radon - Maintainability": "radon_mi"
        }
        return analyzer_id_map.get(analyzer_id)
