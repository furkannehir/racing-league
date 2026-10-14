from bson.objectid import ObjectId
from datetime import datetime, timezone
from src.config.mongo import db


class LeagueMember:
    def __init__(self, league_id, user_id, role="member", display_name=None,
                 _id=None, joined_at=None, is_participating=True):
        self._id = _id
        self.league_id = league_id  # ObjectId
        self.user_id = user_id  # MongoDB user _id serialized as a string
        self.role = role  # owner / admin / member
        self.is_participating = is_participating
        self.display_name = display_name
        self.joined_at = joined_at if joined_at is not None else datetime.now(timezone.utc)

    def serialize(self):
        return {
            "_id": str(self._id) if self._id else None,
            "league_id": str(self.league_id),
            "user_id": self.user_id,
            "role": self.role,
            "is_participating": self.is_participating,
            "display_name": self.display_name,
            "joined_at": self.joined_at,
        }

    def save(self, session=None):
        """Insert a new membership"""
        doc = {
            "league_id": self.league_id,
            "user_id": self.user_id,
            "role": self.role,
            "is_participating": self.is_participating,
            "display_name": self.display_name,
            "joined_at": self.joined_at,
        }
        result = db.league_members.insert_one(doc, session=session)
        self._id = result.inserted_id

    def update(self, session=None):
        """Update membership (role or display_name)"""
        db.league_members.update_one(
            {"_id": self._id},
            {"$set": {
                "role": self.role,
                "is_participating": self.is_participating,
                "display_name": self.display_name,
            }}, session=session
        )

    @staticmethod
    def get_members(league_id):
        """Get all members of a league"""
        docs = db.league_members.find({"league_id": ObjectId(league_id)})
        return [LeagueMember._from_doc(d) for d in docs]

    @staticmethod
    def get_member(league_id, user_id, session=None):
        """Get a specific member's membership"""
        doc = db.league_members.find_one({
            "league_id": ObjectId(league_id),
            "user_id": user_id
        }, session=session)
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
    def get_participant_count(league_id, session=None):
        # Old memberships have no flag and retain their existing participation.
        return db.league_members.count_documents({
            "league_id": ObjectId(league_id), "is_participating": {"$ne": False},
        }, session=session)

    @staticmethod
    def is_participant(league_id, user_id):
        member = LeagueMember.get_member(league_id, user_id)
        return bool(member and member.is_participating)

    @staticmethod
    def lock_league(league_id, session):
        """Serialize capacity changes on one league within the caller's transaction."""
        from src.league_module.league import League
        league = League.get_by_id(league_id, session=session)
        if not league:
            raise ValueError("League not found")
        db.leagues.update_one({"_id": league._id}, {"$inc": {"membership_version": 1}},
                              session=session)
        return league

    @staticmethod
    def join_as_participant(league_id, user_id, display_name, session, require_public=False):
        league = LeagueMember.lock_league(league_id, session)
        if require_public and not league.public:
            raise ValueError("This league is private")
        if LeagueMember.get_member(league_id, user_id, session=session):
            raise ValueError("Already a member of this league")
        if LeagueMember.get_participant_count(league_id, session=session) >= league.max_players:
            raise ValueError("League is full")
        member = LeagueMember(league._id, user_id, display_name=display_name, is_participating=True)
        member.save(session=session)
        return member

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
        """Remove current membership and team assignments together; retain race history."""
        from src.config import mongo

        def leave(session):
            league = LeagueMember.lock_league(league_id, session)
            member = LeagueMember.get_member(league_id, user_id, session=session)
            if league.owner_id == user_id or (member and member.role == "owner"):
                raise ValueError("The owner cannot leave their league")
            affected = [team['_id'] for team in db.teams.find(
                {"league_id": league._id, "member_ids": user_id}, {'_id': 1}, session=session)]
            db.teams.update_many({"league_id": league._id, "member_ids": user_id},
                                 {"$pull": {"member_ids": user_id}}, session=session)
            # A saved team requires at least one driver. Remove only teams emptied by this leave.
            db.teams.delete_many({'_id': {'$in': affected}, 'league_id': league._id,
                                  'member_ids': {'$size': 0}}, session=session)
            db.league_members.delete_one({"league_id": league._id, "user_id": user_id}, session=session)

        mongo.run_transaction(leave)

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
            is_participating=doc.get("is_participating") is not False,
            display_name=doc.get("display_name"),
            joined_at=doc.get("joined_at"),
        )
