class MLSAnalysisError(Exception):
    """Base exception for MLS analysis operations."""
    
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class SessionError(MLSAnalysisError):
    """Errors related to session management."""
    
    def __init__(self, message: str):
        super().__init__(message, status_code=400)


class SessionNotFoundError(MLSAnalysisError):
    """Session not found or expired."""
    
    def __init__(self, session_id: str):
        super().__init__(f"Session not found or expired: {session_id}", status_code=404)
        self.session_id = session_id


class ValidationError(MLSAnalysisError):
    """Request validation errors."""
    
    def __init__(self, message: str, field: str = None):
        super().__init__(message, status_code=422)
        self.field = field


class AnalyzerError(MLSAnalysisError):
    """Errors during code analysis."""
    
    def __init__(self, message: str, analyzer_type: str = None):
        super().__init__(message, status_code=500)
        self.analyzer_type = analyzer_type


class ReportGenerationError(MLSAnalysisError):
    """Errors during report generation."""
    
    def __init__(self, message: str):
        super().__init__(message, status_code=500)


class FileUploadError(MLSAnalysisError):
    """Errors during file upload."""
    
    def __init__(self, message: str):
        super().__init__(message, status_code=400)
