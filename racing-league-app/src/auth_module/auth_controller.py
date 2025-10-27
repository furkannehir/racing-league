# project/src/auth_module/auth_controller.py
from flask import Blueprint, request, jsonify
from src.auth_module.auth_service import AuthService, login_required
from src.user_module.user import User
from src.email_module.email_service import EmailService

# Set the URL prefix for all routes in this blueprint
auth_blueprint = Blueprint('auth', __name__, url_prefix='/api/v1/auth')

@auth_blueprint.route('/login', methods=['POST'])
def login():
    email = request.json.get('email')
    password = request.json.get('password')

    if not email or not password:
        return jsonify({"message": "Email and password are required"}), 400

    id_token, uid = AuthService.login_user(email, password)
    user = User.get_user_by_mail(email)
    if not user:
        return jsonify({"message": "User not found."}), 404
    if not AuthService.check_email_verified(user.email):
        return jsonify({"message": "Email not verified."}), 401
    if id_token and uid:
        # No longer creating a session
        return jsonify({
            "message": "Login successful!",
            "token": id_token,
            "user": {
                "id": uid,
                "email": user.email,
                "name": user.name
            }
        }), 200
    else:
        return jsonify({"message": "Login failed. Invalid credentials."}), 400

@auth_blueprint.route('/register', methods=['POST'])
def register():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    name = data.get('name')
    ea_username = data.get('ea_username') if 'ea_username' in data else None

    if not email or not password:
        return jsonify({"message": "Email and password are required"}), 400

    response = AuthService.register_user(email, password)

    if isinstance(response, str) and "uid" not in response:
        return jsonify({"message": response}), 400  # Error message from Firebase

    user = User(
        _id=response.uid,
        email=email,
        name=name,
        eaUsername=ea_username
    )
    user.save()

    EmailService.send_verification_email(to_email=email, name=name)

    return jsonify({"message": "User created successfully!", "uid": response.uid}), 201

@auth_blueprint.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.json
    email = data.get('email')

    if not email:
        return jsonify({"message": "Email is required"}), 400
    user = User.get_user_by_mail(email)
    if not user:
        return jsonify({"message": "Reset password email sent successfully!"}), 200

    EmailService.send_reset_password_email(to_email=email, name=user.name)

    return jsonify({"message": "Reset password email sent successfully!"}), 200

@auth_blueprint.route('/verification-email', methods=['POST'])
def verification_email():
    data = request.json
    email = data.get('email')

    if not email:
        return jsonify({"message": "Email is required"}), 400
    
    user = User.get_user_by_mail(email)
    if not user:
        return jsonify({"message": "Verification email sent successfully!"}), 200

    EmailService.send_verification_email(to_email=email, name=user.name)
    return jsonify({"message": "Verification email sent successfully!"}), 200

@auth_blueprint.route('/verify', methods=['GET'])
@login_required
def verify():
    uid = AuthService.get_current_user()
    if uid:
        return jsonify({"message": "Token is valid", "uid": uid}), 200
    return jsonify({"message": "Token is invalid"}), 401

@auth_blueprint.route('/logout')
@login_required
def logout():
    return jsonify({"message": "Logged out successfully!"}), 200


