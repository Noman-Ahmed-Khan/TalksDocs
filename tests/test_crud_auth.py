import pytest
from datetime import datetime, timedelta
from app.db import crud, models
from app.schemas import user as user_schema

def test_create_user_crud(db):
    user_in = user_schema.UserCreate(email="crud@example.com", password="Password123!")
    user = crud.create_user(db, user=user_in)
    assert user.email == "crud@example.com"
    assert user.hashed_password != "Password123!"

def test_get_user_by_email_crud(db):
    email = "get@example.com"
    user_in = user_schema.UserCreate(email=email, password="Password123!")
    crud.create_user(db, user=user_in)
    
    user = crud.get_user_by_email(db, email=email)
    assert user is not None
    assert user.email == email

def test_failed_login_locking_crud(db):
    email = "lock@example.com"
    user_in = user_schema.UserCreate(email=email, password="Password123!")
    user = crud.create_user(db, user=user_in)
    
    # Simulate failed logins
    from app.settings import settings
    for _ in range(settings.MAX_LOGIN_ATTEMPTS):
        crud.increment_failed_login(db, user)
    
    assert crud.is_user_locked(user) is True
    assert user.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS

def test_reset_failed_login_crud(db):
    email = "reset_lock@example.com"
    user_in = user_schema.UserCreate(email=email, password="Password123!")
    user = crud.create_user(db, user=user_in)
    
    crud.increment_failed_login(db, user)
    assert user.failed_login_attempts == 1
    
    crud.reset_failed_login(db, user)
    assert user.failed_login_attempts == 0
    assert user.locked_until is None

def test_refresh_token_crud(db):
    user_in = user_schema.UserCreate(email="token@example.com", password="Password123!")
    user = crud.create_user(db, user=user_in)
    
    token_str = "test_refresh_token"
    expires = datetime.utcnow() + timedelta(days=1)
    
    db_token = crud.create_refresh_token(db, user_id=user.id, token=token_str, expires_at=expires)
    assert db_token.token == token_str
    assert db_token.user_id == user.id
    
    retrieved = crud.get_refresh_token(db, token=token_str)
    assert retrieved.id == db_token.id
    
    crud.revoke_refresh_token(db, db_token)
    assert db_token.is_revoked is True

def test_update_user_crud(db):
    user_in = user_schema.UserCreate(email="update@example.com", password="Password123!")
    user = crud.create_user(db, user=user_in)
    
    update_data = user_schema.UserUpdate(email="updated@example.com")
    updated_user = crud.update_user(db, db_user=user, user_update=update_data)
    assert updated_user.email == "updated@example.com"

def test_update_user_password_crud(db):
    user_in = user_schema.UserCreate(email="pwd_update@example.com", password="Password123!")
    user = crud.create_user(db, user=user_in)
    old_hash = user.hashed_password
    
    crud.update_user_password(db, user_id=user.id, new_password="newPassword123!")
    db.refresh(user)
    assert user.hashed_password != old_hash

def test_deactivate_activate_user_crud(db):
    user_in = user_schema.UserCreate(email="active@example.com", password="Password123!")
    user = crud.create_user(db, user=user_in)
    assert user.is_active is True
    
    crud.deactivate_user(db, user_id=user.id)
    db.refresh(user)
    assert user.is_active is False
    
    crud.activate_user(db, user_id=user.id)
    db.refresh(user)
    assert user.is_active is True

def test_delete_user_crud(db):
    user_in = user_schema.UserCreate(email="delete@example.com", password="Password123!")
    user = crud.create_user(db, user=user_in)
    user_id = user.id
    
    crud.delete_user(db, db_user=user)
    assert crud.get_user(db, user_id=user_id) is None

def test_cleanup_deactivated_users_crud(db):
    user_in = user_schema.UserCreate(email="cleanup@example.com", password="Password123!")
    user = crud.create_user(db, user=user_in)
    
    # Manually set deactivated_at to 31 days ago
    from datetime import timezone
    user.is_active = False
    user.deactivated_at = datetime.now(timezone.utc) - timedelta(days=31)
    db.commit()
    
    count = crud.cleanup_deactivated_users(db)
    assert count == 1
    assert crud.get_user_by_email(db, email="cleanup@example.com") is None

def test_revoke_token_family_crud(db):
    user_in = user_schema.UserCreate(email="family@example.com", password="Password123!")
    user = crud.create_user(db, user=user_in)
    
    import uuid
    family_id = uuid.uuid4()
    crud.create_refresh_token(db, user_id=user.id, token="t1", expires_at=datetime.utcnow() + timedelta(days=1), family_id=family_id)
    crud.create_refresh_token(db, user_id=user.id, token="t2", expires_at=datetime.utcnow() + timedelta(days=1), family_id=family_id)
    
    count = crud.revoke_token_family(db, family_id=family_id)
    assert count == 2

def test_get_user_active_sessions_crud(db):
    user_in = user_schema.UserCreate(email="sessions_crud@example.com", password="Password123!")
    user = crud.create_user(db, user=user_in)
    
    crud.create_refresh_token(db, user_id=user.id, token="t1", expires_at=datetime.utcnow() + timedelta(days=1))
    
    sessions = crud.get_user_active_sessions(db, user_id=user.id)
    assert len(sessions) == 1

def test_verification_token_crud(db):
    user_in = user_schema.UserCreate(email="verify_crud@example.com", password="Password123!")
    user = crud.create_user(db, user=user_in)
    
    token = crud.create_verification_token(db, user_id=user.id)
    assert token.user_id == user.id
    
    retrieved = crud.get_verification_token(db, token=token.token)
    assert retrieved.id == token.id
    
    crud.use_verification_token(db, token)
    assert token.is_used is True

def test_password_reset_token_crud(db):
    user_in = user_schema.UserCreate(email="reset_crud@example.com", password="Password123!")
    user = crud.create_user(db, user=user_in)
    
    token = crud.create_password_reset_token(db, user_id=user.id)
    assert token.user_id == user.id
    
    retrieved = crud.get_password_reset_token(db, token=token.token)
    assert retrieved.id == token.id
    
    crud.use_password_reset_token(db, token)
    assert token.is_used is True
