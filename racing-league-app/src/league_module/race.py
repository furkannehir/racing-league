from bson.objectid import ObjectId
from datetime import datetime, timezone
from src.config.mongo import db


class Race:
    def __init__(self, league_id, track, date, status="Upcoming",
                 _id=None, created_at=None):
        self._id = _id
        self.league_id = league_id  # ObjectId
        self.track = track
        self.date = date  # datetime (timezone-aware)
        self.status = status  # Upcoming / Completed
        self.created_at = created_at if created_at is not None else datetime.now(timezone.utc)

    def serialize(self):
        date_value = self.date.isoformat() if isinstance(self.date, datetime) else self.date
        return {
            "_id": str(self._id) if self._id else None,
            "league_id": str(self.league_id),
            "track": self.track,
            "date": date_value,
            "status": self.status,
            "created_at": self.created_at,
        }

    def save(self, session=None):
        """Insert a new race"""
        doc = {
            "league_id": self.league_id,
            "track": self.track,
            "date": self.date,
            "status": self.status,
            "created_at": self.created_at,
        }
        result = db.races.insert_one(doc, session=session)
        self._id = result.inserted_id

    def update(self):
        """Update an existing race"""
        db.races.update_one(
            {"_id": self._id},
            {"$set": {
                "track": self.track,
                "date": self.date,
                "status": self.status,
            }}
        )

    @staticmethod
    def get_by_id(race_id):
        doc = db.races.find_one({"_id": ObjectId(race_id)})
        if doc:
            return Race._from_doc(doc)
        return None

    @staticmethod
    def get_by_league(league_id):
        """Get all races for a league, sorted by date"""
        docs = db.races.find({"league_id": ObjectId(league_id)}).sort("date", 1)
        return [Race._from_doc(d) for d in docs]

    @staticmethod
    def get_next_race(league_id):
        """Get the next upcoming race for a league"""
        doc = db.races.find_one(
            {"league_id": ObjectId(league_id), "status": "Upcoming",
             "date": {"$gt": datetime.now(timezone.utc)}},
            sort=[("date", 1)]
        )
        if doc:
            return Race._from_doc(doc)
        return None

    @staticmethod
    def mark_completed(race_id):
        db.races.update_one(
            {"_id": ObjectId(race_id)},
            {"$set": {"status": "Completed"}}
        )

    @staticmethod
    def delete(race_id):
        db.races.delete_one({"_id": ObjectId(race_id)})

    @staticmethod
    def _from_doc(doc):
        date = doc.get("date")
        if isinstance(date, str):
            try:
                if date.endswith('Z'):
                    date = datetime.fromisoformat(date.replace('Z', '+00:00'))
                else:
                    date = datetime.fromisoformat(date)
                    if not date.tzinfo:
                        date = date.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                date = datetime.now(timezone.utc)
        elif isinstance(date, datetime) and not date.tzinfo:
            date = date.replace(tzinfo=timezone.utc)

        return Race(
            _id=doc.get("_id"),
            league_id=doc.get("league_id"),
            track=doc.get("track"),
            date=date,
            status=doc.get("status", "Upcoming"),
            created_at=doc.get("created_at"),
        )
