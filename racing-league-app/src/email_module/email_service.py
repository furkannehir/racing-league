from mailersend import MailerSendClient, EmailRequest, EmailContact
from src.config.config import Config
from src.auth_module.auth_service import AuthService

email_client = MailerSendClient(api_key=Config.MAILER_SENDER_API_KEY)

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
            print(f"Email sent successfully: {response}")
            return response
        except Exception as e:
            print(f"Failed to send email: {str(e)}")

    @staticmethod
    def send_verification_email(to_email: str, name: str):
        url = AuthService.generate_verification_link(to_email)
        if "Error" in url:
            print(f"Failed to generate verification link: {url}")
            return
        subject = "Please verify your email address"
        template_id = Config.EMAIL_TEMPLATE_ID
        variables = {
            "name": name,
            "url": url,
            "message_top": "Click the button below to verify your email.",
            "message_bottom": "If you experience any issues with the button, you can verify your email using the link below.",
            "button_name": "Verify my email"
        }
        response = EmailService.send_email(
            to_email= EmailContact(email=to_email, name=name),
            subject=subject,
            template_id=template_id,
            variables=variables
        )

    @staticmethod
    def send_reset_password_email(to_email: str, name: str):
        url = AuthService.generate_reset_password_link(to_email)
        if "Error" in url:
            print(f"Failed to generate verification link: {url}")
            return
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
        EmailService.send_email(
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
        EmailService.send_email(
            to_email=EmailContact(email=to_email, name=name),
            subject=subject,
            template_id=template_id,
            variables=variables
        )