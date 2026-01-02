from bson.objectid import ObjectId
from src.config.mongo import db
from datetime import datetime, timezone
from src.league_module.race import Race
from src.user_module.user import User

class League:
    def __init__(self, name, owner, public, calendar, pointSystem, status, max_players=20, fastestLapPoint=0, _id=None, standings={}, participants=[], admins=[], created_at=None, updated_at=None, deleted_at=None, teams=None):
        self._id = _id
        self.admins = admins
        self.calendar = calendar
        self.created_at = created_at if created_at is not None else datetime.now(timezone.utc)
        self.deleted_at = deleted_at
        self.fastestLapPoint = fastestLapPoint
        self.max_players = max_players
        self.name = name
        self.owner = owner
        self.participants = participants
        self.pointSystem = pointSystem
        self.public = public
        self.standings = standings if standings else {"overall": {}, "races": {}}
        self.updated_at = updated_at
        self.participantsCount = len(participants)
        self.next_race = self.get_next_race()
        self.status = status
        self.teams = teams if teams else {}
        # Teams structure stored in DB:
        # {
        #     "Red Bull": ["email1@example.com", "email2@example.com"],
        #     "Ferrari": ["email3@example.com"]
        # }

    def get_next_race(self):
        """Find the next upcoming race in the calendar"""
        if not self.calendar or len(self.calendar) == 0:
            return None

        next_race = None
        # Make current_time timezone aware
        current_time = datetime.now(timezone.utc)

        for race in self.calendar:
            # Ensure race date is a proper datetime object and timezone aware
            race_date = race.date
            if isinstance(race_date, str):
                # If somehow we still have a string, parse it
                try:
                    if race_date.endswith('Z'):
                        race_date = datetime.fromisoformat(race_date.replace('Z', '+00:00'))
                    else:
                        race_date = datetime.fromisoformat(race_date)
                        if not race_date.tzinfo:
                            race_date = race_date.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    continue  # Skip this race if we can't parse the date
            elif isinstance(race_date, datetime):
                if not race_date.tzinfo:
                    # If race date is naive, assume it's in UTC
                    race_date = race_date.replace(tzinfo=timezone.utc)
            else:
                continue  # Skip if date is neither string nor datetime

            if race.status == "Upcoming" and race_date > current_time:
                if next_race is None:
                    next_race = race
                else:
                    next_race_date = next_race.date
                    if isinstance(next_race_date, str):
                        try:
                            if next_race_date.endswith('Z'):
                                next_race_date = datetime.fromisoformat(next_race_date.replace('Z', '+00:00'))
                            else:
                                next_race_date = datetime.fromisoformat(next_race_date)
                                if not next_race_date.tzinfo:
                                    next_race_date = next_race_date.replace(tzinfo=timezone.utc)
                        except (ValueError, TypeError):
                            next_race = race
                            continue
                    elif isinstance(next_race_date, datetime) and not next_race_date.tzinfo:
                        next_race_date = next_race_date.replace(tzinfo=timezone.utc)
                    
                    if race_date < next_race_date:
                        next_race = race

        return next_race

    def serialize(self):
        calendar_serialized = [race.serialize() for race in self.calendar] if self.calendar else []
        next_race_serialized = self.next_race.serialize() if self.next_race else None
        detailed_participants = self.get_participants_with_details()

        result = {
            "_id": str(self._id) if self._id else None,
            "name": self.name,
            "owner": self.owner,
            "public": self.public,
            "calendar": calendar_serialized,
            "pointSystem": self.pointSystem,
            "max_players": self.max_players,
            "fastestLapPoint": self.fastestLapPoint,
            "standings": self.standings,
            "participants": detailed_participants,
            "participantsCount": self.participantsCount,
            "next_race": next_race_serialized,
            "status": self.status,
            "admins": self.admins,
            "teams": self.get_teams(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "deleted_at": self.deleted_at
        }
        if hasattr(self, 'position'):
            result["position"] = self.position

        return result

    def get_participants_with_details(self):
        """Fetch detailed information for all participants"""
        participants_with_details = []

        for participant in self.participants:
            # Handle both old format (string) and new format (dict)
            if isinstance(participant, str):
                email = participant
                league_user_name = None
            else:
                email = participant.get('email')
                league_user_name = participant.get('league_user_name')
            
            user = User.get_user_by_mail(email)
            if user:
                participants_with_details.append({
                    "email": email,
                    "name": user.name,
                    "league_user_name": league_user_name or user.name,
                    "id": str(user._id)
                })
            else:
                # Include at least the email if user not found
                participants_with_details.append({
                    "email": email,
                    "league_user_name": league_user_name or email
                })

        return participants_with_details

    @staticmethod
    def get_league_by_id(league_id):
        league_data = db.leagues.find_one({"_id": ObjectId(league_id)})
        if league_data:
            return League._create_league_from_document(league_data)
        return None

    def save(self):
        """Save or update the league in MongoDB"""
        self.participantsCount = len(self.participants)
        self.updated_at = datetime.now(timezone.utc)

        if self._id:
            # Update existing league
            db.leagues.update_one(
                {"_id": self._id},
                {"$set": {
                    "name": self.name,
                    "owner": self.owner,
                    "public": self.public,
                    "calendar": [race.serialize() for race in self.calendar],
                    "pointSystem": self.pointSystem,
                    "max_players": self.max_players,
                    "fastestLapPoint": self.fastestLapPoint,
                    "status": self.status,
                    "updated_at": self.updated_at,
                    "participants": self.participants,
                    "admins": self.admins,
                    "standings": self.standings,
                    "teams": self.teams
                }}
            )
        else:
            # Create new league
            league = {
                "name": self.name,
                "owner": self.owner,
                "public": self.public,
                "calendar": [race.serialize() for race in self.calendar],
                "pointSystem": self.pointSystem,
                "max_players": self.max_players,
                "fastestLapPoint": self.fastestLapPoint,
                "standings": self.standings,
                "participants": self.participants,
                "admins": self.admins,
                "status": self.status,
                "teams": self.teams,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "deleted_at": self.deleted_at,
            }
            result = db.leagues.insert_one(league)
            self._id = result.inserted_id

    def add_race_result(self, race_id, results):
        """
        Add race results to standings with extended statistics

        Args:
            race_id: The ID of the race
            results: Dict mapping user emails to their results with extended stats
                    Format: {'email@example.com': {
                        'position': 1,
                        'fastest_lap': True,
                        'dnf': False,
                        'wins': 1,
                        'podiums': 1
                    }}
        """
        race_id = str(race_id)

        # Initialize race results if not exists
        if "races" not in self.standings:
            self.standings["races"] = {}

        self.standings["races"][race_id] = {}

        # Process each participant's result
        for participant, result in results.items():
            position = int(result.get('position', 0))
            fastest_lap = result.get('fastest_lap', False)
            dnf = result.get('dnf', False)

            # Calculate points based on position - no points for DNF
            points = 0 if dnf else self.pointSystem.get(str(position), 0)

            # Add fastest lap point if applicable
            if fastest_lap and self.fastestLapPoint > 0:
                points += self.fastestLapPoint

            # Store race result with extended statistics
            self.standings["races"][race_id][participant] = {
                "position": position,
                "points": points,
                "fastest_lap": fastest_lap,
                "dnf": dnf,
                "wins": result.get('wins', 0),
                "podiums": result.get('podiums', 0)
            }

        # Recalculate overall standings
        self.calculate_overall_standings()

        # Change race status to completed
        for race in self.calendar:
            if str(race._id) == race_id:
                race.status = "Completed"
                break

        # Save changes to database
        self.save()

        return self.standings

    def calculate_overall_standings(self):
        """Recalculate overall standings with extended statistics based on all race results"""
        overall = {}

        # Initialize all participants with zero values for all stats
        for participant in self.participants:
            # Handle both old format (string) and new format (dict)
            email = participant if isinstance(participant, str) else participant.get('email')
            overall[email] = {
                "points": 0,
                "wins": 0,
                "podiums": 0,
                "dnfs": 0,
                "fastestLaps": 0
            }

        # Sum points and stats from all races
        if "races" in self.standings:
            for race_id, race_results in self.standings["races"].items():
                for participant, result in race_results.items():
                    if participant not in overall:
                        overall[participant] = {
                            "points": 0,
                            "wins": 0,
                            "podiums": 0,
                            "dnfs": 0,
                            "fastestLaps": 0
                        }

                    # Accumulate statistics
                    overall[participant]["points"] += result.get("points", 0)
                    overall[participant]["wins"] += 1 if result.get("wins", 0) > 0 else 0
                    overall[participant]["podiums"] += 1 if result.get("podiums", 0) > 0 else 0
                    overall[participant]["dnfs"] += 1 if result.get("dnf", False) else 0
                    overall[participant]["fastestLaps"] += 1 if result.get("fastest_lap", False) else 0

        self.standings["overall"] = overall
        return overall

    def get_participant_standings(self, participant):
        """Get standings for a specific participant"""
        results = {
            "overall": self.standings.get("overall", {}).get(participant, 0),
            "races": {}
        }

        if "races" in self.standings:
            for race_id, race_results in self.standings["races"].items():
                if participant in race_results:
                    results["races"][race_id] = race_results[participant]

        return results

    @staticmethod
    def delete_league(league_id):
        db.leagues.update_one(
            {"_id": ObjectId(league_id)},
            {"$set": {"deleted_at": datetime.now(timezone.utc)}}
        )

    @staticmethod
    def get_all_leagues():
        leagues = db.leagues.find({
            "deleted_at": None,
            "public": True
        })
        return [League._create_league_from_document(league) for league in leagues]
    
    @staticmethod
    def get_all_leagues_pagination(page=1, page_size=10):
        leagues = db.leagues.find().skip((page - 1) * page_size).limit(page_size)
        return [League._create_league_from_document(league) for league in leagues]
    
    @staticmethod
    def get_leagues_by_owner(owner_email):
        leagues = db.leagues.find({"owner": owner_email})
        return [League._create_league_from_document(league) for league in leagues]
    
    @staticmethod
    def get_leagues_by_participant(participant_email):
        # Query supports both old format (string array) and new format (object array)
        agg = [
            {
            "$match": {
                "$or": [
                    {"participants": {"$in": [participant_email]}},  # Old format
                    {"participants.email": participant_email}  # New format
                ]
            }
            }
        ]
        leagues = db.leagues.aggregate(agg)
        return [League._create_league_from_document(league) for league in leagues]
    
    @staticmethod
    def get_public_leagues():
        leagues = db.leagues.find({"public": True})
        return [League._create_league_from_document(league) for league in leagues]

    def add_participant(self, participant_email, user_name=None, league_user_name=None):
        # Check if participant already exists (handle both formats)
        for p in self.participants:
            existing_email = p if isinstance(p, str) else p.get('email')
            if existing_email == participant_email:
                return

        # Create participant object with email and league_user_name
        participant_obj = {
            "email": participant_email,
            "league_user_name": league_user_name or user_name or participant_email
        }

        # Add to participants list in the database
        db.leagues.update_one(
            {"_id": self._id},
            {"$push": {"participants": participant_obj}}
        )

        # Add to local participants list
        self.participants.append(participant_obj)

        # Initialize participant in standings with 0 points
        if "overall" not in self.standings:
            self.standings["overall"] = {}

        self.standings["overall"][participant_email] = {
            "name": user_name,
            "points": 0,
            "wins": 0,
            "podiums": 0,
            "dnfs": 0,
            "fastestLaps": 0
        }

        # Update standings in database
        db.leagues.update_one(
            {"_id": self._id},
            {"$set": {"standings": self.standings}}
        )

        # Update participant count
        self.participantsCount = len(self.participants)

    def remove_participant(self, participant_email):
        # Check if participant exists (handle both formats)
        participant_exists = False
        for p in self.participants:
            existing_email = p if isinstance(p, str) else p.get('email')
            if existing_email == participant_email:
                participant_exists = True
                break
        
        if participant_exists:
            # Remove using both possible formats
            db.leagues.update_one(
                {"_id": ObjectId(self._id)},
                {"$pull": {
                    "participants": {
                        "$or": [
                            participant_email,  # Old format (string)
                            {"email": participant_email}  # New format (object)
                        ]
                    }
                }}
            )
            # Also try direct pull for both formats separately as fallback
            db.leagues.update_one(
                {"_id": ObjectId(self._id)},
                {"$pull": {"participants": participant_email}}
            )
            db.leagues.update_one(
                {"_id": ObjectId(self._id)},
                {"$pull": {"participants": {"email": participant_email}}}
            )
            
            # Update local list
            self.participants = [p for p in self.participants 
                               if (p if isinstance(p, str) else p.get('email')) != participant_email]
            self.participantsCount = len(self.participants)

    def set_teams(self, teams_config):
        """
        Create/update teams from a configuration dictionary
        
        Args:
            teams_config: Dict mapping team names to member email lists
                         Format: {"Team Name": ["email1@example.com", "email2@example.com"]}
        
        Returns:
            The updated teams dictionary
        
        Raises:
            ValueError: If validation fails
        """
        # Validate all teams
        all_assigned_members = []
        
        # Build a list of participant emails for validation
        participant_emails = [p if isinstance(p, str) else p.get('email') for p in self.participants]
        
        for team_name, members in teams_config.items():
            if not team_name or not isinstance(team_name, str):
                raise ValueError("Team name must be a non-empty string")
            
            if not members or not isinstance(members, list):
                raise ValueError(f"Team '{team_name}' must have a list of members")
            
            if len(members) < 1 or len(members) > 3:
                raise ValueError(f"Team '{team_name}' must have 1-3 members, got {len(members)}")
            
            # Validate all members are participants
            for member in members:
                if member not in participant_emails:
                    raise ValueError(f"Member '{member}' in team '{team_name}' is not a league participant")
                
                # Check for duplicate assignments
                if member in all_assigned_members:
                    raise ValueError(f"Member '{member}' is assigned to multiple teams")
                all_assigned_members.append(member)
        
        # All validations passed, update teams
        self.teams = teams_config
        
        # Save to database
        db.leagues.update_one(
            {"_id": self._id},
            {"$set": {"teams": self.teams}}
        )
        
        return self.teams

    def get_teams(self):
        """
        Get all teams with calculated total points from member standings
        
        Returns:
            Dict with team details and aggregated statistics
            Format: {
                "Team Name": {
                    "members": ["email1", "email2"],
                    "total_points": 150,
                    "total_wins": 3,
                    "total_podiums": 5,
                    "total_dnfs": 1,
                    "total_fastest_laps": 2,
                    "member_details": [
                        {"email": "email1", "name": "John", "points": 100, ...},
                        {"email": "email2", "name": "Jane", "points": 50, ...}
                    ]
                }
            }
        """
        teams_with_stats = {}
        overall_standings = self.standings.get("overall", {})
        
        for team_name, members in self.teams.items():
            team_stats = {
                "members": members,
                "total_points": 0,
                "total_wins": 0,
                "total_podiums": 0,
                "total_dnfs": 0,
                "total_fastest_laps": 0,
                "member_details": []
            }
            
            for member_email in members:
                # Get member's standings
                member_standings = overall_standings.get(member_email, {
                    "points": 0,
                    "wins": 0,
                    "podiums": 0,
                    "dnfs": 0,
                    "fastestLaps": 0
                })
                
                # Get member's name
                user = User.get_user_by_mail(member_email)
                member_name = user.name if user else member_email
                
                # Aggregate team totals
                team_stats["total_points"] += member_standings.get("points", 0)
                team_stats["total_wins"] += member_standings.get("wins", 0)
                team_stats["total_podiums"] += member_standings.get("podiums", 0)
                team_stats["total_dnfs"] += member_standings.get("dnfs", 0)
                team_stats["total_fastest_laps"] += member_standings.get("fastestLaps", 0)
                
                # Add member details
                team_stats["member_details"].append({
                    "email": member_email,
                    "name": member_name,
                    "points": member_standings.get("points", 0),
                    "wins": member_standings.get("wins", 0),
                    "podiums": member_standings.get("podiums", 0),
                    "dnfs": member_standings.get("dnfs", 0),
                    "fastestLaps": member_standings.get("fastestLaps", 0)
                })
            
            teams_with_stats[team_name] = team_stats
        
        return teams_with_stats

    def get_team_standings(self):
        """
        Get teams sorted by total points (for leaderboard)
        
        Returns:
            List of teams sorted by total_points descending
        """
        teams_with_stats = self.get_teams()
        
        sorted_teams = sorted(
            [{"name": name, **stats} for name, stats in teams_with_stats.items()],
            key=lambda x: (x["total_points"], x["total_wins"], x["total_podiums"]),
            reverse=True
        )
        
        # Add position
        for i, team in enumerate(sorted_teams):
            team["position"] = i + 1
        
        return sorted_teams

    def get_participant_team(self, participant_email):
        """Get the team name a participant belongs to"""
        for team_name, members in self.teams.items():
            if participant_email in members:
                return team_name
        return None

    def remove_team(self, team_name):
        """Remove a team by name"""
        if team_name in self.teams:
            del self.teams[team_name]
            db.leagues.update_one(
                {"_id": self._id},
                {"$unset": {f"teams.{team_name}": ""}}
            )

    @staticmethod
    def _create_league_from_document(league_data):
        # Convert stored calendar data back to Race objects
        # Make sure Race.deserialize properly preserves original dates
        calendar = []
        if 'calendar' in league_data and league_data['calendar']:
            calendar = [Race.deserialize(race_data) for race_data in league_data['calendar']]

        return League(
            _id=league_data.get('_id'),
            name=league_data.get('name'),
            owner=league_data.get('owner'),
            public=league_data.get('public', False),
            calendar=calendar,
            pointSystem=league_data.get('pointSystem', {}),
            status=league_data.get('status'),
            max_players=league_data.get('max_players', 20),
            fastestLapPoint=league_data.get('fastestLapPoint', 0),
            standings=league_data.get('standings', {}),
            participants=league_data.get('participants', []),
            admins=league_data.get('admins', []),
            created_at=league_data.get('created_at', datetime.now(timezone.utc)),
            updated_at=league_data.get('updated_at'),
            deleted_at=league_data.get('deleted_at'),
            teams=league_data.get('teams', {})
        )