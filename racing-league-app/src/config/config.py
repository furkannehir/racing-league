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

    @staticmethod
    def init_firebase():
        if os.getenv('ENV') == 'development':
            path = './serviceAccountKey.json'
        else:
            path = '/etc/secrets/serviceAccountKey.json'
        cred = credentials.Certificate(path)
        firebase_admin.initialize_app(cred)
