import pytest
from datetime import timedelta
from uuid import uuid4
from jose import jwt

from app.utils import hashing, security
from app.settings import settings

def test_password_hashing():
    password = "testpassword123"
    hashed = hashing.get_password_hash(password)
    assert hashed != password
    assert hashing.verify_password(password, hashed) is True
    assert hashing.verify_password("wrongpassword", hashed) is False

def test_password_hashing_truncation():
    # bcrypt truncates at 72 chars, our util does it explicitly
    long_password = "a" * 100
    hashed = hashing.get_password_hash(long_password)
    assert hashing.verify_password("a" * 72, hashed) is True
    assert hashing.verify_password("a" * 100, hashed) is True

def test_create_access_token():
    user_id = uuid4()
    token = security.create_access_token(subject=user_id)
    payload = security.decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"

def test_decode_invalid_access_token():
    assert security.decode_access_token("invalidtoken") is None

def test_create_token_pair():
    user_id = uuid4()
    tokens = security.create_token_pair(user_id)
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"
    
    payload = security.decode_access_token(tokens["access_token"])
    assert payload["sub"] == str(user_id)

def test_generate_secure_token():
    token = security.generate_secure_token()
    assert len(token) >= 32
