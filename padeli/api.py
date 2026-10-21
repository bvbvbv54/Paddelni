"""JSON API for Padeli Hyeti."""

from __future__ import annotations

import re
import secrets
import sqlite3
from datetime import date, datetime
from functools import wraps

from flask import Blueprint, current_app, g, jsonify, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db


bp = Blueprint("api", __name__, url_prefix="/api")
SKILL_LEVELS = ("Beginner", "Intermediate", "Advanced")
# Digits with optional leading "+" and common separators (spaces, dashes, dots, brackets).
PHONE_PATTERN = re.compile(r"^\+?[\d\s\-().]+$")
# Compared against when no account matches, so a missing account costs the same time as a wrong password.
_DUMMY_PASSWORD_HASH = generate_password_hash("padeli-timing-equaliser")


def success(data=None, message: str = "Request completed successfully.", status: int = 200):
    response = jsonify({"success": True, "message": message, "data": data if data is not None else {}})
    response.status_code = status
    return response


def error(status: int, code: str, message: str):
    return jsonify({"success": False, "error": {"code": code, "message": message}}), status


def json_body():
    data = request.get_json(silent=True)
    if data is None and request.form:
        data = request.form.to_dict()
    return data if isinstance(data, dict) else {}


def normalized_phone(value: object) -> str:
    return re.sub(r"\D", "", str(value or ""))


def canonical_skill(value: object) -> str | None:
    supplied = str(value or "").strip().casefold()
    return next((level for level in SKILL_LEVELS if level.casefold() == supplied), None)


def validate_user_fields(data: dict, *, require_password: bool = True):
    required = ["name", "phone", "skill_level"]
    if require_password:
        required += ["password", "confirm_password"]
    missing = [field for field in required if not str(data.get(field, "")).strip()]
    if missing:
        labels = ", ".join(field.replace("_", " ") for field in missing)
        return None, error(400, "missing_fields", f"Please provide: {labels}.")

    name = str(data.get("name", "")).strip()
    phone = normalized_phone(data.get("phone"))
    skill = canonical_skill(data.get("skill_level"))
    location = str(data.get("location", "")).strip()
    bio = str(data.get("bio", "")).strip()

    if not 2 <= len(name) <= 80:
        return None, error(400, "invalid_name", "Name must be between 2 and 80 characters.")
    if not PHONE_PATTERN.fullmatch(str(data.get("phone", "")).strip()) or not 7 <= len(phone) <= 15:
        return None, error(400, "invalid_phone", "Enter a valid phone number containing 7 to 15 digits.")
    if skill is None:
        return None, error(400, "invalid_skill_level", "Choose Beginner, Intermediate or Advanced.")
    if len(location) > 100:
        return None, error(400, "invalid_location", "Location must be 100 characters or fewer.")
    if len(bio) > 300:
        return None, error(400, "invalid_bio", "Description must be 300 characters or fewer.")

    clean = {"name": name, "phone": phone, "skill_level": skill, "location": location, "bio": bio}
    if require_password:
        password = str(data.get("password", ""))
        confirmation = str(data.get("confirm_password", ""))
        if len(password) < 8:
            return None, error(400, "short_password", "Password must be at least 8 characters.")
        if password != confirmation:
            return None, error(400, "password_mismatch", "Password and confirmation do not match.")
        clean["password"] = password
    return clean, None


def login_required(view):
    @wraps(view)
    def wrapped(**kwargs):
        if g.user is None:
            return error(401, "authentication_required", "Log in to perform this action.")
        return view(**kwargs)

    return wrapped


def player_dict(row, *, include_phone: bool = False) -> dict:
    player = {
        "id": row["id"],
        "name": row["name"],
        "skill_level": row["skill_level"],
        "location": row["location"],
        "bio": row["bio"],
        "created_at": row["created_at"],
    }
    if include_phone:
        player["phone"] = row["phone"]
    keys = row.keys()
    if "average_rating" in keys:
        player["average_rating"] = round(row["average_rating"], 1) if row["average_rating"] is not None else None
        player["feedback_count"] = row["feedback_count"]
    return player


def parse_game_time(value: object):
    text = str(value or "").strip()
    for pattern in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(text, pattern).time()
        except ValueError:
            continue
    raise ValueError("invalid time")


def game_has_started(game_date: str, game_time: str) -> bool:
    """True once the scheduled start (server local time) is in the past."""
    try:
        start = datetime.combine(date.fromisoformat(game_date), parse_game_time(game_time))
    except ValueError:
        return False
    return start <= datetime.now()


def game_dict(row) -> dict:
    count = row["participant_count"]
    maximum = row["max_players"]
    if game_has_started(row["game_date"], row["game_time"]):
        status = "past"
    elif count >= maximum:
        status = "full"
    else:
        status = "available"
    return {
        "id": row["id"],
        "title": row["title"],
        "organizer": {"id": row["organizer_id"], "name": row["organizer_name"]},
        "location": row["location"],
        "date": row["game_date"],
        "time": row["game_time"],
        "required_level": row["required_level"],
        "participant_count": count,
        "max_players": maximum,
        "available_places": max(maximum - count, 0),
        "status": status,
        "created_at": row["created_at"],
    }


def fetch_game(game_id: int):
    return get_db().execute(
        """
        SELECT g.*, u.name AS organizer_name, COUNT(gp.id) AS participant_count
        FROM games g
        JOIN users u ON u.id = g.organizer_id
        LEFT JOIN game_participants gp ON gp.game_id = g.id
        WHERE g.id = ?
        GROUP BY g.id
        """,
        (game_id,),
    ).fetchone()


@bp.get("/health")
def health():
    get_db().execute("SELECT 1").fetchone()
    return success({"status": "healthy", "service": "Padeli Hyeti"}, "Server and database are ready.")


@bp.get("/csrf-token")
def csrf():
    token = session.get("csrf_token")
    if token is None:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return success({"csrf_token": token}, "CSRF token created.")


@bp.post("/register")
def register():
    clean, validation_error = validate_user_fields(json_body())
    if validation_error:
        return validation_error

    database = get_db()
    try:
        cursor = database.execute(
            """
            INSERT INTO users (name, phone, password_hash, skill_level, location, bio)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                clean["name"],
                clean["phone"],
                generate_password_hash(clean["password"]),
                clean["skill_level"],
                clean["location"],
                clean["bio"],
            ),
        )
        database.commit()
    except sqlite3.IntegrityError:
        return error(409, "phone_exists", "An account with that phone number already exists.")

    user = database.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    response = success(player_dict(user, include_phone=True), "Account created. You can now log in.", 201)
    response.headers["Location"] = url_for("api.get_player", player_id=user["id"])
    return response


@bp.post("/login")
def login():
    data = json_body()
    identifier = str(data.get("identifier", "")).strip()
    password = str(data.get("password", ""))
    if not identifier or not password:
        return error(400, "missing_fields", "Enter your phone number or name and your password.")

    database = get_db()
    rows = []
    phone = normalized_phone(identifier)
    if PHONE_PATTERN.fullmatch(identifier) and 7 <= len(phone) <= 15:
        rows = database.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchall()
    if not rows:
        rows = database.execute("SELECT * FROM users WHERE name = ? COLLATE NOCASE", (identifier,)).fetchall()
        if len(rows) > 1:
            return error(400, "ambiguous_name", "More than one player has that name. Log in with your phone number.")

    user = rows[0] if rows else None
    # One generic answer for "no such account" and "wrong password" so the login form
    # cannot be used to discover which phone numbers are registered.
    password_hash = user["password_hash"] if user is not None else _DUMMY_PASSWORD_HASH
    if not check_password_hash(password_hash, password) or user is None:
        return error(401, "invalid_credentials", "Incorrect phone number/name or password.")

    session.clear()
    session["user_id"] = user["id"]
    session["csrf_token"] = secrets.token_urlsafe(32)
    return success(player_dict(user, include_phone=True), f"Welcome back, {user['name']}!")


@bp.post("/logout")
@login_required
def logout():
    session.clear()
    session["csrf_token"] = secrets.token_urlsafe(32)
    return success({}, "You have been logged out.")


@bp.get("/players")
def list_players():
    name = request.args.get("name", "").strip()
    location = request.args.get("location", "").strip()
    supplied_skill = request.args.get("skill_level", "").strip()
    skill = canonical_skill(supplied_skill) if supplied_skill else None
    if supplied_skill and skill is None:
        return error(400, "invalid_skill_level", "Choose Beginner, Intermediate or Advanced.")

    clauses = ["1 = 1"]
    parameters: list[object] = []
    if name:
        clauses.append("u.name LIKE ? COLLATE NOCASE")
        parameters.append(f"%{name}%")
    if location:
        clauses.append("u.location LIKE ? COLLATE NOCASE")
        parameters.append(f"%{location}%")
    if skill:
        clauses.append("u.skill_level = ?")
        parameters.append(skill)

    rows = get_db().execute(
        f"""
        SELECT u.*, AVG(f.rating) AS average_rating, COUNT(f.id) AS feedback_count
        FROM users u
        LEFT JOIN feedback f ON f.reviewed_user_id = u.id
        WHERE {' AND '.join(clauses)}
        GROUP BY u.id
        ORDER BY u.name COLLATE NOCASE
        """,
        parameters,
    ).fetchall()
    players = [player_dict(row, include_phone=g.user is not None and row["id"] == g.user["id"]) for row in rows]
    return success({"players": players, "count": len(players)}, "Players retrieved.")


@bp.get("/players/<int:player_id>")
def get_player(player_id: int):
    row = get_db().execute(
        """
        SELECT u.*, AVG(f.rating) AS average_rating, COUNT(f.id) AS feedback_count
        FROM users u
        LEFT JOIN feedback f ON f.reviewed_user_id = u.id
        WHERE u.id = ?
        GROUP BY u.id
        """,
        (player_id,),
    ).fetchone()
    if row is None:
        return error(404, "player_not_found", "That player does not exist.")
    return success(
        player_dict(row, include_phone=g.user is not None and row["id"] == g.user["id"]),
        "Player retrieved.",
    )


@bp.get("/profile")
@login_required
def current_profile():
    row = get_db().execute(
        """
        SELECT u.*, AVG(f.rating) AS average_rating, COUNT(f.id) AS feedback_count
        FROM users u
        LEFT JOIN feedback f ON f.reviewed_user_id = u.id
        WHERE u.id = ?
        GROUP BY u.id
        """,
        (g.user["id"],),
    ).fetchone()
    return success(player_dict(row, include_phone=True), "Your profile.")


@bp.put("/profile")
@login_required
def update_profile():
    data = json_body()
    allowed = {"name", "phone", "skill_level", "location", "bio"}
    if not any(field in data for field in allowed):
        return error(400, "missing_fields", "Provide at least one profile field to update.")

    merged = {field: g.user[field] for field in allowed}
    for field in allowed:
        if field in data:
            merged[field] = data[field]
    clean, validation_error = validate_user_fields(merged, require_password=False)
    if validation_error:
        return validation_error

    database = get_db()
    try:
        database.execute(
            """
            UPDATE users SET name = ?, phone = ?, skill_level = ?, location = ?, bio = ?
            WHERE id = ?
            """,
            (
                clean["name"], clean["phone"], clean["skill_level"], clean["location"], clean["bio"], g.user["id"]
            ),
        )
        database.commit()
    except sqlite3.IntegrityError:
        return error(409, "phone_exists", "Another account already uses that phone number.")
    updated = database.execute("SELECT * FROM users WHERE id = ?", (g.user["id"],)).fetchone()
    return success(player_dict(updated, include_phone=True), "Profile updated.")


@bp.get("/games")
def list_games():
    skill_filter = request.args.get("skill_level", "").strip()
    skill = canonical_skill(skill_filter) if skill_filter else None
    if skill_filter and skill is None:
        return error(400, "invalid_skill_level", "Choose Beginner, Intermediate or Advanced.")
    location = request.args.get("location", "").strip()
    available_only = request.args.get("available", "").lower() in {"1", "true", "yes"}

    clauses = ["1 = 1"]
    parameters: list[object] = []
    if skill:
        clauses.append("g.required_level = ?")
        parameters.append(skill)
    if location:
        clauses.append("g.location LIKE ? COLLATE NOCASE")
        parameters.append(f"%{location}%")
    having = "HAVING COUNT(gp.id) < g.max_players" if available_only else ""
    if available_only:
        clauses.append("(g.game_date || ' ' || g.game_time) > ?")
        parameters.append(datetime.now().strftime("%Y-%m-%d %H:%M"))
    rows = get_db().execute(
        f"""
        SELECT g.*, u.name AS organizer_name, COUNT(gp.id) AS participant_count
        FROM games g
        JOIN users u ON u.id = g.organizer_id
        LEFT JOIN game_participants gp ON gp.game_id = g.id
        WHERE {' AND '.join(clauses)}
        GROUP BY g.id
        {having}
        ORDER BY g.game_date, g.game_time, g.created_at
        """,
        parameters,
    ).fetchall()
    games = [game_dict(row) for row in rows]
    return success({"games": games, "count": len(games)}, "Games retrieved.")


@bp.post("/games")
@login_required
def create_game():
    data = json_body()
    required = ["title", "location", "date", "time", "required_level", "max_players"]
    missing = [field for field in required if not str(data.get(field, "")).strip()]
    if missing:
        return error(400, "missing_fields", f"Please provide: {', '.join(missing)}.")

    title = str(data["title"]).strip()
    location = str(data["location"]).strip()
    skill = canonical_skill(data["required_level"])
    try:
        game_date = date.fromisoformat(str(data["date"]))
        game_time = parse_game_time(data["time"])
        if isinstance(data["max_players"], bool):
            raise ValueError("boolean is not a player count")
        maximum = int(data["max_players"])
    except (TypeError, ValueError):
        return error(400, "invalid_game", "Enter a valid date, time and maximum player count.")

    if not 2 <= len(title) <= 100:
        return error(400, "invalid_title", "Game title must be between 2 and 100 characters.")
    if not 2 <= len(location) <= 120:
        return error(400, "invalid_location", "Game location must be between 2 and 120 characters.")
    if skill is None:
        return error(400, "invalid_skill_level", "Choose Beginner, Intermediate or Advanced.")
    if datetime.combine(game_date, game_time) <= datetime.now():
        return error(400, "past_date", "Choose a date and time in the future.")
    if not 2 <= maximum <= 8:
        return error(400, "invalid_max_players", "Maximum players must be between 2 and 8.")

    database = get_db()
    try:
        cursor = database.execute(
            """
            INSERT INTO games
                (organizer_id, title, location, game_date, game_time, required_level, max_players)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (g.user["id"], title, location, game_date.isoformat(), game_time.strftime("%H:%M"), skill, maximum),
        )
        game_id = cursor.lastrowid
        database.execute(
            "INSERT INTO game_participants (game_id, user_id) VALUES (?, ?)", (game_id, g.user["id"])
        )
        database.commit()
    except Exception:
        database.rollback()
        raise

    created = game_dict(fetch_game(game_id))
    response = success(created, "Game created. You are the first participant.", 201)
    response.headers["Location"] = url_for("api.get_game", game_id=game_id)
    return response


@bp.get("/games/<int:game_id>")
def get_game(game_id: int):
    row = fetch_game(game_id)
    if row is None:
        return error(404, "game_not_found", "That game does not exist.")
    participants = get_db().execute(
        """
        SELECT u.id, u.name, u.skill_level, u.location, gp.joined_at
        FROM game_participants gp
        JOIN users u ON u.id = gp.user_id
        WHERE gp.game_id = ?
        ORDER BY gp.joined_at, gp.id
        """,
        (game_id,),
    ).fetchall()
    payload = game_dict(row)
    payload["participants"] = [dict(participant) for participant in participants]
    return success(payload, "Game retrieved.")


@bp.post("/games/<int:game_id>/join")
@login_required
def join_game(game_id: int):
    database = get_db()
    try:
        database.execute("BEGIN IMMEDIATE")
        game = database.execute(
            "SELECT id, max_players, game_date, game_time FROM games WHERE id = ?", (game_id,)
        ).fetchone()
        if game is None:
            database.rollback()
            return error(404, "game_not_found", "That game does not exist.")
        if game_has_started(game["game_date"], game["game_time"]):
            database.rollback()
            return error(409, "game_started", "This game has already started and can no longer be joined.")
        joined = database.execute(
            "SELECT 1 FROM game_participants WHERE game_id = ? AND user_id = ?", (game_id, g.user["id"])
        ).fetchone()
        if joined:
            database.rollback()
            return error(409, "already_joined", "You have already joined this game.")
        count = database.execute(
            "SELECT COUNT(*) AS count FROM game_participants WHERE game_id = ?", (game_id,)
        ).fetchone()["count"]
        if count >= game["max_players"]:
            database.rollback()
            return error(409, "game_full", "This game is already full.")
        database.execute("INSERT INTO game_participants (game_id, user_id) VALUES (?, ?)", (game_id, g.user["id"]))
        database.commit()
    except sqlite3.IntegrityError:
        database.rollback()
        return error(409, "already_joined", "You have already joined this game.")
    except Exception:
        database.rollback()
        raise
    return success(game_dict(fetch_game(game_id)), "You joined the game.")


@bp.post("/feedback")
@login_required
def create_feedback():
    data = json_body()
    try:
        if any(isinstance(data.get(key), bool) for key in ("game_id", "reviewed_user_id", "rating")):
            raise ValueError("booleans are not ids or ratings")
        game_id = int(data.get("game_id", ""))
        reviewed_user_id = int(data.get("reviewed_user_id", ""))
        rating = int(data.get("rating", ""))
    except (TypeError, ValueError):
        return error(400, "invalid_feedback", "Choose a game, player and rating from 1 to 5.")
    comment = str(data.get("comment", "")).strip()
    if not 1 <= rating <= 5:
        return error(400, "invalid_rating", "Rating must be between 1 and 5.")
    if len(comment) > 300:
        return error(400, "comment_too_long", "Feedback comments must be 300 characters or fewer.")
    if reviewed_user_id == g.user["id"]:
        return error(400, "self_feedback", "You cannot leave feedback for yourself.")

    database = get_db()
    game = database.execute("SELECT id FROM games WHERE id = ?", (game_id,)).fetchone()
    if game is None:
        return error(404, "game_not_found", "That game does not exist.")
    reviewed = database.execute("SELECT id FROM users WHERE id = ?", (reviewed_user_id,)).fetchone()
    if reviewed is None:
        return error(404, "player_not_found", "That player does not exist.")
    participant_ids = {
        row["user_id"]
        for row in database.execute("SELECT user_id FROM game_participants WHERE game_id = ?", (game_id,)).fetchall()
    }
    if g.user["id"] not in participant_ids or reviewed_user_id not in participant_ids:
        return error(403, "not_shared_game", "Feedback is only allowed between participants in the same game.")

    try:
        cursor = database.execute(
            """
            INSERT INTO feedback (game_id, reviewer_id, reviewed_user_id, rating, comment)
            VALUES (?, ?, ?, ?, ?)
            """,
            (game_id, g.user["id"], reviewed_user_id, rating, comment),
        )
        database.commit()
    except sqlite3.IntegrityError:
        return error(409, "duplicate_feedback", "You already reviewed this player for this game.")

    row = database.execute(
        """
        SELECT f.id, f.game_id, f.reviewer_id, f.reviewed_user_id, f.rating, f.comment, f.created_at,
               u.name AS reviewer_name, g.title AS game_title
        FROM feedback f
        JOIN users u ON u.id = f.reviewer_id
        JOIN games g ON g.id = f.game_id
        WHERE f.id = ?
        """,
        (cursor.lastrowid,),
    ).fetchone()
    return success(dict(row), "Feedback submitted.", 201)


@bp.get("/players/<int:player_id>/feedback")
def player_feedback(player_id: int):
    database = get_db()
    if database.execute("SELECT 1 FROM users WHERE id = ?", (player_id,)).fetchone() is None:
        return error(404, "player_not_found", "That player does not exist.")
    rows = database.execute(
        """
        SELECT f.id, f.game_id, f.rating, f.comment, f.created_at,
               u.id AS reviewer_id, u.name AS reviewer_name, g.title AS game_title
        FROM feedback f
        JOIN users u ON u.id = f.reviewer_id
        JOIN games g ON g.id = f.game_id
        WHERE f.reviewed_user_id = ?
        ORDER BY f.created_at DESC, f.id DESC
        """,
        (player_id,),
    ).fetchall()
    return success({"feedback": [dict(row) for row in rows], "count": len(rows)}, "Feedback retrieved.")


@bp.get("/test/error")
def test_error():
    if not current_app.testing:
        return error(404, "not_found", "The requested API resource does not exist.")
    raise RuntimeError("Controlled test-only server error")
