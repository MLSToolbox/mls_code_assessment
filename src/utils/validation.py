from typing import Dict, Tuple


def validate_analysis_request(data: Dict) -> Tuple[bool, str]:
    """
    Validate analysis request payload.
    
    Args:
        data: Request data dictionary
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check required fields
    if 'analyzers' not in data:
        return False, "Missing required field: analyzers"
    
    if not isinstance(data['analyzers'], list):
        return False, "Field 'analyzers' must be a list"
    
    if len(data['analyzers']) == 0:
        return False, "At least one analyzer must be specified"
    
    # Validate analyzer types
    valid_analyzers = {'pylint', 'radon_cc', 'radon_mi', 'pipeline', 'fpc', 'pfp'}
    for analyzer in data['analyzers']:
        if analyzer not in valid_analyzers:
            return False, f"Invalid analyzer type: {analyzer}. Valid types: {valid_analyzers}"
    
    # Validate overrides if present
    if 'pipeline_overrides' in data:
        is_valid, error = validate_pipeline_overrides(data['pipeline_overrides'])
        if not is_valid:
            return False, error
    
    return True, ""


def validate_pipeline_overrides(overrides: Dict) -> Tuple[bool, str]:
    """
    Validate pipeline overrides structure.
    
    Args:
        overrides: Overrides dictionary
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(overrides, dict):
        return False, "pipeline_overrides must be an object"
    
    # Validate file_stages if present
    if 'file_stages' in overrides:
        file_stages = overrides['file_stages']
        
        if not isinstance(file_stages, dict):
            return False, "file_stages must be an object"
        
        # Valid stage names (includes optional stages)
        valid_stages = {
            "data_collection",
            "data_cleaning",        # Optional
            "feature_engineering",  # Optional
            "model_training",
            "model_evaluation"
        }
        
        for filepath, stages in file_stages.items():
            if not isinstance(stages, list):
                return False, f"Stages for '{filepath}' must be a list"
            
            for stage in stages:
                if stage not in valid_stages:
                    return False, f"Invalid stage '{stage}'. Valid stages: {valid_stages}"
    
    # Validate excluded_files if present
    if 'excluded_files' in overrides:
        excluded = overrides['excluded_files']
        
        if not isinstance(excluded, list):
            return False, "excluded_files must be a list"
        
        for item in excluded:
            if not isinstance(item, str):
                return False, "excluded_files items must be strings"
    
    return True, ""