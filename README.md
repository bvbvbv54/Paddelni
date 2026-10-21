# Padeli Hyeti

Padeli Hyeti is a small Flask/SQLite client-server application for finding padel players and organizing shared games. Every page and action talks to one central Flask server and one persistent SQLite database. It requires no external service and loads all application assets locally.

## What works

- Registration with validated, normalized phone numbers and Werkzeug password hashing
- Login by phone or by an unambiguous name, Flask sessions, and logout
- Private profile editing and public profiles without phone numbers or password data
- Database-backed player search by name, skill level, and location
- Game creation, listing, filtering, details, and participant capacity
- Transaction-safe game joining with duplicate/full-game protection
- Feedback only between two participants in the same game, with duplicate/self-review protection
- Session-bound CSRF protection on every state-changing browser request
- Friendly page states and consistent JSON success/error envelopes
- Real HTTP response codes including 200, 201, 400, 401, 404, 409, and 500 handling

## Start on Windows PowerShell

From the project folder:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
$env:PADELI_SECRET_KEY = "replace-this-with-a-long-random-local-secret"
python -m flask --app app init-db
python app.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Stop the server with `Ctrl+C`.

The database is also initialized automatically on startup. The explicit `init-db` command is safe to run more than once and is included so initialization can be demonstrated. Development data persists in `instance/padeli.sqlite3` between restarts.

If PowerShell blocks virtual-environment activation, run this once in that PowerShell window and activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### Run the automated tests

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest
```

Tests use a separate temporary SQLite database. They never edit `instance/padeli.sqlite3`.

### Optional local configuration

The application binds only to localhost by default.

```powershell
$env:PADELI_HOST = "127.0.0.1"
$env:PADELI_PORT = "8000"
$env:PADELI_DATABASE = "C:\full\path\to\padeli.sqlite3"
$env:PADELI_SECRET_KEY = "a-long-random-value"
python app.py
```

Debug mode is off by default. Do not use Flask debug mode for the LAN demonstration.

## Project structure

```text
PaddelLab/
├── app.py                    # Local server entry point (host/port configuration)
├── padeli/
│   ├── __init__.py           # App factory, sessions, CSRF and error handling
│   ├── api.py                # JSON authentication/player/game/feedback endpoints
│   ├── db.py                 # SQLite lifecycle and init-db command
│   ├── schema.sql            # Tables, foreign keys, checks and uniqueness rules
│   ├── static/               # Local CSS and minimal fetch-based JavaScript
│   └── templates/            # Jinja pages and reusable game card
├── tests/                    # pytest integration and two-client workflow tests
├── requirements.txt
├── README.md
└── NETWORK_LAB.md            # Future LAN and Wireshark procedure (not executed)
```

## JSON API

Responses always use one of these shapes:

```json
{"success": true, "message": "...", "data": {}}
```

```json
{"success": false, "error": {"code": "machine_readable_code", "message": "Friendly message"}}
```

State-changing requests require the `X-CSRF-Token` header. A browser receives the token in the page. An API client can first call `GET /api/csrf-token` in the same cookie session.

| Method | Endpoint | Authentication | Purpose |
|---|---|---:|---|
| GET | `/api/health` | No | Server/database health |
| GET | `/api/csrf-token` | No | Token for the current cookie session |
| POST | `/api/register` | No | Register an account |
| POST | `/api/login` | No | Start an authenticated session |
| POST | `/api/logout` | Yes | End the session |
| GET | `/api/players` | No | Search/list players |
| GET | `/api/players/<id>` | No | Public player data (own phone only) |
| PUT | `/api/profile` | Yes | Update the current user's profile |
| GET | `/api/games` | No | Search/list games |
| POST | `/api/games` | Yes | Create a game and join as organizer |
| GET | `/api/games/<id>` | No | Game and participant details |
| POST | `/api/games/<id>/join` | Yes | Join an available game |
| POST | `/api/feedback` | Yes | Review a player from a shared game |
| GET | `/api/players/<id>/feedback` | No | List received feedback |

Query filters are supported on `/api/players` (`name`, `skill_level`, `location`) and `/api/games` (`skill_level`, `location`, `available=1`). All frontend fetch calls use relative URLs, so no server IP is embedded in the client.

## Required HTTP status demonstrations

The status number is the actual HTTP response status, not a number embedded in a successful response.

| Status | Request/scenario |
|---|---|
| `200 OK` | `GET /api/health`, `GET /api/players/<existing-id>`, or `GET /api/games/<existing-id>` |
| `201 Created` | Valid `POST /api/register` or authenticated valid `POST /api/games` |
| `400 Bad Request` | `POST /api/register` with required fields missing, an invalid CSRF token, or invalid form data |
| `401 Unauthorized` | `POST /api/login` with an incorrect password, or a protected operation while logged out |
| `404 Not Found` | `GET /api/games/999999` or `GET /api/players/999999` |
| `409 Conflict` | Register a phone twice, join the same game twice, or join a full game |
| `500 Internal Server Error` | The automated suite enables and calls a controlled test-only endpoint; it is unavailable in the normal app. The general production handler remains active. |

To inspect a simple response from PowerShell while the server runs:

```powershell
$response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health"
$response.StatusCode
$response.Content
```

The application UI is the easiest safe way to demonstrate state-changing responses because it sends the matching CSRF token automatically. Browser developer tools → Network shows each method, URL, request/response body, and status.

## Two-browser end-to-end demonstration

Use a normal browser window for Athlete 1 and a private/incognito window (or another browser) for Athlete 2. These keep separate session cookies while using the same server and database.

1. In the normal window, register Athlete 1, then log in.
2. Open **Create game**, enter a future date and valid details, and submit. The game detail page shows Athlete 1 as the first participant.
3. In the private window, register Athlete 2 and log in.
4. Open **Games**, select Athlete 1's game, and click **Join game**.
5. Return to or refresh Athlete 1's game page. Athlete 2 now appears in the participant list.
6. Open **Find players** and search for Athlete 2 by name, level, or location. Open the result to see the public profile.
7. On the shared game page, click **Leave feedback** beside Athlete 2, select a rating, and submit.
8. Open Athlete 2's public profile. The persisted feedback and average rating appear there.
9. For conflict handling, try joining from Athlete 2 again or fill a two-player game and attempt to join from a third session.

The automated test `test_two_clients_share_game_and_join` performs the central two-client database workflow with two independent Flask cookie sessions.

## Security and limitations

- Passwords are hashed and never returned by an endpoint.
- SQLite queries are parameterized; write constraints also exist in the database schema.
- Session cookies are HTTP-only and SameSite=Lax. Set `PADELI_SECURE_COOKIES=1` only when serving through HTTPS.
- This is a university demonstration, not an internet-facing service. There is no password recovery, account deletion, moderation, or production WSGI deployment.
- Plain HTTP is acceptable for the current localhost phase but does not encrypt credentials over a LAN. Use dummy accounts for a future lab and do not expose this development server to the public internet.

See [NETWORK_LAB.md](NETWORK_LAB.md) for the separate, future networking procedure. No firewall or network setting is changed by this project.

