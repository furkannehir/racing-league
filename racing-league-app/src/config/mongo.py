from pymongo import MongoClient, ASCENDING
from pymongo.write_concern import WriteConcern
from src.config.config import Config

# Connect to MongoDB
client = MongoClient(Config.MONGO_URI)
db = client[Config.MONGO_DB_NAME]


def get_db():
    return db


def run_transaction(callback, database=None):
    """Commit related writes together; never fall back to non-atomic writes."""
    database = db if database is None else database
    with database.client.start_session() as session:
        return session.with_transaction(callback, write_concern=WriteConcern("majority"))


def assert_schema_ready():
    """Prevent the new app from silently hiding unmigrated legacy records."""
    if (db.leagues.find_one({"owner_id": {"$exists": False}})
            or db.invites.find_one({"league_id": {"$exists": False}})):
        raise RuntimeError(
            "Legacy league data requires migration. Run scripts/migrate_league_schema.py "
            "for a dry run, then run it with --apply before starting the app."
        )


def ensure_indexes():
    """Create all indexes on startup. Safe to call multiple times — MongoDB ignores existing indexes."""
    # users
    db.users.create_index("email", unique=True)

    # leagues
    db.leagues.create_index("owner_id")
    db.leagues.create_index([("deleted_at", ASCENDING), ("public", ASCENDING)])
    db.leagues.create_index(
        "invite_code",
        unique=True,
        partialFilterExpression={"invite_code": {"$type": "string"}}
    )

    # league_members
    db.league_members.create_index([("league_id", ASCENDING), ("user_id", ASCENDING)], unique=True)
    db.league_members.create_index("user_id")

    # races
    db.races.create_index("league_id")
    db.races.create_index([("league_id", ASCENDING), ("status", ASCENDING)])

    # race_results
    db.race_results.create_index(
        [("race_id", ASCENDING), ("user_id", ASCENDING), ("result_type", ASCENDING)],
        unique=True
    )
    db.race_results.create_index("league_id")

    # teams
    db.teams.create_index("league_id")

    # invites
    db.invites.create_index([("invited_email", ASCENDING), ("status", ASCENDING)])
    db.invites.create_index("league_id")

    # point_system_presets
    db.point_system_presets.create_index("active")
    db.point_system_presets.create_index("name", unique=True)
