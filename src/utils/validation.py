from typing import Dict
from core.exceptions import ValidationError, FileUploadError


def validate_analysis_request(data: Dict) -> None:
    """
    Validate analysis request payload.
    
    Args:
        data: Request data dictionary
        
    Raises:
        ValidationError: If validation fails
    """
    if 'analyzers' not in data:
        raise ValidationError("Missing required field: analyzers", field="analyzers")
    
    if not isinstance(data['analyzers'], list):
        raise ValidationError("Field 'analyzers' must be a list", field="analyzers")
    
    if len(data['analyzers']) == 0:
        raise ValidationError("At least one analyzer must be specified", field="analyzers")
    
    valid_analyzers = {'pylint', 'radon_cc', 'radon_mi', 'pipeline', 'fpc', 'file_structure', 'lccml'}
    for analyzer in data['analyzers']:
        if analyzer not in valid_analyzers:
            raise ValidationError(
                f"Invalid analyzer type: {analyzer}. Valid types: {valid_analyzers}",
                field="analyzers"
            )
    
    if 'pipeline_overrides' in data:
        validate_pipeline_overrides(data['pipeline_overrides'])


def validate_pipeline_overrides(overrides: Dict) -> None:
    """
    Validate pipeline overrides structure.
    
    Args:
        overrides: Overrides dictionary
        
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(overrides, dict):
        raise ValidationError("pipeline_overrides must be an object", field="pipeline_overrides")
    
    if 'file_stages' in overrides:
        file_stages = overrides['file_stages']
        
        if not isinstance(file_stages, dict):
            raise ValidationError("file_stages must be an object", field="file_stages")
        
        valid_stages = {
            "data_collection",
            "data_cleaning", 
            "feature_engineering",
            "model_training",
            "model_evaluation"
        }
        
        for filepath, stages in file_stages.items():
            if not isinstance(stages, list):
                raise ValidationError(f"Stages for '{filepath}' must be a list", field="file_stages")
            
            for stage in stages:
                if stage not in valid_stages:
                    raise ValidationError(
                        f"Invalid stage '{stage}'. Valid stages: {valid_stages}",
                        field="file_stages"
                    )
    
    if 'excluded_files' in overrides:
        excluded = overrides['excluded_files']
        
        if not isinstance(excluded, list):
            raise ValidationError("excluded_files must be a list", field="excluded_files")
        
        for item in excluded:
            if not isinstance(item, str):
                raise ValidationError("excluded_files items must be strings", field="excluded_files")


def validate_zip_file(request):
    """
    Validate ZIP file in request.
    
    Returns:
        File content (bytes)
        
    Raises:
        FileUploadError: If validation fails
    """
    if 'file' not in request.files:
        raise FileUploadError("No file provided")
    
    file = request.files['file']
    if not file or file.filename == '':
        raise FileUploadError("No file selected")
    
    if not file.filename.endswith('.zip'):
        raise FileUploadError("File must be a ZIP archive")
    
    app_zip = file.read()
    if not app_zip:
        raise FileUploadError("Empty ZIP file")
    
    return app_zip