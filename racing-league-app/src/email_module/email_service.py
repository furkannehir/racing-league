from mailersend import MailerSendClient, EmailRequest, EmailContact
from src.config.config import Config
from src.auth_module.auth_service import AuthService
import logging

email_client = MailerSendClient(api_key=Config.MAILER_SENDER_API_KEY, timeout=10, max_retries=0)
logger = logging.getLogger(__name__)

class EmailService:
    
    @staticmethod
    def send_email(to_email: EmailContact, subject: str, text: str|None = None, html: str|None = None, template_id: str|None = None, variables: dict|None = None):
        sender = EmailContact(email=Config.SENDER_EMAIL, name=Config.SENDER_NAME)
        email_request = EmailRequest(
            from_email=sender,
            to=[to_email],
            subject=subject,
            text=text,
            html=html,
            template_id=template_id,
            personalization=[{"email": to_email.email, "data": variables}] if variables else None
        )
        try:
            response = email_client.emails.send(email_request)
            return response
        except Exception:
            logger.warning("Email provider request failed")
            return None

    @staticmethod
    def send_verification_email(to_email: str, name: str):
        url = AuthService.generate_verification_link(to_email)
        subject = "Please verify your email address"
        template_id = Config.EMAIL_TEMPLATE_ID
        variables = {
            "name": name,
            "url": url,
            "message_top": "Click the button below to verify your email.",
            "message_bottom": "If you experience any issues with the button, you can verify your email using the link below.",
            "button_name": "Verify my email"
        }
        return EmailService.send_email(
            to_email= EmailContact(email=to_email, name=name),
            subject=subject,
            template_id=template_id,
            variables=variables
        )

    @staticmethod
    def send_reset_password_email(to_email: str, name: str):
        url = AuthService.generate_reset_password_link(to_email)
        subject = "Password Reset Request"
        template_id = Config.EMAIL_TEMPLATE_ID
        variables = {
            "name": name,
            "url": url,
            "message_header": "Forgot your password?",
            "message_top": "It happens to the best of us, don’t worry! Click the button below to reset your password.",
            "message_bottom": "If you experience any issues with the button, you can reset your password using the link below.",
            "button_name": "Reset my password"
        }
        return EmailService.send_email(
            to_email=EmailContact(email=to_email, name=name),
            subject=subject,
            template_id=template_id,
            variables=variables
        )

    @staticmethod
    def send_custom_email(to_email: str, name: str, subject: str, message_top: str, message_bottom: str, button_name: str, url: str):
        template_id = Config.EMAIL_TEMPLATE_ID
        variables = {
            "name": name,
            "url": url,
            "message_top": message_top,
            "message_bottom": message_bottom,
            "button_name": button_name
        }
        return EmailService.send_email(
            to_email=EmailContact(email=to_email, name=name),
            subject=subject,
            template_id=template_id,
            variables=variables
        )
