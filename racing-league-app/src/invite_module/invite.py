from datetime import datetime, timezone

from bson import ObjectId

from src.config.mongo import db
from src.league_module.league import League
from src.user_module.user import User


class Invite:
    def __init__(self, invited_user, league, inviter, status="pending", _id=None, created_at=None, updated_at=None, deleted_at=None):
        self._id = _id
        self.invited_user = invited_user
        self.league = league
        self.inviter = inviter
        self.status = status
        self.created_at = created_at if created_at is not None else datetime.now(timezone.utc)
        self.updated_at = updated_at
        self.deleted_at = deleted_at

    def serialize(self):
        return {
            "_id": str(self._id) if self._id else None,
            "league": self.league.serialize(),
            "invited_user": self.invited_user,
            "inviter": self.inviter.serialize(),
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "deleted_at": self.deleted_at
        }
    
    def save(self):
        invite = {
            "league": str(self.league._id),
            "invited_user": self.invited_user,
            "inviter": self.inviter.email,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "deleted_at": self.deleted_at
        }
        result = db.invites.insert_one(invite)
        self._id = result.inserted_id

    def update(self):
        db.invites.update_one(
            {"_id": self._id},
            {"$set": {
                "league": str(self.league._id),
                "invited_user": self.invited_user,
                "inviter": self.inviter.email,
                "status": self.status,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "deleted_at": self.deleted_at
            }}
        )

    def delete(self):
        db.invites.update_one({"_id": self._id}, {"$set": {"deleted_at": datetime.now(timezone.utc)}})

    def accept(self):
        self.status = "accepted"
        self.update()

    def decline(self):
        self.status = "declined"
        self.update()

    @staticmethod
    def get_invites_by_user(email):
        invites = db.invites.find({"invited_user": email})

        invite_list = [Invite(
            _id=invite["_id"],
            invited_user=invite["invited_user"],
            league=League.get_league_by_id(invite["league"]),
            inviter=User.get_user_by_mail(invite["inviter"]),
            status=invite["status"],
            created_at=invite["created_at"],
            updated_at=invite["updated_at"],
            deleted_at=invite["deleted_at"]
        ) for invite in invites]
        return invite_list

    @staticmethod
    def get_invite_by_id(invite_id):
        invite = db.invites.find_one({"_id": ObjectId(invite_id)})
        return Invite(
            _id=invite["_id"],
            invited_user=invite["invited_user"],
            league=League.get_league_by_id(invite["league"]),
            inviter=User.get_user_by_mail(invite["inviter"]),
            status=invite["status"],
            created_at=invite["created_at"],
            updated_at=invite["updated_at"],
            deleted_at=invite["deleted_at"]
        )

    @staticmethod
    def get_invite_by_league_id(league_id):
        return db.invites.find({"league": league_id})

    @staticmethod
    def get_sent_invites_by_user(email):
        invites = db.invites.find({"inviter": email, "status": "pending"})
        return [Invite(
            _id=invite["_id"],
            invited_user=invite["invited_user"],
            league=invite["league"],
            inviter=invite["inviter"],
            status=invite["status"],
            created_at= invite["created_at"],
            updated_at= invite["updated_at"],
            deleted_at= invite["deleted_at"]
        )for invite in invites]