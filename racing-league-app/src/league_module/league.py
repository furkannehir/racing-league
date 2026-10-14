from bson.objectid import ObjectId
from datetime import datetime, timezone
from src.config.mongo import db


class League:
    def __init__(self, name, owner_id, public, status="active", point_system=None,
                 max_players=20, fastest_lap_point=0, invite_code=None,
                 _id=None, created_at=None, updated_at=None, deleted_at=None):
        self._id = _id
        self.name = name
        self.owner_id = owner_id  # MongoDB user _id serialized as a string
        self.public = public
        self.status = status
        self.point_system = point_system if point_system is not None else {}
        self.max_players = max_players
        self.fastest_lap_point = fastest_lap_point
        self.invite_code = invite_code
        self.created_at = created_at if created_at is not None else datetime.now(timezone.utc)
        self.updated_at = updated_at
        self.deleted_at = deleted_at

    def serialize(self):
        return {
            "_id": str(self._id) if self._id else None,
            "name": self.name,
            "owner_id": self.owner_id,
            "public": self.public,
            "status": self.status,
            "point_system": self.point_system,
            "max_players": self.max_players,
            "fastest_lap_point": self.fastest_lap_point,
            "invite_code": self.invite_code,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def save(self, session=None):
        """Insert a new league"""
        self.updated_at = datetime.now(timezone.utc)
        doc = {
            "name": self.name,
            "owner_id": self.owner_id,
            "public": self.public,
            "status": self.status,
            "point_system": self.point_system,
            "max_players": self.max_players,
            "fastest_lap_point": self.fastest_lap_point,
            "invite_code": self.invite_code,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "deleted_at": self.deleted_at,
        }
        result = db.leagues.insert_one(doc, session=session)
        self._id = result.inserted_id

    def update(self, session=None):
        """Update an existing league"""
        self.updated_at = datetime.now(timezone.utc)
        db.leagues.update_one(
            {"_id": self._id},
            {"$set": {
                "name": self.name,
                "public": self.public,
                "status": self.status,
                "point_system": self.point_system,
                "max_players": self.max_players,
                "fastest_lap_point": self.fastest_lap_point,
                "invite_code": self.invite_code,
                "updated_at": self.updated_at,
            }}, session=session
        )

    @staticmethod
    def get_by_id(league_id, session=None):
        doc = db.leagues.find_one({"_id": ObjectId(league_id), "deleted_at": None}, session=session)
        if doc:
            return League._from_doc(doc)
        return None

    @staticmethod
    def get_public_leagues():
        docs = db.leagues.find({"public": True, "deleted_at": None})
        return [League._from_doc(d) for d in docs]

    @staticmethod
    def get_public_leagues_paginated(page=1, page_size=10):
        docs = db.leagues.find({"public": True, "deleted_at": None}) \
            .skip((page - 1) * page_size).limit(page_size)
        return [League._from_doc(d) for d in docs]

    @staticmethod
    def get_by_invite_code(invite_code):
        doc = db.leagues.find_one({"invite_code": invite_code, "deleted_at": None})
        if doc:
            return League._from_doc(doc)
        return None

    @staticmethod
    def soft_delete(league_id):
        db.leagues.update_one(
            {"_id": ObjectId(league_id)},
            {"$set": {"deleted_at": datetime.now(timezone.utc)}}
        )

    @staticmethod
    def _from_doc(doc):
        return League(
            _id=doc.get("_id"),
            name=doc.get("name"),
            owner_id=doc.get("owner_id"),
            public=doc.get("public", False),
            status=doc.get("status", "active"),
            point_system=doc.get("point_system", {}),
            max_players=doc.get("max_players", 20),
            fastest_lap_point=doc.get("fastest_lap_point", 0),
            invite_code=doc.get("invite_code"),
            created_at=doc.get("created_at"),
            updated_at=doc.get("updated_at"),
            deleted_at=doc.get("deleted_at"),
        )
