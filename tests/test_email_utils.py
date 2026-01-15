import pytest
from unittest.mock import patch, MagicMock
from app.utils.email import EmailService

def test_email_service_send_email():
    with patch("smtplib.SMTP") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server
        
        service = EmailService()
        service.use_ssl = False  # Ensure it uses SMTP instead of SMTP_SSL for this test
        service.smtp_user = "test@example.com"
        service.smtp_password = "password"
        
        success = service.send_email(
            to_email="recipient@example.com",
            subject="Test Subject",
            html_content="<h1>Test</h1>"
        )
        
        assert success is True
        assert mock_smtp.called
        assert mock_server.login.called
        assert mock_server.send_message.called
        assert mock_server.quit.called

def test_email_service_send_email_failure():
    with patch("smtplib.SMTP") as mock_smtp:
        mock_smtp.side_effect = Exception("SMTP Error")
        
        service = EmailService()
        service.use_ssl = False
        
        success = service.send_email(
            to_email="recipient@example.com",
            subject="Test Subject",
            html_content="<h1>Test</h1>"
        )
        
        assert success is False
