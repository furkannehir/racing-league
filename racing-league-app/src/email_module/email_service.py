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
        except Exception as e:
            print(f"Failed to send email: {str(e)}")

    @staticmethod
    def send_verification_email(to_email: str, name: str):
        verify_email_link = AuthService.generate_verification_link(to_email)
        subject = "Please verify your email address"
        template_id = Config.VERIFICATION_EMAIL_TEMPLATE_ID
        variables = {
            "name": name,
            "verify_email_link": verify_email_link
        }
        EmailService.send_email(
            to_email= EmailContact(email=to_email, name=name),
            subject=subject,
            template_id=template_id,
            variables=variables
        )

    @staticmethod
    def send_reset_password_email(to_email: str, name: str):
        reset_password_link = AuthService.generate_reset_password_link(to_email)
        subject = "Password Reset Request"
        template_id = Config.RESET_PASSWORD_EMAIL_TEMPLATE_ID
        variables = {
            "name": name,
            "reset_password_link": reset_password_link
        }
        EmailService.send_email(
            to_email=EmailContact(email=to_email, name=name),
            subject=subject,
            template_id=template_id,
            variables=variables
        )