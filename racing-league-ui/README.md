# Racing League frontend

React, TypeScript, and Vite. Run commands from this directory.

## Development checks

```powershell
npm install
npm run dev
```

Development defaults to `http://localhost:5000/api`. To override it, copy
`.env.example` to `.env.development.local` and change `VITE_API_URL` there.
Keep development overrides in that mode-specific file: a generic `.env` is also
loaded by production builds.

The API URL must be an absolute HTTP(S) URL ending in `/api`. API paths append
`/v1/...` to this base URL. Credentials, query strings, and fragments are rejected.

```powershell
npm test
$env:VITE_API_URL = 'http://localhost:5000/api' # Explicit local preview build.
npm run build
npm run preview
npm run lint
```

Session tests execute the actual session and Axios interceptor code using mocked
HTTP responses and separate browser storage contexts. They cover expiry,
concurrent renewal, Web Locks across tabs, revocation, temporary outages,
permission denials, account changes, and late responses after logout. They do not
contact Firebase or the configured backend. Configuration tests also exercise
the actual Vite configuration: missing or invalid build settings are rejected,
development defaults to localhost, and explicit build settings take precedence.

## Build and deployment configuration

Every build requires an explicit `VITE_API_URL`, including builds with a custom
mode. Missing or invalid values stop the build before bundling. There is no
committed remote fallback. Use the browser-accessible backend URL, including
`/api`; Docker's internal `backend` hostname is not accessible to the browser.

For the Render frontend service, set `VITE_API_URL` to the real HTTPS backend URL
in the service's environment settings before deploying. Render passes it as a
Docker build argument, which the frontend Dockerfile consumes during `npm run
build`. For manual Docker builds:

```powershell
docker build --build-arg VITE_API_URL=https://your-backend.example/api -t racing-league-ui .
```

The example hostname is a placeholder. Compose supplies `http://localhost:5000/api`
as its explicit local build argument; a shell or root Compose `.env` value can
override it. The frontend `.env.development.local` does not configure Compose.

Vite embeds this public URL in the JavaScript bundle at build time. Changing it
on the running Nginx container does not change the bundle; rebuild the image.
Local env files, credentials, and generated directories are excluded from Docker
contexts. The tracked `.env.example` contains only a development example.

## Session behavior

`src/services/session.ts` stores credentials, expiry, and canonical user information
in one record. The default login uses per-tab session storage; remembered sessions
use local storage. Logging out leaves a tab sign-out marker so the tab cannot
silently switch to a different remembered account. Old separate `token` and `user`
records are removed; existing users need one fresh sign-in after deploying this
update.

`src/services/auth-client.ts` renews credentials before authenticated requests when
less than a minute remains. Concurrent requests share one renewal. Browsers with
Web Locks also coordinate remembered-session renewal across tabs. Expired-token
401 responses trigger at most one renewal and retry. Revoked, disabled, invalid,
or missing application accounts end the session; 403 permission denials, network failures,
and 503 outages preserve credentials for retry.

Session IDs prevent old requests or renewals from clearing, overwriting, or
returning protected data into a newer account session. Startup verification gets
the canonical user from the backend. A shared-storage account change reloads the
page to discard the previous account's data. Error objects omit request headers,
bodies, and raw Axios configuration, keeping credentials out of logged errors.

Normal logout clears browser credentials. Password changes revoke existing
sessions and redirect to sign-in. The API also supports explicit account-wide
logout; it is separate from the normal browser logout action.

Deploy with the matching backend login, refresh, and verification endpoints.
The session changes add no dependencies or environment variables beyond the
existing API URL setting required for builds above.

## Registration and profiles

Registration reports account creation and queued verification-email work. A
temporary signup failure asks users to retry the same details; the backend can
recover a missing profile after verifying ownership with their password. Signup
does not create a browser session before email verification.

Profile name and bio are editable; the sign-in email is read-only. The form uses
the profile returned by the server after saving, and the account name in session
storage updates without replacing credentials. Failed saves retain edits and show
the server error. A failed initial load offers a retry instead of presenting an
empty form that could overwrite existing data. Names allow 1–100 characters,
bios up to 1,000, and new passwords 6–128; longer, unique passwords are encouraged.

Password-reset and verification-resend responses describe queued work without
revealing whether an account exists. Network failures, queue outages, and cooldowns
appear as errors and remain retryable. The pages no longer show successful email
delivery after failed requests. Pending work is coalesced and delivered by the
backend account-email worker; see the [backend account instructions](../racing-league-app/README.md#registration-profile-updates-and-account-emails).

Tests also execute the actual account page handlers with mocked hooks and services,
covering read-only email, saved values, failed profile loading/saving, and failed
email requests. Session/API tests check cached name updates and late responses after
an account change. No browser or external service is needed for these checks.

## League participation and invitations

The creation wizard sends `creatorParticipates` and invitation addresses explicitly.
The backend determines ownership from the signed-in account and saves the league,
calendar, owner membership, and pending invitations together. Opting out keeps the
owner's administrative access while excluding them from driver capacity, standings,
results, and teams. Invitees become participating members only after accepting;
pending invitations do not reserve a driver slot.

Owners can change their driver participation under league settings. Opting in
requires room in the roster; opting out requires correcting existing driver results
and removing their team assignment first. Existing memberships remain participating
unless changed explicitly.

The Invite Players dialog lists pending invitations and polls email delivery status.
It stays open after creating invitations so the owner can review progress and retry
failed notifications. Creation success means invitations were saved and emails
queued; email failure does not undo an invitation. `Email sent` means the provider
accepted the notification. Configure the backend's `FRONTEND_URL` to this frontend's
public origin so the email opens `/leagues`; see the [backend README](../racing-league-app/README.md#docker-runtime-configuration).

The league page uses team totals from the same full response as submitted race
results, so the team tab updates immediately. Driver and team views sort by backend
position; older responses fall back to points, wins, podiums, and a stable key.
Leaving removes current team assignments (including teams made empty) while keeping
recorded race history. Team totals use the current team roster.
The creation wizard's fastest-lap bonus starts at zero and follows the selected
preset; owners can still enter a custom bonus.

## Public discovery

Find Leagues fetches one server page of nine summaries at a time using the anonymous
`/leagues/discovery` endpoint. The pagination and result count come from server
metadata. Search matches across all public leagues, is debounced for 250 ms, and
returns to page one when edited. The search field remains mounted during refreshes
and after empty results. Late responses from a previous query/page are ignored;
failed searches offer a retry. If deletions remove the last page, the page refetches
the new last page instead of staying empty.

The backend caps page size and search length, batches related counts and next
races, and keeps private leagues and member details out of every summary. Deploy
with the matching backend endpoint. Tests execute the actual discovery page and
result-submission callback with mocked hooks/services.

## Screenshot uploads and AI result drafts

The result dialog accepts one or two JPEG/PNG files, at most 6 MiB each. It rejects
an invalid selection as a whole and retains the previous files for retry. The file
input resets after selection, allowing the same file to be selected again after
removal. Ordered object-URL previews replace asynchronous FileReader callbacks;
URLs are released after removal, closing, or unmounting.

Extraction uses a multipart request with the browser supplying its boundary and a
60-second timeout. Screenshots go to OpenAI for analysis. The backend verifies
actual content, imposes pixel and usage limits, and does not save application image
files; see [backend extraction settings](../racing-league-app/README.md#ai-screenshot-extraction).

AI output is a draft, matched by unique exact names or aliases after normalizing
case and whitespace. Substring guesses are rejected, identical rows from overlapping
images are deduplicated, and conflicting placements are left for manual review.
Unmatched drivers keep their relative order while filling the unused positions,
so every driver has one unique position. The dialog identifies unmatched drivers
and skipped rows explicitly. Existing DNF and fastest-lap selections are preserved;
the AI only suggests ordering.

Users must confirm that they reviewed the driver order, DNF, and fastest lap before
submitting an AI-assisted draft. Further manual changes clear that confirmation.
Upload/removal, reordering, driver flags, and submission are disabled while a
request is pending. Responses from a previous race, league, roster, closed dialog,
or unmounted component cannot update the current draft. Closing the dialog discards
late callbacks; an already-started backend operation may still finish.

`npm test` includes upload validation and matching regressions, the actual multipart
API call, and actual dialog handlers/hooks with mocked services. Tests cover review
confirmation, preserved flags, stale responses, retained edits after failure, and
preview cleanup without a browser or live AI calls.
