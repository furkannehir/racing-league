# project/src/auth_module/auth_controller.py
from flask import Blueprint, request, jsonify
from src.auth_module.auth_service import AuthService, login_required
from firebase_admin import auth
from src.user_module.user import User
from src.league_module.league_service import LeagueService

user_blueprint = Blueprint('user', __name__, url_prefix='/api/v1/users')

@user_blueprint.route('/profile', methods=['GET'])
@login_required
def user_info():
    current_user = auth.get_user(AuthService.get_current_user())
    user = User.get_user_by_mail(current_user.email)
    if (user is None):
        return jsonify({"message": "User not found"}), 404
    return jsonify(user.serialize()), 200

@user_blueprint.route('/update', methods=['PUT'])
@login_required
def update_user():
    data = request.json
    user = User.get_user_by_id(AuthService.get_current_user())
    if (user is None):
        return jsonify({"message": "User not found"}), 404
    user.name = data.get('name')
    user.save()
    return jsonify(user.serialize()), 200

@user_blueprint.route('/update/password', methods=['PUT'])
@login_required
def update_password():
    data = request.json
    user_id = AuthService.get_current_user()
    user = AuthService.get_user_by_id(user_id)
    if (user is None):
        return jsonify({"message": "User not found"}), 404
    if AuthService.login_user(user.email, data.get('old_password'))[0] is None:
        return jsonify({"message": "Invalid old password"}), 400
    response = AuthService.update_user_password(user_id, data.get('new_password'))
    if response:
        return jsonify({"message": "Password updated successfully"}), 200
    return jsonify({"message": "Password update failed"}), 400

@user_blueprint.route('/<user_id>')
@login_required
def user_info_by_id(user_id):
    user = User.get_user_by_id(user_id)
    if (user is None):
        return jsonify({"message": "User not found"}), 404
    return jsonify(user.serialize()), 200

@user_blueprint.route('/<user_id>/leagues')
@login_required
def user_leagues(user_id):
    user = User.get_user_by_id(user_id)
    leagues = LeagueService.get_leagues_by_participant(user_id)
    if (user is None):
        return jsonify({"message": "User not found"}), 404
    return jsonify(leagues), 200