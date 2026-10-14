from datetime import datetime, timezone
from bson import ObjectId
import re
from src.config.mongo import db


class Invite:
    def __init__(self, league_id, inviter_id, invited_email, status="pending",
                 _id=None, created_at=None, updated_at=None, email_status="pending", email_attempts=0):
        self._id = _id
        self.league_id = league_id  # ObjectId
        self.inviter_id = inviter_id  # MongoDB user _id serialized as a string
        self.invited_email = invited_email
        self.status = status  # pending / accepted / declined
        self.email_status = email_status
        self.email_attempts = email_attempts
        self.created_at = created_at if created_at is not None else datetime.now(timezone.utc)
        self.updated_at = updated_at

    def serialize(self):
        return {
            "_id": str(self._id) if self._id else None,
            "league_id": str(self.league_id),
            "inviter_id": self.inviter_id,
            "invited_email": self.invited_email,
            "status": self.status,
            "email_status": self.email_status,
            "email_attempts": self.email_attempts,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def save(self, session=None):
        """Insert a new invite"""
        doc = {
            "league_id": self.league_id,
            "inviter_id": self.inviter_id,
            "invited_email": self.invited_email,
            "status": self.status,
            "email_status": self.email_status,
            "email_attempts": self.email_attempts,
            "email_retry_at": self.created_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        result = db.invites.insert_one(doc, session=session)
        self._id = result.inserted_id

    def update(self, session=None):
        """Update invite status"""
        self.updated_at = datetime.now(timezone.utc)
        db.invites.update_one(
            {"_id": self._id},
            {"$set": {
                "status": self.status,
                "updated_at": self.updated_at,
            }}, session=session
        )

    @staticmethod
    def get_by_id(invite_id, session=None):
        doc = db.invites.find_one({"_id": ObjectId(invite_id)}, session=session)
        if doc:
            return Invite._from_doc(doc)
        return None

    @staticmethod
    def get_pending_by_email(email):
        """Get all pending invites for an email"""
        docs = db.invites.find({"invited_email": {"$regex": "^" + re.escape(email) + "$", "$options": "i"},
                               "status": "pending"})
        return [Invite._from_doc(d) for d in docs]

    @staticmethod
    def get_sent_by_user(user_id):
        """Get all pending invites sent by a user"""
        docs = db.invites.find({"inviter_id": user_id, "status": "pending"})
        return [Invite._from_doc(d) for d in docs]

    @staticmethod
    def exists(email, league_id, session=None):
        """Check if a pending invite already exists"""
        return db.invites.count_documents({
            "invited_email": {"$regex": "^" + re.escape(email) + "$", "$options": "i"},
            "league_id": ObjectId(league_id),
            "status": "pending"
        }, session=session) > 0

    @staticmethod
    def _from_doc(doc):
        return Invite(
            _id=doc.get("_id"),
            league_id=doc.get("league_id"),
            inviter_id=doc.get("inviter_id"),
            invited_email=doc.get("invited_email"),
            status=doc.get("status", "pending"),
            email_status=doc.get("email_status", "unknown"),
            email_attempts=doc.get("email_attempts", 0),
            created_at=doc.get("created_at"),
            updated_at=doc.get("updated_at"),
        )
