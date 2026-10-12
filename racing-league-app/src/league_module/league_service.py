from bson.objectid import ObjectId
from src.league_module.league import League
from src.league_module.league_member import LeagueMember
from src.league_module.race import Race
from src.league_module.race_result import RaceResult
from src.league_module.team import Team
from src.user_module.user import User
from src.config.config import Config
from datetime import datetime, timezone
import tempfile
from io import BytesIO
import base64

client = None


def get_openai_client():
    global client
    if client is None:
        try:
            from openai import OpenAI
            if not Config.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY not found in environment variables")
            client = OpenAI(api_key=Config.OPENAI_API_KEY)
        except ImportError as e:
            raise ImportError(f"OpenAI package not installed: {e}")
        except Exception as e:
            raise Exception(f"Failed to initialize OpenAI client: {e}")
    return client


class LeagueService:

    @staticmethod
    def validate_settings(name, max_players, fastest_lap_point, point_system, member_count=0):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("League name is required")
        if type(max_players) is not int or max_players < max(1, member_count):
            raise ValueError("Maximum players must be a positive integer and fit existing members")
        if type(fastest_lap_point) is not int or fastest_lap_point < 0:
            raise ValueError("Fastest lap points must be a non-negative integer")
        if not isinstance(point_system, dict) or any(
            not str(pos).isdigit() or int(pos) < 1 or type(points) is not int or points < 0
            for pos, points in point_system.items()
        ):
            raise ValueError("Point system must map positive positions to non-negative integer points")

    @staticmethod
    def create_league(data, owner_id):
        """
        Create a new league and add owner as first member.
        owner_id: MongoDB user _id (string)
        """
        owner_user = User.get_user_by_id(owner_id)
        if not owner_user:
            raise Exception("Owner user not found")

        league = League(
            name=data.get("name"),
            owner_id=owner_id,
            public=data.get("public", False),
            point_system=data.get("point_system", data.get("pointSystem", {})),
            max_players=data.get("max_players", 20),
            fastest_lap_point=data.get("fastest_lap_point", data.get("fastestLapPoint", 0)),
            status=data.get("status", "active"),
        )
        LeagueService.validate_settings(
            league.name, league.max_players, league.fastest_lap_point, league.point_system
        )
        league.save()

        # Add owner as first member
        member = LeagueMember(
            league_id=league._id,
            user_id=owner_id,
            role="owner",
            display_name=owner_user.name or owner_user.email,
        )
        member.save()

        # Create races if calendar provided
        calendar = data.get("calendar", [])
        for race_data in calendar:
            date = race_data.get("date")
            if isinstance(date, str):
                try:
                    if date.endswith('Z'):
                        date = datetime.fromisoformat(date.replace('Z', '+00:00'))
                    else:
                        date = datetime.fromisoformat(date)
                        if not date.tzinfo:
                            date = date.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    date = datetime.now(timezone.utc)

            race = Race(
                league_id=league._id,
                track=race_data.get("track"),
                date=date,
                status=race_data.get("status", "Upcoming"),
            )
            race.save()

        return league

    @staticmethod
    def update_league(league, data):
        """Update league core settings"""
        league.name = data.get("name", league.name)
        league.public = data.get("public", league.public)
        league.max_players = data.get("max_players", league.max_players)
        league.fastest_lap_point = data.get("fastest_lap_point",
                                            data.get("fastestLapPoint", league.fastest_lap_point))
        if "point_system" in data:
            league.point_system = data["point_system"]
        elif "pointSystem" in data:
            league.point_system = data["pointSystem"]
        LeagueService.validate_settings(
            league.name, league.max_players, league.fastest_lap_point, league.point_system,
            LeagueMember.get_member_count(str(league._id))
        )
        league.update()
        return league

    @staticmethod
    def get_league_detail(league_id):
        """
        Compose full league detail from multiple collections.
        Returns a dict matching the shape the frontend expects.
        """
        league = League.get_by_id(league_id)
        if not league:
            return None

        # Fetch related data
        members = LeagueMember.get_members(league_id)
        races = Race.get_by_league(league_id)
        standings_list = RaceResult.get_standings(league_id, result_type="race")
        teams = Team.get_by_league(league_id)
        next_race = Race.get_next_race(league_id)

        # Batch fetch user details for all members
        user_ids = list({m.user_id for m in members} | {s["user_id"] for s in standings_list})
        users_map = User.get_users_by_ids(user_ids) if user_ids else {}

        # Build participants list (matches current frontend shape)
        participants = []
        admins = []
        for m in members:
            user = users_map.get(m.user_id)
            participant = {
                "email": user.email if user else "",
                "name": user.name if user else "",
                "league_user_name": m.display_name or (user.name if user else ""),
                "id": m.user_id,
            }
            participants.append(participant)
            if m.role in ("owner", "admin"):
                admins.append(user.email if user else m.user_id)

        # Build standings dict (matches current frontend shape)
        standings = {"overall": {}, "races": {}}
        for participant in participants:
            key = participant["email"] or participant["id"]
            standings["overall"][key] = {
                "points": 0, "wins": 0, "podiums": 0, "dnfs": 0, "fastestLaps": 0
            }
        for s in standings_list:
            user = users_map.get(s["user_id"])
            email = user.email if user else s["user_id"]
            standings["overall"][email] = {
                "points": s["points"],
                "wins": s["wins"],
                "podiums": s["podiums"],
                "dnfs": s["dnfs"],
                "fastestLaps": s["fastest_laps"],
            }

        # Build per-race results
        for race in races:
            if race.status == "Completed":
                race_results = RaceResult.get_by_race(str(race._id), result_type="race")
                race_standings = {}
                for rr in race_results:
                    user = users_map.get(rr.user_id)
                    email = user.email if user else rr.user_id
                    race_standings[email] = {
                        "position": rr.position,
                        "points": rr.points,
                        "fastest_lap": rr.fastest_lap,
                        "fastestLap": rr.fastest_lap,
                        "dnf": rr.dnf,
                        "wins": 1 if rr.position == 1 and not rr.dnf else 0,
                        "podiums": 1 if 1 <= rr.position <= 3 and not rr.dnf else 0,
                    }
                standings["races"][str(race._id)] = race_standings

        # Build teams dict (matches current frontend shape)
        teams_dict = {}
        for team in teams:
            team_member_details = []
            total_points = 0
            total_wins = 0
            total_podiums = 0
            total_dnfs = 0
            total_fastest_laps = 0

            for member_id in team.member_ids:
                user = users_map.get(member_id)
                email = user.email if user else member_id
                member_stats = standings["overall"].get(email, {
                    "points": 0, "wins": 0, "podiums": 0, "dnfs": 0, "fastestLaps": 0
                })
                total_points += member_stats.get("points", 0)
                total_wins += member_stats.get("wins", 0)
                total_podiums += member_stats.get("podiums", 0)
                total_dnfs += member_stats.get("dnfs", 0)
                total_fastest_laps += member_stats.get("fastestLaps", 0)

                team_member_details.append({
                    "email": email,
                    "name": user.name if user else member_id,
                    **member_stats,
                })

            teams_dict[team.name] = {
                "members": [users_map.get(mid).email if users_map.get(mid) else mid
                            for mid in team.member_ids],
                "total_points": total_points,
                "total_wins": total_wins,
                "total_podiums": total_podiums,
                "total_dnfs": total_dnfs,
                "total_fastest_laps": total_fastest_laps,
                "member_details": team_member_details,
            }

        # Find owner email
        owner_email = next(
            (p["email"] for p in participants
             if p["id"] == league.owner_id and p["email"]), league.owner_id
        )

        # Compose response — use frontend-compatible key names only
        result = {
            "_id": str(league._id),
            "name": league.name,
            "owner": owner_email,
            "public": league.public,
            "status": league.status,
            "max_players": league.max_players,
            "invite_code": league.invite_code,
            "created_at": league.created_at,
            "updated_at": league.updated_at,
            "deleted_at": league.deleted_at,
            "pointSystem": league.point_system,
            "fastestLapPoint": league.fastest_lap_point,
            "calendar": [r.serialize() for r in races],
            "standings": standings,
            "participants": participants,
            "participantsCount": len(participants),
            "next_race": next_race.serialize() if next_race else None,
            "admins": admins,
            "teams": teams_dict,
        }

        return result

    @staticmethod
    def get_my_leagues(user_id):
        """Get all leagues the current user is a member of"""
        memberships = LeagueMember.get_user_leagues(user_id)
        if not memberships:
            return []

        user = User.get_user_by_id(user_id)

        leagues = []
        for membership in memberships:
            league = League.get_by_id(str(membership.league_id))
            if not league:
                continue

            # Get position for this league
            standings = RaceResult.get_standings(str(league._id), result_type="race")
            position = None
            for s in standings:
                if s["user_id"] == user_id:
                    position = s["position"]
                    break

            # Resolve owner email
            owner_email = league.owner_id
            if league.owner_id == user_id and user:
                owner_email = user.email
            else:
                owner_user = User.get_user_by_id(league.owner_id)
                if owner_user:
                    owner_email = owner_user.email

            # Get next race
            next_race = Race.get_next_race(str(league._id))

            # Build clean league summary (no duplicate keys)
            league_data = {
                "_id": str(league._id),
                "name": league.name,
                "owner": owner_email,
                "public": league.public,
                "status": league.status,
                "max_players": league.max_players,
                "pointSystem": league.point_system,
                "fastestLapPoint": league.fastest_lap_point,
                "created_at": league.created_at,
                "updated_at": league.updated_at,
                "participantsCount": LeagueMember.get_member_count(str(league._id)),
                "position": position,
                "next_race": next_race.serialize() if next_race else None,
                "participants": [],
                "standings": {"overall": {}, "races": {}},
                "admins": [],
                "calendar": [],
                "teams": {},
            }

            leagues.append(league_data)

        return leagues

    @staticmethod
    def submit_race_result(league_id, race_id, results, result_type="race"):
        """
        Submit results for a race.

        Args:
            league_id: League ID string
            race_id: Race ID string
            results: Dict mapping user emails to results
                    Format: {'email@example.com': {'position': 1, 'fastest_lap': True, 'dnf': False}}
            result_type: "race" or "qualifying"
        """
        league = League.get_by_id(league_id)
        if not league:
            raise Exception("League not found")

        race = Race.get_by_id(race_id)
        if not race:
            raise Exception("Race not found")

        if str(race.league_id) != str(league._id):
            raise Exception("Race does not belong to this league")

        if result_type not in ("race", "qualifying"):
            raise ValueError("Invalid result type")
        if not isinstance(results, dict) or not results:
            raise ValueError("Race results must be a non-empty object")

        # Validate every driver before touching existing results.
        race_results = []
        positions = set()
        fastest_laps = 0
        for driver_email, result_data in results.items():
            # Look up user by email to get user_id
            user = User.get_user_by_mail(driver_email)
            if not user:
                raise Exception(f"User with email {driver_email} not found")
            if not LeagueMember.is_member(league_id, str(user._id)):
                raise ValueError(f"Participant {driver_email} is not in the league")
            if not isinstance(result_data, dict):
                raise ValueError("Each driver result must be an object")

            position = result_data.get("position")
            if type(position) is not int or position < 1 or position in positions:
                raise ValueError("Finishing positions must be unique positive integers")
            positions.add(position)
            fastest_lap = result_data.get("fastestLap", result_data.get("fastest_lap", False))
            dnf = result_data.get("dnf", False)
            if type(fastest_lap) is not bool or type(dnf) is not bool:
                raise ValueError("Fastest lap and DNF flags must be booleans")
            if dnf and fastest_lap:
                raise ValueError("A DNF driver cannot receive fastest lap points")
            fastest_laps += int(fastest_lap)
            if fastest_laps > 1:
                raise ValueError("Only one driver can have the fastest lap")

            # Calculate points
            points = 0 if dnf else league.point_system.get(str(position), 0)
            if not dnf and fastest_lap and league.fastest_lap_point > 0:
                points += league.fastest_lap_point

            race_results.append(RaceResult(
                race_id=ObjectId(race_id),
                league_id=league._id,
                user_id=str(user._id),
                result_type=result_type,
                position=position,
                points=points,
                fastest_lap=fastest_lap,
                dnf=dnf,
            ))

        RaceResult.replace_by_race(race_id, race_results, result_type)

        return LeagueService.get_league_detail(league_id)

    @staticmethod
    def get_league_standings(league_id):
        """Get computed standings for a league"""
        league = League.get_by_id(league_id)
        if not league:
            raise Exception("League not found")

        standings = RaceResult.get_standings(league_id, result_type="race")

        # Enrich with user details
        user_ids = [s["user_id"] for s in standings]
        users_map = User.get_users_by_ids(user_ids) if user_ids else {}

        for s in standings:
            user = users_map.get(s["user_id"])
            s["email"] = user.email if user else s["user_id"]
            s["name"] = user.name if user else s["user_id"]

        return standings

    @staticmethod
    def set_teams(league_id, teams_config):
        """Accept frontend emails or user IDs, and persist canonical user IDs."""
        league = League.get_by_id(league_id)
        if not league:
            raise Exception("League not found")

        if not isinstance(teams_config, dict):
            raise ValueError("Teams must be an object")
        normalized = {}
        assigned = set()
        for team_name, member_ids in teams_config.items():
            if not team_name or not isinstance(team_name, str):
                raise ValueError("Team name must be a non-empty string")
            if not member_ids or not isinstance(member_ids, list):
                raise ValueError(f"Team '{team_name}' must have a list of members")
            if len(member_ids) < 1 or len(member_ids) > 3:
                raise ValueError(f"Team '{team_name}' must have 1-3 members")
            normalized[team_name] = []
            for member_ref in member_ids:
                if not isinstance(member_ref, str):
                    raise ValueError("Team members must be emails or user IDs")
                user = User.get_user_by_mail(member_ref) or User.get_user_by_id(member_ref)
                if not user or not LeagueMember.is_member(league_id, str(user._id)):
                    raise ValueError(f"User '{member_ref}' is not a league member")
                mid = str(user._id)
                if mid in assigned:
                    raise ValueError("A member can belong to only one team")
                assigned.add(mid)
                normalized[team_name].append(mid)

        Team.set_teams_for_league(league_id, normalized)
        return LeagueService.get_teams(league_id)

    @staticmethod
    def get_teams(league_id):
        """Get all teams with calculated statistics"""
        league = League.get_by_id(league_id)
        if not league:
            raise Exception("League not found")

        teams = Team.get_by_league(league_id)
        standings = RaceResult.get_standings(league_id, result_type="race")
        standings_map = {s["user_id"]: s for s in standings}

        # Batch fetch users
        all_member_ids = []
        for team in teams:
            all_member_ids.extend(team.member_ids)
        users_map = User.get_users_by_ids(all_member_ids) if all_member_ids else {}

        teams_result = {}
        for team in teams:
            team_stats = {
                "members": [],
                "total_points": 0,
                "total_wins": 0,
                "total_podiums": 0,
                "total_dnfs": 0,
                "total_fastest_laps": 0,
                "member_details": [],
            }

            for mid in team.member_ids:
                user = users_map.get(mid)
                s = standings_map.get(mid, {
                    "points": 0, "wins": 0, "podiums": 0, "dnfs": 0, "fastest_laps": 0
                })

                team_stats["members"].append(user.email if user else mid)
                team_stats["total_points"] += s.get("points", 0)
                team_stats["total_wins"] += s.get("wins", 0)
                team_stats["total_podiums"] += s.get("podiums", 0)
                team_stats["total_dnfs"] += s.get("dnfs", 0)
                team_stats["total_fastest_laps"] += s.get("fastest_laps", 0)

                team_stats["member_details"].append({
                    "email": user.email if user else mid,
                    "name": user.name if user else mid,
                    "points": s.get("points", 0),
                    "wins": s.get("wins", 0),
                    "podiums": s.get("podiums", 0),
                    "dnfs": s.get("dnfs", 0),
                    "fastestLaps": s.get("fastest_laps", 0),
                })

            teams_result[team.name] = team_stats

        return teams_result

    @staticmethod
    def get_team_standings(league_id):
        """Get teams sorted by total points"""
        teams = LeagueService.get_teams(league_id)

        sorted_teams = sorted(
            [{"name": name, **stats} for name, stats in teams.items()],
            key=lambda x: (x["total_points"], x["total_wins"], x["total_podiums"]),
            reverse=True,
        )

        for i, team in enumerate(sorted_teams):
            team["position"] = i + 1

        return sorted_teams

    @staticmethod
    def remove_team(league_id, team_name):
        """Remove a team by name"""
        teams = Team.get_by_league(league_id)
        for team in teams:
            if team.name == team_name:
                Team.delete(str(team._id))
                return {"message": f"Team '{team_name}' removed successfully"}
        raise Exception("Team not found")

    @staticmethod
    def extract_race_results(image_files):
        """Extract race results from images using OpenAI"""
        image_data = []
        temp_files = []

        for file in image_files:
            temp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            file.save(temp.name)
            temp_files.append(temp.name)

            buffer = BytesIO()
            file.save(buffer, format="JPEG")
            buffer.seek(0)
            encoded_image = base64.b64encode(buffer.read()).decode('utf-8')

            image_data.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{encoded_image}"
                }
            })

        prompt = """
        Analyze the image(s) and extract any race result tables or listings.

        Return the data in JSON format like this:
        [
          {
            "position": 1,
            "driver": "Name",
            "team": "Team Name",
            "time": "1:23.456"
          },
          ...
        ]
        If information is missing, fill only what is available.
        """

        messages = [
            {
                "role": "system",
                "content": "You are an AI assistant that extracts structured data from images."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    *image_data
                ]
            }
        ]

        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages
        )

        content = response.choices[0].message.content

        import json
        import re

        json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            json_string = json_match.group(1)
        else:
            json_string = content

        try:
            race_results = json.loads(json_string)
            return race_results
        except json.JSONDecodeError as e:
            return {
                "error": "Failed to parse JSON",
                "raw_content": content,
                "json_error": str(e)
            }
