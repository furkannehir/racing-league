from src.user_module.user import User
from src.league_module.league import League
from datetime import datetime


class UserService:

    @staticmethod
    def get_next_race_of_user(email):
        user = User.get_user_by_mail(email)
        if user:
            leagues = user.leagues
            for league in leagues:
                league = League.get_league_by_id(league)
                if league and league.calendar:
                    league.calendar.sort(key=lambda x: x['date'])
                    for race in league.calendar:
                        if race.get('date') > datetime.now():
                            return race