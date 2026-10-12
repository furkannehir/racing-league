from flask import Blueprint, request, jsonify
from src.auth_module.auth_service import login_required, AuthService
from src.invite_module.invite_service import InviteService
from src.league_module.league import League
from src.league_module.league_service import LeagueService
from src.user_module.user import User

invite_blueprint = Blueprint('invite', __name__, url_prefix='/api/v1/invites')


@invite_blueprint.route('/my', methods=['GET'])
@login_required
def get_my_invites():
    user = AuthService.get_current_mongo_user()
    if not user:
        return jsonify([]), 200

    invites = InviteService.get_invites_by_user(user.email)

    # Enrich with league and inviter info
    enriched = []
    for invite in invites:
        league = League.get_by_id(str(invite.league_id))
        if not league:
            continue
        inviter = User.get_user_by_id(invite.inviter_id)

        enriched.append({
            "_id": str(invite._id),
            "league": LeagueService.get_league_detail(str(invite.league_id)),
            "invited_user": invite.invited_email,
            "inviter": inviter.serialize() if inviter else {"_id": invite.inviter_id},
            "status": invite.status,
            "created_at": invite.created_at,
            "createdAt": invite.created_at.isoformat(),
            "updated_at": invite.updated_at,
        })

    return jsonify(enriched), 200


@invite_blueprint.route('/sent', methods=['GET'])
@login_required
def get_sent_invites():
    user = AuthService.get_current_mongo_user()
    if not user:
        return jsonify([]), 200
    invites = InviteService.get_sent_invites_by_user(str(user._id))

    enriched = []
    for invite in invites:
        enriched.append({
            "_id": str(invite._id),
            "league_id": str(invite.league_id),
            "invited_email": invite.invited_email,
            "status": invite.status,
            "created_at": invite.created_at,
        })

    return jsonify(enriched), 200


@invite_blueprint.route('', methods=['POST'])
@login_required
def create_invite():
    try:
        data = request.json
        if not data.get('emails') or not data.get('league_id'):
            return jsonify({"message": "Missing required fields"}), 400
        invites = InviteService.create_invites(data.get('emails'), data.get('league_id'))
        return jsonify([i.serialize() for i in invites]), 201
    except Exception as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            return jsonify({"message": error_msg}), 404
        if "already" in error_msg.lower():
            return jsonify({"message": "Conflict", "details": error_msg}), 409
        return jsonify({"message": error_msg}), 400


@invite_blueprint.route('/<invite_id>/accept', methods=['POST'])
@login_required
def accept_invite(invite_id):
    try:
        data = request.json or {}
        league_user_name = data.get('league_user_name')
        invite = InviteService.accept_invite(invite_id, league_user_name)
        return jsonify(invite.serialize()), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 400


@invite_blueprint.route('/<invite_id>/decline', methods=['POST'])
@login_required
def decline_invite(invite_id):
    try:
        invite = InviteService.decline_invite(invite_id)
        return jsonify(invite.serialize()), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 400


@invite_blueprint.route('/<invite_id>', methods=['DELETE'])
@login_required
def delete_invite(invite_id):
    try:
        InviteService.delete_invite(invite_id)
        return jsonify({"message": "Invite deleted"}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 400
