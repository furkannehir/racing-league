from bson.objectid import ObjectId
from src.config.mongo import db
from datetime import datetime, timezone
from src.league_module.race import Race
from src.user_module.user import User

class League:
    def __init__(self, name, owner, public, calendar, pointSystem, status, max_players=20, fastestLapPoint=0, _id=None, standings={}, participants=[], admins=[], created_at=datetime.now(), updated_at=None, deleted_at=None):
        self._id = _id
        self.admins = admins
        self.calendar = calendar
        self.created_at = created_at
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

    def get_next_race(self):
        """Find the next upcoming race in the calendar"""
        if not self.calendar or len(self.calendar) == 0:
            return None

        next_race = None
        # Make current_time timezone aware
        current_time = datetime.now(timezone.utc)

        for race in self.calendar:
            # Ensure race date is timezone aware for proper comparison
            race_date = race.date
            if not race_date.tzinfo:
                # If race date is naive, assume it's in UTC
                race_date = race_date.replace(tzinfo=timezone.utc)

            if race.status == "Upcoming" and race_date > current_time:
                if next_race is None or race_date < next_race.date:
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

        for email in self.participants:
            user = User.get_user_by_mail(email)
            if user:
                participants_with_details.append({
                    "email": email,
                    "name": user.name,
                    "id": str(user._id)
                })
            else:
                # Include at least the email if user not found
                participants_with_details.append({"email": email})

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
        self.updated_at = datetime.now()

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
                    "standings": self.standings
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
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "deleted_at": self.deleted_at,
            }
            result = db.leagues.insert_one(league)
            self._id = result.inserted_id

    def add_race_result(self, race_id, results):
        """
        Add race results to standings
        results is a dict: {
            'email@example.com': {'position': 1, 'fastest_lap': True}
        }
        """
        race_id = str(race_id)

        # Initialize race results if not exists
        if "races" not in self.standings:
            self.standings["races"] = {}

        self.standings["races"][race_id] = {}

        # Process each participant's result
        for participant, result in results.items():
            position = int(result['position'])
            fastest_lap = result.get('fastest_lap', False)

            # Calculate points based on position
            points = self.pointSystem.get(str(position), 0)

            # Add fastest lap point if applicable
            if fastest_lap and self.fastestLapPoint > 0:
                points += self.fastestLapPoint

            # Store race result
            self.standings["races"][race_id][participant] = {
                "position": position,
                "points": points,
                "fastest_lap": fastest_lap
            }

        # Recalculate overall standings
        self.calculate_overall_standings()

        # Change race status to completed
        for race in self.calendar:
            if race._id == race_id:
                race.status = "Completed"

        # Save changes to database
        self.save()



        return self.standings

    def calculate_overall_standings(self):
        """Recalculate overall standings based on all race results"""
        overall = {}

        # Initialize all participants with zero points
        for participant in self.participants:
            overall[participant] = 0

        # Sum points from all races
        if "races" in self.standings:
            for race_id, race_results in self.standings["races"].items():
                for participant, result in race_results.items():
                    if participant not in overall:
                        overall[participant] = 0
                    overall[participant] += result["points"]

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
            {"$set": {"deleted_at": datetime.now()}}
        )

    @staticmethod
    def get_all_leagues():
        leagues = db.leagues.find()
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
        agg = [
            {
            "$match": {
                "participants": {"$in": [participant_email]}
            }
            }
        ]
        leagues = db.leagues.aggregate(agg)
        return [League._create_league_from_document(league) for league in leagues]
    
    @staticmethod
    def get_public_leagues():
        leagues = db.leagues.find({"public": True})
        return [League._create_league_from_document(league) for league in leagues]

    def add_participant(self, participant_email):
        if participant_email in self.participants:
            return

        # Add to participants list in the database
        db.leagues.update_one(
            {"_id": self._id},
            {"$push": {"participants": participant_email}}
        )

        # Add to local participants list
        self.participants.append(participant_email)

        # Initialize participant in standings with 0 points
        if "overall" not in self.standings:
            self.standings["overall"] = {}

        self.standings["overall"][participant_email] = 0

        # Update standings in database
        db.leagues.update_one(
            {"_id": self._id},
            {"$set": {"standings": self.standings}}
        )

        # Update participant count
        self.participantsCount = len(self.participants)

    def remove_participant(self, participant_id):
        if participant_id in self.participants:
            db.leagues.update_one(
                {"_id": ObjectId(self._id)},
                {"$pull": {"participants": participant_id}}
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
            created_at=league_data.get('created_at', datetime.now()),
            updated_at=league_data.get('updated_at'),
            deleted_at=league_data.get('deleted_at')
        )