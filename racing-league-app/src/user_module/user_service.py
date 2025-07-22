from src.user_module.user import User
from src.league_module.league import League
from datetime import datetime, timezone


class UserService:

    @staticmethod
    def get_next_race_of_user(email):
        user = User.get_user_by_mail(email)
        if user:
            leagues = user.leagues
            for league in leagues:
                league = League.get_league_by_id(league)
                if league and league.calendar:
                    # Use the league's get_next_race method which properly handles timezone-aware comparisons
                    next_race = league.get_next_race()
                    if next_race:
                        return next_race