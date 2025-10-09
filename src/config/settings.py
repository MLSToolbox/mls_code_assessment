"""
Application Settings
Configuration management using environment variables.
"""
import os
from dataclasses import dataclass


@dataclass
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


# Global settings instance
settings = Settings()