import os
import shutil
import subprocess
import tempfile
from typing import BinaryIO, Union
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
    
    def create_session_workspace(self, session_id: str, source: Union[bytes, str], source_type: str = "zip") -> str:
        """
        Create workspace from ZIP file or Git repository.
        
        Args:
            session_id: Session identifier
            source: ZIP file bytes or Git repository URL
            source_type: "zip" or "git"
            
        Returns:
            Path to workspace directory
            
        Raises:
            SessionError: If workspace creation fails
        """
        if source_type == "zip":
            return self._create_from_zip(session_id, source)
        elif source_type == "git":
            return self._create_from_git(session_id, source)
        else:
            raise SessionError(f"Unknown source type: {source_type}")
    
    def _create_from_zip(self, session_id: str, app_zip: bytes) -> str:
        """Create workspace and extract ZIP file."""
        workspace_path = os.path.join(self.base_path, session_id)
        workspace_path = os.path.abspath(workspace_path)
        
        try:
            os.makedirs(workspace_path, exist_ok=True)
            
            zip_path = os.path.join(workspace_path, 'temp.zip')
            with open(zip_path, 'wb') as f:
                f.write(app_zip)
            
            shutil.unpack_archive(zip_path, workspace_path)
            
            os.remove(zip_path)
            
            return workspace_path
            
        except Exception as e:
            self._cleanup_workspace(workspace_path)
            raise SessionError(f"ZIP extraction failed: {str(e)}")
    
    def _create_from_git(self, session_id: str, git_url: str) -> str:
        """Create workspace and clone Git repository."""
        workspace_path = os.path.join(self.base_path, session_id)
        workspace_path = os.path.abspath(workspace_path)
        
        try:
            os.makedirs(workspace_path, exist_ok=True)
            
            # Clone repository into workspace
            result = subprocess.run(
                ['git', 'clone', '--depth', '1', git_url, workspace_path],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            if result.returncode != 0:
                raise SessionError(f"Git clone failed: {result.stderr}")
            
            # Remove .git directory to save space
            git_dir = os.path.join(workspace_path, '.git')
            if os.path.exists(git_dir):
                shutil.rmtree(git_dir, ignore_errors=True)
            
            return workspace_path
            
        except subprocess.TimeoutExpired:
            self._cleanup_workspace(workspace_path)
            raise SessionError("Git clone timed out (max 5 minutes)")
        except Exception as e:
            self._cleanup_workspace(workspace_path)
            raise SessionError(f"Git clone failed: {str(e)}")
    
    def _cleanup_workspace(self, path: str):
        """Clean up workspace on error."""
        if os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)
