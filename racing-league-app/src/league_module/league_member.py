from bson.objectid import ObjectId
from datetime import datetime, timezone
from src.config.mongo import db


class LeagueMember:
    def __init__(self, league_id, user_id, role="member", display_name=None,
                 _id=None, joined_at=None):
        self._id = _id
        self.league_id = league_id  # ObjectId
        self.user_id = user_id  # MongoDB user _id serialized as a string
        self.role = role  # owner / admin / member
        self.display_name = display_name
        self.joined_at = joined_at if joined_at is not None else datetime.now(timezone.utc)

    def serialize(self):
        return {
            "_id": str(self._id) if self._id else None,
            "league_id": str(self.league_id),
            "user_id": self.user_id,
            "role": self.role,
            "display_name": self.display_name,
            "joined_at": self.joined_at,
        }

    def save(self):
        """Insert a new membership"""
        doc = {
            "league_id": self.league_id,
            "user_id": self.user_id,
            "role": self.role,
            "display_name": self.display_name,
            "joined_at": self.joined_at,
        }
        result = db.league_members.insert_one(doc)
        self._id = result.inserted_id

    def update(self):
        """Update membership (role or display_name)"""
        db.league_members.update_one(
            {"_id": self._id},
            {"$set": {
                "role": self.role,
                "display_name": self.display_name,
            }}
        )

    @staticmethod
    def get_members(league_id):
        """Get all members of a league"""
        docs = db.league_members.find({"league_id": ObjectId(league_id)})
        return [LeagueMember._from_doc(d) for d in docs]

    @staticmethod
    def get_member(league_id, user_id):
        """Get a specific member's membership"""
        doc = db.league_members.find_one({
            "league_id": ObjectId(league_id),
            "user_id": user_id
        })
        if doc:
            return LeagueMember._from_doc(doc)
        return None

    @staticmethod
    def get_user_leagues(user_id):
        """Get all league IDs a user belongs to"""
        docs = db.league_members.find({"user_id": user_id})
        return [LeagueMember._from_doc(d) for d in docs]

    @staticmethod
    def get_member_count(league_id):
        return db.league_members.count_documents({"league_id": ObjectId(league_id)})

    @staticmethod
    def is_member(league_id, user_id):
        return db.league_members.count_documents({
            "league_id": ObjectId(league_id),
            "user_id": user_id
        }) > 0

    @staticmethod
    def is_admin_or_owner(league_id, user_id):
        return db.league_members.count_documents({
            "league_id": ObjectId(league_id),
            "user_id": user_id,
            "role": {"$in": ["owner", "admin"]}
        }) > 0

    @staticmethod
    def remove(league_id, user_id):
        db.league_members.delete_one({
            "league_id": ObjectId(league_id),
            "user_id": user_id
        })

    @staticmethod
    def remove_all_for_league(league_id):
        db.league_members.delete_many({"league_id": ObjectId(league_id)})

    @staticmethod
    def update_role(league_id, user_id, new_role):
        db.league_members.update_one(
            {"league_id": ObjectId(league_id), "user_id": user_id},
            {"$set": {"role": new_role}}
        )

    @staticmethod
    def _from_doc(doc):
        return LeagueMember(
            _id=doc.get("_id"),
            league_id=doc.get("league_id"),
            user_id=doc.get("user_id"),
            role=doc.get("role", "member"),
            display_name=doc.get("display_name"),
            joined_at=doc.get("joined_at"),
        )
