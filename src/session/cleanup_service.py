import os
import shutil
import time
import threading
from typing import Set
from config.settings import settings
import uuid

class CleanupService:
    """Service for cleaning up session resources."""
    
    def __init__(self):
        self._active_sessions: Set[str] = set()
        self._start_cleanup_timer()
    
    def cleanup_session(self, session_path: str):
        """Clean up specific session."""
        if os.path.exists(session_path):
            try:
                shutil.rmtree(session_path)
                session_id = os.path.basename(session_path)
                self._active_sessions.discard(session_id)
            except OSError:
                pass  # Ignore cleanup errors
    
    def register_session(self, session_id: str):
        """Register session for tracking."""
        self._active_sessions.add(session_id)
    
    def _start_cleanup_timer(self):
        """Start periodic cleanup of old sessions."""
        def cleanup_old_sessions():
            current_time = time.time()
            
            for item in os.listdir('.'):
                if os.path.isdir(item) and self._looks_like_session_id(item):
                    item_path = os.path.join('.', item)
                    
                    if (current_time - os.path.getctime(item_path) > 
                        settings.MAX_SESSION_LIFETIME):
                        self.cleanup_session(item_path)
            
            timer = threading.Timer(settings.CLEANUP_INTERVAL, cleanup_old_sessions)
            timer.daemon = True
            timer.start()
        
        cleanup_old_sessions()
    
    def _looks_like_session_id(self, name: str) -> bool:
        """Check if directory name looks like a session ID."""
        try:
            uuid.UUID(name)
            return True
        except ValueError:
            return False
