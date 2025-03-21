# project/src/models/user.py
from bson.objectid import ObjectId
from src.config.mongo import db
from datetime import datetime

class User:
    def __init__(self, _id, name, email, eaUsername, leagues=[], races=[], created_at=datetime.now(), updated_at=None, deleted_at=None):
        self._id = _id
        self.name = name
        self.email = email
        self.eaUsername = eaUsername
        self.leagues = leagues
        self.races = races
        self.created_at = created_at
        self.updated_at = updated_at
        self.deleted_at = deleted_at

    def serialize(self):
        return {
            "_id": self._id,
            "name": self.name,
            "email": self.email,
            "eaUsername": self.eaUsername,
            "leagues": self.leagues
        }

    @staticmethod
    def get_user_by_mail(email):
        user_data = db.users.find_one({"email": email})
        if user_data:
            return User(
                _id=user_data['_id'],
                name=user_data['name'],
                email=user_data['email'],
                eaUsername=user_data['eaUsername'],
                leagues=user_data['leagues'],
                races=user_data['races'],
                created_at=user_data['created_at'],
                updated_at=user_data['updated_at'],
                deleted_at=user_data['deleted_at']
            )
        return None

    def save(self):
        user = {
            "_id": self._id,
            "name": self.name,
            "email": self.email,
            "eaUsername": self.eaUsername,
            "leagues": [],
            "races": [],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "deleted_at": self.deleted_at,
        }
        result = db.users.insert_one(user)
        self._id = result.inserted_id

    def update(self):
        """Update the user in MongoDB"""
        db.users.update_one(
            {"_id": self._id},
            {"$set": {"name": self.name, "email": self.email, "eaUsername": self.eaUsername}}
        )

    @staticmethod
    def delete_user(user_id):
        db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"deleted_at": datetime.now()}}
        )

    def to_dict(self):
        """Convert the user object to a dictionary"""
        return {
            "_id": str(self._id),
            "name": self.name,
            "email": self.email,
            "eaUsername": self.eaUsername,
            "leagues": self.leagues,
            "races": self.races,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "deleted_at": self.deleted_at
        }
