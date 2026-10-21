# Padeli Hyeti

Padeli Hyeti is a small Flask/SQLite client-server application for finding padel players and organizing shared games. Every page and action talks to one central Flask server and one persistent SQLite database. It needs no external service and loads all assets locally.

## What works

- Registration (name, phone, skill level, password + confirmation) with server-side validation and Werkzeug salted password hashing
- Login by phone number (any common format) or by a unique player name; ambiguous names are refused with a hint to use the phone number
- One generic error for "unknown account" and "wrong password", so the login form cannot reveal which numbers are registered
- Flask sessions, logout, session/CSRF rotation on login, and protected pages/endpoints
- Private profile view and editing (name, phone, skill level, location, bio); public profiles never show phone numbers or password data
- Database-backed player search by name, skill level and location
- Game creation with full server-side validation (no past dates or already-passed times today), organizer auto-joined as first participant
- Game listing/filtering with organizer, date, time, location, level, capacity and status (`available`, `full`, `past`)
- Transaction-safe joining (`BEGIN IMMEDIATE`) that never overfills a game, even with simultaneous requests
- Feedback (rating 1–5, optional comment) only between participants of the same game, no self-reviews, no duplicates; shown on public profiles
- Session-bound CSRF protection on every state-changing request
- Consistent JSON envelopes for every API response, including 404/405/500 errors
- Real HTTP status codes: 200, 201, 400, 401, 403, 404, 405, 409 and controlled 500

## Start on Windows PowerShell

From the project folder:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m flask --app app init-db
python app.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Stop the server with `Ctrl+C`.

- The database is also initialized automatically on startup. `init-db` is safe to run more than once and is included so initialization can be demonstrated.
- Data persists in `instance/padeli.sqlite3` between restarts.
- If `PADELI_SECRET_KEY` is not set, a random key is generated on first start and stored in `instance/secret_key`, so logins survive restarts. Both files are git-ignored. Delete `instance/padeli.sqlite3` to start with an empty database.

If PowerShell blocks virtual-environment activation, run this once in that window and activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

On macOS/Linux the equivalent is `python3 -m venv .venv`, `source .venv/bin/activate`, then the same `pip`, `flask` and `python app.py` commands.

### Run the automated tests

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest
```

The suite (111 tests) uses a fresh temporary SQLite database per test and never touches `instance/padeli.sqlite3`.

| File | Covers |
|---|---|
| `tests/test_requirements.py` | One focused test per requirement: registration/login validation, logout, protected routes, CSRF, profile privacy, search, game validation, joining (including an 8-thread race for 3 places), feedback rules, JSON errors, cookie flags, secret key, restart persistence, SQLite constraints |
| `tests/test_end_to_end.py` | The full two-athlete workflow with two independent cookie sessions |
| `tests/test_app.py` | Original integration tests, including every required status code and the controlled 500 |
| `tests/helpers.py` | Shared request helpers (fetch CSRF token, register, log in, create game) |

### Optional configuration

The application binds only to localhost by default and debug mode is off.

```powershell
$env:PADELI_HOST = "127.0.0.1"
$env:PADELI_PORT = "8000"
$env:PADELI_DATABASE = "C:\full\path\to\padeli.sqlite3"
$env:PADELI_SECRET_KEY = "a-long-random-value"   # overrides instance/secret_key
$env:PADELI_SECURE_COOKIES = "1"                  # only when served over HTTPS
python app.py
```

Do not set `FLASK_DEBUG=1` for a LAN demonstration.

## Project structure

```text
paddelni/
├── app.py                    # Local server entry point (host/port configuration)
├── padeli/
│   ├── __init__.py           # App factory, secret key, sessions, CSRF and error handling
│   ├── api.py                # JSON authentication/player/game/feedback endpoints
│   ├── views.py              # Server-rendered Jinja pages
│   ├── db.py                 # SQLite lifecycle and init-db command
│   ├── schema.sql            # Tables, foreign keys, checks and uniqueness rules
│   ├── static/               # Local CSS and minimal fetch-based JavaScript
│   └── templates/            # Jinja pages and reusable game card
├── tests/                    # pytest suite (see table above)
├── requirements.txt
├── README.md
└── NETWORK_LAB.md            # Future LAN and Wireshark procedure (not executed)
```

## JSON API

Every response uses one of these shapes:

```json
{"success": true, "message": "...", "data": {}}
```

```json
{"success": false, "error": {"code": "machine_readable_code", "message": "Friendly message"}}
```

State-changing requests (`POST`/`PUT`) to `/api/register`, `/api/login`, and to any endpoint while logged in require the `X-CSRF-Token` header. Browsers get the token from the page; an API client calls `GET /api/csrf-token` first, in the same cookie session.

| Method | Endpoint | Login | Purpose |
|---|---|:---:|---|
| GET | `/api/health` | No | Server/database health |
| GET | `/api/csrf-token` | No | Token for the current cookie session |
| POST | `/api/register` | No | Register (`name`, `phone`, `skill_level`, `password`, `confirm_password`, optional `location`, `bio`) |
| POST | `/api/login` | No | Start a session (`identifier` = phone or unique name, `password`) |
| POST | `/api/logout` | Yes | End the session |
| GET | `/api/profile` | Yes | Your own profile, including your phone number |
| PUT | `/api/profile` | Yes | Update any of `name`, `phone`, `skill_level`, `location`, `bio` (always the logged-in user) |
| GET | `/api/players` | No | Search players: `name`, `skill_level`, `location` |
| GET | `/api/players/<id>` | No | Public player data with average rating (phone shown only to its owner) |
| GET | `/api/players/<id>/feedback` | No | Feedback received by a player |
| GET | `/api/games` | No | List games: `skill_level`, `location`, `available=1` (open, not started) |
| QUERY | `/api/query?resource=games` | No | Optional bonus: read-only game catalogue using the non-standard HTTP QUERY method; supports the same filters as `/api/games` |
| POST | `/api/games` | Yes | Create a game (`title`, `location`, `date` YYYY-MM-DD, `time` HH:MM, `required_level`, `max_players` 2–8) |
| GET | `/api/games/<id>` | No | Game details and participants |
| POST | `/api/games/<id>/join` | Yes | Join an available game |
| POST | `/api/feedback` | Yes | Review a co-participant (`game_id`, `reviewed_user_id`, `rating` 1–5, optional `comment` ≤ 300 chars) |

All frontend fetch calls use relative URLs, so no server IP is embedded in the client.

## HTTP status demonstrations

Each number is the actual HTTP status, not a value inside a 200 response.

| Status | Request / scenario | Error code |
|---|---|---|
| `200 OK` | `GET /api/health`, `GET /api/games/<existing-id>`, successful login or join | — |
| `201 Created` | Valid `POST /api/register`, `POST /api/games`, or `POST /api/feedback` | — |
| `400 Bad Request` | Missing/invalid fields, bad phone, short or mismatched password, past date, missing CSRF token, self-review, ambiguous name | `missing_fields`, `invalid_phone`, `short_password`, `password_mismatch`, `past_date`, `invalid_csrf`, `self_feedback`, `ambiguous_name`, … |
| `401 Unauthorized` | Wrong password or unknown account; any protected endpoint while logged out | `invalid_credentials`, `authentication_required` |
| `403 Forbidden` | Feedback between users who did not share that game | `not_shared_game` |
| `404 Not Found` | `GET /api/games/999999`, `GET /api/players/999999`, unknown `/api/...` route | `game_not_found`, `player_not_found`, `not_found` |
| `405 Method Not Allowed` | e.g. `DELETE /api/health` (JSON body + `Allow` header) | `method_not_allowed` |
| `409 Conflict` | Phone already registered, joining twice, joining a full game, joining a started game, duplicate feedback | `phone_exists`, `already_joined`, `game_full`, `game_started`, `duplicate_feedback` |
| `500 Internal Server Error` | Only via the test-only endpoint `/api/test/error` when `TESTING` is on; it returns 404 in the normal app. The general error handler still converts real crashes into a JSON 500 without a stack trace. | `server_error` |

### From PowerShell while the server runs

```powershell
# 200
(Invoke-WebRequest http://127.0.0.1:8000/api/health).StatusCode

# 404 (PowerShell raises on 4xx; read the status from the exception)
try { Invoke-WebRequest http://127.0.0.1:8000/api/games/999999 } catch { $_.Exception.Response.StatusCode.value__ }

# Optional QUERY bonus (read-only, non-standard HTTP method)
curl.exe -X QUERY "http://127.0.0.1:8000/api/query?resource=games"

# 401 → log in with a wrong password using a session that holds a CSRF token
$s = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$token = (Invoke-RestMethod http://127.0.0.1:8000/api/csrf-token -WebSession $s).data.csrf_token
$body = @{ identifier = "nobody"; password = "wrong-password" } | ConvertTo-Json
try {
  Invoke-WebRequest http://127.0.0.1:8000/api/login -Method Post -WebSession $s `
    -ContentType "application/json" -Headers @{ "X-CSRF-Token" = $token } -Body $body
} catch { $_.Exception.Response.StatusCode.value__ }
```

The browser UI sends the CSRF token automatically. Developer tools → Network shows each method, URL, body and status.

## Two-browser end-to-end demonstration

Use a normal window for Athlete 1 and a private/incognito window (or another browser) for Athlete 2. They keep separate session cookies while sharing the same server and database.

1. Normal window: register Athlete 1, then log in.
2. **Create game** with a future date. The detail page lists Athlete 1 as the first participant.
3. Private window: register Athlete 2 and log in.
4. **Games** → open Athlete 1's game → **Join game**.
5. Refresh Athlete 1's game page: Athlete 2 is now listed.
6. **Find players**: search Athlete 2 by name, level or location and open the public profile.
7. On the shared game page, click **Leave feedback** beside Athlete 2, choose a rating and submit.
8. Open Athlete 2's public profile: the feedback and average rating appear.
9. Conflicts: join again from Athlete 2, or fill a two-player game and try from a third window (409).

`tests/test_end_to_end.py` automates exactly this flow with two independent Flask test clients.

## Security notes

- Passwords are stored only as Werkzeug salted hashes and never returned or logged.
- All SQL is parameterized; `PRAGMA foreign_keys = ON`, `UNIQUE` and `CHECK` constraints back up the application rules.
- Session cookies are `HttpOnly` and `SameSite=Lax`; set `PADELI_SECURE_COOKIES=1` only behind HTTPS.
- The secret key is configurable through `PADELI_SECRET_KEY`; otherwise a random per-installation key is generated (no hard-coded default).
- Debug mode is off unless `FLASK_DEBUG=1`.

## Known limitations

- University demonstration, not an internet-facing service: no password reset, account deletion, game editing/cancellation, leaving a game, or moderation.
- Uses Flask's development server; a production deployment would need a WSGI server (e.g. Waitress on Windows) and HTTPS.
- Plain HTTP does not encrypt credentials on a LAN. Use dummy accounts for the network lab.
- Dates and times are interpreted in the server computer's local time zone.
- Feedback can be left as soon as both players are in the game; it does not wait for the match to be played.
- Phone numbers are checked for format (7–15 digits, optional `+`, spaces, dashes, dots, brackets) but not verified by SMS.
- No rate limiting on login attempts.

See [NETWORK_LAB.md](NETWORK_LAB.md) for the separate, future networking procedure. The project changes no firewall or network setting.
