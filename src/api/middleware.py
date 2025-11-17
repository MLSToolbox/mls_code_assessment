from flask import Flask, request, g
from flask_cors import CORS
import logging
import time
import config.settings as config
from core.execution_orchestrator import AnalyzerExecutionOrchestrator


def setup_middleware(app: Flask) -> Flask:
    
    CORS(app, supports_credentials=True, origins=['*'])
    app.config["CORS_HEADERS"] = ["Content-Type", "X-Requested-With", "X-CSRFToken"]
    
    @app.before_request
    def log_request():
        g.start_time = time.time()
        logging.info(f"Request: {request.method} {request.path}")
    
    @app.before_request
    def resolve_analyzer_dependencies():
        """
        Middleware that resolves analyzer dependencies before execution.
        
        Only applies to /analyze endpoints with 'analyzers' in request body.
        Transforms the analyzer list to include dependencies in execution order.
        """
        # Only process analyze endpoints with JSON body
        if not request.path.endswith('/analyze') and '/analyze/' not in request.path:
            return
        
        if not request.is_json:
            return
        
        data = request.get_json(silent=True)
        if not data or 'analyzers' not in data:
            return
        
        # Resolve dependencies and store in request context
        original_analyzers = data['analyzers']
        ordered_analyzers = AnalyzerExecutionOrchestrator.get_execution_order(
            original_analyzers
        )
        
        # Store both for transparency
        g.original_analyzers = original_analyzers
        g.ordered_analyzers = ordered_analyzers
        
        # Log if dependencies were added
        if ordered_analyzers != original_analyzers:
            added = set(ordered_analyzers) - set(original_analyzers)
            logging.info(
                f"Dependencies resolved: {original_analyzers} → {ordered_analyzers} "
                f"(added: {list(added)})"
            )
    
    @app.after_request
    def log_response(response):
        duration = time.time() - g.start_time
        logging.info(f"Response: {response.status_code} - {duration:.3f}s")
        return response
    
    return app
