class MLSAnalysisError(Exception):
    """Base exception for MLS analysis operations."""
    pass

class SessionError(MLSAnalysisError):
    """Errors related to session management."""
    pass

class AnalyzerError(MLSAnalysisError):
    """Errors during code analysis."""
    pass

class ReportGenerationError(MLSAnalysisError):
    """Errors during report generation."""
    pass
