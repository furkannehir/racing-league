from flask import Blueprint, request, jsonify
from src.auth_module.auth_service import login_required
from src.league_module.league import League
from src.league_module.league_service import LeagueService
from src.auth_module.auth_service import AuthService
from firebase_admin import auth
import io
from PIL import Image

from src.user_module.user import User

league_blueprint = Blueprint('league', __name__, url_prefix='/api/v1/leagues')

@league_blueprint.route('/all', methods=['GET'])
def get_all_leagues():
    leagues = League.get_all_leagues()
    return jsonify([league.serialize() for league in leagues]), 200

@league_blueprint.route('/<int:page>/<int:page_size>', methods=['GET'])
@login_required
def get_all_leagues_page(page, page_size):
    leagues = League.get_all_leagues_pagination(page, page_size)
    return jsonify({
        'page': page,
        'page_size': page_size,
        'leagues': [league.serialize() for league in leagues]
        }), 200


@league_blueprint.route('/my', methods=['GET'])
@login_required
def get_my_leagues():
    leagues = LeagueService.get_my_leagues()
    return jsonify([league.serialize() for league in leagues]), 200

@league_blueprint.route('', methods=['POST'])
@login_required
def create_league():
    data = request.json
    if data.get('name') is None or data.get('public') is None or data.get('pointSystem') is None or data.get('fastestLapPoint') is None:
        return jsonify({"message": "Missing required fields"}), 400
    if not data.get('calendar'):
        data['calendar'] = []
    if not data.get('max_players'):
        data['max_players'] = 20
    if not data.get("calendar") or not isinstance(data.get("calendar"), list):
        data['calendar'] = []
    league = LeagueService.create_league(data)
    return jsonify(league.serialize()), 201 

@league_blueprint.route('/<league_id>', methods=['GET'])
@login_required
def get_league(league_id):
    league = League.get_league_by_id(league_id)
    return jsonify(league.serialize()), 200

@league_blueprint.route('/<league_id>', methods=['PUT'])
@login_required
def update_league(league_id):
    data = request.json
    league = League.get_league_by_id(league_id)
    uid = AuthService.get_current_user()
    current_user = auth.get_user(uid)
    if current_user.email is league.owner or current_user.email not in league.admins:
        return jsonify({"message": "You are not authorized to update this league"}), 403
    league = LeagueService.update_league(league_id, data)
    return jsonify(league.serialize()), 200

@league_blueprint.route('/<league_id>', methods=['DELETE'])
@login_required
def delete_league(league_id):
    uid = AuthService.get_current_user()
    league = League.get_league_by_id(league_id)
    current_user = auth.get_user(uid)
    if current_user.email is league.owner or current_user.email not in league.admins:
        return jsonify({"message": "You are not authorized to delete this league"}), 403
    League.delete_league(league_id)
    return jsonify({"message": "League deleted successfully!"}), 200

@league_blueprint.route('/public', methods=['GET'])
def get_public_leagues():
    leagues = League.get_public_leagues()
    return jsonify([league.serialize() for league in leagues]), 200

@league_blueprint.route('/<league_id>/join', methods=['POST'])
@login_required
def join_league(league_id):
    uid = AuthService.get_current_user()
    user = auth.get_user(uid)
    league = League.get_league_by_id(league_id)
    userObj = User.get_user_by_mail(user.email)
    if league.public:
        league.add_participant(userObj.email, userObj.name)
        return jsonify({"message": "You have joined the league!"}), 200
    return jsonify({"message": "This league is private"}), 403

@league_blueprint.route('/<league_id>/leave', methods=['POST'])
@login_required
def leave_league(league_id):
    uid = AuthService.get_current_user()
    user = auth.get_user(uid)
    league = League.get_league_by_id(league_id)
    league.remove_participant(user.email)
    return jsonify({"message": "You have left the league!"}), 200

@league_blueprint.route('/<league_id>/races/<race_id>/results', methods=['POST'])
@login_required
def submit_race_results(league_id, race_id):
    """Submit results for a race"""
    try:
        # Check if user is league admin or owner
        uid = AuthService.get_current_user()
        user = auth.get_user(uid)
        league = LeagueService.get_league_by_id(league_id)

        if not league:
            return jsonify({"message": "League not found"}), 404

        if user.email != league.owner and user.email not in league.admins:
            return jsonify({"message": "Not authorized to submit results"}), 403

        data = request.json
        if not data or not isinstance(data, dict):
            return jsonify({"message": "Invalid race results format"}), 400

        results = LeagueService.submit_race_result(league_id, race_id, data)
        return jsonify(results), 200

    except Exception as e:
        return jsonify({"message": str(e)}), 400

@league_blueprint.route('/<league_id>/races/<race_id>/extract-results', methods=['POST'])
@login_required
def extract_race_results(league_id, race_id):
    try:

        # Check if user is league admin or owner
        uid = AuthService.get_current_user()
        user = auth.get_user(uid)
        league = LeagueService.get_league_by_id(league_id)
        if not league:
            return jsonify({"message": "League not found"}), 404

        if user.email != league.owner and user.email not in league.admins:
            return jsonify({"message": "Not authorized to extract results"}), 403

        images = request.files.getlist('images')
        if len(images) == 0:
            return jsonify({"message": "No images provided"}), 400
        if len(images) > 2:
            return jsonify({"message": "Too many images provided. Maximum 2 images allowed"}), 400

        image_list = []
        for img in images:
            # Ensure the file is an image
            if img.mimetype not in ['image/jpeg', 'image/png']:
                return jsonify({"message": "Invalid file type. Only JPEG and PNG are supported"}), 400
            image = Image.open(io.BytesIO(img.read()))
            if image.mode == "RGBA":
                # Convert the image to RGB mode
                image = image.convert("RGB")
            image_list.append(image)

        results = LeagueService.extract_race_results(image_list)

        return jsonify(results), 200

    except Exception as e:
        return jsonify({"message": str(e)}), 400


@league_blueprint.route('/<league_id>/standings', methods=['GET'])
@login_required
def get_league_standings(league_id):
    """Get standings for a league"""
    try:
        standings = LeagueService.get_league_standings(league_id)
        return jsonify(standings), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 400


@league_blueprint.route('/<league_id>/standings/<participant_email>', methods=['GET'])
@login_required
def get_participant_standings(league_id, participant_email):
    """Get standings for a specific participant"""
    try:
        standings = LeagueService.get_participant_standings(league_id, participant_email)
        return jsonify(standings), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 400


@league_blueprint.route('/<league_id>/teams', methods=['POST', 'PUT'])
@login_required
def set_teams(league_id):
    """
    Create or update teams for a league
    
    Request body:
    {
        "Team Name": ["email1@example.com", "email2@example.com"],
        "Another Team": ["email3@example.com"]
    }
    """
    try:
        uid = AuthService.get_current_user()
        user = auth.get_user(uid)
        league = LeagueService.get_league_by_id(league_id)
        
        if not league:
            return jsonify({"message": "League not found"}), 404
        
        if user.email != league.owner and user.email not in league.admins:
            return jsonify({"message": "Not authorized to manage teams"}), 403
        
        data = request.json
        if not data or not isinstance(data, dict):
            return jsonify({"message": "Invalid teams format. Expected object with team names as keys"}), 400
        
        teams = LeagueService.set_teams(league_id, data)
        return jsonify(teams), 200
    
    except ValueError as e:
        return jsonify({"message": str(e)}), 400
    except Exception as e:
        return jsonify({"message": str(e)}), 400


@league_blueprint.route('/<league_id>/teams', methods=['GET'])
@login_required
def get_teams(league_id):
    """Get all teams with calculated statistics"""
    try:
        teams = LeagueService.get_teams(league_id)
        return jsonify(teams), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 400


@league_blueprint.route('/<league_id>/teams/standings', methods=['GET'])
@login_required
def get_team_standings(league_id):
    """Get teams sorted by total points (leaderboard)"""
    try:
        standings = LeagueService.get_team_standings(league_id)
        return jsonify(standings), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 400


@league_blueprint.route('/<league_id>/teams/<team_name>', methods=['DELETE'])
@login_required
def remove_team(league_id, team_name):
    """Remove a team from the league"""
    try:
        uid = AuthService.get_current_user()
        user = auth.get_user(uid)
        league = LeagueService.get_league_by_id(league_id)
        
        if not league:
            return jsonify({"message": "League not found"}), 404
        
        if user.email != league.owner and user.email not in league.admins:
            return jsonify({"message": "Not authorized to manage teams"}), 403
        
        result = LeagueService.remove_team(league_id, team_name)
        return jsonify(result), 200
    
    except Exception as e:
        return jsonify({"message": str(e)}), 400