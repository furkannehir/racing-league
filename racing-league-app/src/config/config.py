# project/src/config/config.py
import firebase_admin
from firebase_admin import credentials
from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')
    FIREBASE_API_KEY = os.getenv('FIREBASE_API_KEY')
    FIREBASE_URL = os.getenv('FIREBASE_URL')
    MONGO_URI = os.getenv('MONGO_URI')
    ENV = os.getenv('ENV')
    ORIGINS = os.getenv('ORIGINS').split(',')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    MAX_CONTENT_LENGTH = 13 * 1024 * 1024
    AI_IMAGE_USER_HOURLY_LIMIT = max(0, int(os.getenv('AI_IMAGE_USER_HOURLY_LIMIT', '10')))
    AI_IMAGE_USER_DAILY_LIMIT = max(0, int(os.getenv('AI_IMAGE_USER_DAILY_LIMIT', '30')))
    AI_IMAGE_GLOBAL_DAILY_LIMIT = max(0, int(os.getenv('AI_IMAGE_GLOBAL_DAILY_LIMIT', '100')))
    MONGO_DB_NAME = os.getenv('MONGO_DB_NAME', 'racing_league')
    SENDER_EMAIL = os.getenv('SENDER_EMAIL')
    SENDER_NAME = os.getenv('SENDER_NAME')
    MAILER_SENDER_API_KEY = os.getenv('MAILER_SENDER_API_KEY')
    EMAIL_TEMPLATE_ID = os.getenv('EMAIL_TEMPLATE_ID')
    FRONTEND_URL = os.getenv('FRONTEND_URL')
    INVITATION_EMAIL_WORKER_ENABLED = os.getenv('INVITATION_EMAIL_WORKER_ENABLED', 'true').lower() in ('true', '1', 'yes')
    ACCOUNT_EMAIL_WORKER_ENABLED = os.getenv('ACCOUNT_EMAIL_WORKER_ENABLED', 'true').lower() in ('true', '1', 'yes')
    ACCOUNT_REQUEST_IP_LIMIT = max(0, int(os.getenv('ACCOUNT_REQUEST_IP_LIMIT', '30')))
    ACCOUNT_REQUEST_GLOBAL_HOURLY_LIMIT = max(0, int(os.getenv('ACCOUNT_REQUEST_GLOBAL_HOURLY_LIMIT', '300')))
    ACCOUNT_REQUEST_GLOBAL_DAILY_LIMIT = max(0, int(os.getenv('ACCOUNT_REQUEST_GLOBAL_DAILY_LIMIT', '1000')))
    ACCOUNT_DELIVERY_HOURLY_LIMIT = max(0, int(os.getenv('ACCOUNT_DELIVERY_HOURLY_LIMIT', '100')))
    ACCOUNT_DELIVERY_DAILY_LIMIT = max(0, int(os.getenv('ACCOUNT_DELIVERY_DAILY_LIMIT', '500')))
    TRUSTED_PROXY_HOPS = max(0, int(os.getenv('TRUSTED_PROXY_HOPS', '0')))

    @staticmethod
    def init_firebase():
        if os.getenv('ENV') == 'development':
            path = './serviceAccountKey.json'
        else:
            path = '/etc/secrets/serviceAccountKey.json'
        cred = credentials.Certificate(path)
        firebase_admin.initialize_app(cred, options={"httpTimeout": 10})
