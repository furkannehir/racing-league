# Racing League backend

Run commands from this directory. Python 3.12 is supported. The Flask entry point
is `app:app`, including the Docker/Gunicorn command.

## Development checks

```powershell
python -m venv venv
.\venv\Scripts\python -m pip install -r requirements-dev.txt
.\venv\Scripts\python -m unittest discover -s tests -v
```

The regression suite uses an in-memory MongoDB substitute and mocks Firebase and
email delivery. It covers API response shapes, both user ID formats, invitations,
team assignments, scoring, replacement rollback, and migration behavior.

To run the same suite against real MongoDB transactions, start a disposable local
replica set, set `RACING_LEAGUE_TEST_MONGO_URI` to its local connection URI, then run
the test command. Tests use a unique database name and remove that database on
completion; Firebase and email remain mocked. Remote MongoDB URIs are rejected.

## Database migration before deployment

The new schema stores memberships, races, results, and teams in separate
collections. Existing users keep their IDs, including legacy Firebase UID strings;
Firebase authentication resolves application users by email.

Stop application writes and take a database backup before applying the migration.
Use the same environment configuration (`MONGO_URI`, `MONGO_DB_NAME`, and other
application variables) as the deployment, then run:

```powershell
.\venv\Scripts\python scripts/migrate_league_schema.py
.\venv\Scripts\python scripts/migrate_league_schema.py --apply
```

The first command is a read-only preflight. It resolves all references and reports
the number of operations. Missing users, invalid race references, duplicate user
emails, and standings that cannot be reconstructed cause it to fail before writing.
The apply command runs the same preflight, then commits the conversion in a
transaction. It preserves embedded legacy fields and existing child records,
retains race IDs, converts invitations, and can be rerun without duplicating data.
Run the dry run again after applying; it should report zero operations.

The app refuses to start with unmigrated legacy records, so a missed migration
cannot silently hide existing league data. `scripts/migrate_participants.py` is the
older embedded-format migration and is not a substitute for this migration.

MongoDB must support transactions: use a replica set (including a single-node
replica set for local development) or a sharded cluster. Standalone MongoDB servers
are unsupported for result/team replacements and migration; failures do not fall
back to writes that could partially replace existing data.

League deletion is a soft delete: it hides the league while retaining stored data.
