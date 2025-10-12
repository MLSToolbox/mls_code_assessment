import os


class Settings:
    """Application configuration settings."""
    
    # Server settings
    HOST: str = os.getenv('HOST', '0.0.0.0')
    PORT: int = int(os.getenv('PORT', '5060'))
    DEBUG: bool = os.getenv('DEBUG', 'False').lower() == 'true'
    
    # API settings
    API_PREFIX: str = '/api'
    
    # Session settings
    SESSION_BASE_PATH: str = os.getenv('SESSION_BASE_PATH', '/tmp/mls_sessions')
    SESSION_TTL_MINUTES: int = int(os.getenv('SESSION_TTL_MINUTES', '60'))
    
    # Cleanup scheduler settings
    CLEANUP_INTERVAL_MINUTES: int = int(os.getenv('CLEANUP_INTERVAL_MINUTES', '30'))
    
    # CORS settings
    CORS_ORIGINS: str = os.getenv('CORS_ORIGINS', '*')
    
    # Analyzer configurations
    ANALYZER_CONFIG = {
        "pylint": {
            "output_format": "json2",
            "disable": [
                "E0401",  # import-error (common in isolated environments)
                "C0114",  # missing-module-docstring
                "C0115",  # missing-class-docstring
                "C0116"   # missing-function-docstring
            ]
        },
        "radon_cc": {
            "min": "A",
            "max": "F",
            "show_complexity": True
        },
        "radon_mi": {
            "min": "A",
            "max": "C",
            "show_complexity": True
        }
    }


# Global settings instance
settings = Settings()
