from flask import Blueprint, request, jsonify
from functools import wraps
from bson import ObjectId
from pymongo.errors import PyMongoError
from src.auth_module.auth_service import login_required, AuthService
from src.league_module.league import League
from src.league_module.league_member import LeagueMember
from src.league_module.league_service import LeagueService
from werkzeug.exceptions import RequestEntityTooLarge
from src.league_module.race import Race
from src.league_module.image_extraction import ExtractionError, MAX_REQUEST_BYTES

league_blueprint = Blueprint('league', __name__, url_prefix='/api/v1/leagues')


def league_member_required(view):
    """Keep detailed reads within the league; hide inaccessible league IDs."""
    @wraps(view)
    def decorated(league_id, *args, **kwargs):
        if not ObjectId.is_valid(league_id):
            return jsonify({"message": "League not found"}), 404
        user = AuthService.get_current_mongo_user()
        if (not user or not League.get_by_id(league_id)
                or not LeagueMember.is_member(league_id, str(user._id))):
            return jsonify({"message": "League not found"}), 404
        return view(league_id, *args, **kwargs)
    return decorated


@league_blueprint.route('/all', methods=['GET'])
def get_all_leagues():
    return public_league_page(legacy_array=True)


def public_league_page(page=None, page_size=None, legacy_array=False):
    try:
        result = LeagueService.get_public_league_page(
            int(request.args.get('page', 1)) if page is None else page,
            int(request.args.get('page_size', 10)) if page_size is None else page_size,
            request.args.get('q', ''))
    except ValueError as error:
        return jsonify({"message": str(error)}), 400
    except PyMongoError:
        return jsonify({"message": "League discovery is temporarily unavailable"}), 503
    response = jsonify(result['leagues'] if legacy_array else result)
    response.headers['X-Total-Count'] = str(result['total'])
    return response, 200


@league_blueprint.route('/discovery', methods=['GET'])
def discover_leagues():
    return public_league_page()


@league_blueprint.route('/<int:page>/<int:page_size>', methods=['GET'])
@login_required
def get_all_leagues_page(page, page_size):
    return public_league_page(page=page, page_size=page_size)


@league_blueprint.route('/my', methods=['GET'])
@login_required
def get_my_leagues():
    user = AuthService.get_current_mongo_user()
    if not user:
        return jsonify([]), 200
    mongo_id = str(user._id)
    leagues = LeagueService.get_my_leagues(mongo_id)
    return jsonify(leagues), 200


@league_blueprint.route('', methods=['POST'])
@login_required
def create_league():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"message": "Invalid league settings"}), 400
    if not data.get('name') or data.get('public') is None:
        return jsonify({"message": "Missing required fields"}), 400
    data.setdefault('calendar', [])
    data.setdefault('max_players', 20)

    user = AuthService.get_current_mongo_user()
    if not user:
        return jsonify({"message": "User not found"}), 404

    try:
        league = LeagueService.create_league(data, str(user._id))
    except ValueError as e:
        return jsonify({"message": str(e)}), 400
    return jsonify(LeagueService.get_league_detail(str(league._id))), 201


@league_blueprint.route('/<league_id>', methods=['GET'])
@login_required
@league_member_required
def get_league(league_id):
    league_detail = LeagueService.get_league_detail(league_id)
    if not league_detail:
        return jsonify({"message": "League not found"}), 404
    return jsonify(league_detail), 200


@league_blueprint.route('/<league_id>', methods=['PUT'])
@login_required
def update_league(league_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"message": "Invalid league settings"}), 400
    user = AuthService.get_current_mongo_user()
    if not user:
        return jsonify({"message": "User not found"}), 404
    mongo_id = str(user._id)

    if not LeagueMember.is_admin_or_owner(league_id, mongo_id):
        return jsonify({"message": "You are not authorized to update this league"}), 403

    league = League.get_by_id(league_id)
    if not league:
        return jsonify({"message": "League not found"}), 404

    if 'creatorParticipates' in data and mongo_id != league.owner_id:
        return jsonify({"message": "Only the owner can change their participation"}), 403
    try:
        league = LeagueService.update_league(league, data, actor_id=mongo_id)
    except ValueError as e:
        return jsonify({"message": str(e)}), 400
    return jsonify(LeagueService.get_league_detail(league_id)), 200


@league_blueprint.route('/<league_id>', methods=['DELETE'])
@login_required
def delete_league(league_id):
    user = AuthService.get_current_mongo_user()
    if not user:
        return jsonify({"message": "User not found"}), 404
    mongo_id = str(user._id)

    if not LeagueMember.is_admin_or_owner(league_id, mongo_id):
        return jsonify({"message": "You are not authorized to delete this league"}), 403

    League.soft_delete(league_id)
    return jsonify({"message": "League deleted successfully!"}), 200


@league_blueprint.route('/public', methods=['GET'])
def get_public_leagues():
    return public_league_page(legacy_array=True)


@league_blueprint.route('/<league_id>/join', methods=['POST'])
@login_required
def join_league(league_id):
    user = AuthService.get_current_mongo_user()
    if not user:
        return jsonify({"message": "User not found"}), 404
    mongo_id = str(user._id)

    league = League.get_by_id(league_id)
    if not league:
        return jsonify({"message": "League not found"}), 404

    if not league.public:
        return jsonify({"message": "This league is private"}), 403

    if LeagueMember.is_member(league_id, mongo_id):
        return jsonify({"message": "Already a member"}), 400

    from src.config import mongo
    try:
        mongo.run_transaction(lambda session: LeagueMember.join_as_participant(
            league_id, mongo_id, user.name, session, require_public=True))
    except ValueError as error:
        return jsonify({"message": str(error)}), 400
    return jsonify({"message": "You have joined the league!"}), 200


@league_blueprint.route('/<league_id>/leave', methods=['POST'])
@login_required
def leave_league(league_id):
    user = AuthService.get_current_mongo_user()
    if not user:
        return jsonify({"message": "User not found"}), 404
    if not ObjectId.is_valid(league_id) or not League.get_by_id(league_id):
        return jsonify({"message": "League not found"}), 404
    try:
        LeagueMember.remove(league_id, str(user._id))
    except ValueError as error:
        return jsonify({"message": str(error)}), 400
    except PyMongoError:
        return jsonify({"message": "Unable to leave the league. Please try again"}), 503
    return jsonify({"message": "You have left the league!"}), 200


@league_blueprint.route('/<league_id>/races/<race_id>/results', methods=['POST'])
@login_required
def submit_race_results(league_id, race_id):
    """Submit results for a race"""
    try:
        user = AuthService.get_current_mongo_user()
        if not user:
            return jsonify({"message": "User not found"}), 404
        mongo_id = str(user._id)

        if not LeagueMember.is_admin_or_owner(league_id, mongo_id):
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
@league_member_required
def extract_race_results(league_id, race_id):
    try:
        user = AuthService.get_current_mongo_user()
        if not user:
            return jsonify({"message": "User not found"}), 404
        mongo_id = str(user._id)

        if not LeagueMember.is_admin_or_owner(league_id, mongo_id):
            return jsonify({"message": "Not authorized to extract results"}), 403

        race = Race.get_by_id(race_id) if ObjectId.is_valid(race_id) else None
        if not race or race.league_id != ObjectId(league_id):
            return jsonify({"message": "Race not found"}), 404
        if request.content_length and request.content_length > MAX_REQUEST_BYTES:
            raise RequestEntityTooLarge()
        results = LeagueService.extract_race_results(request.files.getlist('images'), mongo_id)
        return jsonify(results), 200
    except RequestEntityTooLarge:
        return jsonify({"message": "Request must be 13 MiB or smaller", "code": "request_too_large"}), 413
    except ExtractionError as error:
        response = jsonify({"message": str(error), "code": error.code})
        if error.retry_after:
            response.headers['Retry-After'] = str(error.retry_after)
        return response, error.status
    except Exception:
        return jsonify({"message": "Image extraction is currently unavailable"}), 503


@league_blueprint.route('/<league_id>/standings', methods=['GET'])
@login_required
@league_member_required
def get_league_standings(league_id):
    """Get standings for a league"""
    try:
        standings = LeagueService.get_league_standings(league_id)
        return jsonify(standings), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 400


@league_blueprint.route('/<league_id>/standings/<participant_email>', methods=['GET'])
@login_required
@league_member_required
def get_participant_standings(league_id, participant_email):
    """Get standings for a specific participant"""
    try:
        standings = LeagueService.get_league_standings(league_id)
        for s in standings:
            if s.get("email") == participant_email:
                return jsonify(s), 200
        return jsonify({"message": "Participant not found"}), 404
    except Exception as e:
        return jsonify({"message": str(e)}), 400


@league_blueprint.route('/<league_id>/teams', methods=['POST', 'PUT'])
@login_required
def set_teams(league_id):
    """Create or update teams for a league"""
    try:
        user = AuthService.get_current_mongo_user()
        if not user:
            return jsonify({"message": "User not found"}), 404
        mongo_id = str(user._id)

        if not LeagueMember.is_admin_or_owner(league_id, mongo_id):
            return jsonify({"message": "Not authorized to manage teams"}), 403

        data = request.json
        if not isinstance(data, dict):
            return jsonify({"message": "Invalid teams format"}), 400

        teams = LeagueService.set_teams(league_id, data)
        return jsonify(teams), 200

    except ValueError as e:
        return jsonify({"message": str(e)}), 400
    except Exception as e:
        return jsonify({"message": str(e)}), 400


@league_blueprint.route('/<league_id>/teams', methods=['GET'])
@login_required
@league_member_required
def get_teams(league_id):
    """Get all teams with calculated statistics"""
    try:
        teams = LeagueService.get_teams(league_id)
        return jsonify(teams), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 400


@league_blueprint.route('/<league_id>/teams/standings', methods=['GET'])
@login_required
@league_member_required
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
        user = AuthService.get_current_mongo_user()
        if not user:
            return jsonify({"message": "User not found"}), 404
        mongo_id = str(user._id)

        if not LeagueMember.is_admin_or_owner(league_id, mongo_id):
            return jsonify({"message": "Not authorized to manage teams"}), 403

        result = LeagueService.remove_team(league_id, team_name)
        return jsonify(result), 200

    except Exception as e:
        return jsonify({"message": str(e)}), 400
