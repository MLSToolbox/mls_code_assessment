from flask import Flask, request, g
from flask_cors import cross_origin
from pydantic import ValidationError as PydanticValidationError

from api.serializers import ResponseSerializer
from api.services import UploadService, AnalysisService
from api.validation import validate_upload
from analyzers.pipeline.pipeline_overrides import AnalysisRequest
from core.exceptions import ValidationError
import config.settings as config


def create_routes(app: Flask) -> Flask:

    @app.route(f'{config.settings.API_PREFIX}/upload', methods=['POST'])
    @cross_origin()
    def upload():
        """
        Upload code source (ZIP file or Git repository) and get auto-detected pipeline.
        
        Accepts either:
        - Form data with 'file': ZIP archive
        - Form data with 'git_url': Git repository URL (must end with .git)
        
        Returns session_id, tree_structure, and auto_detected_pipeline.
        """
        upload_data = validate_upload(request)
        result = UploadService.process_upload(upload_data)
        return ResponseSerializer.success(result)

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
        data = request.get_json()
        
        if not data:
            return ResponseSerializer.error("Request body required", 400)
        
        try:
            analysis_request = AnalysisRequest.model_validate(data)
        except PydanticValidationError as e:
            # Convert Pydantic validation errors to our ValidationError
            errors = e.errors()
            first_error = errors[0]
            field = ".".join(str(loc) for loc in first_error['loc'])
            raise ValidationError(first_error['msg'], field=field)
        
        result = AnalysisService.analyze_session(session_id, analysis_request)
        return ResponseSerializer.success(result)

    return app