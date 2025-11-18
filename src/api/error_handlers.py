import logging
from flask import Flask
from werkzeug.exceptions import HTTPException

from api.serializers import ResponseSerializer
from core.exceptions import (
    MLSAnalysisError,
    SessionError,
    SessionNotFoundError,
    ValidationError,
    AnalyzerError,
    FileUploadError
)

logger = logging.getLogger(__name__)


def register_error_handlers(app: Flask) -> None:
    """Register all error handlers with the Flask app."""
    
    @app.errorhandler(ValidationError)
    def handle_validation_error(error: ValidationError):
        """Handle validation errors (422)."""
        logger.warning(f"Validation error: {error.message}")
        details = {"field": error.field} if error.field else None
        return ResponseSerializer.error(error.message, error.status_code, details)
    
    @app.errorhandler(SessionNotFoundError)
    def handle_session_not_found(error: SessionNotFoundError):
        """Handle session not found errors (404)."""
        logger.warning(f"Session not found: {error.session_id}")
        return ResponseSerializer.error(error.message, error.status_code)
    
    @app.errorhandler(SessionError)
    def handle_session_error(error: SessionError):
        """Handle session errors (400)."""
        logger.error(f"Session error: {error.message}")
        return ResponseSerializer.error(error.message, error.status_code)
    
    @app.errorhandler(FileUploadError)
    def handle_file_upload_error(error: FileUploadError):
        """Handle file upload errors (400)."""
        logger.warning(f"File upload error: {error.message}")
        return ResponseSerializer.error(error.message, error.status_code)
    
    @app.errorhandler(AnalyzerError)
    def handle_analyzer_error(error: AnalyzerError):
        """Handle analyzer errors (500)."""
        logger.error(f"Analyzer error: {error.message}")
        details = {"analyzer": error.analyzer_type} if error.analyzer_type else None
        return ResponseSerializer.error(error.message, error.status_code, details)
    
    @app.errorhandler(MLSAnalysisError)
    def handle_mls_error(error: MLSAnalysisError):
        """Handle generic MLS errors."""
        logger.error(f"MLS Analysis error: {error.message}")
        return ResponseSerializer.error(error.message, error.status_code)
    
    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException):
        """Handle Werkzeug HTTP exceptions (404, 405, etc)."""
        logger.warning(f"HTTP error {error.code}: {error.description}")
        return ResponseSerializer.error(error.description, error.code)
    
    @app.errorhandler(ValueError)
    def handle_value_error(error: ValueError):
        """Handle ValueError as bad request."""
        logger.warning(f"ValueError: {str(error)}")
        return ResponseSerializer.error(str(error), 400)
    
    @app.errorhandler(Exception)
    def handle_generic_error(error: Exception):
        """Handle all unhandled exceptions (500)."""
        logger.exception(f"Unhandled exception: {str(error)}")
        
        # In production, don't expose internal error details
        if app.config.get('DEBUG'):
            message = f"Internal server error: {str(error)}"
        else:
            message = "An unexpected error occurred. Please try again later."
        
        return ResponseSerializer.error(message, 500)
