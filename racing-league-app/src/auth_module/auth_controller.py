# project/src/auth_module/auth_controller.py
from flask import Blueprint, request, jsonify
from src.auth_module.auth_service import AuthService, AuthError, auth_error_response, login_required
from firebase_admin import auth, exceptions as firebase_errors
from src.user_module.account_service import AccountService
from src.user_module.account_validation import normalize_email
from src.email_module.account_notifications import request_email
from pymongo.errors import PyMongoError
from src.auth_module.account_limits import reserve_request, RateLimited

# Set the URL prefix for all routes in this blueprint
auth_blueprint = Blueprint('auth', __name__, url_prefix='/api/v1/auth')


@auth_blueprint.before_request
def limit_account_email_producers():
    if request.method != 'POST' or request.endpoint not in (
            'auth.register', 'auth.reset_password', 'auth.verification_email'):
        return None
    try:
        reserve_request(request.remote_addr or 'unknown')
    except RateLimited as error:
        response = jsonify({'message': str(error), 'code': 'account_rate_limited'})
        response.headers['Retry-After'] = str(error.retry_after)
        return response, 429
    except PyMongoError:
        return jsonify({'message': 'Account requests are temporarily unavailable. Please try again.',
                        'code': 'account_unavailable'}), 503
    return None


@auth_blueprint.after_request
def prevent_auth_caching(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'
    return response


@auth_blueprint.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"message": "Email and password are required"}), 400
    email = data.get('email')
    password = data.get('password')

    if not isinstance(email, str) or not email.strip() or not isinstance(password, str) or not password:
        return jsonify({"message": "Email and password are required"}), 400

    try:
        tokens = AuthService.login_user(email.strip(), password)
        payload = AuthService.token_payload(tokens)
        return jsonify({"message": "Login successful!", **payload}), 200
    except AuthError as error:
        return auth_error_response(error)


@auth_blueprint.route('/refresh', methods=['POST'])
def refresh():
    data = request.get_json(silent=True)
    refresh_token = data.get('refreshToken') if isinstance(data, dict) else None
    if not isinstance(refresh_token, str) or not refresh_token.strip():
        return jsonify({"message": "Refresh token is required", "code": "missing_refresh_token"}), 400
    try:
        tokens = AuthService.refresh_tokens(refresh_token)
        return jsonify(AuthService.token_payload(tokens)), 200
    except AuthError as error:
        return auth_error_response(error)

@auth_blueprint.route('/register', methods=['POST'])
def register():
    try:
        user = AccountService.register(request.get_json(silent=True))
    except ValueError as error:
        return jsonify({'message': str(error), 'code': 'invalid_registration'}), 400
    except AuthError as error:
        return auth_error_response(error)
    return jsonify({'message': 'Account created. Your verification email is queued.',
                    'uid': user.firebase_uid, 'emailStatus': 'queued'}), 201

@auth_blueprint.route('/reset-password', methods=['POST'])
def reset_password():
    return queue_account_email('password_reset')

@auth_blueprint.route('/verification-email', methods=['POST'])
def verification_email():
    return queue_account_email('verification')


def queue_account_email(kind):
    data = request.get_json(silent=True)
    try:
        email = normalize_email(data.get('email') if isinstance(data, dict) else None)
        request_email(kind, email)
    except ValueError as error:
        return jsonify({'message': str(error), 'code': 'invalid_email'}), 400
    except AuthError as error:
        return auth_error_response(error)
    except PyMongoError:
        return jsonify({'message': 'Email requests are temporarily unavailable. Please try again.',
                        'code': 'email_unavailable'}), 503
    return jsonify({'message': 'If this account is eligible, an email is queued. Please check your inbox shortly.',
                    'code': 'email_queued'}), 202

@auth_blueprint.route('/verify', methods=['GET'])
@login_required
def verify():
    from flask import g
    return jsonify({"message": "Token is valid", "uid": AuthService.get_current_user(),
                    "user": AuthService.user_payload(g.auth_identity)}), 200

@auth_blueprint.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict) or type(data.get('allDevices', False)) is not bool:
        return jsonify({"message": "Invalid logout request"}), 400
    all_devices = data.get('allDevices', False)
    if all_devices:
        try:
            auth.revoke_refresh_tokens(AuthService.get_current_user())
        except firebase_errors.FirebaseError:
            return jsonify({"message": "Sign-out is temporarily unavailable. Please try again.",
                            "code": "auth_unavailable"}), 503
    return jsonify({"message": "Logged out successfully!", "allDevices": all_devices}), 200


