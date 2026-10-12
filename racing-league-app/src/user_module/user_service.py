from src.user_module.user import User
from src.league_module.race import Race
from src.league_module.league_member import LeagueMember


class UserService:

    @staticmethod
    def get_next_race_of_user(user_id):
        """Get the next upcoming race for any league the user is in"""
        memberships = LeagueMember.get_user_leagues(user_id)

        next_race = None
        for membership in memberships:
            race = Race.get_next_race(str(membership.league_id))
            if race:
                if next_race is None or race.date < next_race.date:
                    next_race = race

        return next_race
