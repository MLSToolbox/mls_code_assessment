from typing import Dict, Any
from datetime import datetime
from werkzeug.datastructures import FileStorage

from session.session_manager import SessionManager
from session.session_storage import SessionStorage
from analyzers.factory import AnalyzerFactory
from core.tree_generator import TreeGenerator
from core.analysis_context import AnalysisContext
from core.models.pipeline_overrides import AnalysisRequest
from core.models.analysis_result import AnalysisResult
from core.metrics import get_metric_metadata
import config.settings as config


class UploadService:
    """Handles ZIP upload and initial pipeline detection."""
    
    @staticmethod
    def process_upload(app_zip: FileStorage) -> Dict[str, Any]:
        """
        Process uploaded ZIP file and create session.
        
        Args:
            app_zip: Uploaded file from request
            
        Returns:
            Dictionary with session_id, tree_structure, and auto_detected_pipeline
            
        Raises:
            SessionError: If session creation fails
            Exception: For other processing errors
        """
        session = SessionManager(
            app_zip=app_zip,
            base_path=config.settings.SESSION_BASE_PATH
        )
        
        session.ensure_setup()
        
        # Generate tree structure
        tree_generator = TreeGenerator(session.local_path)
        tree_structure = tree_generator.generate()
        
        # Auto-detect pipeline
        pipeline_analyzer = AnalyzerFactory.create_analyzer(
            "pipeline", session.session_id, session.local_path
        )
        pipeline_result = pipeline_analyzer.analyze()
        
        # Save session metadata
        session.save_session(
            tree_structure=tree_structure,
            auto_detected_pipeline=pipeline_result.details,
            ttl_minutes=config.settings.SESSION_TTL_MINUTES
        )
        
        return {
            "session_id": session.session_id,
            "tree_structure": tree_structure,
            "auto_detected_pipeline": pipeline_result.details
        }


class AnalysisService:
    """Handles code analysis for existing sessions."""
    
    @staticmethod
    def analyze_session(session_id: str, analysis_request: AnalysisRequest) -> Dict[str, Any]:
        """
        Perform analysis on an existing session.
        
        Args:
            session_id: ID of the session to analyze
            analysis_request: Analysis configuration and overrides
            
        Returns:
            Dictionary with analysis results and metadata
            
        Raises:
            ValueError: If session not found or expired
            SessionError: If session invalid
            Exception: For analysis errors
        """
        # Validate session exists
        if not SessionStorage.exists(session_id, config.settings.SESSION_BASE_PATH):
            raise ValueError("Session not found or expired")
        
        # Load session
        session = SessionManager.load_session(
            session_id, 
            base_path=config.settings.SESSION_BASE_PATH
        )
        
        # Get pipeline metadata
        metadata = session.get_metadata()
        pipeline_metadata = metadata.get("auto_detected_pipeline")
        
        # Create shared analysis context
        shared_context = AnalysisContext(
            session_id, 
            session.local_path,
            pipeline_metadata=pipeline_metadata,
            all_files=analysis_request.all_files
        )
        
        results = {}
        
        # Handle pipeline analysis with overrides
        if "pipeline" in analysis_request.analyzers:
            results["pipeline"] = AnalysisService._analyze_pipeline(
                session_id=session_id,
                local_path=session.local_path,
                shared_context=shared_context,
                session=session,
                overrides=analysis_request.pipeline_overrides
            )
        
        # Run other analyzers
        for analyzer_type in analysis_request.analyzers:
            if analyzer_type == "pipeline":
                continue
            
            analyzer = AnalyzerFactory.create_analyzer(
                analyzer_type, session_id, session.local_path, shared_context
            )
            result = analyzer.analyze()
            results[analyzer_type] = result
        
        # Serialize results
        serialized_results = {
            key: value.to_dict() if isinstance(value, AnalysisResult) else value
            for key, value in results.items()
        }
        
        # Save results to session
        session.save_analysis_results(serialized_results)
        
        return {
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "results": serialized_results
        }
    
    @staticmethod
    def _analyze_pipeline(
        session_id: str,
        local_path: str,
        shared_context: AnalysisContext,
        session: SessionManager,
        overrides: Dict = None
    ) -> AnalysisResult:
        """
        Analyze pipeline with optional overrides.
        
        Args:
            session_id: Session identifier
            local_path: Path to code files
            shared_context: Shared analysis context
            session: Session manager instance
            overrides: Optional pipeline overrides
            
        Returns:
            Pipeline analysis result
        """
        pipeline_analyzer = AnalyzerFactory.create_analyzer(
            "pipeline", session_id, local_path, shared_context
        )
        
        if overrides:
            metadata = session.get_metadata()
            auto_detected = metadata["auto_detected_pipeline"]
            
            modified = pipeline_analyzer.apply_overrides(
                auto_detected=auto_detected,
                overrides=overrides
            )
            
            return AnalysisResult(
                analyzer_id="pipeline_detection",
                score=10.0 if modified["is_valid_pipeline"] else 0.0,
                messages={},
                module_count=modified.get("files_analyzed", 0),
                metric_metadata=get_metric_metadata("pipeline_detection"),
                details=modified
            )
        else:
            return pipeline_analyzer.analyze()
