"""Server-rendered pages for Padeli Hyeti."""

from __future__ import annotations

from datetime import date
from functools import wraps

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .api import SKILL_LEVELS, canonical_skill, fetch_game, game_dict
from .db import get_db


bp = Blueprint("views", __name__)


def page_login_required(view):
    @wraps(view)
    def wrapped(**kwargs):
        if g.user is None:
            flash("Log in to view that page.", "info")
            return redirect(url_for("views.login"))
        return view(**kwargs)

    return wrapped


@bp.get("/")
def home():
    database = get_db()
    stats = {
        "players": database.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "games": database.execute("SELECT COUNT(*) FROM games").fetchone()[0],
    }
    return render_template("home.html", stats=stats)


@bp.get("/register")
def register():
    if g.user is not None:
        return redirect(url_for("views.dashboard"))
    return render_template("register.html", skill_levels=SKILL_LEVELS)


@bp.get("/login")
def login():
    if g.user is not None:
        return redirect(url_for("views.dashboard"))
    return render_template("login.html")


@bp.get("/dashboard")
@page_login_required
def dashboard():
    games = get_db().execute(
        """
        SELECT g.*, organizer.name AS organizer_name, COUNT(all_gp.id) AS participant_count
        FROM games g
        JOIN users organizer ON organizer.id = g.organizer_id
        JOIN game_participants mine ON mine.game_id = g.id AND mine.user_id = ?
        LEFT JOIN game_participants all_gp ON all_gp.game_id = g.id
        GROUP BY g.id
        ORDER BY g.game_date, g.game_time
        """,
        (g.user["id"],),
    ).fetchall()
    return render_template("dashboard.html", games=[game_dict(row) for row in games])


@bp.get("/profile")
@page_login_required
def edit_profile():
    return render_template("profile_edit.html", skill_levels=SKILL_LEVELS)


@bp.get("/players")
def players():
    name = request.args.get("name", "").strip()
    location = request.args.get("location", "").strip()
    skill_input = request.args.get("skill_level", "").strip()
    skill = canonical_skill(skill_input) if skill_input else None
    if skill_input and skill is None:
        flash("Choose a valid skill level.", "error")

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
        SELECT u.id, u.name, u.skill_level, u.location, u.bio,
               AVG(f.rating) AS average_rating, COUNT(f.id) AS feedback_count
        FROM users u
        LEFT JOIN feedback f ON f.reviewed_user_id = u.id
        WHERE {' AND '.join(clauses)}
        GROUP BY u.id
        ORDER BY u.name COLLATE NOCASE
        """,
        parameters,
    ).fetchall()
    return render_template(
        "players.html",
        players=rows,
        filters={"name": name, "location": location, "skill_level": skill or ""},
        skill_levels=SKILL_LEVELS,
    )


@bp.get("/players/<int:player_id>")
def player_profile(player_id: int):
    database = get_db()
    player = database.execute(
        """
        SELECT u.id, u.name, u.skill_level, u.location, u.bio, u.created_at,
               AVG(f.rating) AS average_rating, COUNT(f.id) AS feedback_count
        FROM users u
        LEFT JOIN feedback f ON f.reviewed_user_id = u.id
        WHERE u.id = ?
        GROUP BY u.id
        """,
        (player_id,),
    ).fetchone()
    if player is None:
        abort(404)
    feedback = database.execute(
        """
        SELECT f.rating, f.comment, f.created_at, reviewer.name AS reviewer_name, games.title AS game_title
        FROM feedback f
        JOIN users reviewer ON reviewer.id = f.reviewer_id
        JOIN games ON games.id = f.game_id
        WHERE f.reviewed_user_id = ?
        ORDER BY f.created_at DESC, f.id DESC
        """,
        (player_id,),
    ).fetchall()
    return render_template("player_profile.html", player=player, feedback=feedback)


@bp.get("/games")
def games():
    skill_input = request.args.get("skill_level", "").strip()
    skill = canonical_skill(skill_input) if skill_input else None
    location = request.args.get("location", "").strip()
    available_only = request.args.get("available") == "1"
    if skill_input and skill is None:
        flash("Choose a valid skill level.", "error")

    clauses = ["1 = 1"]
    parameters: list[object] = []
    if skill:
        clauses.append("g.required_level = ?")
        parameters.append(skill)
    if location:
        clauses.append("g.location LIKE ? COLLATE NOCASE")
        parameters.append(f"%{location}%")
    having = "HAVING COUNT(gp.id) < g.max_players" if available_only else ""
    rows = get_db().execute(
        f"""
        SELECT g.*, organizer.name AS organizer_name, COUNT(gp.id) AS participant_count
        FROM games g
        JOIN users organizer ON organizer.id = g.organizer_id
        LEFT JOIN game_participants gp ON gp.game_id = g.id
        WHERE {' AND '.join(clauses)}
        GROUP BY g.id
        {having}
        ORDER BY g.game_date, g.game_time
        """,
        parameters,
    ).fetchall()
    return render_template(
        "games.html",
        games=[game_dict(row) for row in rows],
        filters={"skill_level": skill or "", "location": location, "available": available_only},
        skill_levels=SKILL_LEVELS,
    )


@bp.get("/games/create")
@page_login_required
def create_game():
    return render_template("create_game.html", skill_levels=SKILL_LEVELS, today=date.today().isoformat())


@bp.get("/games/<int:game_id>")
def game_detail(game_id: int):
    database = get_db()
    row = fetch_game(game_id)
    if row is None:
        abort(404)
    participants = database.execute(
        """
        SELECT u.id, u.name, u.skill_level, u.location, gp.joined_at
        FROM game_participants gp
        JOIN users u ON u.id = gp.user_id
        WHERE gp.game_id = ?
        ORDER BY gp.joined_at, gp.id
        """,
        (game_id,),
    ).fetchall()
    joined = False
    reviewed_ids: set[int] = set()
    if g.user is not None:
        joined = any(participant["id"] == g.user["id"] for participant in participants)
        reviewed_ids = {
            item["reviewed_user_id"]
            for item in database.execute(
                "SELECT reviewed_user_id FROM feedback WHERE game_id = ? AND reviewer_id = ?",
                (game_id, g.user["id"]),
            ).fetchall()
        }
    return render_template(
        "game_detail.html",
        game=game_dict(row),
        participants=participants,
        joined=joined,
        reviewed_ids=reviewed_ids,
    )

