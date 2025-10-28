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
    MONGO_DB_NAME = os.getenv('MONGO_DB_NAME', 'racing_league')
    SENDER_EMAIL = os.getenv('SENDER_EMAIL')
    SENDER_NAME = os.getenv('SENDER_NAME')
    MAILER_SENDER_API_KEY = os.getenv('MAILER_SENDER_API_KEY')
    EMAIL_TEMPLATE_ID = os.getenv('EMAIL_TEMPLATE_ID')

    @staticmethod
    def init_firebase():
        if os.getenv('ENV') == 'development':
            path = './serviceAccountKey.json'
        else:
            path = '/etc/secrets/serviceAccountKey.json'
        cred = credentials.Certificate(path)
        firebase_admin.initialize_app(cred)
