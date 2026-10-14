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
owner participation, notification leases/retries, team assignments, scoring,
creation/acceptance/replacement rollback, migration behavior, and the
authentication lifecycle. Authentication tests mock every Firebase HTTP exchange.
The remaining-audit tests also cover leave rollback, consistent tie rankings,
bounded discovery/search, archived migration data, the actual Docker command,
F1 preset upgrades, and shared account-request and email-worker budgets.

To run the same suite against real MongoDB transactions, start a disposable local
replica set, set `RACING_LEAGUE_TEST_MONGO_URI` to its local connection URI, then run
the test command. Tests use a unique database name and remove that database on
completion; Firebase and email remain mocked. Remote MongoDB URIs are rejected.

## Docker runtime configuration

The backend Docker context excludes `.env` files, `serviceAccountKey.json`, virtual
environments, and Python caches. Supply environment variables and credentials at
runtime. On Render, retain the backend service's environment settings and the
`serviceAccountKey.json` secret file mounted at `/etc/secrets/serviceAccountKey.json`.

Local Compose reads `racing-league-app/.env` through `env_file` and mounts the local
Firebase key read-only at the same runtime path. Both files must exist before
running Compose. Compose sets `ENV=production` so the backend reads the mounted
credential path; ordinary Python development still uses its existing local path.
Include `http://localhost:3000` in the backend's `ORIGINS` for the Compose frontend
and `http://localhost:5173` for Vite development. The configured MongoDB must
support the transactions described below.

The image's default `gunicorn` command is expanded by the startup script after
database preparation. It binds to `0.0.0.0:$PORT`, defaults to 5000, and keeps four
workers with a 90-second timeout. Invalid ports stop before database preparation.
Compose explicitly sets `PORT=5000` to match its published backend port, while
Render supplies its own port; see [Render's port-binding instructions](https://render.com/docs/web-services#port-binding).
An explicit command override with Gunicorn arguments is preserved, so include the
intended bind address and worker timeout in such an override.

Set `FRONTEND_URL` on the backend to the browser-accessible frontend origin:
`http://localhost:5173` for Vite development, or your frontend's HTTPS origin in
production. Compose explicitly supplies `http://localhost:3000`; a shell or root
Compose `.env` can override it. This is separate from the frontend's `VITE_API_URL`.
Invitation emails link to `${FRONTEND_URL}/leagues`, where users sign in and view
their pending invitations. Credentials, query strings, fragments, and malformed
ports are rejected. A missing or invalid setting leaves notification delivery
failed and retryable; it does not remove the invitation from the application.

## Membership, participation, and invitations

Membership roles (`owner`, `admin`, `member`) grant access and management rights.
The separate membership field `is_participating` determines whether someone is a
driver. Creation accepts an explicit boolean `creatorParticipates` (default true).
The authenticated account becomes the owner; client-supplied owner, admin, and
participant lists do not grant membership. An owner who opts out keeps private
league access and administrative rights, but takes no driver slot and does not
appear in the driver roster, standings, results, or teams.

Only participating drivers count toward `max_players`. Legacy memberships without
the flag continue participating, so existing standings are preserved without a
new migration. Owners can correct participation in league settings; opting in
requires capacity, and opting out requires removing their team assignment and
correcting their recorded driver results first. Historical ignored opt-outs cannot
be inferred automatically from stored memberships.

Creation validates settings, calendar dates, and invitation addresses before any
write. The league, owner membership, races, and pending invitations commit in one
MongoDB transaction. Invitation batches also commit together, and acceptance
commits the new participating membership and accepted status together. Creation
and batch sending normalize addresses and remove duplicates; pending lookup and
acceptance ignore email casing, including for older invitations.

Pending invitations grant neither membership nor a driver slot. Acceptance checks
capacity at that time; an invitation stays pending if the league is full. Capacity
changes, participation changes, and result/team replacements update the same
league within their transactions, so concurrent changes cannot use stale eligibility
or both claim the final driver slot. Declining or cancelling uses a conditional
pending-status update, preventing an accepted invitation from being overwritten.

Invitation records also hold durable email work. No email is sent inside an HTTP
transaction. A background scheduler starts on the first HTTP request in each
serving process (including with Gunicorn preload), polling every 15 seconds.
Each process uses a memory scheduler; atomic MongoDB leases coordinate delivery
across processes. Provider calls have a bounded timeout and failed attempts use
exponential backoff, up to five attempts. A crashed worker's lease expires so
another process can recover the work. Delivery is at least once: a crash after
the provider accepts a message but before acknowledgement can produce a duplicate.

Owners and admins can inspect pending delivery status in the Invite Players
dialog and retry failed emails. `sent` means the provider accepted the message;
it does not guarantee mailbox delivery. An email failure leaves the in-app
invitation valid. Legacy invitations without delivery metadata have status
`unknown` and are not automatically mailed; an administrator can explicitly
retry them. Accepted, declined, cancelled invitations and deleted leagues are
skipped. `INVITATION_EMAIL_WORKER_ENABLED=false` disables automatic delivery;
in-app invitations still work. The default is enabled.

`GET /api/v1/invites/sent?league_id=<id>` lists pending invitations and delivery
status for league owners/admins. `POST /api/v1/invites/<id>/retry-email` queues a
pending invitation for retry; a current unexpired delivery claim cannot be reset.

## Authentication and sessions

`POST /api/v1/auth/login` accepts `email` and `password`. A successful response
includes `token`, `refreshToken`, `expiresIn` (seconds), and the canonical `user`
with Firebase `id`, application `mongoId`, `email`, and `name`.
`POST /api/v1/auth/refresh` accepts `{"refreshToken": "..."}` and returns the same
credential fields. Both exchanges use Firebase, then verify the issued token and
account state before returning credentials. Authentication responses are not cached.

Protected routes require `Authorization: Bearer <token>`. Each request checks token
signature, expiry, revocation, Firebase account status, email verification, and an
active application account. The verified identity is reused within that request.
Email matching ignores case, but ambiguous legacy accounts are rejected.
`GET /api/v1/auth/verify` returns the current canonical user rather than relying on
the browser's cached profile.

Authentication failures return 401 with a machine-readable `code`, such as
`token_expired`, `token_revoked`, `account_disabled`, or `email_not_verified`.
Temporary Firebase or database failures return 503 `auth_unavailable`, preserving
the distinction between a rejected session and an outage. Permission denials
remain 403. Password and refresh exchanges have bounded HTTP timeouts.

Normal browser logout removes the browser's credentials. For account-wide logout,
send an authenticated `POST /api/v1/auth/logout` with `{"allDevices": true}`;
Firebase revokes that user's existing sessions on every device. The default and
legacy GET logout do not revoke other devices.

`PUT /api/v1/users/update/password` accepts `currentPassword`, `newPassword`, and
optional `confirmPassword` (legacy snake-case password fields are also accepted).
It reauthenticates the current account, changes the password, and revokes existing
sessions. Success includes `code: password_updated`; the client must sign in again.
If the password changes but revocation fails, the endpoint returns 503 with
`code: password_changed_revocation_failed`, explicitly reporting that partial outcome.

Deploy the backend and frontend changes together. Existing browser sessions use
the old storage format and require one fresh sign-in after this update. No new
environment variables or database migration are required for these session changes.

## Registration, profile updates, and account emails

`POST /api/v1/auth/register` accepts `name`, `email`, and `password`. Names contain
1–100 characters, and passwords contain 6–128 characters; the same password bounds
apply to password changes. Email addresses are validated without DNS requests,
trimmed, and normalized. Malformed requests return 400 before external account
creation. Existing, deleted, and ambiguous application accounts are rejected with
409, including differently cased addresses. A per-address MongoDB lease prevents
concurrent signup attempts from racing recovery against Firebase cleanup.

Firebase and MongoDB do not share a transaction. After Firebase creation, the
application profile and its verification-email work commit in one MongoDB
transaction. If persistence fails, registration checks for a committed profile
before compensating: it deletes only the Firebase account created by that attempt,
only after confirming that no profile committed and that it still owns the lease.
Uncertain database outcomes and failed cleanup return a sanitized 503 instructing
the user to retry the same details. A crash or failed cleanup can leave a Firebase
account without an application profile; retrying registration restores that profile
only after Firebase verifies the supplied password and account identity. Existing
Firebase accounts are never deleted on a failed recovery. A crashed registration
lease expires after ten minutes. No passwords or authentication tokens are stored
in registration leases or email work.

New profiles store a unique `firebase_uid` independently of their application ID.
Authentication rejects a different Firebase UID even if it has the same email.
Legacy profiles retain their IDs and current email-based matching; no backfill or
manual migration is needed for this change. Deleted application profiles cannot be
restored by signup or account email requests. Firebase-only failed signups can still
receive a password-reset email before retrying registration.

A successful registration returns 201 with `uid`, `emailStatus: queued`, and a
message that the verification email is queued. Email delivery is independent of
account persistence, so a provider failure does not invalidate or duplicate signup.
`POST /api/v1/auth/reset-password` and `/verification-email` accept an email and
return the same generic 202 queued response for known and unknown addresses.
Malformed addresses return 400, queue outages return 503, and address cooldowns
return 429. Public requests do not synchronously look up accounts or send emails.

Account email work uses `account_notifications`. Pending work is coalesced, each
address/type allows at most three new requests per hour with a minimum one-minute
interval, and retries are bounded to five attempts with exponential backoff. Expired
delivery leases can be recovered by another process; stale claims cannot overwrite
new work. Only eligible Firebase accounts receive messages. Unknown, disabled,
deleted, ambiguous, or differently bound accounts are skipped; verification emails
also skip already verified accounts. Records expire after seven days. Delivery is
at least once, so a crash after provider acceptance can produce a duplicate.

The account-email scheduler starts in each serving process on its first HTTP
request, independently of the invitation scheduler. Both coordinate through
MongoDB leases. `ACCOUNT_EMAIL_WORKER_ENABLED` defaults to true; setting it to false
pauses account email delivery while requests continue queuing. Keep the service
health check at `/api/v1/check`. Delivery uses the existing Firebase and MailerSend
settings; no additional credentials are required. Per-address controls do not
replace deployment-wide abuse controls for attacks using many different addresses.

`GET /api/v1/users/profile` returns the signed-in account's `_id`, `name`, `email`,
`bio`, and timestamps. `PUT /api/v1/users/update` saves only supplied `name` and
`bio` fields, validates the complete request before writing, and returns the stored
profile. Bio may be empty and is limited to 1,000 characters. Email stays read-only;
a changed address or unsupported field is rejected rather than silently ignored.
Older clients may include their unchanged email. The legacy `/users/<id>` endpoint
is restricted to the current account, and bios are omitted from invitation sender
summaries. The frontend displays the saved values, updates its cached account name
without replacing credentials, and retains edits when a save fails.

## Database migration before deployment

The new schema stores memberships, races, results, and teams in separate
collections. Existing users keep their IDs, including legacy Firebase UID strings;
Firebase authentication resolves application users by email.

The Docker entrypoint now runs this migration automatically once per container,
before launching Gunicorn. It preflights the live-data conversion, commits it in a
transaction, checks the resulting schema, and creates indexes. Already migrated
databases require zero conversion operations. A validation or transaction failure
stops startup with a single database-preparation error instead of booting workers
against incompatible data. The original embedded fields remain in the database.

On Render, leave **Docker Command** empty to use the image's default command. An
override should contain only the Gunicorn command/arguments; the image entrypoint
still handles database preparation. To use the same startup flow outside Docker,
run `python scripts/start_server.py` (it honors `PORT`, defaulting to 5000).
Set the backend service's **Health Check Path** to `/api/v1/check` to check HTTP
readiness. A deployment label alone does not verify that the app remains healthy.

Stop application writes and take a database backup before the first deployment
that applies the migration. To inspect or apply the migration manually, bypass the
startup entrypoint and use the script directly.
Use the same environment configuration (`MONGO_URI`, `MONGO_DB_NAME`, and other
application variables) as the deployment, then run:

```powershell
.\venv\Scripts\python scripts/migrate_league_schema.py
.\venv\Scripts\python scripts/migrate_league_schema.py --apply
```

The first command is a read-only preflight. It resolves live references and reports
the number of operations. Missing users, invalid race references, duplicate user
emails, and standings that cannot be reconstructed cause it to fail before writing.
The apply command runs the same preflight, then commits the conversion in a
transaction. It preserves embedded legacy fields and existing child records,
retains valid ObjectId race IDs, converts invitations, and can be rerun without
duplicating data. Legacy UUID race IDs receive stable ObjectIds, with the original
value retained as `legacy_id`; per-race standings are linked to the mapped IDs.
Run the dry run again after applying; it should report zero operations. For a
one-off Docker migration command, use `docker run --entrypoint python ...` so the
normal automatic-startup migration does not run before a requested dry run.

Soft-deleted legacy leagues, inactive/deleted legacy invitations, and invitations
to soft-deleted leagues are retained unchanged in their original format. Preflight,
apply, and startup report their counts; missing historical references in these
archives do not prevent serving valid live data. Pending invitations to missing or
malformed league references and corrupt active leagues still fail preflight before
any write. Reactivating an archive requires repairing its references and rerunning
the migration before starting the app. The migration does not erase archives or
invent replacement owners/users.

The app still refuses to start with unmigrated legacy records when launched
directly without the startup script. `scripts/migrate_participants.py` is the
older embedded-format migration and is not a substitute for this migration.

MongoDB must support transactions: use a replica set (including a single-node
replica set for local development) or a sharded cluster. Standalone MongoDB servers
are unsupported for registration/account-email requests, league creation, joins,
invite batches/acceptance, settings changes,
result/team replacements, leaving a league, account rate counters/email-worker
claims, and migration. Failures do not fall back to partial writes.

AI extraction usage counters also require transactions. See the limits below.

League deletion is a soft delete: it hides the league while retaining stored data.

Public discovery (`GET /api/v1/leagues/discovery`, `/all`, `/public`, and the paginated listing)
returns summaries: league ID, name, visibility, status, capacity, driver count,
and next race track/date. These responses omit members, email addresses, owner
information, standings, teams, and the full calendar. Invitation previews use the
same summary format.

`GET /api/v1/leagues/discovery?page=1&page_size=9&q=Spa` is anonymous and returns
`{leagues, page, page_size, total, total_pages}`. Pages are positive integers; page
sizes are limited to 1-50 (default 10), and search text to 100 characters. Search
matches literal league-name text without treating input as a regular expression.
Results use stable newest-first ordering with league ID as a tie breaker. Counts
and next races are batched for the selected page; a nonempty page uses four database
queries rather than two queries per league. Out-of-range pages return an empty
list. Existing `/all` and `/public` clients retain an array response, now limited
to one page with the same query options and an `X-Total-Count` header. The older
authenticated `/<page>/<page_size>` route uses the same bounds and summaries.

Full league details, standings (including an individual driver's standings), and
teams require an existing application user with membership in that league. This
applies to both public and private leagues. Missing, deleted, malformed, and
inaccessible leagues return 404; rejected authentication or inactive accounts return 401. Private
leagues remain hidden from discovery, while their members can still read details.
An invitation grants a summary preview; accepting it grants membership and access
to full details. Leaving the league removes that access.

## Leaving leagues and standings

Leaving removes membership and all current team assignments in one transaction
under the same league lock used by joins and result/team updates. Teams emptied by
that leave are removed; unrelated teams and recorded race results remain intact.
The owner cannot leave. A failed write restores membership and team assignments
together. Rejoining consumes a driver slot through the ordinary join/invite flow.

Driver standings rank points, wins, and podiums descending, with canonical user ID
as a stable final tie breaker. Current participating drivers with no results are
included at zero, and departed drivers' recorded results remain in the history.
Nonparticipating members are excluded. Detail responses, standings endpoints, and
My Leagues use these ranks. Team standings use total points, wins, podiums, then
team name, and include a position in detail and team responses. Team totals reflect
their current assigned drivers. The UI uses backend positions and updates team
totals from the same response as submitted driver results.

## Account request and delivery limits

Signup, password-reset, and verification-resend POST requests share distributed
MongoDB counters before parsing inputs, creating Firebase accounts, or queuing
work. The limits count failed/malformed/repeated requests too, so changing email
addresses does not bypass them. Existing per-address cooldowns and coalescing also
remain in effect. Defaults are configurable in backend environment settings:

| Setting | Default | Fixed UTC window |
| --- | --- | --- |
| `ACCOUNT_REQUEST_IP_LIMIT` | 30 | Requests per peer address per 10 minutes |
| `ACCOUNT_REQUEST_GLOBAL_HOURLY_LIMIT` | 300 | Requests across the service per hour |
| `ACCOUNT_REQUEST_GLOBAL_DAILY_LIMIT` | 1000 | Requests across the service per day |
| `ACCOUNT_DELIVERY_HOURLY_LIMIT` | 100 | Account-email worker attempts per hour |
| `ACCOUNT_DELIVERY_DAILY_LIMIT` | 500 | Account-email worker attempts per day |

Counters persist across workers/restarts and expire through TTL indexes. Client
addresses are normalized and hashed in the counters; IPv6 addresses share a /64
budget. Exhausted request budgets return generic 429 responses with `Retry-After`;
counter outages return sanitized 503 responses and admit no new work. Global limits
also apply when traffic arrives from many addresses.

The account worker commits a job claim and delivery-budget reservation together.
Limits include unknown-account lookups and failed provider attempts. Exhausted
budgets leave jobs pending without consuming retry attempts; the regular poll
resumes them when a window reopens. Setting a request limit to zero stops those
requests; setting a delivery limit to zero pauses claims while retaining queued
work. These application limits bound provider use and queue growth; infrastructure
controls are still needed for volumetric traffic attacks.

`TRUSTED_PROXY_HOPS` defaults to zero, so client-supplied `X-Forwarded-For` is
ignored. Behind a proxy, set it only to the verified number of trusted forwarding
hops, and ensure clients cannot reach the backend around those proxies. The setting
trusts only the client-IP header; host, scheme, and path remain unchanged. A default
of zero behind a proxy shares the peer budget among requests from that proxy;
global budgets work either way. See [Flask's proxy guidance](https://flask.palletsprojects.com/en/stable/deploying/proxy_fix/).

## F1 scoring preset

`F1 Current (2025–Present)` uses full-distance Grand Prix place points without a
fastest-lap bonus, following [Formula 1's rule-change announcement](https://www.formula1.com/en/latest/article/fastest-lap-point-to-be-scrapped-in-2025-after-latest-fia-world-motor-sport.4pUjDzWnGRN7KVWENLc1BY).
Startup seeds the corrected preset and deactivates only the unchanged obsolete
`F1 Current (2010–Present)` default. Its record remains stored. Customized presets,
existing league point settings, and recorded scores are preserved; owners can
configure their own fastest-lap bonus explicitly.
The creation wizard also starts with zero bonus, and selecting a preset applies
its configured bonus. Manual bonus editing remains available.

## AI screenshot extraction

`POST /api/v1/leagues/<league_id>/races/<race_id>/extract-results` accepts one or
two multipart files named `images`. A verified account must be an administrator or
owner of an active league, and the race must belong to that league. Extraction
returns suggestions only; saving race results remains a separate request.

The application limits each file to 6 MiB, the entire request to 13 MiB, decoded
dimensions to 12 million pixels and 8192 pixels per side, and image count to two.
The 13 MiB request cap applies to all application routes. File contents must be
JPEG or PNG; MIME headers alone are insufficient. Empty, corrupt, animated, and
oversized images are rejected before making a paid request. EXIF orientation is
applied, indexed/grayscale/CMYK images are converted, transparency is composited
onto white, and the longest side is reduced to at most 2048 pixels. JPEG encoding
and its resources remain in memory; no application image file is saved.

MongoDB coordinates one active decoding/extraction operation across all workers.
A 120-second lease allows recovery after a worker crash. A busy service returns
429 with `Retry-After`; usage-limit responses also include `Retry-After`. Usage
reservations update user and global counters together. Counters survive restarts
and expire through TTL indexes created at startup. Defaults, configurable through
backend environment variables, are:

| Setting | Default | Scope |
| --- | --- | --- |
| `AI_IMAGE_USER_HOURLY_LIMIT` | 10 | Outbound attempts per account per UTC hour |
| `AI_IMAGE_USER_DAILY_LIMIT` | 30 | Outbound attempts per account per UTC day |
| `AI_IMAGE_GLOBAL_DAILY_LIMIT` | 100 | Outbound attempts across the service per UTC day |

Setting a limit to zero disables extraction for that scope. Invalid uploads and
missing client configuration do not consume quota. Every reserved outbound attempt
counts, including timeouts and provider failures; automatic SDK retries are
disabled. These are attempt limits, not a dollar-denominated billing cap.

The existing `gpt-4o` model is retained. It receives bounded JPEG data URLs and
returns strict structured JSON, using OpenAI's documented [image inputs](https://developers.openai.com/api/docs/guides/images-vision?api-mode=chat)
and [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat).
The response is `{results: [{driver: string | null, position: integer | null}]}`.
Missing or unreadable fields stay null; the backend validates the structure and
bounds again. Invalid, refused, or truncated responses return 502, provider/config
outages return 503, and SDK timeouts return 504. Raw provider content and error
details are never returned. `store=false` disables stored completion retrieval;
it does not make a claim about the provider's data-retention policies.

Provider calls use a 20-second SDK timeout and 4000 output-token cap. Image requests
have a 60-second browser timeout, while Docker and the default startup script give
Gunicorn workers 90 seconds. Deployment overrides must retain a suitable worker
timeout. Closing a dialog discards its eventual response but does not cancel an
already-started provider call or undo a completed result submission.

`tests/test_images.py` tests actual Pillow uploads, authorization, image limits,
provider failures, quota rollback, and lease recovery with mocked external calls.
Real MongoDB worker concurrency and live AI recognition require separate integration
checks; the local tests do not incur API charges.
