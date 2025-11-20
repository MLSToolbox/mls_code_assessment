from flask import Flask, request, g
from flask_cors import CORS
import logging
import time
import config.settings as config



def setup_middleware(app: Flask) -> Flask:
    
    CORS(app, supports_credentials=True, origins=['*'])
    app.config["CORS_HEADERS"] = ["Content-Type", "X-Requested-With", "X-CSRFToken"]
    
    @app.before_request
    def log_request():
        g.start_time = time.time()
        logging.info(f"Request: {request.method} {request.path}")
    
    
    
    @app.after_request
    def log_response(response):
        duration = time.time() - g.start_time
        logging.info(f"Response: {response.status_code} - {duration:.3f}s")
        return response
    
    return app
