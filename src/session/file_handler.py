import os
import shutil
import tempfile
from typing import BinaryIO
from core.exceptions import SessionError

class FileHandler:
    """Handles file operations for sessions."""
    
    def create_session_workspace(self, session_id: str, app_zip: bytes) -> str:
        """Create workspace and extract ZIP file."""
        # Use absolute path to avoid issues with changing working directories
        workspace_path = os.path.abspath(f"./{session_id}")
        
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
