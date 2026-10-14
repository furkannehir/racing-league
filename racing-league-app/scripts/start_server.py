"""Prepare the database once per container, then replace this process with Gunicorn."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def prepare_database():
    from src.config.mongo import assert_schema_ready, db, ensure_indexes
    from scripts.migrate_league_schema import migrate

    print("Preparing database schema before starting Gunicorn...", flush=True)
    summary = migrate(db, apply=True)
    assert_schema_ready()
    ensure_indexes()
    print(f"Database ready: {summary['operations']} migration operations.", flush=True)
    print(f"Retained archives: {summary['skipped_archived_leagues']} leagues, {summary['skipped_archived_invites']} invitations.", flush=True)


def main(argv=None):
    command = list(sys.argv[1:] if argv is None else argv)
    if not command or command == ["gunicorn"]:
        try:
            port = int(os.getenv('PORT', '5000'))
            if not 1 <= port <= 65535:
                raise ValueError()
        except ValueError:
            print("PORT must be an integer between 1 and 65535", file=sys.stderr, flush=True)
            return 1
        command = [
            "gunicorn", "--workers", "4", "--timeout", "90", "--bind",
            f"0.0.0.0:{port}", "app:app",
        ]
    try:
        prepare_database()
    except Exception as exc:
        print(f"Database preparation failed; server was not started: {exc}", file=sys.stderr, flush=True)
        return 1
    os.execvp(command[0], command)
    return 0


if __name__ == "__main__":
    sys.exit(main())
