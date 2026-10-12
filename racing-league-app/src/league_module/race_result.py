from bson.objectid import ObjectId
from datetime import datetime, timezone
from src.config.mongo import db
from src.config.mongo import run_transaction


class RaceResult:
    def __init__(self, race_id, league_id, user_id, result_type="race",
                 position=0, points=0, fastest_lap=False, dnf=False,
                 _id=None, created_at=None):
        self._id = _id
        self.race_id = race_id  # ObjectId
        self.league_id = league_id  # ObjectId
        self.user_id = user_id  # MongoDB user _id serialized as a string
        self.result_type = result_type  # "race" or "qualifying"
        self.position = position
        self.points = points
        self.fastest_lap = fastest_lap
        self.dnf = dnf
        self.created_at = created_at if created_at is not None else datetime.now(timezone.utc)

    def serialize(self):
        return {
            "_id": str(self._id) if self._id else None,
            "race_id": str(self.race_id),
            "league_id": str(self.league_id),
            "user_id": self.user_id,
            "result_type": self.result_type,
            "position": self.position,
            "points": self.points,
            "fastest_lap": self.fastest_lap,
            "dnf": self.dnf,
            "created_at": self.created_at,
        }

    def save(self):
        """Insert a new race result"""
        doc = {
            "race_id": self.race_id,
            "league_id": self.league_id,
            "user_id": self.user_id,
            "result_type": self.result_type,
            "position": self.position,
            "points": self.points,
            "fastest_lap": self.fastest_lap,
            "dnf": self.dnf,
            "created_at": self.created_at,
        }
        result = db.race_results.insert_one(doc)
        self._id = result.inserted_id

    @staticmethod
    def get_by_race(race_id, result_type="race"):
        """Get all results for a race, sorted by position"""
        docs = db.race_results.find({
            "race_id": ObjectId(race_id),
            "result_type": result_type
        }).sort("position", 1)
        return [RaceResult._from_doc(d) for d in docs]

    @staticmethod
    def get_by_league(league_id, result_type="race"):
        """Get all results for a league"""
        docs = db.race_results.find({
            "league_id": ObjectId(league_id),
            "result_type": result_type
        })
        return [RaceResult._from_doc(d) for d in docs]

    @staticmethod
    def get_standings(league_id, result_type="race"):
        """
        Compute overall standings from race_results using aggregation.
        Returns sorted list: [{user_id, points, wins, podiums, dnfs, fastest_laps}, ...]
        """
        pipeline = [
            {"$match": {
                "league_id": ObjectId(league_id),
                "result_type": result_type
            }},
            {"$group": {
                "_id": "$user_id",
                "points": {"$sum": "$points"},
                "wins": {"$sum": {"$cond": [{"$and": [
                    {"$eq": ["$position", 1]}, {"$eq": ["$dnf", False]}
                ]}, 1, 0]}},
                "podiums": {"$sum": {"$cond": [{"$and": [
                    {"$gte": ["$position", 1]}, {"$lte": ["$position", 3]},
                    {"$eq": ["$dnf", False]}
                ]}, 1, 0]}},
                "dnfs": {"$sum": {"$cond": ["$dnf", 1, 0]}},
                "fastest_laps": {"$sum": {"$cond": ["$fastest_lap", 1, 0]}},
                "races": {"$sum": 1},
            }},
            {"$sort": {"points": -1, "wins": -1, "podiums": -1}},
        ]
        results = list(db.race_results.aggregate(pipeline))
        standings = []
        for i, r in enumerate(results):
            standings.append({
                "user_id": r["_id"],
                "position": i + 1,
                "points": r["points"],
                "wins": r["wins"],
                "podiums": r["podiums"],
                "dnfs": r["dnfs"],
                "fastest_laps": r["fastest_laps"],
                "races": r["races"],
            })
        return standings

    @staticmethod
    def replace_by_race(race_id, results, result_type="race"):
        """Replace validated results and race status in a single transaction."""
        def replace(session):
            db.race_results.delete_many({
                "race_id": ObjectId(race_id), "result_type": result_type
            }, session=session)
            RaceResult.bulk_save(results, session=session)
            if result_type == "race":
                db.races.update_one(
                    {"_id": ObjectId(race_id)},
                    {"$set": {"status": "Completed"}}, session=session
                )
        run_transaction(replace)

    @staticmethod
    def bulk_save(results, session=None):
        """Insert multiple race results at once"""
        if results:
            docs = [{
                "race_id": r.race_id,
                "league_id": r.league_id,
                "user_id": r.user_id,
                "result_type": r.result_type,
                "position": r.position,
                "points": r.points,
                "fastest_lap": r.fastest_lap,
                "dnf": r.dnf,
                "created_at": r.created_at,
            } for r in results]
            db.race_results.insert_many(docs, session=session)

    @staticmethod
    def delete_by_race(race_id, result_type="race"):
        """Delete all results for a race (for re-submission)"""
        db.race_results.delete_many({
            "race_id": ObjectId(race_id),
            "result_type": result_type
        })

    @staticmethod
    def _from_doc(doc):
        return RaceResult(
            _id=doc.get("_id"),
            race_id=doc.get("race_id"),
            league_id=doc.get("league_id"),
            user_id=doc.get("user_id"),
            result_type=doc.get("result_type", "race"),
            position=doc.get("position", 0),
            points=doc.get("points", 0),
            fastest_lap=doc.get("fastest_lap", False),
            dnf=doc.get("dnf", False),
            created_at=doc.get("created_at"),
        )
