import json
import os
from datetime import datetime, timedelta, timezone 
from typing import Dict, Optional, Any


class SessionStorage:
    """Manages session metadata persistence."""
    
    @staticmethod
    def save_metadata(
        session_id: str,
        base_path: str,
        local_path: str,
        tree_structure: Dict,
        auto_detected_pipeline: Dict,
        ttl_minutes: int = 60
    ) -> None:
        """
        Save session metadata to JSON file.
        
        Args:
            session_id: Unique session identifier
            base_path: Base directory for sessions
            local_path: Path to extracted files
            tree_structure: File tree structure
            auto_detected_pipeline: Pipeline detection results
            ttl_minutes: Time to live in minutes
        """
        session_dir = os.path.join(base_path, session_id)
        os.makedirs(session_dir, exist_ok=True)
        
        metadata_path = os.path.join(session_dir, "metadata.json")
        
        created_at = datetime.now(timezone.utc)
        expires_at = created_at + timedelta(minutes=ttl_minutes)
        
        metadata = {
            "session_id": session_id,
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "local_path": local_path,
            "tree_structure": tree_structure,
            "auto_detected_pipeline": auto_detected_pipeline,
            "analysis_results": {}
        }
        
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
    
    @staticmethod
    def load_metadata(session_id: str, base_path: str) -> Optional[Dict[str, Any]]:
        """
        Load session metadata from JSON file.
        
        Args:
            session_id: Unique session identifier
            base_path: Base directory for sessions
            
        Returns:
            Session metadata dict or None if not found/expired
        """
        metadata_path = os.path.join(base_path, session_id, "metadata.json")
        
        if not os.path.exists(metadata_path):
            return None
        
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            expires_at = datetime.fromisoformat(
                metadata["expires_at"].replace("Z", "+00:00")
            )
            if datetime.now(timezone.utc) > expires_at:
                return None
            
            return metadata
            
        except (json.JSONDecodeError, KeyError, ValueError):
            return None
    
    @staticmethod
    def exists(session_id: str, base_path: str) -> bool:
        """
        Check if session exists and is not expired.
        
        Args:
            session_id: Unique session identifier
            base_path: Base directory for sessions
            
        Returns:
            True if session exists and is valid
        """
        return SessionStorage.load_metadata(session_id, base_path) is not None
    
    @staticmethod
    def update_analysis_results(
        session_id: str,
        base_path: str,
        results: Dict
    ) -> None:
        """
        Update analysis results in session metadata.
        
        Args:
            session_id: Unique session identifier
            base_path: Base directory for sessions
            results: Analysis results to save
        """
        metadata = SessionStorage.load_metadata(session_id, base_path)
        if not metadata:
            raise ValueError(f"Session {session_id} not found or expired")
        
        metadata["analysis_results"] = results
        
        metadata_path = os.path.join(base_path, session_id, "metadata.json")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)