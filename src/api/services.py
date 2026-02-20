from typing import Dict, Any, Tuple, Union
from datetime import datetime
from werkzeug.datastructures import FileStorage
from session.session_manager import SessionManager
from session.session_storage import SessionStorage
from analyzers.factory import AnalyzerFactory
from core.tree_generator import TreeGenerator
from core.analysis_context import AnalysisContext
from analyzers.pipeline.pipeline_overrides import AnalysisRequest
from core.analysis_result import AnalysisResult
from core.exceptions import SessionNotFoundError
from metrics import get_metric_metadata
import config.settings as config


class UploadService:
    """Handles ZIP upload and initial pipeline detection."""
    
    @staticmethod
    def process_upload(upload_data: Tuple[str, Union[bytes, str]]) -> Dict[str, Any]:
        """
        Process uploaded file (ZIP or Git URL) and create session.
        
        Args:
            upload_data: Tuple of (source_type, content) where:
                - source_type is "zip" or "git"
                - content is bytes for ZIP or string URL for Git
            
        Returns:
            Dictionary with session_id, tree_structure, and auto_detected_pipeline
            
        Raises:
            SessionError: If session creation fails
            Exception: For other processing errors
        """
        source_type, content = upload_data
        
        # Create session with appropriate source
        if source_type == "zip":
            session = SessionManager(
                app_zip=content,
                base_path=config.settings.SESSION_BASE_PATH
            )
        elif source_type == "git":
            session = SessionManager(
                git_url=content,
                base_path=config.settings.SESSION_BASE_PATH
            )
        else:
            raise ValueError(f"Unknown source type: {source_type}")
        
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
            SessionNotFoundError: If session not found or expired
            SessionError: If session invalid
            AnalyzerError: For analysis errors
        """
        # Validate session exists
        if not SessionStorage.exists(session_id, config.settings.SESSION_BASE_PATH):
            raise SessionNotFoundError(session_id)
        
        # Load session
        session = SessionManager.load_session(
            session_id, 
            base_path=config.settings.SESSION_BASE_PATH
        )
        
        # Get pipeline metadata
        metadata = session.get_metadata()
        pipeline_metadata = metadata.get("auto_detected_pipeline")
        tree_metadata = metadata.get("tree_structure")

        
        # Apply pipeline overrides FIRST if they exist
        # This ensures all analyzers use the updated metadata
        if analysis_request.pipeline_overrides:
            pipeline_analyzer = AnalyzerFactory.create_analyzer(
                "pipeline", session_id, session.local_path, None
            )
            pipeline_metadata = pipeline_analyzer.apply_overrides(
                auto_detected=pipeline_metadata,
                overrides=analysis_request.pipeline_overrides
            )
        
        # Create shared analysis context with (potentially overridden) pipeline metadata
        shared_context = AnalysisContext(
            session_id, 
            session.local_path,
            pipeline_metadata=pipeline_metadata,
            tree_metadata=tree_metadata,
            all_files=analysis_request.all_files
        )
        
        results = {}
        
        # Run all analyzers (including pipeline if requested)
        for analyzer_type in analysis_request.analyzers:
            if analyzer_type == "pipeline":
                # For pipeline, just create the result from the metadata we already have
                results["pipeline"] = AnalysisResult(
                    analyzer_id="pipeline_detection",
                    score=10.0 if pipeline_metadata["is_valid_pipeline"] else 0.0,
                    messages={},
                    module_count=pipeline_metadata.get("files_analyzed", 0),
                    metric_metadata=get_metric_metadata("pipeline_detection"),
                    details=pipeline_metadata
                )
            else:
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
