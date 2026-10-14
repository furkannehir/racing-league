from bson.objectid import ObjectId
from datetime import datetime, timezone
from src.config.mongo import db, run_transaction
from src.league_module.league_member import LeagueMember


class Team:
    def __init__(self, league_id, name, member_ids=None, _id=None, created_at=None):
        self._id = _id
        self.league_id = league_id  # ObjectId
        self.name = name
        self.member_ids = member_ids if member_ids is not None else []  # list of user_id strings
        self.created_at = created_at if created_at is not None else datetime.now(timezone.utc)

    def serialize(self):
        return {
            "_id": str(self._id) if self._id else None,
            "league_id": str(self.league_id),
            "name": self.name,
            "member_ids": self.member_ids,
            "created_at": self.created_at,
        }

    def save(self):
        """Insert a new team"""
        doc = {
            "league_id": self.league_id,
            "name": self.name,
            "member_ids": self.member_ids,
            "created_at": self.created_at,
        }
        result = db.teams.insert_one(doc)
        self._id = result.inserted_id

    def update(self):
        """Update team name or members"""
        db.teams.update_one(
            {"_id": self._id},
            {"$set": {
                "name": self.name,
                "member_ids": self.member_ids,
            }}
        )

    @staticmethod
    def get_by_league(league_id):
        """Get all teams for a league"""
        docs = db.teams.find({"league_id": ObjectId(league_id)})
        return [Team._from_doc(d) for d in docs]

    @staticmethod
    def get_by_id(team_id):
        doc = db.teams.find_one({"_id": ObjectId(team_id)})
        if doc:
            return Team._from_doc(doc)
        return None

    @staticmethod
    def delete(team_id):
        db.teams.delete_one({"_id": ObjectId(team_id)})

    @staticmethod
    def delete_all_for_league(league_id):
        db.teams.delete_many({"league_id": ObjectId(league_id)})

    @staticmethod
    def set_teams_for_league(league_id, teams_config):
        """
        Replace all teams for a league with a new configuration.

        Args:
            league_id: The league ObjectId
            teams_config: Dict mapping team names to member ID lists
                         Format: {"Team Name": ["user_id_1", "user_id_2"]}

        Returns:
            List of new Team objects
        """
        league_oid = ObjectId(league_id)

        new_teams = []
        for team_name, member_ids in teams_config.items():
            team = Team(
                league_id=league_oid,
                name=team_name,
                member_ids=member_ids,
            )
            new_teams.append(team)

        def replace(session):
            LeagueMember.lock_league(league_id, session)
            for team in new_teams:
                for user_id in team.member_ids:
                    member = LeagueMember.get_member(league_id, user_id, session=session)
                    if not member or not member.is_participating:
                        raise ValueError("Teams require participating drivers")
            db.teams.delete_many({"league_id": league_oid}, session=session)
            if new_teams:
                db.teams.insert_many([{
                    "_id": team._id, "league_id": team.league_id,
                    "name": team.name, "member_ids": team.member_ids,
                    "created_at": team.created_at,
                } for team in new_teams], session=session)
        for team in new_teams:
            team._id = ObjectId()
        run_transaction(replace)
        return new_teams

    @staticmethod
    def _from_doc(doc):
        return Team(
            _id=doc.get("_id"),
            league_id=doc.get("league_id"),
            name=doc.get("name"),
            member_ids=doc.get("member_ids", []),
            created_at=doc.get("created_at"),
        )
