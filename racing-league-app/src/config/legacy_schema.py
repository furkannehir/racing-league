"""Only live legacy data must be converted before the application serves requests."""
from bson import ObjectId

ACTIVE_LEGACY_LEAGUES = {"owner_id": {"$exists": False}, "deleted_at": None}
INACTIVE_INVITE_STATUSES = ("accepted", "declined", "cancelled", "deleted", "expired")


def live_legacy_invites(database):
    for invite in database.invites.find({"league_id": {"$exists": False}}):
        if invite.get("deleted_at") is not None or invite.get("status") in INACTIVE_INVITE_STATUSES:
            continue
        if not ObjectId.is_valid(invite.get("league")):
            raise ValueError("A pending invitation has an invalid league reference")
        league = database.leagues.find_one({"_id": ObjectId(invite["league"])})
        if not league:
            raise ValueError("A pending invitation references a missing league")
        if league.get("deleted_at") is not None:
            continue
        yield invite
