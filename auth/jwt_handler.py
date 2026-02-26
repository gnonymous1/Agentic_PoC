"""
Authentication and Authorization System for AgentOS
Implements JWT-based authentication and RBAC
"""

from datetime import datetime, timedelta
from typing import Optional, List
from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from enum import Enum

from sqlalchemy.orm import Session
from database.models import User as UserModel
from database import get_db

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


class UserRole(str, Enum):
    """User roles for RBAC"""
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class Permission(str, Enum):
    """System permissions"""
    # Synthesis
    CREATE_PLAN = "synthesis:create"
    EXECUTE_PLAN = "synthesis:execute"
    VIEW_PLAN = "synthesis:view"
    CANCEL_PLAN = "synthesis:cancel"
    
    # Self-Evolution
    ANALYZE_CODE = "evolution:analyze"
    PROPOSE_MODIFICATION = "evolution:propose"
    APPLY_MODIFICATION = "evolution:apply"
    ROLLBACK_MODIFICATION = "evolution:rollback"
    CREATE_TOOL = "evolution:create_tool"
    
    # Memory
    READ_MEMORY = "memory:read"
    WRITE_MEMORY = "memory:write"
    CONSOLIDATE_MEMORY = "memory:consolidate"
    WIPE_MEMORY = "memory:wipe"
    
    # System
    VIEW_METRICS = "system:view_metrics"
    VIEW_LOGS = "system:view_logs"
    MANAGE_USERS = "system:manage_users"
    CONFIGURE_SYSTEM = "system:configure"


# Role-Permission mapping
ROLE_PERMISSIONS = {
    UserRole.ADMIN: list(Permission),  # All permissions
    UserRole.USER: [
        Permission.CREATE_PLAN,
        Permission.EXECUTE_PLAN,
        Permission.VIEW_PLAN,
        Permission.CANCEL_PLAN,
        Permission.ANALYZE_CODE,
        Permission.PROPOSE_MODIFICATION,
        Permission.READ_MEMORY,
        Permission.WRITE_MEMORY,
        Permission.CONSOLIDATE_MEMORY,
        Permission.VIEW_METRICS,
        Permission.VIEW_LOGS,
    ],
    UserRole.VIEWER: [
        Permission.VIEW_PLAN,
        Permission.READ_MEMORY,
        Permission.VIEW_METRICS,
        Permission.VIEW_LOGS,
    ]
}


class User(BaseModel):
    """User model"""
    id: str
    email: EmailStr
    username: str
    role: UserRole = UserRole.USER
    is_active: bool = True
    created_at: datetime
    last_login: Optional[datetime] = None


class UserCreate(BaseModel):
    """User creation schema"""
    email: EmailStr
    username: str
    password: str
    role: UserRole = UserRole.USER


class UserInDB(User):
    """User model with password hash"""
    password_hash: str


class Token(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """JWT token payload"""
    user_id: str
    username: str
    role: UserRole
    exp: datetime


class AuthService:
    """Authentication service"""
    
    def __init__(self, secret_key: str, algorithm: str = "HS256", 
                 token_expire_minutes: int = 30):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.token_expire_minutes = token_expire_minutes
    
    def hash_password(self, password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    def create_access_token(self, user: User) -> Token:
        """Create JWT access token"""
        expires_delta = timedelta(minutes=self.token_expire_minutes)
        expire = datetime.utcnow() + expires_delta
        
        role_value = user.role.value if hasattr(user.role, "value") else user.role

        to_encode = {
            "user_id": user.id,
            "username": user.username,
            "role": role_value,
            "exp": expire
        }
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        
        return Token(
            access_token=encoded_jwt,
            expires_in=int(expires_delta.total_seconds())
        )
    
    def verify_token(self, token: str) -> Optional[TokenData]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            user_id: str = payload.get("user_id")
            username: str = payload.get("username")
            role: str = payload.get("role")
            exp: datetime = datetime.fromtimestamp(payload.get("exp"))
            
            if user_id is None or username is None:
                return None
            
            return TokenData(
                user_id=user_id,
                username=username,
                role=UserRole(role),
                exp=exp
            )
        except JWTError:
            return None
    
    def authenticate_user(self, db: Session, username: str, password: str) -> Optional[UserModel]:
        """Authenticate user with database"""
        user = db.query(UserModel).filter(UserModel.username == username).first()
        if not user:
            return None
        if not self.verify_password(password, user.password_hash):
            return None
        return user


class AuthorizationService:
    """Authorization service for RBAC"""
    
    @staticmethod
    def has_permission(user: User, permission: Permission) -> bool:
        """Check if user has a specific permission"""
        role_permissions = ROLE_PERMISSIONS.get(user.role, [])
        return permission in role_permissions
    
    @staticmethod
    def has_any_permission(user: User, permissions: List[Permission]) -> bool:
        """Check if user has any of the specified permissions"""
        return any(AuthorizationService.has_permission(user, p) for p in permissions)
    
    @staticmethod
    def has_all_permissions(user: User, permissions: List[Permission]) -> bool:
        """Check if user has all of the specified permissions"""
        return all(AuthorizationService.has_permission(user, p) for p in permissions)
    
    @staticmethod
    def require_permission(user: User, permission: Permission):
        """Raise exception if user doesn't have permission"""
        if not AuthorizationService.has_permission(user, permission):
            raise PermissionError(
                f"User {user.username} does not have permission: {permission.value}"
            )
    
    @staticmethod
    def get_user_permissions(user: User) -> List[Permission]:
        """Get all permissions for a user"""
        return ROLE_PERMISSIONS.get(user.role, [])


# Helper dependency
def get_current_user(token: str, auth_service: AuthService, db: Session = None) -> Optional[User]:
    """Get current user from JWT token"""
    token_data = auth_service.verify_token(token)
    if token_data is None:
        return None
    
    # In a real dependency injection scenario, db would be passed
    # For now, we'll create a new session if not provided (not ideal but works for this helper)
    if db is None:
        from database import SessionLocal
        db = SessionLocal()
        try:
            user = db.query(UserModel).filter(UserModel.username == token_data.username).first()
        finally:
            db.close()
    else:
        user = db.query(UserModel).filter(UserModel.username == token_data.username).first()
        
    if user is None:
        return None
    
    return User(
        id=user.id,
        email=user.email,
        username=user.username,
        role=UserRole(user.role),
        is_active=user.is_active,
        created_at=user.created_at,
        last_login=user.last_login
    )
