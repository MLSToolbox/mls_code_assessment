import os
import shutil
import tempfile
from typing import BinaryIO
from core.exceptions import SessionError

class FileHandler:
    """Handles file operations for sessions."""
    
    def __init__(self, base_path: str):
        """
        Initialize FileHandler.
        
        Args:
            base_path: Base directory for session workspaces
        """
        self.base_path = base_path
    
    def create_session_workspace(self, session_id: str, app_zip: bytes) -> str:
        """Create workspace and extract ZIP file."""
        # Use base_path to create session directory
        workspace_path = os.path.join(self.base_path, session_id)
        workspace_path = os.path.abspath(workspace_path)
        
        try:
            # Create session directory
            os.makedirs(workspace_path, exist_ok=True)
            
            # Write ZIP file
            zip_path = os.path.join(workspace_path, 'temp.zip')
            with open(zip_path, 'wb') as f:
                f.write(app_zip)
            
            # Extract ZIP
            shutil.unpack_archive(zip_path, workspace_path)
            
            # Remove ZIP file
            os.remove(zip_path)
            
            return workspace_path
            
        except Exception as e:
            self._cleanup_workspace(workspace_path)
            raise SessionError(f"Workspace creation failed: {str(e)}")
    
    def _cleanup_workspace(self, path: str):
        """Clean up workspace on error."""
        if os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)
