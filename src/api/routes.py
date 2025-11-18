from flask import Flask, request
from flask_cors import cross_origin

from api.serializers import ResponseSerializer
from api.services import UploadService, AnalysisService
from core.exceptions import SessionError
from core.models.pipeline_overrides import AnalysisRequest
import config.settings as config
from utils.validation import validate_analysis_request, validate_zip_file


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
            
            result = UploadService.process_upload(app_zip)
            return ResponseSerializer.success(result)
            
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
            data = request.get_json()
            if not data:
                return ResponseSerializer.error("Request body required", 400)
            
            is_valid, error_msg = validate_analysis_request(data)
            if not is_valid:
                return ResponseSerializer.error(error_msg, 400)
            
            analysis_request = AnalysisRequest.from_dict(data)
            
            result = AnalysisService.analyze_session(session_id, analysis_request)
            return ResponseSerializer.success(result)
            
        except ValueError as e:
            return ResponseSerializer.error(str(e), 404)
        except SessionError as e:
            return ResponseSerializer.error(f"Session error: {str(e)}", 400)
        except Exception as e:
            return ResponseSerializer.error(f"Analysis failed: {str(e)}", 500)

    return app