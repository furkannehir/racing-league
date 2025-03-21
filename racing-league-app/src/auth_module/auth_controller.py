# project/src/auth_module/auth_controller.py
from flask import Blueprint, request, jsonify
from src.auth_module.auth_service import AuthService, login_required
from firebase_admin import auth
from src.user_module.user import User

auth_blueprint = Blueprint('auth', __name__)

@auth_blueprint.route('/login', methods=['POST'])
def login():
    email = request.json.get('email')
    password = request.json.get('password')

    if not email or not password:
        return jsonify({"message": "Email and password are required"}), 400

    id_token, uid = AuthService.login_user(email, password)
    user = User.get_user_by_mail(email)
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

    return jsonify({"message": "User created successfully!", "uid": response.uid}), 201

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

@auth_blueprint.route('/dashboard')
@login_required
def dashboard():
    return jsonify({"message": f"Welcome {AuthService.get_current_user()}!"}), 200

@auth_blueprint.route('/user')
@login_required
def user_info():
    current_user = auth.get_user(AuthService.get_current_user())
    user = User.get_user_by_mail(current_user.email)
    if (user is None):
        return jsonify({"message": "User not found"}), 404
    return jsonify(user.serialize()), 200
