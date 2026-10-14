from src.user_module.user import User
from src.league_module.race import Race
from src.league_module.league_member import LeagueMember
from src.user_module.account_validation import validate_name, validate_bio


class UserService:

    @staticmethod
    def update_profile(user, data):
        if not isinstance(data, dict) or not data:
            raise ValueError('Provide a name or bio to update')
        if set(data) - {'name', 'bio', 'email'}:
            raise ValueError('Only name and bio can be updated')
        if 'email' in data:
            email = data['email']
            if not isinstance(email, str) or email.strip().casefold() != user.email.casefold():
                raise ValueError('Email changes are not supported by profile updates')
        fields = {}
        if 'name' in data:
            fields['name'] = validate_name(data['name'])
        if 'bio' in data:
            fields['bio'] = validate_bio(data['bio'])
        if not fields:
            raise ValueError('Provide a name or bio to update')
        return User.update_profile(user._id, fields)

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
