from datetime import datetime, timezone
from bson import ObjectId
from src.config.mongo import db


def user_id_candidates(user_id):
    """Match generated ObjectIds and legacy string IDs without changing stored IDs."""
    candidates = [user_id]
    if isinstance(user_id, ObjectId):
        candidates.append(str(user_id))
    elif isinstance(user_id, str) and ObjectId.is_valid(user_id):
        candidates.append(ObjectId(user_id))
    return candidates


class User:
    def __init__(self, _id, name, email, created_at=None, updated_at=None, deleted_at=None):
        self._id = _id  # MongoDB ObjectId (or string) — NOT Firebase UID
        self.name = name
        self.email = email
        self.created_at = created_at if created_at is not None else datetime.now(timezone.utc)
        self.updated_at = updated_at
        self.deleted_at = deleted_at

    def serialize(self):
        return {
            "_id": str(self._id),
            "name": self.name,
            "email": self.email,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def save(self):
        """Insert a new user. If _id is None, MongoDB generates one."""
        user = {
            "name": self.name,
            "email": self.email,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "deleted_at": self.deleted_at,
        }
        if self._id is not None:
            user["_id"] = self._id
        result = db.users.insert_one(user)
        self._id = result.inserted_id

    def update(self):
        """Update an existing user"""
        self.updated_at = datetime.now(timezone.utc)
        db.users.update_one(
            {"_id": self._id},
            {"$set": {
                "name": self.name,
                "email": self.email,
                "updated_at": self.updated_at,
            }}
        )

    @staticmethod
    def get_user_by_mail(email):
        user_data = db.users.find_one({"email": email, "deleted_at": None})
        if user_data:
            return User._from_doc(user_data)
        return None

    @staticmethod
    def get_user_by_id(user_id):
        user_data = db.users.find_one({"_id": {"$in": user_id_candidates(user_id)}, "deleted_at": None})
        if user_data:
            return User._from_doc(user_data)
        return None

    @staticmethod
    def get_users_by_ids(user_ids):
        """Batch fetch users by IDs — avoids N+1 queries"""
        ids = [candidate for user_id in user_ids for candidate in user_id_candidates(user_id)]
        users = db.users.find({"_id": {"$in": ids}, "deleted_at": None})
        return {str(u["_id"]): User._from_doc(u) for u in users}

    @staticmethod
    def delete_user(user_id):
        db.users.update_one(
            {"_id": {"$in": user_id_candidates(user_id)}},
            {"$set": {"deleted_at": datetime.now(timezone.utc)}}
        )

    @staticmethod
    def _from_doc(doc):
        return User(
            _id=doc["_id"],
            name=doc.get("name"),
            email=doc.get("email"),
            created_at=doc.get("created_at"),
            updated_at=doc.get("updated_at"),
            deleted_at=doc.get("deleted_at"),
        )
