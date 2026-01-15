import pytest
from unittest.mock import patch
from fastapi import status
from app.settings import settings
from app.db import crud

@pytest.fixture
def mock_email():
    with patch("app.utils.email.send_verification_email") as mock_v, \
         patch("app.utils.email.send_password_reset_email") as mock_p, \
         patch("app.utils.email.send_password_changed_email") as mock_c, \
         patch("app.utils.email.send_security_alert_email") as mock_s, \
         patch("app.utils.email.send_email_change_verification") as mock_e:
        yield {
            "verify": mock_v, 
            "reset": mock_p, 
            "changed": mock_c, 
            "alert": mock_s, 
            "email_change": mock_e
        }

def test_register_success(client, mock_email, db):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "Password123!"}
    )
    assert response.status_code == status.HTTP_200_OK
    assert "Registration successful" in response.json()["message"]
    
    # Check if user was created
    user = crud.get_user_by_email(db, email="test@example.com")
    assert user is not None
    assert user.email == "test@example.com"

def test_register_duplicate_email(client, db):
    # Create a user first
    client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "Password123!"}
    )
    
    # Try to register again
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "Password123!"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "already exists" in response.json()["detail"]

def test_login_success(client, db):
    # Register user (verified by default in test if setting is off, 
    # but let's ensure it's verified for the test)
    email = "login_test@example.com"
    password = "Password123!"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password}
    )
    
    user = crud.get_user_by_email(db, email=email)
    user.is_verified = True
    db.add(user)
    db.commit()
    db.refresh(user)

    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

def test_login_invalid_credentials(client, db):
    email = "wrong@example.com"
    password = "Password123!"
    
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Incorrect email or password" in response.json()["detail"]

def test_verify_email(client, db):
    email = "verify@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!"}
    )
    user = crud.get_user_by_email(db, email=email)
    
    # Create verification token
    token_obj = crud.create_verification_token(db, user_id=user.id)
    
    response = client.post(
        "/api/v1/auth/verify-email",
        json={"token": token_obj.token}
    )
    assert response.status_code == status.HTTP_200_OK
    assert "verified successfully" in response.json()["message"]
    
    db.refresh(user)
    assert user.is_verified is True

def test_refresh_token(client, db):
    email = "refresh@example.com"
    password = "Password123!"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password}
    )
    user = crud.get_user_by_email(db, email=email)
    user.is_verified = True
    db.add(user)
    db.commit()
    db.refresh(user)

    login_resp = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password}
    )
    refresh_token = login_resp.json()["refresh_token"]

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token}
    )
    assert response.status_code == status.HTTP_200_OK
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()

def test_logout(client, db):
    email = "logout@example.com"
    password = "Password123!"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password}
    )
    user = crud.get_user_by_email(db, email=email)
    user.is_verified = True
    db.add(user)
    db.commit()
    db.refresh(user)

    login_resp = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password}
    )
    access_token = login_resp.json()["access_token"]
    refresh_token = login_resp.json()["refresh_token"]

    response = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    assert "logged out" in response.json()["message"]

    # Try to refresh with the same token - should fail as it was revoked
    refresh_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token}
    )
    assert refresh_resp.status_code == status.HTTP_401_UNAUTHORIZED

def test_forgot_password(client, mock_email, db):
    email = "forgot@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!"}
    )
    
    response = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": email}
    )
    assert response.status_code == status.HTTP_200_OK
    assert mock_email["reset"].called

def test_reset_password(client, db):
    email = "reset@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!"}
    )
    user = crud.get_user_by_email(db, email=email)
    user.is_verified = True
    db.add(user)
    db.commit()
    db.refresh(user)
    
    reset_token = crud.create_password_reset_token(db, user_id=user.id)
    
    response = client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token.token, "new_password": "newPassword123!"}
    )
    assert response.status_code == status.HTTP_200_OK
    
    # Try login with new password
    login_resp = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "newPassword123!"}
    )
    assert login_resp.status_code == status.HTTP_200_OK

def test_verify_email_get(client, db):
    email = "verify_get@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!"}
    )
    user = crud.get_user_by_email(db, email=email)
    token_obj = crud.create_verification_token(db, user_id=user.id)
    
    response = client.get(f"/api/v1/auth/verify-email?token={token_obj.token}", follow_redirects=False)
    assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert "login" in response.headers["location"]
    
    db.refresh(user)
    assert user.is_verified is True

def test_resend_verification(client, mock_email, db):
    email = "resend@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!"}
    )
    
    response = client.post(
        "/api/v1/auth/resend-verification",
        json={"email": email}
    )
    assert response.status_code == status.HTTP_200_OK
    assert mock_email["verify"].called

def test_logout_all(client, db):
    email = "logout_all@example.com"
    password = "Password123!"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password}
    )
    user = crud.get_user_by_email(db, email=email)
    user.is_verified = True
    db.add(user)
    db.commit()
    db.refresh(user)

    login_resp = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password}
    )
    access_token = login_resp.json()["access_token"]

    response = client.post(
        "/api/v1/auth/logout-all",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    assert "Successfully logged out" in response.json()["message"]

def test_change_password(client, db, mock_email):
    email = "change_pwd@example.com"
    password = "Password123!"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password}
    )
    user = crud.get_user_by_email(db, email=email)
    user.is_verified = True
    db.add(user)
    db.commit()
    db.refresh(user)

    login_resp = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password}
    )
    access_token = login_resp.json()["access_token"]

    response = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": password, "new_password": "newPassword123!"},
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    assert mock_email["changed"].called

def test_change_email(client, db, mock_email):
    email = "old@example.com"
    new_email = "new@example.com"
    password = "Password123!"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password}
    )
    user = crud.get_user_by_email(db, email=email)
    user.is_verified = True
    db.add(user)
    db.commit()
    db.refresh(user)

    login_resp = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password}
    )
    access_token = login_resp.json()["access_token"]

    response = client.post(
        "/api/v1/auth/change-email",
        json={"new_email": new_email, "password": password},
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    assert mock_email["email_change"].called

def test_get_sessions(client, db):
    email = "sessions@example.com"
    password = "Password123!"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password}
    )
    user = crud.get_user_by_email(db, email=email)
    user.is_verified = True
    db.add(user)
    db.commit()
    db.refresh(user)

    login_resp = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password}
    )
    access_token = login_resp.json()["access_token"]

    response = client.get(
        "/api/v1/auth/sessions",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    assert "sessions" in response.json()
    assert len(response.json()["sessions"]) > 0

def test_get_auth_status(client, db):
    email = "status@example.com"
    password = "Password123!"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password}
    )
    user = crud.get_user_by_email(db, email=email)
    user.is_verified = True
    db.add(user)
    db.commit()
    db.refresh(user)

    login_resp = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password}
    )
    access_token = login_resp.json()["access_token"]

    response = client.get(
        "/api/v1/auth/status",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["is_authenticated"] is True
    assert response.json()["email"] == email

def test_login_lockout(client, db):
    email = "lockout_api@example.com"
    password = "Password123!"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password}
    )
    user = crud.get_user_by_email(db, email=email)
    user.is_verified = True
    db.add(user)
    db.commit()
    db.refresh(user)

    # Fail login multiple times
    for _ in range(settings.MAX_LOGIN_ATTEMPTS):
        client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": "wrongpassword"}
        )
    
    # Next attempt should be locked
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password}
    )
    assert response.status_code == status.HTTP_423_LOCKED
    assert "locked" in response.json()["detail"]

def test_refresh_token_reuse_detection(client, db, mock_email):
    email = "reuse@example.com"
    password = "Password123!"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password}
    )
    user = crud.get_user_by_email(db, email=email)
    user.is_verified = True
    db.add(user)
    db.commit()
    db.refresh(user)

    login_resp = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password}
    )
    refresh_token = login_resp.json()["refresh_token"]

    # First refresh - OK
    client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    
    # Second refresh with SAME token - Detection!
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "revoked" in response.json()["detail"]
    assert mock_email["alert"].called
