from flask import jsonify
from typing import Any, Dict

class ResponseSerializer:
    """Handles API response serialization."""
    
    @staticmethod
    def success(data: Any, status_code: int = 200):
        """Create success response."""
        response = jsonify({
            "success": True,
            "data": data
        })
        response.status_code = status_code
        return response
    
    @staticmethod
    def error(message: str, status_code: int = 400, details: Dict = None):
        """Create error response."""
        error_data = {"message": message}
        if details:
            error_data["details"] = details
            
        response = jsonify({
            "success": False,
            "error": error_data
        })
        response.status_code = status_code
        return response
