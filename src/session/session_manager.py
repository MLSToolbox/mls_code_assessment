import os
import shutil
import uuid
from typing import Dict, List, Optional, Any

from session.file_handler import FileHandler
from analyzers.factory import AnalyzerFactory
from core.models.analysis_result import AnalysisResult
from core.exceptions import SessionError
from session.session_storage import SessionStorage


class SessionManager:
    """
    Manages a single analysis session.
    
    Handles file extraction, analyzer execution, and session lifecycle.
    """
    
    def __init__(
        self, 
        app_zip: Optional[bytes] = None,
        session_id: Optional[str] = None,
        analyzer_types: Optional[List[str]] = None,
        base_path: str = "/tmp"
    ):
        """
        Initialize SessionManager.
        
        Args:
            app_zip: ZIP file content (for new sessions)
            session_id: Existing session ID (for loading sessions)
            analyzer_types: List of analyzer types to use
            base_path: Base path for session storage
        """
        # Validate mutually exclusive parameters
        if app_zip is not None and session_id is not None:
            raise ValueError("Cannot provide both app_zip and session_id")
        
        if app_zip is None and session_id is None:
            raise ValueError("Must provide either app_zip or session_id")
        
        self.base_path = base_path
        self.analyzer_types = analyzer_types or []
        self.app_zip = app_zip
        self.local_path: Optional[str] = None
        self.metadata: Optional[Dict[str, Any]] = None
        
        if session_id:
            # Load existing session
            self.session_id = session_id
            self.load_session()
        else:
            # Create new session
            self.session_id = str(uuid.uuid4())
        
        self.file_handler = FileHandler(self.base_path)
    
    def load_session(self) -> None:
        """Load existing session from storage."""
        self.metadata = SessionStorage.load_metadata(self.session_id, self.base_path)
        
        if not self.metadata:
            raise SessionError(f"Session {self.session_id} not found or expired")
        
        self.local_path = self.metadata.get("local_path")
    
    @classmethod
    def load_session(cls, session_id: str, base_path: str = "/tmp") -> 'SessionManager':
        """
        Factory method to load existing session.
        
        Args:
            session_id: Session identifier
            base_path: Base path for session storage
            
        Returns:
            SessionManager instance
        """
        return cls(session_id=session_id, base_path=base_path)
    
    def _setup_session(self) -> str:
        """
        Private method to setup session workspace.
        
        Returns:
            Path to extracted files
        """
        try:
            local_path = self.file_handler.create_session_workspace(
                self.session_id, self.app_zip
            )
            return local_path
        except Exception as e:
            raise SessionError(f"Session setup failed: {str(e)}")
    
    def ensure_setup(self) -> str:
        """
        Ensure session is set up and return local path.
        
        Public interface for session setup that maintains encapsulation.
        
        Returns:
            Path to extracted files
        """
        if self.local_path is None:
            self.local_path = self._setup_session()
        return self.local_path
    
    def save_session(
        self, 
        tree_structure: Dict, 
        auto_detected_pipeline: Dict,
        ttl_minutes: int = 60
    ) -> None:
        """
        Save session metadata to persistent storage.
        
        Args:
            tree_structure: File tree structure
            auto_detected_pipeline: Pipeline detection results
            ttl_minutes: Session time-to-live in minutes
        """
        if not self.local_path:
            raise SessionError("Session not set up. Call ensure_setup() first.")
        
        SessionStorage.save_metadata(
            session_id=self.session_id,
            base_path=self.base_path,
            local_path=self.local_path,
            tree_structure=tree_structure,
            auto_detected_pipeline=auto_detected_pipeline,
            ttl_minutes=ttl_minutes
        )
        
        # Update internal metadata cache
        self.metadata = SessionStorage.load_metadata(self.session_id, self.base_path)
    
    def save_analysis_results(self, results: Dict) -> None:
        """
        Save analysis results to session.
        
        Args:
            results: Analysis results dictionary
        """
        SessionStorage.update_analysis_results(
            self.session_id, 
            self.base_path, 
            results
        )
        
        # Update internal cache
        self.metadata = SessionStorage.load_metadata(self.session_id, self.base_path)
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get session metadata.
        
        Returns:
            Session metadata dictionary
            
        Raises:
            SessionError: If session not found or expired
        """
        if self.metadata is None:
            self.metadata = SessionStorage.load_metadata(
                self.session_id, self.base_path
            )
            if self.metadata is None:
                raise SessionError(f"Session {self.session_id} not found or expired")
        return self.metadata
    
    def run_analysis(self) -> Dict[str, AnalysisResult]:
        """
        Execute all configured analyzers.
        
        Returns:
            Dictionary mapping analyzer types to results
        """
        if not self.local_path:
            raise SessionError("Session not set up")
        
        results = {}
        
        for analyzer_type in self.analyzer_types:
            analyzer = AnalyzerFactory.create_analyzer(
                analyzer_type,
                self.session_id,
                self.local_path
            )
            results[analyzer_type] = analyzer.analyze()
        
        return results
    
    def cleanup(self) -> None:
        """Remove session files and metadata."""
        if self.local_path and os.path.exists(self.local_path):
            shutil.rmtree(self.local_path)
        
        session_dir = os.path.join(self.base_path, self.session_id)
        if os.path.exists(session_dir):
            shutil.rmtree(session_dir)