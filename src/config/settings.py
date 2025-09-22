import os
from typing import Dict, Any

class Settings:
    """Application configuration."""
    
    EXECUTION_MODE = os.getenv("EXECUTION_MODE", "debug")
    HOST = "0.0.0.0"
    PORT = 5060
    
    # Analysis settings
    MAX_SESSION_LIFETIME = 3600  # seconds
    CLEANUP_INTERVAL = 300  # seconds
    
    # File handling
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    ALLOWED_EXTENSIONS = ['.py', '.zip']
    
    @classmethod
    def get_analyzer_config(cls) -> Dict[str, Any]:
        """Get analyzer-specific configuration."""
        return {
            "pylint": {
                "disable": ["E0401"],
                "output_format": "json2"
            },
            "radon": {
                "complexity_threshold": 10,
                "maintainability_threshold": 20
            }
        }

settings = Settings()