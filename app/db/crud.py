from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from uuid import UUID
import secrets
import os

from app.db import models
from app.schemas import user as user_schema
from app.schemas import project as project_schema
from app.utils.hashing import get_password_hash
from app.settings import settings


# ============== User CRUD ==============

def get_user(db: Session, user_id: UUID) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.email == email).first()


def create_user(db: Session, user: user_schema.UserCreate) -> models.User:
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        email=user.email,
        hashed_password=hashed_password,
        is_verified=not settings.REQUIRE_EMAIL_VERIFICATION
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(db: Session, db_user: models.User, user_update: user_schema.UserUpdate) -> models.User:
    update_data = user_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_user, field, value)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user_password(
    db: Session,
    user_id: UUID,
    new_password: str
) -> models.User:
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    
    if not db_user:
        raise ValueError("User not found")

    db_user.hashed_password = get_password_hash(new_password)
    db_user.password_changed_at = datetime.utcnow()

    db.commit()
    db.refresh(db_user)
    return db_user

def verify_user_email(db: Session, db_user: models.User) -> models.User:
    db_user.is_verified = True
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user_email(db: Session, db_user: models.User, new_email: str) -> models.User:
    db_user.email = new_email
    db_user.is_verified = True
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def deactivate_user(db: Session, user_id: UUID) -> models.User:
    db_user = (
        db.query(models.User)
        .filter(models.User.id == user_id)
        .first()
    )

    if not db_user:
        raise ValueError("User not found")

    db_user.is_active = False
    db_user.deactivated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(db_user)
    return db_user


def activate_user(db: Session, user_id: UUID) -> models.User:
    db_user = (
        db.query(models.User)
        .filter(models.User.id == user_id)
        .first()
    )

    if not db_user:
        raise ValueError("User not found")

    db_user.is_active = True
    db_user.deactivated_at = None
    db.commit()
    db.refresh(db_user)
    return db_user


def delete_user(db: Session, db_user: models.User) -> None:
    # Delete associated files
    for project in db_user.projects:
        for doc in project.documents:
            if os.path.exists(doc.file_path):
                try:
                    os.remove(doc.file_path)
                except Exception:
                    pass
    
    db.delete(db_user)
    db.commit()


def cleanup_deactivated_users(db: Session) -> int:
    """Permanently delete users deactivated for more than 30 days."""
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    
    expired_users = (
        db.query(models.User)
        .filter(
            models.User.is_active == False,
            models.User.deactivated_at <= thirty_days_ago
        )
        .all()
    )
    
    count = 0
    for user in expired_users:
        delete_user(db, user)
        count += 1
    
    return count


def increment_failed_login(db: Session, db_user: models.User) -> models.User:
    db_user.failed_login_attempts += 1
    if db_user.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
        db_user.locked_until = datetime.utcnow() + timedelta(minutes=settings.LOCKOUT_DURATION_MINUTES)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def reset_failed_login(db: Session, db_user: models.User) -> models.User:
    db_user.failed_login_attempts = 0
    db_user.locked_until = None
    db_user.last_login_at = datetime.utcnow()
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def is_user_locked(db_user: models.User) -> bool:
    if db_user.locked_until is None:
        return False
    return datetime.utcnow() < db_user.locked_until


# ============== Refresh Token CRUD ==============

def create_refresh_token(
    db: Session,
    user_id: UUID,
    token: str,
    expires_at: datetime,
    device_info: Optional[str] = None,
    ip_address: Optional[str] = None,
    family_id: Optional[UUID] = None
) -> models.RefreshToken:
    import uuid as uuid_module
    db_token = models.RefreshToken(
        token=token,
        user_id=user_id,
        expires_at=expires_at,
        device_info=device_info,
        ip_address=ip_address,
        family_id=family_id or uuid_module.uuid4()
    )
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    return db_token


def get_refresh_token(db: Session, token: str) -> Optional[models.RefreshToken]:
    return db.query(models.RefreshToken).filter(
        models.RefreshToken.token == token
    ).first()


def get_active_refresh_token(db: Session, token: str) -> Optional[models.RefreshToken]:
    return db.query(models.RefreshToken).filter(
        and_(
            models.RefreshToken.token == token,
            models.RefreshToken.is_revoked == False,
            models.RefreshToken.expires_at > datetime.utcnow()
        )
    ).first()


def revoke_refresh_token(
    db: Session, 
    db_token: models.RefreshToken, 
    replaced_by: Optional[UUID] = None
) -> models.RefreshToken:
    db_token.is_revoked = True
    db_token.revoked_at = datetime.utcnow()
    db_token.replaced_by = replaced_by
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    return db_token


def revoke_token_family(db: Session, family_id: UUID) -> int:
    """Revoke all tokens in a family (used for refresh token reuse detection)"""
    result = db.query(models.RefreshToken).filter(
        and_(
            models.RefreshToken.family_id == family_id,
            models.RefreshToken.is_revoked == False
        )
    ).update({
        "is_revoked": True,
        "revoked_at": datetime.utcnow()
    })
    db.commit()
    return result


def revoke_all_user_tokens(db: Session, user_id: UUID) -> int:
    """Revoke all refresh tokens for a user"""
    result = db.query(models.RefreshToken).filter(
        and_(
            models.RefreshToken.user_id == user_id,
            models.RefreshToken.is_revoked == False
        )
    ).update({
        "is_revoked": True,
        "revoked_at": datetime.utcnow()
    })
    db.commit()
    return result


def get_user_active_sessions(db: Session, user_id: UUID) -> List[models.RefreshToken]:
    """Get all active sessions for a user"""
    return db.query(models.RefreshToken).filter(
        and_(
            models.RefreshToken.user_id == user_id,
            models.RefreshToken.is_revoked == False,
            models.RefreshToken.expires_at > datetime.utcnow()
        )
    ).order_by(models.RefreshToken.created_at.desc()).all()


def cleanup_expired_tokens(db: Session) -> int:
    """Clean up expired tokens (run periodically via background task/cron)"""
    result = db.query(models.RefreshToken).filter(
        models.RefreshToken.expires_at < datetime.utcnow()
    ).delete()
    db.commit()
    return result


# ============== Verification Token CRUD ==============

def create_verification_token(
    db: Session,
    user_id: UUID,
    token_type: str = "email_verification",
    new_email: Optional[str] = None
) -> models.VerificationToken:
    # Invalidate any existing verification tokens for this user and type
    db.query(models.VerificationToken).filter(
        and_(
            models.VerificationToken.user_id == user_id,
            models.VerificationToken.token_type == token_type,
            models.VerificationToken.is_used == False
        )
    ).update({"is_used": True})
    
    expires_at = datetime.utcnow() + timedelta(hours=settings.VERIFICATION_TOKEN_EXPIRE_HOURS)
    db_token = models.VerificationToken(
        user_id=user_id,
        token=secrets.token_urlsafe(32),
        token_type=token_type,
        new_email=new_email,
        expires_at=expires_at
    )
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    return db_token


def get_verification_token(db: Session, token: str) -> Optional[models.VerificationToken]:
    return db.query(models.VerificationToken).filter(
        and_(
            models.VerificationToken.token == token,
            models.VerificationToken.is_used == False,
            models.VerificationToken.expires_at > datetime.utcnow()
        )
    ).first()


def use_verification_token(db: Session, db_token: models.VerificationToken) -> models.VerificationToken:
    db_token.is_used = True
    db_token.used_at = datetime.utcnow()
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    return db_token


# ============== Password Reset Token CRUD ==============

def create_password_reset_token(db: Session, user_id: UUID) -> models.PasswordResetToken:
    # Invalidate any existing password reset tokens for this user
    db.query(models.PasswordResetToken).filter(
        and_(
            models.PasswordResetToken.user_id == user_id,
            models.PasswordResetToken.is_used == False
        )
    ).update({"is_used": True})
    
    expires_at = datetime.utcnow() + timedelta(hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS)
    db_token = models.PasswordResetToken(
        user_id=user_id,
        token=secrets.token_urlsafe(32),
        expires_at=expires_at
    )
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    return db_token


def get_password_reset_token(db: Session, token: str) -> Optional[models.PasswordResetToken]:
    return db.query(models.PasswordResetToken).filter(
        and_(
            models.PasswordResetToken.token == token,
            models.PasswordResetToken.is_used == False,
            models.PasswordResetToken.expires_at > datetime.utcnow()
        )
    ).first()


def use_password_reset_token(db: Session, db_token: models.PasswordResetToken) -> models.PasswordResetToken:
    db_token.is_used = True
    db_token.used_at = datetime.utcnow()
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    return db_token


# ============== Project CRUD (unchanged) ==============

def create_project(db: Session, project: project_schema.ProjectCreate, owner_id: UUID):
    db_project = models.Project(**project.model_dump(), owner_id=owner_id)
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


def get_projects(db: Session, owner_id: UUID):
    return db.query(models.Project).filter(models.Project.owner_id == owner_id).all()


def get_project(db: Session, project_id: UUID, owner_id: UUID):
    return db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.owner_id == owner_id
    ).first()


# ============== Document CRUD (unchanged) ==============

def create_document(db: Session, filename: str, project_id: UUID, file_path: str):
    db_document = models.Document(
        filename=filename,
        project_id=project_id,
        file_path=file_path
    )
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    return db_document


def get_documents_by_project(db: Session, project_id: UUID):
    return db.query(models.Document).filter(models.Document.project_id == project_id).all()