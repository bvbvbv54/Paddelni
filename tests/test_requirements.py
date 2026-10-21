"""One focused test per requirement in the project brief, plus the security fixes."""

from __future__ import annotations

import threading
from datetime import date, datetime, timedelta

import pytest

from padeli import create_app
from padeli.db import get_db

from helpers import (
    PASSWORD,
    api,
    create_game,
    future_date,
    login,
    my_id,
    register,
    registered_client,
    registration,
)


def error_code(response):
    return response.get_json()["error"]["code"]


def assert_error_envelope(response, status, code):
    assert response.status_code == status
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == code
    assert body["error"]["message"]


# --------------------------------------------------------------------------- registration


def test_registration_success_envelope_and_location_header(client):
    response = register(client)
    assert response.status_code == 201
    body = response.get_json()
    assert body["success"] is True and body["message"]
    assert set(body["data"]) >= {"id", "name", "phone", "skill_level", "location", "bio"}
    assert "password" not in body["data"] and "password_hash" not in body["data"]
    assert response.headers["Location"].endswith(f"/api/players/{body['data']['id']}")


def test_registration_stores_only_a_salted_hash(app, client):
    register(client)
    with app.app_context():
        stored = get_db().execute("SELECT password_hash FROM users").fetchone()["password_hash"]
    assert PASSWORD not in stored
    assert stored.startswith(("scrypt:", "pbkdf2:"))  # Werkzeug salted hash format


def test_duplicate_phone_even_with_different_formatting_is_409(client):
    assert register(client, phone="080 1234 5678").status_code == 201
    assert_error_envelope(register(client, name="Someone Else", phone="080-1234-5678"), 409, "phone_exists")


@pytest.mark.parametrize("missing_field", ["name", "phone", "skill_level", "password", "confirm_password"])
def test_registration_missing_each_field_is_400(client, missing_field):
    payload = registration()
    payload.pop(missing_field)
    response = api(client, "POST", "/api/register", payload)
    assert_error_envelope(response, 400, "missing_fields")


@pytest.mark.parametrize("phone", ["12345", "1234567890123456", "call-me-maybe", "0801234567x", "+216 2O 123 456"])
def test_invalid_phone_numbers_are_400(client, phone):
    assert_error_envelope(register(client, phone=phone), 400, "invalid_phone")


@pytest.mark.parametrize("phone", ["+216 20 123 456", "(080) 1234-5678", "08012345678"])
def test_valid_phone_formats_are_accepted_and_normalized(client, phone):
    response = register(client, phone=phone)
    assert response.status_code == 201
    assert response.get_json()["data"]["phone"].isdigit()


@pytest.mark.parametrize("skill", ["Expert", "pro", "0"])
def test_invalid_skill_level_is_400(client, skill):
    assert_error_envelope(register(client, skill=skill), 400, "invalid_skill_level")


def test_skill_level_is_case_insensitive_and_canonicalised(client):
    response = register(client, skill="advanced")
    assert response.status_code == 201
    assert response.get_json()["data"]["skill_level"] == "Advanced"


def test_short_password_is_400(client):
    response = register(client, password="short", confirm_password="short")
    assert_error_envelope(response, 400, "short_password")


def test_password_mismatch_is_400(client):
    response = register(client, confirm_password="something-else-123")
    assert_error_envelope(response, 400, "password_mismatch")


# --------------------------------------------------------------------------- login / logout


def test_login_by_phone_in_any_format(client):
    register(client)
    assert login(client, "080 1234 5678").status_code == 200


def test_login_by_unique_name_case_insensitive(client):
    register(client)
    response = login(client, "amina musa")
    assert response.status_code == 200
    assert response.get_json()["data"]["name"] == "Amina Musa"


def test_login_by_name_that_contains_digits(client):
    register(client, name="Player 1234567", phone="0700000001")
    assert login(client, "Player 1234567").status_code == 200


def test_ambiguous_name_is_400_but_phone_still_works(app):
    first, second = app.test_client(), app.test_client()
    register(first, "Same Name", "08011111111")
    register(second, "Same Name", "08022222222")
    assert_error_envelope(login(first, "Same Name"), 400, "ambiguous_name")
    assert login(first, "08011111111").status_code == 200


def test_invalid_login_does_not_reveal_whether_account_exists(client):
    register(client)
    wrong_password = login(client, password="wrong-password")
    unknown_phone = login(client, "07099999999")
    unknown_name = login(client, "Nobody Here")
    for response in (wrong_password, unknown_phone, unknown_name):
        assert_error_envelope(response, 401, "invalid_credentials")
    assert wrong_password.get_json() == unknown_phone.get_json() == unknown_name.get_json()


def test_login_missing_fields_is_400(client):
    assert_error_envelope(api(client, "POST", "/api/login", {"identifier": "x"}), 400, "missing_fields")


def test_login_rotates_session_and_csrf_token(app):
    client = app.test_client()
    register(client)
    before = client.get("/api/csrf-token").get_json()["data"]["csrf_token"]
    login(client)
    after = client.get("/api/csrf-token").get_json()["data"]["csrf_token"]
    assert before != after


def test_logout_ends_session(app):
    client = registered_client(app, "Amina Musa", "08012345678")
    assert client.get("/api/profile").status_code == 200
    response = api(client, "POST", "/api/logout")
    assert response.status_code == 200 and response.get_json()["success"] is True
    assert_error_envelope(client.get("/api/profile"), 401, "authentication_required")
    assert_error_envelope(api(client, "POST", "/api/logout"), 401, "authentication_required")


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/profile"),
        ("PUT", "/api/profile"),
        ("POST", "/api/games"),
        ("POST", "/api/games/1/join"),
        ("POST", "/api/feedback"),
        ("POST", "/api/logout"),
    ],
)
def test_protected_endpoints_require_login(client, method, path):
    assert_error_envelope(client.open(path, method=method, json={}), 401, "authentication_required")


@pytest.mark.parametrize("path", ["/dashboard", "/profile", "/games/create"])
def test_protected_pages_redirect_to_login(client, path):
    response = client.get(path)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_logged_in_state_change_without_csrf_is_rejected(app):
    client = registered_client(app, "Amina Musa", "08012345678")
    response = client.post("/api/games", json={})
    assert_error_envelope(response, 400, "invalid_csrf")
    response = client.post("/api/games", json={}, headers={"X-CSRF-Token": "forged"})
    assert_error_envelope(response, 400, "invalid_csrf")


# --------------------------------------------------------------------------- profile


def test_current_profile_includes_own_phone_but_never_hash(app):
    client = registered_client(app, "Amina Musa", "08012345678")
    data = client.get("/api/profile").get_json()["data"]
    assert data["phone"] == "08012345678"
    assert "password_hash" not in data


def test_profile_update_all_fields_and_login_with_new_phone(app):
    client = registered_client(app, "Amina Musa", "08012345678")
    response = api(
        client,
        "PUT",
        "/api/profile",
        {"name": "Amina M.", "phone": "08099999999", "skill_level": "Advanced", "location": "Tunis", "bio": "Evenings."},
    )
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert (data["name"], data["phone"], data["skill_level"], data["location"], data["bio"]) == (
        "Amina M.", "08099999999", "Advanced", "Tunis", "Evenings."
    )
    api(client, "POST", "/api/logout")
    assert login(client, "08099999999").status_code == 200


def test_profile_update_validation_and_phone_conflict(app):
    owner = registered_client(app, "Owner", "08011111111")
    registered_client(app, "Other", "08022222222")
    assert_error_envelope(api(owner, "PUT", "/api/profile", {}), 400, "missing_fields")
    assert_error_envelope(api(owner, "PUT", "/api/profile", {"skill_level": "Guru"}), 400, "invalid_skill_level")
    assert_error_envelope(api(owner, "PUT", "/api/profile", {"bio": "x" * 301}), 400, "invalid_bio")
    assert_error_envelope(api(owner, "PUT", "/api/profile", {"phone": "08022222222"}), 409, "phone_exists")


def test_profile_update_only_changes_the_logged_in_user(app):
    owner = registered_client(app, "Owner", "08011111111")
    other = registered_client(app, "Other", "08022222222")
    other_id = my_id(other)
    # Even if a client tries to smuggle another user's id, only the session user is updated.
    api(owner, "PUT", "/api/profile", {"id": other_id, "user_id": other_id, "location": "Hijacked"})
    assert other.get("/api/profile").get_json()["data"]["location"] == ""
    assert owner.get("/api/profile").get_json()["data"]["location"] == "Hijacked"
    # There is no endpoint for editing someone else's profile by id.
    assert api(owner, "PUT", f"/api/players/{other_id}", {"location": "x"}).status_code == 405


# --------------------------------------------------------------------------- player finder


def test_player_search_filters_and_empty_result(app):
    a = registered_client(app, "Amina Musa", "08011111111", "Beginner")
    b = registered_client(app, "Bola Ade", "08022222222", "Advanced")
    api(a, "PUT", "/api/profile", {"location": "La Marsa"})
    api(b, "PUT", "/api/profile", {"location": "Ariana"})

    def names(query):
        response = a.get(f"/api/players{query}")
        assert response.status_code == 200
        return [p["name"] for p in response.get_json()["data"]["players"]]

    assert names("") == ["Amina Musa", "Bola Ade"]
    assert names("?name=bola") == ["Bola Ade"]
    assert names("?skill_level=beginner") == ["Amina Musa"]
    assert names("?location=ariana") == ["Bola Ade"]
    empty = a.get("/api/players?name=zzz-nobody")
    assert empty.status_code == 200
    assert empty.get_json()["data"] == {"players": [], "count": 0}
    assert_error_envelope(a.get("/api/players?skill_level=Legend"), 400, "invalid_skill_level")


def test_player_search_treats_sql_wildcards_and_quotes_safely(app):
    client = registered_client(app, "O'Brien", "08011111111")
    response = client.get("/api/players?name=' OR 1=1 --")
    assert response.status_code == 200
    assert response.get_json()["data"]["count"] == 0
    assert client.get("/api/players?name=O'Brien").get_json()["data"]["count"] == 1


def test_public_player_data_never_exposes_phone_or_hash(app):
    owner = registered_client(app, "Owner", "08011111111")
    viewer = registered_client(app, "Viewer", "08022222222")
    owner_id = my_id(owner)
    anonymous = app.test_client()
    for client in (viewer, anonymous):
        for payload in (
            client.get(f"/api/players/{owner_id}").get_json()["data"],
            *client.get("/api/players").get_json()["data"]["players"],
        ):
            if payload["id"] == owner_id:
                assert "phone" not in payload
            assert "password_hash" not in payload and "password" not in payload
    page = viewer.get(f"/players/{owner_id}")
    assert page.status_code == 200 and b"08011111111" not in page.data


def test_missing_player_is_404_for_api_and_page(client):
    assert_error_envelope(client.get("/api/players/999999"), 404, "player_not_found")
    assert_error_envelope(client.get("/api/players/999999/feedback"), 404, "player_not_found")
    assert client.get("/players/999999").status_code == 404


# --------------------------------------------------------------------------- games


def test_game_creation_returns_201_with_all_display_fields(app):
    owner = registered_client(app, "Owner", "08011111111")
    response = create_game(owner, maximum=4)
    assert response.status_code == 201
    game = response.get_json()["data"]
    assert response.headers["Location"].endswith(f"/api/games/{game['id']}")
    assert game["organizer"]["name"] == "Owner"
    assert (game["participant_count"], game["max_players"], game["available_places"], game["status"]) == (1, 4, 3, "available")
    assert {"date", "time", "location", "required_level", "title"} <= set(game)


def test_organizer_is_automatically_first_participant(app):
    owner = registered_client(app, "Owner", "08011111111")
    game_id = create_game(owner).get_json()["data"]["id"]
    with app.app_context():
        rows = get_db().execute("SELECT user_id FROM game_participants WHERE game_id = ?", (game_id,)).fetchall()
    assert [row["user_id"] for row in rows] == [my_id(owner)]


@pytest.mark.parametrize(
    "overrides,code",
    [
        ({"title": "x"}, "invalid_title"),
        ({"location": "x"}, "invalid_location"),
        ({"date": "2026-02-30"}, "invalid_game"),
        ({"date": "not-a-date"}, "invalid_game"),
        ({"time": "25:00"}, "invalid_game"),
        ({"max_players": "four"}, "invalid_game"),
        ({"max_players": 1}, "invalid_max_players"),
        ({"max_players": 9}, "invalid_max_players"),
        ({"required_level": "Pro"}, "invalid_skill_level"),
        ({"date": "2000-01-01"}, "past_date"),
    ],
)
def test_game_field_validation(app, overrides, code):
    owner = registered_client(app, "Owner", "08011111111")
    assert_error_envelope(create_game(owner, **overrides), 400, code)


def test_game_today_with_a_time_already_passed_is_rejected(app):
    owner = registered_client(app, "Owner", "08011111111")
    one_minute_ago = datetime.now() - timedelta(minutes=1)
    if one_minute_ago.date() != date.today():
        pytest.skip("Just after midnight; 'earlier today' does not exist yet.")
    response = create_game(owner, date=one_minute_ago.date().isoformat(), time=one_minute_ago.strftime("%H:%M"))
    assert_error_envelope(response, 400, "past_date")


def test_game_time_with_seconds_is_accepted(app):
    owner = registered_client(app, "Owner", "08011111111")
    response = create_game(owner, time="18:30:00")
    assert response.status_code == 201
    assert response.get_json()["data"]["time"] == "18:30"


def test_games_list_persists_and_filters(app):
    owner = registered_client(app, "Owner", "08011111111")
    create_game(owner, "Beginner game", required_level="Beginner", location="Gammarth Club")
    full_id = create_game(owner, "Full game", maximum=2).get_json()["data"]["id"]
    joiner = registered_client(app, "Joiner", "08022222222")
    api(joiner, "POST", f"/api/games/{full_id}/join")

    anonymous = app.test_client()
    all_games = anonymous.get("/api/games").get_json()["data"]
    assert all_games["count"] == 2
    statuses = {g["title"]: g["status"] for g in all_games["games"]}
    assert statuses == {"Beginner game": "available", "Full game": "full"}
    assert [g["title"] for g in anonymous.get("/api/games?available=1").get_json()["data"]["games"]] == ["Beginner game"]
    assert anonymous.get("/api/games?skill_level=Beginner").get_json()["data"]["count"] == 1
    assert anonymous.get("/api/games?location=gammarth").get_json()["data"]["count"] == 1
    assert anonymous.get("/games").status_code == 200


def test_missing_game_is_404(app, client):
    assert_error_envelope(client.get("/api/games/999999"), 404, "game_not_found")
    assert client.get("/games/999999").status_code == 404
    user = registered_client(app, "User", "08011111111")
    assert_error_envelope(api(user, "POST", "/api/games/999999/join"), 404, "game_not_found")


# --------------------------------------------------------------------------- joining


def test_join_updates_count_and_is_visible_to_organizer(app):
    owner = registered_client(app, "Owner", "08011111111")
    joiner = registered_client(app, "Joiner", "08022222222")
    game_id = create_game(owner, maximum=3).get_json()["data"]["id"]
    response = api(joiner, "POST", f"/api/games/{game_id}/join")
    assert response.status_code == 200
    assert (response.get_json()["data"]["participant_count"], response.get_json()["data"]["available_places"]) == (2, 1)
    detail = owner.get(f"/api/games/{game_id}").get_json()["data"]
    assert [p["name"] for p in detail["participants"]] == ["Owner", "Joiner"]
    assert all("phone" not in p for p in detail["participants"])
    assert b"Joiner" in owner.get(f"/games/{game_id}").data


def test_organizer_cannot_join_own_game_twice(app):
    owner = registered_client(app, "Owner", "08011111111")
    game_id = create_game(owner).get_json()["data"]["id"]
    assert_error_envelope(api(owner, "POST", f"/api/games/{game_id}/join"), 409, "already_joined")


def test_duplicate_join_is_409_and_does_not_change_count(app):
    owner = registered_client(app, "Owner", "08011111111")
    joiner = registered_client(app, "Joiner", "08022222222")
    game_id = create_game(owner).get_json()["data"]["id"]
    api(joiner, "POST", f"/api/games/{game_id}/join")
    assert_error_envelope(api(joiner, "POST", f"/api/games/{game_id}/join"), 409, "already_joined")
    assert owner.get(f"/api/games/{game_id}").get_json()["data"]["participant_count"] == 2


def test_full_game_is_409(app):
    owner = registered_client(app, "Owner", "08011111111")
    second = registered_client(app, "Second", "08022222222")
    third = registered_client(app, "Third", "08033333333")
    game_id = create_game(owner, maximum=2).get_json()["data"]["id"]
    api(second, "POST", f"/api/games/{game_id}/join")
    assert_error_envelope(api(third, "POST", f"/api/games/{game_id}/join"), 409, "game_full")


def test_started_game_cannot_be_joined(app):
    owner = registered_client(app, "Owner", "08011111111")
    joiner = registered_client(app, "Joiner", "08022222222")
    game_id = create_game(owner).get_json()["data"]["id"]
    with app.app_context():
        database = get_db()
        database.execute("UPDATE games SET game_date = ? WHERE id = ?", ((date.today() - timedelta(days=1)).isoformat(), game_id))
        database.commit()
    assert owner.get(f"/api/games/{game_id}").get_json()["data"]["status"] == "past"
    assert_error_envelope(api(joiner, "POST", f"/api/games/{game_id}/join"), 409, "game_started")


def test_concurrent_joins_never_overfill_a_game(app):
    """Eight players race for three free places; exactly three must win."""
    owner = registered_client(app, "Owner", "08010000000")
    game_id = create_game(owner, maximum=4).get_json()["data"]["id"]
    racers = [registered_client(app, f"Racer {i}", f"0802000000{i}") for i in range(8)]
    tokens = [r.get("/api/csrf-token").get_json()["data"]["csrf_token"] for r in racers]
    barrier = threading.Barrier(len(racers))
    statuses: list[int] = []
    lock = threading.Lock()

    def attempt(client, token):
        barrier.wait()
        response = client.post(f"/api/games/{game_id}/join", json={}, headers={"X-CSRF-Token": token})
        with lock:
            statuses.append(response.status_code)

    threads = [threading.Thread(target=attempt, args=pair) for pair in zip(racers, tokens)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(statuses) == [200] * 3 + [409] * 5
    detail = owner.get(f"/api/games/{game_id}").get_json()["data"]
    assert detail["participant_count"] == 4 and detail["status"] == "full"


# --------------------------------------------------------------------------- feedback


def shared_game(app):
    owner = registered_client(app, "Owner", "08011111111")
    teammate = registered_client(app, "Teammate", "08022222222")
    game_id = create_game(owner).get_json()["data"]["id"]
    api(teammate, "POST", f"/api/games/{game_id}/join")
    return owner, teammate, game_id, my_id(owner), my_id(teammate)


def test_feedback_success_and_public_listing(app):
    owner, teammate, game_id, owner_id, _ = shared_game(app)
    response = api(teammate, "POST", "/api/feedback", {"game_id": game_id, "reviewed_user_id": owner_id, "rating": 4, "comment": "  Solid volleys  "})
    assert response.status_code == 201
    created = response.get_json()["data"]
    assert (created["rating"], created["comment"], created["reviewer_name"]) == (4, "Solid volleys", "Teammate")

    anonymous = app.test_client()
    listing = anonymous.get(f"/api/players/{owner_id}/feedback").get_json()["data"]
    assert listing["count"] == 1 and listing["feedback"][0]["comment"] == "Solid volleys"
    assert anonymous.get(f"/api/players/{owner_id}").get_json()["data"]["average_rating"] == 4.0
    assert b"Solid volleys" in anonymous.get(f"/players/{owner_id}").data


def test_feedback_comment_is_optional(app):
    _, teammate, game_id, owner_id, _ = shared_game(app)
    response = api(teammate, "POST", "/api/feedback", {"game_id": game_id, "reviewed_user_id": owner_id, "rating": 3})
    assert response.status_code == 201 and response.get_json()["data"]["comment"] == ""


@pytest.mark.parametrize("rating,code", [(0, "invalid_rating"), (6, "invalid_rating"), ("five", "invalid_feedback"), (True, "invalid_feedback"), (None, "invalid_feedback")])
def test_feedback_rating_must_be_1_to_5(app, rating, code):
    _, teammate, game_id, owner_id, _ = shared_game(app)
    response = api(teammate, "POST", "/api/feedback", {"game_id": game_id, "reviewed_user_id": owner_id, "rating": rating})
    assert_error_envelope(response, 400, code)


def test_feedback_comment_length_limit(app):
    _, teammate, game_id, owner_id, _ = shared_game(app)
    response = api(teammate, "POST", "/api/feedback", {"game_id": game_id, "reviewed_user_id": owner_id, "rating": 5, "comment": "x" * 301})
    assert_error_envelope(response, 400, "comment_too_long")


def test_self_feedback_is_rejected(app):
    owner, _, game_id, owner_id, _ = shared_game(app)
    response = api(owner, "POST", "/api/feedback", {"game_id": game_id, "reviewed_user_id": owner_id, "rating": 5})
    assert_error_envelope(response, 400, "self_feedback")


def test_feedback_for_unshared_game_is_rejected(app):
    owner, _, game_id, owner_id, teammate_id = shared_game(app)
    outsider = registered_client(app, "Outsider", "08033333333")
    # Outsider reviewing a participant.
    assert_error_envelope(api(outsider, "POST", "/api/feedback", {"game_id": game_id, "reviewed_user_id": owner_id, "rating": 2}), 403, "not_shared_game")
    # Participant reviewing someone who was not in that game.
    outsider_id = my_id(outsider)
    assert_error_envelope(api(owner, "POST", "/api/feedback", {"game_id": game_id, "reviewed_user_id": outsider_id, "rating": 2}), 403, "not_shared_game")


def test_feedback_for_missing_game_or_player_is_404(app):
    owner, _, game_id, _, _ = shared_game(app)
    assert_error_envelope(api(owner, "POST", "/api/feedback", {"game_id": 999999, "reviewed_user_id": 2, "rating": 5}), 404, "game_not_found")
    assert_error_envelope(api(owner, "POST", "/api/feedback", {"game_id": game_id, "reviewed_user_id": 999999, "rating": 5}), 404, "player_not_found")


def test_duplicate_feedback_is_409(app):
    _, teammate, game_id, owner_id, _ = shared_game(app)
    payload = {"game_id": game_id, "reviewed_user_id": owner_id, "rating": 5}
    assert api(teammate, "POST", "/api/feedback", payload).status_code == 201
    assert_error_envelope(api(teammate, "POST", "/api/feedback", {**payload, "rating": 1}), 409, "duplicate_feedback")


# --------------------------------------------------------------------------- HTTP / config / persistence


def test_unknown_api_route_and_wrong_method_return_json(client):
    assert_error_envelope(client.get("/api/does-not-exist"), 404, "not_found")
    wrong_method = client.delete("/api/health")
    assert_error_envelope(wrong_method, 405, "method_not_allowed")
    assert "GET" in wrong_method.headers["Allow"]


def test_test_error_endpoint_is_hidden_outside_testing(tmp_path):
    production_like = create_app({"SECRET_KEY": "x", "DATABASE": str(tmp_path / "p.sqlite3")})
    assert production_like.debug is False
    response = production_like.test_client().get("/api/test/error")
    assert_error_envelope(response, 404, "not_found")


def test_session_cookie_flags(app):
    client = app.test_client()
    response = client.get("/api/csrf-token")
    cookie = response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True


def test_secret_key_is_random_and_persisted_when_not_configured(tmp_path):
    from padeli import _load_or_create_secret_key

    first = _load_or_create_secret_key(tmp_path)
    second = _load_or_create_secret_key(tmp_path)  # simulates a restart
    assert len(first) == 64 and first == second
    assert (tmp_path / "secret_key").read_text().strip() == first
    other_install = tmp_path / "elsewhere"
    other_install.mkdir()
    assert _load_or_create_secret_key(other_install) != first


def test_secret_key_comes_from_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("PADELI_SECRET_KEY", "from-the-environment")
    application = create_app({"DATABASE": str(tmp_path / "db.sqlite3")})
    assert application.config["SECRET_KEY"] == "from-the-environment"


def test_data_and_sessions_survive_an_application_restart(tmp_path):
    config = {"TESTING": True, "SECRET_KEY": "restart-secret", "DATABASE": str(tmp_path / "persist.sqlite3")}
    first_run = create_app(dict(config))
    client = registered_client(first_run, "Persistent Player", "08055555555")
    game_id = create_game(client).get_json()["data"]["id"]

    second_run = create_app(dict(config))  # same database file, brand-new app instance
    fresh = second_run.test_client()
    assert fresh.get(f"/api/games/{game_id}").status_code == 200
    assert fresh.get("/api/players?name=Persistent").get_json()["data"]["count"] == 1
    assert login(fresh, "08055555555").status_code == 200


def test_foreign_keys_and_unique_constraints_are_enforced_by_sqlite(app):
    import sqlite3

    with app.app_context():
        database = get_db()
        assert database.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            database.execute("INSERT INTO game_participants (game_id, user_id) VALUES (12345, 67890)")
        database.rollback()
