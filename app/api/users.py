import os
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.dependencies import get_current_user, get_current_active_user, get_current_verified_user
from app.db import models, crud
from app.db.session import get_db
from app.schemas import user as user_schema
from app.utils import hashing, email as email_utils

router = APIRouter()


@router.get("/me", response_model=user_schema.UserProfile)
async def get_current_user_profile(
    current_user: models.User = Depends(get_current_active_user)
):
    """Get the current user's profile."""
    return current_user


@router.patch("/me", response_model=user_schema.User)
async def update_user_profile(
    user_update: user_schema.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_verified_user)
):
    """Update the current user's profile (except email and password)."""
    if user_update.email:
        raise HTTPException(
            status_code=400,
            detail="Use the /auth/change-email endpoint to change email"
        )
    
    updated_user = crud.update_user(db, current_user, user_update)
    return updated_user


@router.post("/me/deactivate")
async def deactivate_account(
    password_confirm: user_schema.DeleteAccountRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Deactivate the current user's account.
    
    This is a soft delete - the account can be reactivated by admin.
    """
    # Verify password
    if not hashing.verify_password(password_confirm.password, current_user.hashed_password):
        raise HTTPException(
            status_code=400,
            detail="Incorrect password"
        )
    
    # Revoke all sessions
    crud.revoke_all_user_tokens(db, current_user.id)
    
    # Deactivate account
    crud.deactivate_user(db, current_user.id)
    
    return {"message": "Account deactivated successfully"}


@router.post("/me/activate")
async def activate_account(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Reactivate the current user's account.
    """
    if current_user.is_active:
        return {"message": "Account is already active"}
    
    crud.activate_user(db, current_user.id)
    
    return {"message": "Account reactivated successfully"}


@router.delete("/me")
async def delete_account(
    password_confirm: user_schema.DeleteAccountRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Permanently delete the current user's account and all associated data.
    
    This action is irreversible.
    """
    # Verify password
    if not hashing.verify_password(password_confirm.password, current_user.hashed_password):
        raise HTTPException(
            status_code=400,
            detail="Incorrect password"
        )
    
    # Verify confirmation
    if password_confirm.confirmation != "DELETE":
        raise HTTPException(
            status_code=400,
            detail="Please type 'DELETE' to confirm account deletion"
        )
    
    # Store email before deletion for notification
    user_email = current_user.email
    
    # Delete user (cascades to projects, documents, tokens, and deletes files)
    crud.delete_user(db, current_user)
    
    # Send confirmation email
    background_tasks.add_task(
        email_utils.send_account_deleted_email,
        user_email
    )
    
    return {"message": "Account and all associated data deleted successfully"}


@router.get("/me/security-info")
async def get_security_info(
    current_user: models.User = Depends(get_current_active_user)
):
    """Get security-related information for the current user."""
    return {
        "email": current_user.email,
        "is_verified": current_user.is_verified,
        "password_changed_at": current_user.password_changed_at,
        "last_login_at": current_user.last_login_at,
        "created_at": current_user.created_at,
        "failed_login_attempts": current_user.failed_login_attempts,
        "is_locked": crud.is_user_locked(current_user)
    }