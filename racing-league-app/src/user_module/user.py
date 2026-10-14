from datetime import datetime, timezone
import re
from bson import ObjectId
from src.config.mongo import db
from pymongo import ReturnDocument


def user_id_candidates(user_id):
    """Match generated ObjectIds and legacy string IDs without changing stored IDs."""
    candidates = [user_id]
    if isinstance(user_id, ObjectId):
        candidates.append(str(user_id))
    elif isinstance(user_id, str) and ObjectId.is_valid(user_id):
        candidates.append(ObjectId(user_id))
    return candidates


class User:
    def __init__(self, _id, name, email, created_at=None, updated_at=None, deleted_at=None,
                 bio='', firebase_uid=None):
        self._id = _id  # MongoDB ObjectId (or string) — NOT Firebase UID
        self.name = name
        self.email = email
        self.bio = bio
        self.firebase_uid = firebase_uid
        self.created_at = created_at if created_at is not None else datetime.now(timezone.utc)
        self.updated_at = updated_at
        self.deleted_at = deleted_at

    def serialize(self, include_bio=False):
        result = {
            "_id": str(self._id),
            "name": self.name,
            "email": self.email,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if include_bio:
            result['bio'] = self.bio if isinstance(self.bio, str) else ''
        return result

    def save(self, session=None):
        """Insert a new user. If _id is None, MongoDB generates one."""
        user = {
            "name": self.name,
            "email": self.email,
            "bio": self.bio,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "deleted_at": self.deleted_at,
        }
        if self._id is not None:
            user["_id"] = self._id
        if self.firebase_uid is not None:
            user['firebase_uid'] = self.firebase_uid
        result = db.users.insert_one(user, session=session)
        self._id = result.inserted_id

    def update(self):
        """Update an existing user"""
        self.updated_at = datetime.now(timezone.utc)
        db.users.update_one(
            {"_id": self._id},
            {"$set": {
                "name": self.name,
                "email": self.email,
                "bio": self.bio,
                "updated_at": self.updated_at,
            }}
        )

    @staticmethod
    def update_profile(user_id, fields):
        """Update only supplied profile fields without overwriting account identity."""
        doc = db.users.find_one_and_update(
            {'_id': {'$in': user_id_candidates(user_id)}, 'deleted_at': None},
            {'$set': {**fields, 'updated_at': datetime.now(timezone.utc)}},
            return_document=ReturnDocument.AFTER)
        return User._from_doc(doc) if doc else None

    @staticmethod
    def get_by_firebase_uid(uid):
        doc = db.users.find_one({'firebase_uid': uid, 'deleted_at': None})
        return User._from_doc(doc) if doc else None

    @staticmethod
    def email_is_registered(email):
        # Deleted and ambiguous legacy accounts must not be recreated by signup.
        return db.users.find_one({'email': {
            '$regex': '^' + re.escape(email) + '$', '$options': 'i'}}) is not None

    @staticmethod
    def get_user_by_mail(email):
        user_data = db.users.find_one({"email": email, "deleted_at": None})
        if user_data:
            return User._from_doc(user_data)
        return None

    @staticmethod
    def get_user_by_auth_email(email):
        """Firebase treats email casing alike; reject ambiguous legacy matches."""
        if not isinstance(email, str) or not email:
            return None
        matches = list(db.users.find({
            "email": {"$regex": "^" + re.escape(email) + "$", "$options": "i"},
            "deleted_at": None,
        }).limit(2))
        return User._from_doc(matches[0]) if len(matches) == 1 else None

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
            bio=doc.get('bio', ''),
            firebase_uid=doc.get('firebase_uid'),
        )
