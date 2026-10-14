# project/src/auth_module/auth_service.py
from dataclasses import dataclass
from firebase_admin import auth, exceptions as firebase_errors
from flask import g, request, jsonify, make_response
import requests
from pymongo.errors import PyMongoError
from src.config.config import Config
from functools import wraps


class AuthError(Exception):
    def __init__(self, message, code, status=401):
        super().__init__(message)
        self.code = code
        self.status = status


@dataclass(frozen=True)
class AuthTokens:
    uid: str
    token: str
    refresh_token: str
    expires_in: int


def auth_error_response(error):
    response = jsonify({"message": str(error), "code": error.code})
    response.headers['Cache-Control'] = 'no-store'
    return response, error.status


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            parts = request.headers.get('Authorization', '').split()
            if len(parts) != 2 or parts[0].lower() != 'bearer':
                raise AuthError("Missing or invalid token", "missing_token")
            g.auth_identity = AuthService.authenticate_token(parts[1])
        except AuthError as error:
            return auth_error_response(error)

        # Route exceptions belong to Flask, not the authentication handler.
        response = make_response(f(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-store'
        return response

    return decorated_function

class AuthService:
    @staticmethod
    def authenticate_token(token):
        """Verify credentials and account state before resolving application identity."""
        from src.user_module.user import User

        try:
            claims = auth.verify_id_token(token, check_revoked=True)
            uid = claims.get('uid') or claims.get('user_id') or claims.get('sub')
            if not isinstance(uid, str) or not uid:
                raise AuthError("Invalid token", "invalid_token")
            firebase_user = auth.get_user(uid)
            if firebase_user.disabled:
                raise AuthError("Your account is disabled", "account_disabled")
            if claims.get('email_verified') is not True or firebase_user.email_verified is not True:
                raise AuthError("Email not verified. Please verify your email.", "email_not_verified")
            user = User.get_user_by_auth_email(firebase_user.email)
            if user is None or (user.firebase_uid is not None and user.firebase_uid != uid):
                raise AuthError("Your application account is unavailable", "account_unavailable")
            return {"uid": uid, "user": user, "firebase_user": firebase_user}
        except auth.ExpiredIdTokenError as exc:
            raise AuthError("Your token has expired", "token_expired") from exc
        except auth.RevokedIdTokenError as exc:
            raise AuthError("Your session has been revoked. Please sign in again.", "token_revoked") from exc
        except auth.UserDisabledError as exc:
            raise AuthError("Your account is disabled", "account_disabled") from exc
        except (auth.InvalidIdTokenError, auth.UserNotFoundError, ValueError) as exc:
            raise AuthError("Invalid token", "invalid_token") from exc
        except (auth.CertificateFetchError, firebase_errors.FirebaseError, PyMongoError,
                requests.RequestException) as exc:
            raise AuthError("Authentication is temporarily unavailable. Please try again.",
                            "auth_unavailable", 503) from exc

    @staticmethod
    def user_payload(identity):
        user = identity['user']
        return {"id": identity['uid'], "mongoId": str(user._id),
                "email": user.email, "name": user.name if isinstance(user.name, str) else ""}

    @staticmethod
    def token_payload(tokens):
        identity = AuthService.authenticate_token(tokens.token)
        if identity['uid'] != tokens.uid:
            raise AuthError("Authentication is temporarily unavailable. Please try again.",
                            "auth_unavailable", 503)
        return {"token": tokens.token, "refreshToken": tokens.refresh_token,
                "expiresIn": tokens.expires_in, "user": AuthService.user_payload(identity)}

    @staticmethod
    def _exchange_tokens(url, payload, refresh=False):
        try:
            response = requests.post(url, **({'data': payload} if refresh else {'json': payload}),
                                     timeout=(5, 10))
            if response.status_code >= 500 or response.status_code == 429:
                raise AuthError("Authentication is temporarily unavailable. Please try again.",
                                "auth_unavailable", 503)
            if response.status_code != 200:
                error_code = response.json().get('error', {}).get('message', '').split(' : ')[0]
                invalid_codes = ({'TOKEN_EXPIRED', 'USER_DISABLED', 'USER_NOT_FOUND', 'INVALID_REFRESH_TOKEN'}
                                 if refresh else {'INVALID_LOGIN_CREDENTIALS', 'INVALID_PASSWORD',
                                                  'EMAIL_NOT_FOUND', 'USER_DISABLED', 'INVALID_EMAIL'})
                if error_code not in invalid_codes:
                    raise AuthError("Authentication is temporarily unavailable. Please try again.",
                                    "auth_unavailable", 503)
                raise AuthError("Your session has expired. Please sign in again." if refresh
                                else "Login failed. Invalid credentials.",
                                "invalid_refresh_token" if refresh else "invalid_credentials")
            data = response.json()
            tokens = AuthTokens(
                uid=data.get('user_id' if refresh else 'localId'),
                token=data.get('id_token' if refresh else 'idToken'),
                refresh_token=data.get('refresh_token' if refresh else 'refreshToken'),
                expires_in=int(data.get('expires_in' if refresh else 'expiresIn', 0)),
            )
            if (not all(isinstance(value, str) and value for value in
                        (tokens.uid, tokens.token, tokens.refresh_token)) or tokens.expires_in <= 0):
                raise ValueError("Incomplete token response")
            return tokens
        except (requests.RequestException, ValueError, TypeError, AttributeError) as exc:
            raise AuthError("Authentication is temporarily unavailable. Please try again.",
                            "auth_unavailable", 503) from exc

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

        return AuthService._exchange_tokens(url, payload)

    @staticmethod
    def refresh_tokens(refresh_token):
        url = f"https://securetoken.googleapis.com/v1/token?key={Config.FIREBASE_API_KEY}"
        return AuthService._exchange_tokens(url, {
            "grant_type": "refresh_token", "refresh_token": refresh_token,
        }, refresh=True)

    @staticmethod
    def check_email_verified(user_email):
        user = auth.get_user_by_email(user_email)
        if user.email_verified:
            return True
        return False
    
    @staticmethod
    def generate_verification_link(email):
        """Generate email verification link"""
        return auth.generate_email_verification_link(email)

    @staticmethod
    def generate_reset_password_link(email):
        """Generate password reset link"""
        return auth.generate_password_reset_link(email)

    @staticmethod
    def get_current_user():
        identity = getattr(g, 'auth_identity', None)
        return identity['uid'] if identity else None

    @staticmethod
    def get_current_mongo_user():
        """Use the application identity already verified for this request."""
        identity = getattr(g, 'auth_identity', None)
        return identity['user'] if identity else None

    @staticmethod
    def get_current_firebase_user():
        identity = getattr(g, 'auth_identity', None)
        return identity['firebase_user'] if identity else None

    @staticmethod
    def resolve_firebase_uid(firebase_uid):
        """
        Resolve a Firebase UID to a MongoDB user via email.
        Useful for stored Firebase UIDs (e.g. inviter_id).
        """
        from src.user_module.user import User

        try:
            fb_user = auth.get_user(firebase_uid)
            return User.get_user_by_mail(fb_user.email)
        except Exception:
            return None

    @staticmethod
    def register_user(email, password, name=None):
        # Link generation and email delivery happen after application persistence.
        return auth.create_user(email=email, password=password, display_name=name)
        
    @staticmethod
    def get_user_by_id(user_id):
        try:
            user = auth.get_user(user_id)
            return user
        except Exception as e:
            return str(e)
        
    @staticmethod
    def delete_user(user_id):
        try:
            auth.delete_user(user_id)
            return True
        except Exception as e:
            return str(e)
        
    @staticmethod
    def update_user(user_id, **kwargs):
        try:
            user = auth.update_user(user_id, **kwargs)
            return user
        except Exception as e:
            return str(e)
        
    @staticmethod
    def update_user_password(user_id, password):
        auth.update_user(user_id, password=password)
        try:
            auth.revoke_refresh_tokens(user_id)
        except firebase_errors.FirebaseError as exc:
            raise AuthError("Your password was changed, but ending other sessions failed. "
                            "Sign in with the new password and try signing out all devices.",
                            "password_changed_revocation_failed", 503) from exc

