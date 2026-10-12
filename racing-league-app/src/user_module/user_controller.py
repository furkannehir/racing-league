from flask import Blueprint, request, jsonify
from src.auth_module.auth_service import login_required, AuthService
from src.user_module.user import User

user_blueprint = Blueprint('user', __name__, url_prefix='/api/v1/users')


@user_blueprint.route('/profile', methods=['GET'])
@login_required
def user_info():
    user = AuthService.get_current_mongo_user()
    if user is None:
        return jsonify({"message": "User not found"}), 404
    return jsonify(user.serialize()), 200


@user_blueprint.route('/update', methods=['PUT'])
@login_required
def update_user():
    data = request.json
    user = AuthService.get_current_mongo_user()
    if user is None:
        return jsonify({"message": "User not found"}), 404
    user.name = data.get('name', user.name)
    user.update()
    return jsonify(user.serialize()), 200


@user_blueprint.route('/update/password', methods=['PUT'])
@login_required
def update_password():
    data = request.json
    uid = AuthService.get_current_user()
    firebase_user = AuthService.get_user_by_id(uid)
    if firebase_user is None:
        return jsonify({"message": "User not found"}), 404
    if AuthService.login_user(firebase_user.email, data.get('old_password'))[0] is None:
        return jsonify({"message": "Invalid old password"}), 400
    response = AuthService.update_user_password(uid, data.get('new_password'))
    if response:
        return jsonify({"message": "Password updated successfully"}), 200
    return jsonify({"message": "Password update failed"}), 400


@user_blueprint.route('/<user_id>')
@login_required
def user_info_by_id(user_id):
    user = User.get_user_by_id(user_id)
    if user is None:
        return jsonify({"message": "User not found"}), 404
    return jsonify(user.serialize()), 200