from bson.objectid import ObjectId
from src.invite_module.invite import Invite
from src.league_module.league import League
from src.league_module.league_member import LeagueMember
from src.auth_module.auth_service import AuthService
from src.user_module.user import User
from src.email_module.email_service import EmailService


class InviteService:

    @staticmethod
    def create_invite(email, league_id):
        """Create a single invite"""
        inviter = AuthService.get_current_mongo_user()
        if not inviter:
            raise Exception("User not found")

        league = League.get_by_id(league_id)
        if not league:
            raise Exception("League not found")
        if not LeagueMember.is_admin_or_owner(league_id, str(inviter._id)):
            raise ValueError("Only league owners or admins can send invites")

        # Check if invite already exists
        if Invite.exists(email, league_id):
            raise Exception("Invite already sent to this user")

        # Check if user is already a member
        invitee = User.get_user_by_mail(email)
        if invitee and LeagueMember.is_member(league_id, str(invitee._id)):
            raise Exception("User is already a member of this league")

        invite = Invite(
            league_id=ObjectId(league_id),
            inviter_id=str(inviter._id),  # Store MongoDB _id
            invited_email=email,
            status="pending",
        )
        invite.save()

        # Send email notification
        invitee_name = invitee.name if invitee else email
        EmailService.send_custom_email(
            to_email=email,
            name=invitee_name,
            subject="You're invited to join a league!",
            message_top="You have been invited to join a league. Log in to your account to accept or decline the invitation. If you're not registered yet, you can sign up to join the league.",
            message_bottom="If you have any questions, feel free to reach out to us.",
            button_name="View Invitation",
            url="https://yourapp.com/invites",
        )

        return invite

    @staticmethod
    def create_invites(email_list, league_id):
        """Create invites for multiple emails"""
        invites = []
        for email in email_list:
            invites.append(InviteService.create_invite(email, league_id))
        return invites

    @staticmethod
    def get_invites_by_user(email):
        """Get pending invites for a user email"""
        return Invite.get_pending_by_email(email)

    @staticmethod
    def get_sent_invites_by_user(mongo_user_id):
        """Get pending invites sent by a user (uses MongoDB _id)"""
        return Invite.get_sent_by_user(mongo_user_id)

    @staticmethod
    def accept_invite(invite_id, league_user_name=None):
        """Accept an invite — adds user to league"""
        user = AuthService.get_current_mongo_user()
        if not user:
            raise Exception("User not found")
        mongo_id = str(user._id)

        invite = Invite.get_by_id(invite_id)
        if not invite:
            raise Exception("Invite not found")

        if user.email != invite.invited_email:
            raise Exception("You are not allowed to accept this invite")

        if invite.status != "pending":
            raise Exception("Invite is not pending")

        league = League.get_by_id(str(invite.league_id))
        if not league:
            raise ValueError("League not found")
        if LeagueMember.is_member(str(league._id), mongo_id):
            raise ValueError("Already a member of this league")
        if LeagueMember.get_member_count(str(league._id)) >= league.max_players:
            raise ValueError("League is full")

        # Add user as league member
        member = LeagueMember(
            league_id=invite.league_id,
            user_id=mongo_id,  # MongoDB _id
            role="member",
            display_name=league_user_name or user.name,
        )
        member.save()

        # Update invite status
        invite.status = "accepted"
        invite.update()

        return invite

    @staticmethod
    def decline_invite(invite_id):
        """Decline an invite"""
        user = AuthService.get_current_mongo_user()
        if not user:
            raise Exception("User not found")

        invite = Invite.get_by_id(invite_id)
        if not invite:
            raise Exception("Invite not found")

        if user.email != invite.invited_email:
            raise Exception("You are not allowed to decline this invite")

        if invite.status != "pending":
            raise Exception("Invite is not pending")

        invite.status = "declined"
        invite.update()
        return invite

    @staticmethod
    def delete_invite(invite_id):
        """Delete/cancel an invite (by the inviter)"""
        user = AuthService.get_current_mongo_user()
        if not user:
            raise Exception("User not found")
        mongo_id = str(user._id)

        invite = Invite.get_by_id(invite_id)
        if not invite:
            raise Exception("Invite not found")

        if invite.inviter_id != mongo_id:
            raise Exception("You are not allowed to delete this invite")

        invite.status = "deleted"
        invite.update()
        return invite
