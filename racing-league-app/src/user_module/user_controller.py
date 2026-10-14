from flask import Blueprint, request, jsonify
from src.auth_module.auth_service import login_required, AuthService, AuthError, auth_error_response
from firebase_admin import exceptions as firebase_errors
from src.user_module.user import user_id_candidates
from src.user_module.user_service import UserService
from src.user_module.account_validation import validate_password
from pymongo.errors import PyMongoError

user_blueprint = Blueprint('user', __name__, url_prefix='/api/v1/users')


@user_blueprint.route('/profile', methods=['GET'])
@login_required
def user_info():
    user = AuthService.get_current_mongo_user()
    if user is None:
        return jsonify({"message": "User not found"}), 404
    return jsonify(user.serialize(include_bio=True)), 200


@user_blueprint.route('/update', methods=['PUT'])
@login_required
def update_user():
    data = request.get_json(silent=True)
    user = AuthService.get_current_mongo_user()
    if user is None:
        return jsonify({"message": "User not found"}), 404
    try:
        updated = UserService.update_profile(user, data)
    except ValueError as error:
        return jsonify({'message': str(error), 'code': 'invalid_profile'}), 400
    except PyMongoError:
        return jsonify({'message': 'Profile updates are temporarily unavailable. Please try again.',
                        'code': 'profile_unavailable'}), 503
    if updated is None:
        return jsonify({'message': 'Your application account is unavailable',
                        'code': 'account_unavailable'}), 401
    return jsonify(updated.serialize(include_bio=True)), 200


@user_blueprint.route('/update/password', methods=['PUT'])
@login_required
def update_password():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"message": "Current and new passwords are required"}), 400
    old_password = data.get('currentPassword', data.get('old_password'))
    new_password = data.get('newPassword', data.get('new_password'))
    if not all(isinstance(value, str) and value for value in (old_password, new_password)):
        return jsonify({"message": "Current and new passwords are required"}), 400
    try:
        validate_password(new_password)
    except ValueError as error:
        return jsonify({'message': str(error)}), 400
    if 'confirmPassword' in data and data['confirmPassword'] != new_password:
        return jsonify({"message": "New passwords do not match"}), 400
    uid = AuthService.get_current_user()
    firebase_user = AuthService.get_current_firebase_user()
    try:
        credentials = AuthService.login_user(firebase_user.email, old_password)
        if credentials.uid != uid:
            return jsonify({"message": "Invalid current password"}), 400
        AuthService.update_user_password(uid, new_password)
    except AuthError as error:
        if error.code == 'invalid_credentials':
            return jsonify({"message": "Invalid current password"}), 400
        return auth_error_response(error)
    except (ValueError, firebase_errors.InvalidArgumentError):
        return jsonify({"message": "The new password was rejected"}), 400
    except firebase_errors.FirebaseError:
        return jsonify({"message": "Password change is temporarily unavailable. Please try again."}), 503
    return jsonify({"message": "Password updated successfully. Please sign in again.",
                    "code": "password_updated"}), 200


@user_blueprint.route('/<user_id>')
@login_required
def user_info_by_id(user_id):
    user = AuthService.get_current_mongo_user()
    if user is None or user._id not in user_id_candidates(user_id):
        return jsonify({"message": "User not found"}), 404
    return jsonify(user.serialize()), 200
