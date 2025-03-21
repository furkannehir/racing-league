# project/src/auth_module/auth_service.py
from firebase_admin import auth
from flask import session, request, jsonify
import requests
from src.config.config import Config
from functools import wraps


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"message": "Missing or invalid token"}), 401

        token = auth_header.split(' ')[1]
        try:
            decoded_token = auth.verify_id_token(token)
            # Store uid in request context for the route to use
            request.uid = decoded_token['user_id']
            return f(*args, **kwargs)
        except Exception as e:
            if str(e).startswith('Invalid token'):
                return jsonify({"message": "Invalid token"}), 401
            else:
                return jsonify({"message": str(e)}), 500

    return decorated_function

class AuthService:
    
    @staticmethod
    def verify_id_token(id_token):
        """Verify Firebase ID token"""
        try:
            decoded_token = auth.verify_id_token(id_token)
            return decoded_token['user_id']
        except Exception as e:
            return None

    @staticmethod
    def login_user(email, password):
        """Login a user by verifying their credentials using Firebase"""
        # Use Firebase's REST API to authenticate the user
        api_key = Config.FIREBASE_API_KEY
        url = f"{Config.FIREBASE_URL}/v1/accounts:signInWithPassword?key={api_key}"

        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }

        response = requests.post(url, json=payload)

        if response.status_code == 200:
            id_token = response.json().get("idToken")
            user_id = response.json().get("localId")
            return id_token, user_id  # Return the ID token and user ID
        else:
            return None, None
        
    @staticmethod
    def create_session(user_id):
        """Create a user session"""
        session['user'] = user_id
        
    @staticmethod
    def logout_user():
        session.pop('user', None)

    @staticmethod
    def get_current_user():
        """Get current user from the token in Authorization header"""
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return None

        token = auth_header.split(' ')[1]
        try:
            decoded_token = auth.verify_id_token(token)
            return decoded_token['user_id']
        except:
            return None

    @staticmethod
    def register_user(email, password):
        try:
            user = auth.create_user(
                email=email,
                password=password
            )
            return user
        except Exception as e:
            return str(e)