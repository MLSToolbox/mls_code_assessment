# api/routes.py
from flask import Flask, request, make_response
from flask_cors import cross_origin
from typing import Dict, Any

from session.session_manager import SessionManager
from api.serializers import ResponseSerializer
from api.middleware import setup_middleware
from core.exceptions import SessionError, AnalyzerError
from utils.validation import validate_session_id

def create_routes(app: Flask) -> Flask:
    """Create and configure API routes."""
    
    @app.route('/api/rate_app', methods=['POST'])
    @cross_origin()
    def rate_app():
        """Analyze code quality."""
        try:
            # Get binary ZIP data
            content = request.data
            if not content:
                return ResponseSerializer.error("No data provided", 400)
            
            # Create session and run analysis
            session = SessionManager(content)
            results = session.run_analysis()
            session.cleanup()
            
            return ResponseSerializer.success(results)
            
        except SessionError as e:
            return ResponseSerializer.error(f"Session error: {str(e)}", 400)
        except Exception as e:
            return ResponseSerializer.error(f"Analysis failed: {str(e)}", 500)
    
    @app.route('/api/get_report', methods=['POST'])
    @cross_origin()
    def get_report():
        """Generate detailed report for specific analyzer."""
        try:
            # Get parameters
            content = request.data
            test_id = request.args.get('test_id', default="NONE", type=str)
            
            if test_id == "NONE":
                return ResponseSerializer.error("Please provide test_id", 400)
            
            if not content:
                return ResponseSerializer.error("No data provided", 400)
            
            # Create session and generate report
            session = SessionManager(content)
            report_data = session.generate_report(test_id)
            session.cleanup()
            
            if report_data is None:
                return ResponseSerializer.error(f"No report found for test_id: {test_id}", 404)
            
            # Create binary response
            response = make_response(report_data)
            response.headers.set('Content-Type', 'application/x-binary')
            response.headers.set('Content-Disposition', 'attachment', filename='report.txt')
            response.headers.set('Access-Control-Allow-Origin', '*')
            response.headers.set('Access-Control-Allow-Methods', 'GET, PUT, POST, DELETE, OPTIONS')
            response.status_code = 200
            
            return response
            
        except SessionError as e:
            return ResponseSerializer.error(f"Session error: {str(e)}", 400)
        except Exception as e:
            return ResponseSerializer.error(f"Report generation failed: {str(e)}", 500)
    
    @app.route('/', methods=['GET', 'POST'])
    @cross_origin()
    def health_check():
        """Health check endpoint."""
        return ResponseSerializer.success({
            "service": "mls_code_assessment",
            "status": "healthy",
            "method": request.method
        })
    
    @app.route('/api/analyzers', methods=['GET'])
    @cross_origin()
    def get_analyzers():
        """Get available analyzers."""
        from analyzers.factory import AnalyzerFactory
        analyzers = AnalyzerFactory.get_available_analyzers()
        return ResponseSerializer.success({"analyzers": analyzers})
    
    return app
