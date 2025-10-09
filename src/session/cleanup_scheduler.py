"""
Cleanup Scheduler Module
Background task to clean up expired sessions.
"""
import os
import shutil
import time
import threading
import logging
from datetime import datetime, timezone
from typing import Optional

from session.session_storage import SessionStorage

logger = logging.getLogger(__name__)


class CleanupScheduler:
    """Scheduled cleanup of expired sessions."""
    
    def __init__(self, interval_minutes: int, base_path: str):
        """
        Initialize CleanupScheduler.
        
        Args:
            interval_minutes: Cleanup interval in minutes
            base_path: Base path for sessions
        """
        self.interval_minutes = interval_minutes
        self.base_path = base_path
        self.running = False
        self.thread: Optional[threading.Thread] = None
    
    def start(self) -> None:
        """Start the cleanup scheduler."""
        if self.running:
            logger.warning("Cleanup scheduler already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        
        logger.info(
            f"Cleanup scheduler started with {self.interval_minutes}min interval",
            extra={
                'interval_minutes': self.interval_minutes,
                'base_path': self.base_path
            }
        )
    
    def stop(self) -> None:
        """Stop the cleanup scheduler."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        
        logger.info("Cleanup scheduler stopped")
    
    def _run(self) -> None:
        """Main scheduler loop."""
        while self.running:
            try:
                self._cleanup_expired_sessions()
            except Exception as e:
                logger.error(f"Cleanup failed: {str(e)}", exc_info=True)
            
            # Sleep in small intervals to allow quick shutdown
            sleep_time = self.interval_minutes * 60
            elapsed = 0
            while elapsed < sleep_time and self.running:
                time.sleep(1)
                elapsed += 1
    
    def _cleanup_expired_sessions(self) -> None:
        """Remove expired session directories."""
        if not os.path.exists(self.base_path):
            return
        
        removed_count = 0
        
        try:
            for session_id in os.listdir(self.base_path):
                session_dir = os.path.join(self.base_path, session_id)
                
                if not os.path.isdir(session_dir):
                    continue
                
                # Check if session is expired
                metadata = SessionStorage.load_metadata(session_id, self.base_path)
                
                if metadata is None:
                    # Session expired or invalid, remove it
                    try:
                        shutil.rmtree(session_dir)
                        removed_count += 1
                        logger.info(
                            f"Removed expired session: {session_id}",
                            extra={'session_id': session_id}
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to remove session {session_id}: {str(e)}",
                            extra={'session_id': session_id}
                        )
        
        except Exception as e:
            logger.error(f"Cleanup iteration failed: {str(e)}", exc_info=True)
        
        if removed_count > 0:
            logger.info(
                f"Cleanup completed: removed {removed_count} expired sessions",
                extra={'removed_count': removed_count}
            )
    
    def run_once(self) -> None:
        """Run cleanup once (useful for testing)."""
        self._cleanup_expired_sessions()


# Global scheduler instance
_scheduler: Optional[CleanupScheduler] = None


def get_scheduler() -> Optional[CleanupScheduler]:
    """Get global scheduler instance."""
    return _scheduler


def start_scheduler(interval_minutes: int, base_path: str) -> CleanupScheduler:
    """
    Start global cleanup scheduler.
    
    Args:
        interval_minutes: Cleanup interval
        base_path: Base path for sessions
        
    Returns:
        CleanupScheduler instance
    """
    global _scheduler
    
    if _scheduler is not None:
        logger.warning("Scheduler already started")
        return _scheduler
    
    _scheduler = CleanupScheduler(interval_minutes, base_path)
    _scheduler.start()
    
    return _scheduler


def stop_scheduler() -> None:
    """Stop global cleanup scheduler."""
    global _scheduler
    
    if _scheduler is not None:
        _scheduler.stop()
        _scheduler = None