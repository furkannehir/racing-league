from bson.objectid import ObjectId
from src.invite_module.invite import Invite
from src.league_module.league import League
from src.league_module.league_member import LeagueMember
from src.auth_module.auth_service import AuthService
from src.user_module.user import User
from src.config import mongo
from email_validator import validate_email, EmailNotValidError
from datetime import datetime, timezone


class InviteService:

    @staticmethod
    def normalize_emails(email_list):
        if not isinstance(email_list, list) or len(email_list) > 100:
            raise ValueError("Invitations must be a list of at most 100 email addresses")
        normalized = []
        for email in email_list:
            if not isinstance(email, str):
                raise ValueError("Each invitation needs a valid email address")
            try:
                # Syntax only: league creation must not make DNS or email requests.
                value = validate_email(email.strip(), check_deliverability=False).normalized.casefold()
            except EmailNotValidError as exc:
                raise ValueError("Each invitation needs a valid email address") from exc
            if value not in normalized:
                normalized.append(value)
        return normalized

    @staticmethod
    def create_invite(email, league_id):
        return InviteService.create_invites([email], league_id)[0]

    @staticmethod
    def create_invites(email_list, league_id):
        """Save the entire batch and its delivery work atomically."""
        emails = InviteService.normalize_emails(email_list)
        if not emails:
            raise ValueError("At least one invitation email is required")
        inviter = AuthService.get_current_mongo_user()
        if not inviter:
            raise Exception("User not found")

        def persist(session):
            LeagueMember.lock_league(league_id, session)
            membership = LeagueMember.get_member(league_id, str(inviter._id), session=session)
            if not membership or membership.role not in ("owner", "admin"):
                raise ValueError("Only league owners or admins can send invites")
            # Validate the entire batch before saving its first row.
            for email in emails:
                if Invite.exists(email, league_id, session=session):
                    raise ValueError("Invite already sent to this user")
                invitee = User.get_user_by_auth_email(email)
                if invitee and LeagueMember.get_member(league_id, str(invitee._id), session=session):
                    raise ValueError("User is already a member of this league")
            invites = []
            for email in emails:
                invite = Invite(ObjectId(league_id), str(inviter._id), email)
                invite.save(session=session)
                invites.append(invite)
            return invites

        return mongo.run_transaction(persist)

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

        if league_user_name is not None and (not isinstance(league_user_name, str) or not league_user_name.strip()):
            raise ValueError("Driver name must be a non-empty string")

        def accept(session):
            invite = Invite.get_by_id(invite_id, session=session)
            if not invite:
                raise ValueError("Invite not found")
            if user.email.casefold() != invite.invited_email.casefold():
                raise ValueError("You are not allowed to accept this invite")
            if invite.status != "pending":
                raise ValueError("Invite is not pending")
            LeagueMember.join_as_participant(str(invite.league_id), mongo_id,
                league_user_name.strip() if league_user_name else user.name, session)
            invite.status = "accepted"
            invite.update(session=session)
            return invite

        return mongo.run_transaction(accept)

    @staticmethod
    def decline_invite(invite_id):
        """Decline an invite"""
        user = AuthService.get_current_mongo_user()
        if not user:
            raise Exception("User not found")

        invite = Invite.get_by_id(invite_id)
        if not invite:
            raise Exception("Invite not found")

        if user.email.casefold() != invite.invited_email.casefold():
            raise Exception("You are not allowed to decline this invite")

        if invite.status != "pending":
            raise Exception("Invite is not pending")

        InviteService.finish_pending_invite(invite, "declined")
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

        InviteService.finish_pending_invite(invite, "deleted")
        return invite

    @staticmethod
    def finish_pending_invite(invite, status):
        # Acceptance may have committed since the initial permission check.
        now = datetime.now(timezone.utc)
        result = mongo.db.invites.update_one(
            {'_id': invite._id, 'status': 'pending'},
            {'$set': {'status': status, 'updated_at': now}})
        if result.matched_count != 1:
            raise ValueError("Invite is no longer pending")
        invite.status = status
        invite.updated_at = now

    @staticmethod
    def retry_notification(invite_id):
        user = AuthService.get_current_mongo_user()
        if not ObjectId.is_valid(invite_id):
            raise ValueError("Invite not found")
        invite = Invite.get_by_id(invite_id)
        if not invite or not League.get_by_id(str(invite.league_id)):
            raise ValueError("Invite not found")
        if not user or not LeagueMember.is_admin_or_owner(str(invite.league_id), str(user._id)):
            raise PermissionError("Only league owners or admins can retry invitation emails")
        if invite.status != 'pending':
            raise ValueError("Only pending invitations can be retried")
        now = datetime.now(timezone.utc)
        result = mongo.db.invites.update_one({'_id': invite._id, 'status': 'pending', '$or': [
            {'email_status': {'$ne': 'sending'}}, {'email_lock_until': {'$lte': now}},
        ]}, {'$set': {'email_status': 'pending', 'email_attempts': 0, 'email_retry_at': now},
             '$unset': {'email_claim_token': '', 'email_lock_until': ''}})
        if result.matched_count != 1:
            raise ValueError("The invitation email is already being sent")
        return Invite.get_by_id(invite_id)
