from __future__ import annotations

from datetime import date, timedelta

from padeli.db import get_db


PASSWORD = "strong-pass-123"


def csrf(client) -> str:
    response = client.get("/api/csrf-token")
    assert response.status_code == 200
    return response.get_json()["data"]["csrf_token"]


def api(client, method: str, path: str, payload=None):
    headers = {"X-CSRF-Token": csrf(client)}
    return client.open(path, method=method, json=payload or {}, headers=headers)


def register(client, name="Amina Musa", phone="08012345678", skill="Intermediate"):
    return api(
        client,
        "POST",
        "/api/register",
        {
            "name": name,
            "phone": phone,
            "skill_level": skill,
            "password": PASSWORD,
            "confirm_password": PASSWORD,
        },
    )


def login(client, identifier="08012345678", password=PASSWORD):
    return api(client, "POST", "/api/login", {"identifier": identifier, "password": password})


def future_date(days=7):
    return (date.today() + timedelta(days=days)).isoformat()


def create_game(client, title="Friday Padel", maximum=4):
    return api(
        client,
        "POST",
        "/api/games",
        {
            "title": title,
            "location": "Central Padel Club",
            "date": future_date(),
            "time": "18:30",
            "required_level": "Intermediate",
            "max_players": maximum,
        },
    )


def registered_client(app, name, phone):
    new_client = app.test_client()
    assert register(new_client, name, phone).status_code == 201
    assert login(new_client, phone).status_code == 200
    return new_client


def test_home_and_health_check(client):
    assert client.get("/").status_code == 200
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["data"]["status"] == "healthy"


def test_query_method_bonus_returns_read_only_game_catalogue(client):
    response = client.open("/api/query?resource=capabilities", method="QUERY")
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["method"] == "QUERY"
    assert body["data"]["read_only"] is True

    games = client.open("/api/query?resource=games", method="QUERY")
    assert games.status_code == 200
    assert games.get_json()["data"]["method"] == "QUERY"


def test_successful_registration_hashes_password(app, client):
    response = register(client)
    assert response.status_code == 201
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["phone"] == "08012345678"
    assert "password" not in body["data"]
    with app.app_context():
        row = get_db().execute("SELECT password_hash FROM users WHERE phone = ?", ("08012345678",)).fetchone()
        assert row["password_hash"] != PASSWORD
        assert "strong-pass-123" not in row["password_hash"]


def test_duplicate_registration_is_conflict(client):
    assert register(client).status_code == 201
    response = register(client)
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "phone_exists"


def test_registration_missing_and_invalid_information(client):
    missing = api(client, "POST", "/api/register", {"name": "Amina"})
    assert missing.status_code == 400
    assert missing.get_json()["error"]["code"] == "missing_fields"
    mismatch = api(
        client,
        "POST",
        "/api/register",
        {
            "name": "Amina",
            "phone": "1234567",
            "skill_level": "Expert",
            "password": "12345678",
            "confirm_password": "different",
        },
    )
    assert mismatch.status_code == 400


def test_successful_login_by_phone_and_unique_name(client):
    register(client)
    response = login(client)
    assert response.status_code == 200
    assert response.get_json()["data"]["name"] == "Amina Musa"
    api(client, "POST", "/api/logout")
    assert login(client, "Amina Musa").status_code == 200


def test_invalid_login_and_nonexistent_account_return_401(client):
    register(client)
    wrong_password = login(client, password="wrong-password")
    assert wrong_password.status_code == 401
    assert wrong_password.get_json()["error"]["code"] == "invalid_credentials"
    unknown = login(client, "07000000000")
    assert unknown.status_code == 401
    # Same code and message as a wrong password, so accounts cannot be enumerated.
    assert unknown.get_json()["error"] == wrong_password.get_json()["error"]


def test_ambiguous_name_requires_phone(app):
    first = app.test_client()
    second = app.test_client()
    assert register(first, "Same Name", "08011111111").status_code == 201
    assert register(second, "Same Name", "08022222222").status_code == 201
    response = login(first, "Same Name")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "ambiguous_name"


def test_unauthorized_protected_api_and_page(client):
    response = client.post("/api/games", json={})
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "authentication_required"
    page = client.get("/dashboard")
    assert page.status_code == 302
    assert "/login" in page.headers["Location"]


def test_csrf_is_required_for_public_state_change(client):
    response = client.post("/api/register", json={})
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_csrf"


def test_player_search_and_public_profile_hide_phone(app):
    owner = registered_client(app, "Amina Musa", "08012345678")
    other = registered_client(app, "Bola Ade", "08087654321")
    api(owner, "PUT", "/api/profile", {"location": "Lagos"})
    response = other.get("/api/players?name=Amina&skill_level=Intermediate&location=Lagos")
    assert response.status_code == 200
    players = response.get_json()["data"]["players"]
    assert len(players) == 1
    assert players[0]["name"] == "Amina Musa"
    assert "phone" not in players[0]
    public = other.get(f"/api/players/{players[0]['id']}").get_json()["data"]
    assert "password_hash" not in public
    assert "phone" not in public


def test_profile_update_persists_and_is_owner_only(app):
    owner = registered_client(app, "Amina Musa", "08012345678")
    response = api(
        owner,
        "PUT",
        "/api/profile",
        {"location": "Abuja", "bio": "I prefer evening doubles.", "skill_level": "Advanced"},
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["location"] == "Abuja"
    with app.app_context():
        row = get_db().execute("SELECT location, bio, skill_level FROM users WHERE phone = ?", ("08012345678",)).fetchone()
        assert dict(row) == {"location": "Abuja", "bio": "I prefer evening doubles.", "skill_level": "Advanced"}


def test_game_creation_adds_organizer_as_first_participant(app):
    owner = registered_client(app, "Amina Musa", "08012345678")
    response = create_game(owner)
    assert response.status_code == 201
    game = response.get_json()["data"]
    assert game["participant_count"] == 1
    detail = owner.get(f"/api/games/{game['id']}")
    assert detail.status_code == 200
    assert detail.get_json()["data"]["participants"][0]["name"] == "Amina Musa"


def test_two_clients_share_game_and_join(app):
    athlete_one = registered_client(app, "Athlete One", "08011111111")
    athlete_two = registered_client(app, "Athlete Two", "08022222222")
    game_id = create_game(athlete_one).get_json()["data"]["id"]
    discovered = athlete_two.get("/api/games").get_json()["data"]["games"]
    assert any(game["id"] == game_id for game in discovered)
    joined = api(athlete_two, "POST", f"/api/games/{game_id}/join")
    assert joined.status_code == 200
    detail_for_organizer = athlete_one.get(f"/api/games/{game_id}").get_json()["data"]
    assert detail_for_organizer["participant_count"] == 2
    assert {player["name"] for player in detail_for_organizer["participants"]} == {"Athlete One", "Athlete Two"}


def test_joining_same_game_twice_is_conflict(app):
    owner = registered_client(app, "Owner", "08011111111")
    joiner = registered_client(app, "Joiner", "08022222222")
    game_id = create_game(owner).get_json()["data"]["id"]
    assert api(joiner, "POST", f"/api/games/{game_id}/join").status_code == 200
    response = api(joiner, "POST", f"/api/games/{game_id}/join")
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "already_joined"


def test_joining_full_game_is_conflict(app):
    owner = registered_client(app, "Owner", "08011111111")
    second = registered_client(app, "Second", "08022222222")
    third = registered_client(app, "Third", "08033333333")
    game_id = create_game(owner, maximum=2).get_json()["data"]["id"]
    assert api(second, "POST", f"/api/games/{game_id}/join").status_code == 200
    response = api(third, "POST", f"/api/games/{game_id}/join")
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "game_full"


def test_nonexistent_player_and_game_return_404(client):
    assert client.get("/api/players/99999").status_code == 404
    assert client.get("/api/games/99999").status_code == 404


def test_feedback_submission_is_persisted_and_displayed(app):
    owner = registered_client(app, "Owner", "08011111111")
    teammate = registered_client(app, "Teammate", "08022222222")
    game_id = create_game(owner).get_json()["data"]["id"]
    owner_id = owner.get(f"/api/games/{game_id}").get_json()["data"]["organizer"]["id"]
    assert api(teammate, "POST", f"/api/games/{game_id}/join").status_code == 200
    response = api(
        teammate,
        "POST",
        "/api/feedback",
        {"game_id": game_id, "reviewed_user_id": owner_id, "rating": 5, "comment": "Great teammate."},
    )
    assert response.status_code == 201
    feedback = teammate.get(f"/api/players/{owner_id}/feedback").get_json()["data"]["feedback"]
    assert feedback[0]["rating"] == 5
    assert feedback[0]["comment"] == "Great teammate."
    profile_page = teammate.get(f"/players/{owner_id}")
    assert b"Great teammate." in profile_page.data


def test_invalid_self_unshared_and_duplicate_feedback(app):
    owner = registered_client(app, "Owner", "08011111111")
    teammate = registered_client(app, "Teammate", "08022222222")
    outsider = registered_client(app, "Outsider", "08033333333")
    game_id = create_game(owner).get_json()["data"]["id"]
    detail = owner.get(f"/api/games/{game_id}").get_json()["data"]
    owner_id = detail["organizer"]["id"]
    assert api(teammate, "POST", f"/api/games/{game_id}/join").status_code == 200
    teammate_id = next(item["id"] for item in teammate.get(f"/api/games/{game_id}").get_json()["data"]["participants"] if item["name"] == "Teammate")

    self_review = api(owner, "POST", "/api/feedback", {"game_id": game_id, "reviewed_user_id": owner_id, "rating": 5})
    assert self_review.status_code == 400
    unshared = api(outsider, "POST", "/api/feedback", {"game_id": game_id, "reviewed_user_id": owner_id, "rating": 4})
    assert unshared.status_code == 403
    payload = {"game_id": game_id, "reviewed_user_id": teammate_id, "rating": 4}
    assert api(owner, "POST", "/api/feedback", payload).status_code == 201
    duplicate = api(owner, "POST", "/api/feedback", payload)
    assert duplicate.status_code == 409
    assert duplicate.get_json()["error"]["code"] == "duplicate_feedback"


def test_game_validation_rejects_bad_input(app):
    owner = registered_client(app, "Owner", "08011111111")
    missing = api(owner, "POST", "/api/games", {"title": "No details"})
    assert missing.status_code == 400
    past = api(
        owner,
        "POST",
        "/api/games",
        {
            "title": "Old game",
            "location": "Club",
            "date": "2000-01-01",
            "time": "18:00",
            "required_level": "Beginner",
            "max_players": 4,
        },
    )
    assert past.status_code == 400
    assert past.get_json()["error"]["code"] == "past_date"


def test_all_required_status_codes_and_controlled_500(app, client):
    # 200 OK
    assert client.get("/api/health").status_code == 200
    # 201 Created
    assert register(client).status_code == 201
    # 400 Bad Request
    assert api(client, "POST", "/api/login", {}).status_code == 400
    # 401 Unauthorized
    assert login(client, password="not-the-password").status_code == 401
    # 404 Not Found
    assert client.get("/api/games/424242").status_code == 404
    # 409 Conflict
    assert register(client).status_code == 409
    # 500 Internal Server Error: this endpoint only exists in TESTING mode.
    failure = client.get("/api/test/error")
    assert failure.status_code == 500
    assert failure.get_json()["error"]["code"] == "server_error"


def test_cli_init_database_is_idempotent(runner):
    first = runner.invoke(args=["init-db"])
    second = runner.invoke(args=["init-db"])
    assert first.exit_code == 0
    assert second.exit_code == 0
    assert "initialized" in second.output

