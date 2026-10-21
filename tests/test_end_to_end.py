"""End-to-end workflow from the project brief, using two independent client sessions."""

from __future__ import annotations

from helpers import PASSWORD, api, future_date


def test_two_athletes_full_workflow(app):
    athlete_one = app.test_client()  # e.g. a normal browser window
    athlete_two = app.test_client()  # e.g. a private window: separate cookie jar

    # 1. Register Athlete 1.
    r = api(athlete_one, "POST", "/api/register", {
        "name": "Athlete One", "phone": "+216 20 111 111", "skill_level": "Intermediate",
        "password": PASSWORD, "confirm_password": PASSWORD,
    })
    assert r.status_code == 201
    athlete_one_id = r.get_json()["data"]["id"]

    # 2. Register Athlete 2.
    r = api(athlete_two, "POST", "/api/register", {
        "name": "Athlete Two", "phone": "+216 20 222 222", "skill_level": "Intermediate",
        "password": PASSWORD, "confirm_password": PASSWORD,
    })
    assert r.status_code == 201
    athlete_two_id = r.get_json()["data"]["id"]

    # 3. Log in Athlete 1.
    assert api(athlete_one, "POST", "/api/login", {"identifier": "+216 20 111 111", "password": PASSWORD}).status_code == 200

    # 4. Create a game.
    r = api(athlete_one, "POST", "/api/games", {
        "title": "Sunset doubles", "location": "La Marsa Padel", "date": future_date(3),
        "time": "19:00", "required_level": "Intermediate", "max_players": 4,
    })
    assert r.status_code == 201
    game_id = r.get_json()["data"]["id"]

    # 5. Log in Athlete 2 in the separate session (by unique name this time).
    assert api(athlete_two, "POST", "/api/login", {"identifier": "Athlete Two", "password": PASSWORD}).status_code == 200
    assert athlete_two.get("/api/profile").get_json()["data"]["id"] == athlete_two_id
    assert athlete_one.get("/api/profile").get_json()["data"]["id"] == athlete_one_id  # sessions stay separate

    # 6. Retrieve the game as Athlete 2.
    r = athlete_two.get(f"/api/games/{game_id}")
    assert r.status_code == 200
    assert r.get_json()["data"]["organizer"]["name"] == "Athlete One"
    assert r.get_json()["data"]["participant_count"] == 1

    # 7. Join the game.
    r = api(athlete_two, "POST", f"/api/games/{game_id}/join")
    assert r.status_code == 200
    assert r.get_json()["data"]["participant_count"] == 2

    # 8-9. Retrieve the game as Athlete 1 and confirm Athlete 2 is listed.
    detail = athlete_one.get(f"/api/games/{game_id}").get_json()["data"]
    assert {p["id"] for p in detail["participants"]} == {athlete_one_id, athlete_two_id}
    assert b"Athlete Two" in athlete_one.get(f"/games/{game_id}").data

    # 10. Submit feedback (Athlete 1 reviews Athlete 2).
    r = api(athlete_one, "POST", "/api/feedback", {
        "game_id": game_id, "reviewed_user_id": athlete_two_id, "rating": 5, "comment": "Great net play!",
    })
    assert r.status_code == 201

    # 11. Feedback appears on Athlete 2's public profile (API and HTML page, seen by anyone).
    public = app.test_client()
    feedback = public.get(f"/api/players/{athlete_two_id}/feedback").get_json()["data"]["feedback"]
    assert [(f["reviewer_name"], f["rating"], f["comment"]) for f in feedback] == [("Athlete One", 5, "Great net play!")]
    profile = public.get(f"/api/players/{athlete_two_id}").get_json()["data"]
    assert profile["average_rating"] == 5.0 and profile["feedback_count"] == 1
    assert "phone" not in profile
    page = public.get(f"/players/{athlete_two_id}")
    assert page.status_code == 200 and b"Great net play!" in page.data
