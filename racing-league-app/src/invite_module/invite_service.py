from src.league_module.league_service import LeagueService
from src.invite_module.invite import Invite
from src.auth_module.auth_service import AuthService
from firebase_admin import auth
from src.user_module.user import User

class InviteService:

    @staticmethod
    def get_all_invites():
        return Invite.get_all_invites()

    @staticmethod
    def create_invite(email, league_id):
        uid = AuthService.get_current_user()
        user = auth.get_user(uid)
        inviter = User.get_user_by_mail(user.email)

        if not inviter:
            raise Exception("User not found")
        if not LeagueService.get_league_by_id(league_id):
            raise Exception("League not found")
        invites = Invite.get_invites_by_user(email)
        if len(invites) > 0:
            for invite in invites:
                if invite.invited_user == email and str(invite.league._id) == league_id:
                    raise Exception("Invite already sent")

        invite = Invite(
            league=LeagueService.get_league_by_id(league_id),
            inviter=inviter,
            invited_user=email,
            status="pending"
        )
        invite.save()
        return invite

    @staticmethod
    def get_invites_by_user(email):
        return Invite.get_invites_by_user(email)

    @staticmethod
    def get_sent_invites_by_user(email):
        return Invite.get_sent_invites_by_user(email)

    @staticmethod
    def accept_invite(invite_id):
        uid = AuthService.get_current_user()
        user = auth.get_user(uid)
        invite = Invite.get_invite_by_id(invite_id)
        if not invite:
            raise Exception("Invite not found")
        if user.email != invite.invited_user:
            raise Exception("You are not allowed to accept this invite")
        invite = Invite.get_invite_by_id(invite_id)
        if invite.status != "pending":
            raise Exception("Invite is not pending")
        invite.league.add_participant(user.email)
        invite.accept()
        return invite

    @staticmethod
    def decline_invite(invite_id):
        uid = AuthService.get_current_user()
        user = auth.get_user(uid)
        invite = Invite.get_invite_by_id(invite_id)
        if user.email != invite.invited_user:
            raise Exception("You are not allowed to reject this invite")
        invite = Invite.get_invite_by_id(invite_id)
        if invite.status != "pending":
            raise Exception("Invite is not pending")
        invite.status = "declined"
        invite.save()
        return invite

    @staticmethod
    def delete_invite(invite_id):
        uid = AuthService.get_current_user()
        user = auth.get_user(uid)
        invite = Invite.get_invite_by_id(invite_id)
        if user.email != invite.inviter:
            raise Exception("You are not allowed to delete this invite")
        invite.status = "deleted"
        invite.save()
        return invite
