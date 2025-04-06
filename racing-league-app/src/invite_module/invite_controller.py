from flask import Blueprint, request, jsonify
from src.auth_module.auth_service import login_required
from src.invite_module.invite_service import InviteService
from src.auth_module.auth_service import AuthService
from firebase_admin import auth

invite_blueprint = Blueprint('invite', __name__, url_prefix='/api/v1/invites')

@invite_blueprint.route('/my', methods=['GET'])
@login_required
def get_my_invites():
    uid = AuthService.get_current_user()
    user = auth.get_user(uid)
    invites = InviteService.get_invites_by_user(user.email)
    return jsonify([invite.serialize() for invite in invites]), 200

@invite_blueprint.route('/sent', methods=['GET'])
@login_required
def get_sent_invites():
    uid = AuthService.get_current_user()
    user = auth.get_user(uid)
    invites = InviteService.get_sent_invites_by_user(user.email)
    return jsonify([invite.serialize() for invite in invites])


@invite_blueprint.route('', methods=['POST'])
@login_required
def create_invite():
    try:
        data = request.json
        if not data.get('emails') or not data.get('league_id'):
            return jsonify({"message": "Missing required fields"}), 400
        invites = InviteService.create_invites(data.get('emails'), data.get('league_id'))
        return jsonify([invite.serialize() for invite in invites]), 201
    except Exception as e:
        if str(e) == "User not found":
            return jsonify({"message": "User not found"}), 404
        if str(e) == "League not found":
            return jsonify({"message": "League not found"}), 404
        if str(e).__contains__("already sent"):
            return jsonify({
                "message": "Conflict",
                "details": "Invite already sent to user!"
            }), 409

@invite_blueprint.route('/<invite_id>/accept', methods=['POST'])
@login_required
def accept_invite(invite_id):
    invite = InviteService.accept_invite(invite_id)
    return jsonify(invite.serialize()), 200

@invite_blueprint.route('/<invite_id>/decline', methods=['POST'])
@login_required
def decline_invite(invite_id):
    invite = InviteService.decline_invite(invite_id)
    return jsonify(invite.serialize()), 200


@invite_blueprint.route('/<invite_id>', methods=['DELETE'])
@login_required
def delete_invite(invite_id):
    InviteService.delete_invite(invite_id)
    return jsonify({"message": "Invite deleted"}), 200
