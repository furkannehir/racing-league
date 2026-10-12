"""Preflight and migrate embedded league data. Dry run unless --apply is supplied."""
import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def parse_date(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime):
        raise ValueError("A calendar race is missing a valid date")
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def build_plan(database):
    """Resolve every reference before writing anything; retain all legacy fields."""
    users = list(database.users.find({}))
    by_email = {}
    by_id = {}
    for user in users:
        if user.get("email") in by_email:
            raise ValueError("Duplicate user emails must be resolved before migration")
        by_email[user.get("email")] = user
        by_id[str(user["_id"])] = user

    def resolve(ref):
        user = by_email.get(ref) or by_id.get(str(ref))
        if not user:
            raise ValueError(f"Cannot resolve user reference {ref!r}")
        return user

    plan = []

    def add(collection, query, values, preserve=True):
        plan.append((collection, query, values, preserve))

    for league in database.leagues.find({"owner_id": {"$exists": False}}):
        league_id = league["_id"]
        owner = resolve(league.get("owner"))
        created_at = league.get("created_at") or datetime.now(timezone.utc)
        point_system = league.get("pointSystem", {})
        fastest_lap_point = league.get("fastestLapPoint", 0)
        members = {}
        for participant in league.get("participants", []):
            ref = participant.get("email") if isinstance(participant, dict) else participant
            user = resolve(ref)
            members[str(user["_id"])] = {
                "league_id": league_id, "user_id": str(user["_id"]), "role": "member",
                "display_name": (participant.get("league_user_name") if isinstance(participant, dict) else None)
                                or user.get("name") or user["email"],
                "joined_at": created_at,
            }
        for admin_ref in league.get("admins", []):
            user = resolve(admin_ref)
            mid = str(user["_id"])
            members.setdefault(mid, {
                "league_id": league_id, "user_id": mid,
                "display_name": user.get("name") or user["email"], "joined_at": created_at,
            })["role"] = "admin"
        owner_id = str(owner["_id"])
        members.setdefault(owner_id, {
            "league_id": league_id, "user_id": owner_id,
            "display_name": owner.get("name") or owner["email"], "joined_at": created_at,
        })["role"] = "owner"

        race_ids = {}
        race_tracks = {}
        for index, race in enumerate(league.get("calendar", [])):
            if not isinstance(race, dict) or not race.get("track"):
                raise ValueError(f"League {league_id} has an invalid calendar race")
            # Stable IDs allow a dry run and repeated runs to produce the same mapping.
            race_id = ObjectId(race["_id"]) if race.get("_id") else ObjectId(
                hashlib.sha256(f"{league_id}:{index}".encode()).hexdigest()[:24]
            )
            existing = database.races.find_one({"_id": race_id})
            if existing and existing.get("league_id") != league_id:
                raise ValueError("A race ID is already assigned to another league")
            race_ids[str(race_id)] = race_id
            race_tracks.setdefault(race["track"], []).append(race_id)
            add("races", {"_id": race_id}, {
                "league_id": league_id, "track": race["track"],
                "date": parse_date(race.get("date")),
                "status": race.get("status", "Upcoming"), "created_at": created_at,
            })

        standings = league.get("standings", {})
        if not standings.get("races") and any(
            stats.get("points", 0) for stats in standings.get("overall", {}).values()
        ):
            raise ValueError(f"League {league_id} has overall points without per-race results")
        for race_ref, results in standings.get("races", {}).items():
            race_id = race_ids.get(str(race_ref))
            if race_id is None and len(race_tracks.get(race_ref, [])) == 1:
                race_id = race_tracks[race_ref][0]
            if race_id is None:
                raise ValueError(f"League {league_id} has results for an unknown or ambiguous race")
            for driver, result in results.items():
                user = resolve(driver)
                mid = str(user["_id"])
                dnf = result.get("dnf", False)
                fastest_lap = result.get("fastest_lap", result.get("fastestLap", False))
                position = int(result.get("position", 0))
                points = 0 if dnf else point_system.get(str(position), 0)
                if fastest_lap and not dnf:
                    points += fastest_lap_point
                add("race_results", {
                    "race_id": race_id, "user_id": mid, "result_type": "race"
                }, {
                    "league_id": league_id, "position": position,
                    "points": result.get("points", points), "dnf": dnf,
                    "fastest_lap": fastest_lap, "created_at": created_at,
                })
            if results:
                add("races", {"_id": race_id}, {"status": "Completed"}, preserve=False)

        for name, refs in league.get("teams", {}).items():
            if isinstance(refs, dict):
                refs = refs.get("members", [])
            member_ids = [str(resolve(ref)["_id"]) for ref in refs]
            add("teams", {"league_id": league_id, "name": name}, {
                "member_ids": member_ids, "created_at": created_at,
            })
        for mid, member in members.items():
            add("league_members", {"league_id": league_id, "user_id": mid}, member)
        add("leagues", {"_id": league_id}, {
            "owner_id": owner_id, "point_system": point_system,
            "fastest_lap_point": fastest_lap_point, "schema_version": 2,
        }, preserve=False)

    for invite in database.invites.find({"league_id": {"$exists": False}}):
        league_id = ObjectId(invite.get("league"))
        if not database.leagues.find_one({"_id": league_id}):
            raise ValueError("An invitation references a missing league")
        inviter = resolve(invite.get("inviter"))
        invited_email = invite.get("invited_user")
        if not isinstance(invited_email, str) or not invited_email:
            raise ValueError("An invitation is missing its recipient email")
        values = {
            "league_id": league_id, "inviter_id": str(inviter["_id"]),
            "invited_email": invited_email,
        }
        if invite.get("deleted_at"):
            values["status"] = "deleted"
        add("invites", {"_id": invite["_id"]}, values, preserve=False)
    return plan


def migrate(database, apply=False):
    plan = build_plan(database)
    if apply and plan:
        from src.config.mongo import run_transaction

        def write(session):
            for collection, query, values, preserve in plan:
                database[collection].update_one(
                    query, {"$setOnInsert" if preserve else "$set": values},
                    upsert=preserve, session=session,
                )
        run_transaction(write, database=database)
    return {"operations": len(plan), "applied": bool(apply and plan)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply the preflighted migration")
    args = parser.parse_args()
    from src.config.mongo import db, ensure_indexes
    try:
        summary = migrate(db, apply=args.apply)
        if args.apply:
            ensure_indexes()
        print(f"{'Applied' if args.apply else 'Dry run'}: {summary['operations']} operations")
    except Exception as exc:
        print(f"Migration failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
