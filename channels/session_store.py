"""
Session Store for Gateway - Persistent session management with encryption
"""

import json
import secrets
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
import base64


@dataclass
class Session:
    """Session data structure"""
    session_id: str
    device_id: str
    device_name: str
    channel_type: str
    auth_token: str
    metadata: Dict[str, Any]
    created_at: str
    expires_at: str
    last_active: str


class SessionStore:
    """
    Persistent session storage with encryption.
    Manages device sessions for Gateway connections.
    """
    
    def __init__(self, storage_path: str = "sessions", secret_key: Optional[str] = None):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize encryption
        if secret_key:
            # Use provided key
            key = base64.urlsafe_b64encode(secret_key.encode().ljust(32)[:32])
        else:
            # Generate new key
            key = Fernet.generate_key()
        
        self.cipher = Fernet(key)
        self.expiry_hours = 24
    
    def generate_session_id(self) -> str:
        """Generate unique session ID"""
        return secrets.token_hex(32)  # 64 character hex string
    
    def generate_auth_token(self) -> str:
        """Generate secure authentication token"""
        return secrets.token_urlsafe(32)
    
    def save_session(self, session: Session) -> bool:
        """
        Save session to disk with encryption.
        
        Args:
            session: Session object to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            session_file = self.storage_path / f"{session.session_id}.json"
            
            # Convert to dict and encrypt sensitive data
            session_dict = asdict(session)
            session_dict['auth_token'] = self._encrypt(session.auth_token)
            
            # Write to file
            with open(session_file, 'w') as f:
                json.dump(session_dict, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"[SessionStore] Error saving session: {e}")
            return False
    
    def load_session(self, session_id: str) -> Optional[Session]:
        """
        Load session from disk.
        
        Args:
            session_id: Session ID to load
            
        Returns:
            Session object if found and valid, None otherwise
        """
        try:
            session_file = self.storage_path / f"{session_id}.json"
            
            if not session_file.exists():
                return None
            
            # Read from file
            with open(session_file, 'r') as f:
                session_dict = json.load(f)
            
            # Decrypt sensitive data
            session_dict['auth_token'] = self._decrypt(session_dict['auth_token'])
            
            # Create Session object
            session = Session(**session_dict)
            
            # Check if expired
            if self._is_expired(session):
                self.delete_session(session_id)
                return None
            
            return session
            
        except Exception as e:
            print(f"[SessionStore] Error loading session: {e}")
            return None
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete session from disk.
        
        Args:
            session_id: Session ID to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            session_file = self.storage_path / f"{session_id}.json"
            
            if session_file.exists():
                session_file.unlink()
                return True
            
            return False
            
        except Exception as e:
            print(f"[SessionStore] Error deleting session: {e}")
            return False
    
    def list_active_sessions(self) -> List[Session]:
        """
        List all active (non-expired) sessions.
        
        Returns:
            List of active Session objects
        """
        active_sessions = []
        
        for session_file in self.storage_path.glob("*.json"):
            session = self.load_session(session_file.stem)
            if session:  # load_session returns None if expired
                active_sessions.append(session)
        
        return active_sessions
    
    def cleanup_expired(self) -> int:
        """
        Remove all expired sessions.
        
        Returns:
            Number of sessions cleaned up
        """
        count = 0
        
        for session_file in self.storage_path.glob("*.json"):
            session = self.load_session(session_file.stem)
            if session is None:  # Expired sessions return None
                count += 1
        
        return count
    
    def update_last_active(self, session_id: str) -> bool:
        """
        Update last active timestamp for session.
        
        Args:
            session_id: Session ID to update
            
        Returns:
            True if successful, False otherwise
        """
        session = self.load_session(session_id)
        if session:
            session.last_active = datetime.now().isoformat()
            return self.save_session(session)
        return False
    
    def validate_token(self, session_id: str, auth_token: str) -> bool:
        """
        Validate authentication token for session.
        
        Args:
            session_id: Session ID
            auth_token: Token to validate
            
        Returns:
            True if valid, False otherwise
        """
        session = self.load_session(session_id)
        if session and session.auth_token == auth_token:
            self.update_last_active(session_id)
            return True
        return False
    
    def _encrypt(self, data: str) -> str:
        """Encrypt string data"""
        return self.cipher.encrypt(data.encode()).decode()
    
    def _decrypt(self, encrypted_data: str) -> str:
        """Decrypt string data"""
        return self.cipher.decrypt(encrypted_data.encode()).decode()
    
    def _is_expired(self, session: Session) -> bool:
        """Check if session is expired"""
        expires_at = datetime.fromisoformat(session.expires_at)
        return datetime.now() > expires_at
    
    def create_session(self, device_id: str, device_name: str, 
                      channel_type: str, metadata: Dict[str, Any] = None) -> Session:
        """
        Create new session.
        
        Args:
            device_id: Unique device identifier
            device_name: Human-readable device name
            channel_type: Type of channel (web, telegram, whatsapp, etc.)
            metadata: Additional metadata
            
        Returns:
            New Session object
        """
        now = datetime.now()
        expires_at = now + timedelta(hours=self.expiry_hours)
        
        session = Session(
            session_id=self.generate_session_id(),
            device_id=device_id,
            device_name=device_name,
            channel_type=channel_type,
            auth_token=self.generate_auth_token(),
            metadata=metadata or {},
            created_at=now.isoformat(),
            expires_at=expires_at.isoformat(),
            last_active=now.isoformat()
        )
        
        self.save_session(session)
        return session
