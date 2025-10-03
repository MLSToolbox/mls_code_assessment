import os
import logging
from flask import Flask
from waitress import serve

from api.routes import create_routes
from api.middleware import setup_middleware
from config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def create_app() -> Flask:
    """Create and configure Flask application."""
    app = Flask(__name__)
    
    app = setup_middleware(app)
    
    app = create_routes(app)
    
    return app

def main():
    """Main entry point."""
    app = create_app()
    
    if settings.EXECUTION_MODE == "prod":
        serve(app, host=settings.HOST, port=settings.PORT)
    else:
        app.run(host=settings.HOST, port=settings.PORT, debug=True)

if __name__ == '__main__':
    main()