from flask import Flask, request
from flask_cors import cross_origin
from datetime import datetime
import warnings

from session.session_manager import SessionManager
from session.session_storage import SessionStorage
from api.serializers import ResponseSerializer
from core.exceptions import SessionError
import config.settings as config
from analyzers.factory import AnalyzerFactory
from core.tree_generator import TreeGenerator
from core.models.pipeline_overrides import AnalysisRequest
from core.models.analysis_result import AnalysisResult
from core.metrics import get_metric_metadata
from utils.validation import validate_analysis_request, validate_zip_file
from core.analysis_context import AnalysisContext


def create_routes(app: Flask) -> Flask:

    @app.route(f'{config.settings.API_PREFIX}/upload-zip', methods=['POST'])
    @cross_origin()
    def upload_zip():
        """
        Upload ZIP and get auto-detected pipeline.
        
        Returns session_id, tree_structure, and auto_detected_pipeline.
        """
        try:
            app_zip, error = validate_zip_file(request)
            if error:
                return ResponseSerializer.error(error, 400)
            
            session = SessionManager(
                app_zip=app_zip,
                base_path=config.settings.SESSION_BASE_PATH
            )
            
            session.ensure_setup()
            
            tree_generator = TreeGenerator(session.local_path)
            tree_structure = tree_generator.generate()
            
            pipeline_analyzer = AnalyzerFactory.create_analyzer(
                "pipeline", session.session_id, session.local_path
            )
            pipeline_result = pipeline_analyzer.analyze()
            
            session.save_session(
                tree_structure=tree_structure,
                auto_detected_pipeline=pipeline_result.details,
                ttl_minutes=config.settings.SESSION_TTL_MINUTES
            )
            
            return ResponseSerializer.success({
                "session_id": session.session_id,
                "tree_structure": tree_structure,
                "auto_detected_pipeline": pipeline_result.details
            })
            
        except SessionError as e:
            return ResponseSerializer.error(f"Session error: {str(e)}", 400)
        except Exception as e:
            return ResponseSerializer.error(f"Upload failed: {str(e)}", 500)

    @app.route(f'{config.settings.API_PREFIX}/analyze/<session_id>', methods=['POST'])
    @cross_origin()
    def analyze_session(session_id: str):
        """
        Analyze code for existing session with optional overrides.
        
        Expects JSON body:
        {
          "analyzers": ["pylint", "radon_cc", "pipeline"],
          "all_files": false,  // Optional: analyze all files vs ML-only (default: false)
          "pipeline_overrides": {
            "file_stages": {"path/to/file.py": ["data_collection"]},
            "excluded_files": ["tests/", "docs/"]
          }
        }
        """
        try:
            if not SessionStorage.exists(session_id, config.settings.SESSION_BASE_PATH):
                return ResponseSerializer.error("Session not found or expired", 404)
            
            data = request.get_json()
            if not data:
                return ResponseSerializer.error("Request body required", 400)
            
            is_valid, error_msg = validate_analysis_request(data)
            if not is_valid:
                return ResponseSerializer.error(error_msg, 400)
            
            analysis_request = AnalysisRequest.from_dict(data)
            
            # Extract all_files parameter (default: False for backward compatibility)
            all_files = data.get('all_files', False)
            
            session = SessionManager.load_session(
                session_id, 
                base_path=config.settings.SESSION_BASE_PATH
            )
            
            metadata = session.get_metadata()
            pipeline_metadata = metadata.get("auto_detected_pipeline")
            
            shared_context = AnalysisContext(
                session_id, 
                session.local_path,
                pipeline_metadata=pipeline_metadata,
                all_files=all_files  # Pass all_files to context
            )
            
            results = {}
        
            
            if "pipeline" in analysis_request.analyzers:
                pipeline_analyzer = AnalyzerFactory.create_analyzer(
                    "pipeline", session_id, session.local_path, shared_context
                )
                
                
                if analysis_request.pipeline_overrides:
                    metadata = session.get_metadata()
                    auto_detected = metadata["auto_detected_pipeline"]
                    
                    modified = pipeline_analyzer.apply_overrides(
                        auto_detected=auto_detected,
                        overrides=analysis_request.pipeline_overrides
                    )
                    
                    results["pipeline"] = AnalysisResult(
                        analyzer_id="pipeline_detection",
                        score=10.0 if modified["is_valid_pipeline"] else 0.0,
                        message_count={},
                        module_count=modified.get("files_analyzed", 0),
                        metric_metadata=get_metric_metadata("pipeline_detection"),
                        details=modified
                    )
                else:
                    results["pipeline"] = pipeline_analyzer.analyze()
            
            for analyzer_type in analysis_request.analyzers:
                if analyzer_type == "pipeline":
                    continue
                
                
                analyzer = AnalyzerFactory.create_analyzer(
                    analyzer_type, session_id, session.local_path, shared_context
                )
                result = analyzer.analyze()
                
                results[analyzer_type] = result
            
            serialized_results = {
                key: value.to_dict() if isinstance(value, AnalysisResult) else value
                for key, value in results.items()
            }
            
            session.save_analysis_results(serialized_results)
            
            return ResponseSerializer.success({
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                
                "results": serialized_results
            })
            
        except SessionError as e:
            return ResponseSerializer.error(f"Session error: {str(e)}", 400)
        except Exception as e:
            print(e)
            return ResponseSerializer.error(f"Analysis failed: {str(e)}", 500)

    @app.route(f'{config.settings.API_PREFIX}/rate_app', methods=['POST'])
    @cross_origin()
    def rate_app():
        """
        Legacy endpoint for backward compatibility.
        
        @deprecated Use /api/upload-zip + /api/analyze instead
        """
        warnings.warn(
            "rate_app endpoint is deprecated. Use /upload-zip + /analyze instead",
            DeprecationWarning
        )
        
        try:
            app_zip, error = validate_zip_file(request)
            if error:
                return ResponseSerializer.error(error, 400)
            
            session = SessionManager(
                app_zip=app_zip,
                analyzer_types=['pylint', 'radon_cc', 'radon_mi'],
                base_path=config.settings.SESSION_BASE_PATH
            )
            
            session.ensure_setup()
            
            results = session.run_analysis()
            
            legacy_response = {
                "session_id": session.session_id,
                "results": {
                    analyzer_type: {
                        "score": result.score,
                        "message_count": result.message_count,
                        "module_count": result.module_count
                    }
                    for analyzer_type, result in results.items()
                }
            }
            
            return ResponseSerializer.success(legacy_response)
            
        except Exception as e:
            return ResponseSerializer.error(f"Analysis failed: {str(e)}", 500)

    return app