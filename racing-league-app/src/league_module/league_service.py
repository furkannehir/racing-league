from src.league_module.league import League
from src.auth_module.auth_service import AuthService
from src.config.config import Config
from firebase_admin import auth
import tempfile
import os
from openai import OpenAI
from io import BytesIO
import base64

client = OpenAI(
    # This is the default and can be omitted
    api_key=Config.OPENAI_API_KEY
)

class LeagueService:
    
    @staticmethod
    def create_league(data):
        uid = AuthService.get_current_user()
        owner = auth.get_user(uid)
        data["owner"] = owner.email

        # Convert date strings to datetime objects for calendar entries
        if 'calendar' in data and data['calendar']:
            from datetime import datetime
            for race in data['calendar']:
                if 'date' in race and isinstance(race['date'], str):
                    try:
                        race['date'] = datetime.fromisoformat(race['date'].replace('Z', '+00:00'))
                    except (ValueError, TypeError):
                        race['date'] = datetime.now()

        league = League._create_league_from_document(data)
        league.save()
        return league
    
    @staticmethod
    def update_league(league: League, data):
        league.name = data.get('name')
        league.public = data.get('public')
        league.calendar = data.get('calendar')
        league.pointSystem = data.get('pointSystem')
        league.fastestLapPoint = data.get('fastestLapPoint')
        league.save()
        return league

    @staticmethod
    def get_my_leagues():
        uid = AuthService.get_current_user()
        owner = auth.get_user(uid)
        email = owner.email

        # Get leagues owned by the user
        owned_leagues = League.get_leagues_by_owner(email)

        # Create a dictionary to track leagues by their ID
        league_dict = {str(league._id): league for league in owned_leagues}

        # Get leagues where user is a participant
        participant_leagues = League.get_leagues_by_participant(email)

        # Add participant leagues to the dictionary if not already there
        for league in participant_leagues:
            league_id = str(league._id)
            if league_id not in league_dict:
                league_dict[league_id] = league

        # Get unique leagues
        leagues = list(league_dict.values())
        # Add position information to each league
        for league in leagues:
            # Get standings info for each league
            if "overall" in league.standings:
                # Get all participants' points and sort them in descending order
                points_list = [(participant, data.get('points', 0)) for participant, data in
                               league.standings["overall"].items()]
                points_list.sort(key=lambda x: x[1], reverse=True)

                # Find user's position
                position = 1
                for i, (participant, points) in enumerate(points_list):
                    if participant == email:
                        # Handle ties (same points get same position)
                        if i > 0 and points_list[i - 1][1] == points:
                            # If tied with previous participant, use their position
                            position = next((j for j, (_, p) in enumerate(points_list)
                                             if p == points), i) + 1
                        else:
                            position = i + 1
                        break

                # Add position info to league object
                league.position = position
            else:
                # No standings data yet
                league.position = None

        return leagues
    
    @staticmethod
    def get_leagues_by_participant(email):
        return League.get_leagues_by_participant(email)
    
    def get_leagues_by_owner(email):
        return League.get_leagues_by_owner(email)

    @staticmethod
    def get_league_by_id(league_id):
        return League.get_league_by_id(league_id)

    @staticmethod
    def submit_race_result(league_id, race_id, results):
        """
        Submit results for a race in a league with extended statistics tracking

        Args:
            league_id: The ID of the league
            race_id: The ID of the race
            results: Dict mapping user emails to their results
                    Format: {'email@example.com': {'position': 1, 'fastest_lap': True, 'dnf': False}}
        """
        league = League.get_league_by_id(league_id)
        if not league:
            raise Exception("League not found")

        # Verify race exists in the calendar
        race_exists = False
        for race in league.calendar:
            if str(race._id) == race_id:
                race_exists = True
                break

        if not race_exists:
            raise Exception("Race not found in league calendar")

        # Verify all participants in results are in the league
        for participant in results.keys():
            if participant not in league.participants:
                raise Exception(f"Participant {participant} is not in the league")

        # Process extended statistics from results
        enhanced_results = {}
        for driver, result in results.items():
            position = result.get('position')
            enhanced_results[driver] = {
                'position': position,
                'fastest_lap': result.get('fastest_lap', False),
                'dnf': result.get('dnf', False),
                'wins': 1 if position == 1 else 0,
                'podiums': 1 if position and position <= 3 else 0,
            }

        # Submit the enhanced results including statistics
        return league.add_race_result(race_id, enhanced_results)

    @staticmethod
    def get_league_standings(league_id):
        """Get the current standings for a league"""
        league = League.get_league_by_id(league_id)
        if not league:
            raise Exception("League not found")

        return league.standings

    @staticmethod
    def get_participant_standings(league_id, participant_email):
        """Get standings for a specific participant in a league"""
        league = League.get_league_by_id(league_id)
        if not league:
            raise Exception("League not found")

        if participant_email not in league.participants:
            raise Exception("Participant not found in league")

        return league.get_participant_standings(participant_email)

    @staticmethod
    def extract_race_results(image_files):
        # Save temp files and create OpenAI image URL objects
        image_data = []
        temp_files = []

        for file in image_files:
            temp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            file.save(temp.name)
            temp_files.append(temp.name)

            # Convert Image to base64 string
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

        # Prompt to extract structured results
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

        # Create messages with system prompt and images
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

        # Make API call with correct format
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages
        )

        return response.choices[0].message.content