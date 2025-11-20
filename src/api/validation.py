from core.exceptions import FileUploadError


def validate_zip_file(request):
    """
    Validate ZIP file in request.
    
    Args:
        request: Flask request object
    
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