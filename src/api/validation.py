from typing import Tuple, Union
from core.exceptions import FileUploadError


def validate_upload(request) -> Tuple[str, Union[bytes, str]]:
    """
    Validate upload in request (ZIP file or Git URL).
    
    Args:
        request: Flask request object
    
    Returns:
        Tuple of (source_type, content) where:
        - source_type is "zip" or "git"
        - content is bytes for ZIP or string URL for Git
        
    Raises:
        FileUploadError: If validation fails
    """
    has_file = 'file' in request.files
    has_git_url = 'git_url' in request.form
    
    # Check that exactly one source is provided
    if not has_file and not has_git_url:
        raise FileUploadError("Must provide either 'file' (ZIP) or 'git_url' (Git repository)")
    
    if has_file and has_git_url:
        raise FileUploadError("Cannot provide both 'file' and 'git_url'. Choose one source.")
    
    # Handle ZIP file upload
    if has_file:
        file = request.files['file']
        if not file or file.filename == '':
            raise FileUploadError("No file selected")
        
        if not file.filename.endswith('.zip'):
            raise FileUploadError("File must be a ZIP archive")
        
        app_zip = file.read()
        if not app_zip:
            raise FileUploadError("Empty ZIP file")
        
        return ("zip", app_zip)
    
    # Handle Git URL
    if has_git_url:
        git_url = request.form['git_url'].strip()
        
        if not git_url:
            raise FileUploadError("Git URL cannot be empty")
        
        if not git_url.endswith('.git'):
            raise FileUploadError("Git URL must end with '.git'")
        
        # Basic URL validation
        if not (git_url.startswith('http://') or git_url.startswith('https://')):
            raise FileUploadError("Git URL must start with 'http://' or 'https://'")
        
        return ("git", git_url)


def validate_zip_file(request):
    """
    DEPRECATED: Use validate_upload() instead.
    
    Validate ZIP file in request.
    
    Args:
        request: Flask request object
    
    Returns:
        File content (bytes)
        
    Raises:
        FileUploadError: If validation fails
    """
    source_type, content = validate_upload(request)
    if source_type != "zip":
        raise FileUploadError("Expected ZIP file")
    return content