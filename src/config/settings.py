import os
from typing import Literal, Set


class Settings:
    # Server settings
    HOST: str = os.getenv('HOST', '0.0.0.0')
    PORT: int = int(os.getenv('PORT', '5060'))
    DEBUG: bool = os.getenv('DEBUG', 'False').lower() == 'true'
    
    # API settings
    API_PREFIX: str = '/api'
    
    # Valid analyzer types
    VALID_ANALYZERS: Set[str] = {
        "pylint",
        "radon_cc",
        "radon_mi",
        "pipeline",
        "ccpm",
        "file_structure",
        "lccml",
        "ml_content",
        "scpm",
        "fcpm"
    }
    
    # Valid pipeline stages
    VALID_PIPELINE_STAGES: Set[str] = {
        "data_collection",
        "data_cleaning",
        "feature_engineering",
        "model_training",
        "model_evaluation"
    }
    
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
        },
        "ccpm": {
            # Minimum number of lines of code for a file to be considered 
            # in cohesion evaluation. Files below this threshold will be 
            # analyzed but marked as "too_small" if they show low cohesion.
            "nloc_threshold": 30
        }
    }


# Global settings instance
settings = Settings()


# Type aliases for type hints
AnalyzerType = Literal[
    "pylint",
    "radon_cc",
    "radon_mi",
    "pipeline",
    "ccpm",
    "file_structure",
    "lccml",
    "ml_content",
    "scpm",
    "fcpm"
]

PipelineStage = Literal[
    "data_collection",
    "data_cleaning",
    "feature_engineering",
    "model_training",
    "model_evaluation"
]
