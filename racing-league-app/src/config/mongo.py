from pymongo import MongoClient, ASCENDING
from pymongo.write_concern import WriteConcern
from src.config.config import Config
from src.config.legacy_schema import ACTIVE_LEGACY_LEAGUES, live_legacy_invites

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
    """Require live data to be migrated; retain inactive archives without activating them."""
    try:
        pending = bool(db.leagues.find_one(ACTIVE_LEGACY_LEAGUES)) or next(live_legacy_invites(db), None) is not None
    except ValueError:
        pending = True
    if pending:
        raise RuntimeError(
            "Legacy league data requires migration. Run scripts/migrate_league_schema.py "
            "for a dry run, then run it with --apply before starting the app."
        )


def ensure_indexes():
    """Create all indexes on startup. Safe to call multiple times — MongoDB ignores existing indexes."""
    # users
    db.users.create_index("email", unique=True)
    db.users.create_index('firebase_uid', unique=True, sparse=True)
    db.account_notifications.create_index([('status', ASCENDING), ('retry_at', ASCENDING)])
    db.account_notifications.create_index('expires_at', expireAfterSeconds=0)
    db.account_rate_limits.create_index('expires_at', expireAfterSeconds=0)
    db.registration_leases.create_index('expires_at', expireAfterSeconds=0)
    db.ai_image_leases.create_index('expires_at', expireAfterSeconds=0)
    db.ai_image_usage.create_index('expires_at', expireAfterSeconds=0)

    # leagues
    db.leagues.create_index("owner_id")
    db.leagues.create_index([("deleted_at", ASCENDING), ("public", ASCENDING)])
    db.leagues.create_index([("deleted_at", 1), ("public", 1), ("created_at", -1), ("_id", -1)])
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
    db.races.create_index([("league_id", 1), ("status", 1), ("date", 1)])

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
    db.invites.create_index([("status", ASCENDING), ("email_status", ASCENDING), ("email_retry_at", ASCENDING)])

    # point_system_presets
    db.point_system_presets.create_index("active")
    db.point_system_presets.create_index("name", unique=True)
