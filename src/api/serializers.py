from flask import jsonify
from typing import Any, Dict
from core.models.analysis_result import AnalysisResult


class ResponseSerializer:
    
    @staticmethod
    def success(data: Any, status_code: int = 200):
        serialized_data = ResponseSerializer._serialize_data(data)
        response = jsonify({
            "success": True,
            "data": serialized_data
        })
        response.status_code = status_code
        return response
    
    @staticmethod
    def error(message: str, status_code: int = 400, details: Dict = None):
        error_data = {"message": message}
        if details:
            error_data["details"] = details
            
        response = jsonify({
            "success": False,
            "error": error_data
        })
        response.status_code = status_code
        return response
    
    @staticmethod
    def _serialize_data(data: Any) -> Any:
        if isinstance(data, AnalysisResult):
            return data.to_dict()
        elif isinstance(data, dict):
            return {key: ResponseSerializer._serialize_data(value) 
                    for key, value in data.items()}
        elif isinstance(data, (list, tuple)):
            return [ResponseSerializer._serialize_data(item) for item in data]
        else:
            return data
