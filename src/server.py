import logging
from flask import Flask
from waitress import serve

from api.routes import create_routes
from api.middleware import setup_middleware
from api.error_handlers import register_error_handlers
from config.settings import settings
from session.cleanup_scheduler import start_scheduler 

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def create_app() -> Flask:
    """Create and configure Flask application."""
    app = Flask(__name__)
    app.config['DEBUG'] = settings.DEBUG
    
    app = setup_middleware(app)
    
    register_error_handlers(app)
    
    app = create_routes(app)
    
    start_scheduler(
        interval_minutes=settings.CLEANUP_INTERVAL_MINUTES,
        base_path=settings.SESSION_BASE_PATH
    )
    
    return app

if __name__ == '__main__':
    app = create_app()
    
    logging.info(
        f"Starting server on {settings.HOST}:{settings.PORT}",
        extra={
            'host': settings.HOST,
            'port': settings.PORT,
            'debug': settings.DEBUG
        }
    )
    
    if settings.DEBUG:
        app.run(
            host=settings.HOST,
            port=settings.PORT,
            debug=True,
            
        )
    else:
        serve(app, host=settings.HOST, port=settings.PORT)