from bson.objectid import ObjectId
from datetime import datetime, timezone
from src.config.mongo import db


class PointSystemPreset:
    def __init__(self, name, points, fastest_lap_point=0, description=None,
                 active=True, _id=None, created_at=None):
        self._id = _id
        self.name = name
        self.description = description
        self.points = points  # dict: {"1": 25, "2": 18, ...}
        self.fastest_lap_point = fastest_lap_point
        self.active = active
        self.created_at = created_at if created_at is not None else datetime.now(timezone.utc)

    def serialize(self):
        return {
            "_id": str(self._id) if self._id else None,
            "name": self.name,
            "description": self.description,
            "points": self.points,
            "fastest_lap_point": self.fastest_lap_point,
            "active": self.active,
        }

    def save(self):
        doc = {
            "name": self.name,
            "description": self.description,
            "points": self.points,
            "fastest_lap_point": self.fastest_lap_point,
            "active": self.active,
            "created_at": self.created_at,
        }
        result = db.point_system_presets.insert_one(doc)
        self._id = result.inserted_id

    @staticmethod
    def get_active():
        """Get all active presets"""
        docs = db.point_system_presets.find({"active": True})
        return [PointSystemPreset._from_doc(d) for d in docs]

    @staticmethod
    def get_by_id(preset_id):
        doc = db.point_system_presets.find_one({"_id": ObjectId(preset_id)})
        if doc:
            return PointSystemPreset._from_doc(doc)
        return None

    @staticmethod
    def seed_defaults():
        """Seed default point system presets if they don't exist"""
        presets = [
            PointSystemPreset(
                name="F1 Current (2010–Present)",
                description="Current Formula 1 point system used since 2010",
                points={
                    "1": 25, "2": 18, "3": 15, "4": 12, "5": 10,
                    "6": 8, "7": 6, "8": 4, "9": 2, "10": 1
                },
                fastest_lap_point=1,
            ),
            PointSystemPreset(
                name="F1 Classic (2003–2009)",
                description="Formula 1 point system used from 2003 to 2009",
                points={
                    "1": 10, "2": 8, "3": 6, "4": 5, "5": 4,
                    "6": 3, "7": 2, "8": 1
                },
                fastest_lap_point=0,
            ),
            PointSystemPreset(
                name="MotoGP",
                description="MotoGP Grand Prix point system",
                points={
                    "1": 25, "2": 20, "3": 16, "4": 13, "5": 11,
                    "6": 10, "7": 9, "8": 8, "9": 7, "10": 6,
                    "11": 5, "12": 4, "13": 3, "14": 2, "15": 1
                },
                fastest_lap_point=0,
            ),
            PointSystemPreset(
                name="IndyCar",
                description="IndyCar Series point system",
                points={
                    "1": 50, "2": 40, "3": 35, "4": 32, "5": 30,
                    "6": 28, "7": 26, "8": 24, "9": 22, "10": 20,
                    "11": 19, "12": 18, "13": 17, "14": 16, "15": 15,
                    "16": 14, "17": 13, "18": 12, "19": 11, "20": 10,
                    "21": 9, "22": 8, "23": 7, "24": 6, "25": 5
                },
                fastest_lap_point=0,
            ),
        ]

        for preset in presets:
            # Several Gunicorn workers may seed simultaneously.
            db.point_system_presets.update_one(
                {"name": preset.name},
                {"$setOnInsert": {
                    "name": preset.name, "description": preset.description,
                    "points": preset.points, "fastest_lap_point": preset.fastest_lap_point,
                    "active": preset.active, "created_at": preset.created_at,
                }}, upsert=True,
            )

    @staticmethod
    def _from_doc(doc):
        return PointSystemPreset(
            _id=doc.get("_id"),
            name=doc.get("name"),
            description=doc.get("description"),
            points=doc.get("points", {}),
            fastest_lap_point=doc.get("fastest_lap_point", 0),
            active=doc.get("active", True),
            created_at=doc.get("created_at"),
        )
