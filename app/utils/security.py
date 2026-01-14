from datetime import datetime, timedelta
from typing import Any, Union, Optional, Tuple
from uuid import UUID
import secrets
from jose import jwt, JWTError
from app.settings import settings


def create_access_token(
    subject: Union[str, UUID, Any],
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[dict] = None
) -> str:
    """Create a short-lived access token"""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),  # Convert UUID to string
        "type": "access",
        "iat": datetime.utcnow()
    }
    
    if additional_claims:
        to_encode.update(additional_claims)
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(
    subject: Union[str, UUID, Any],
    expires_delta: Optional[timedelta] = None
) -> Tuple[str, datetime]:
    """Create a long-lived refresh token and return both token and expiry"""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    # Generate a secure random token
    token = secrets.token_urlsafe(32)
    
    return token, expire


def create_token_pair(user_id: UUID) -> dict:
    """Create both access and refresh tokens"""
    access_token = create_access_token(subject=user_id)
    refresh_token, refresh_expires = create_refresh_token(subject=user_id)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "refresh_expires_at": refresh_expires,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate an access token"""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        
        # Verify it's an access token
        if payload.get("type") != "access":
            return None
        
        return payload
    except JWTError:
        return None


def verify_token_not_expired(payload: dict) -> bool:
    """Check if token is not expired"""
    exp = payload.get("exp")
    if exp is None:
        return False
    return datetime.utcnow() < datetime.fromtimestamp(exp)


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure token"""
    return secrets.token_urlsafe(length)