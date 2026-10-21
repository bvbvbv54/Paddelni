"""Shared helpers for the Padeli Hyeti test-suite (real HTTP calls through the Flask test client)."""

from __future__ import annotations

from datetime import date, timedelta

PASSWORD = "strong-pass-123"


def csrf(client) -> str:
    response = client.get("/api/csrf-token")
    assert response.status_code == 200
    return response.get_json()["data"]["csrf_token"]


def api(client, method: str, path: str, payload=None):
    headers = {"X-CSRF-Token": csrf(client)}
    return client.open(path, method=method, json=payload if payload is not None else {}, headers=headers)


def registration(name="Amina Musa", phone="08012345678", skill="Intermediate", **overrides):
    payload = {
        "name": name,
        "phone": phone,
        "skill_level": skill,
        "password": PASSWORD,
        "confirm_password": PASSWORD,
    }
    payload.update(overrides)
    return payload


def register(client, name="Amina Musa", phone="08012345678", skill="Intermediate", **overrides):
    return api(client, "POST", "/api/register", registration(name, phone, skill, **overrides))


def login(client, identifier="08012345678", password=PASSWORD):
    return api(client, "POST", "/api/login", {"identifier": identifier, "password": password})


def future_date(days=7):
    return (date.today() + timedelta(days=days)).isoformat()


def game_payload(title="Friday Padel", maximum=4, **overrides):
    payload = {
        "title": title,
        "location": "Central Padel Club",
        "date": future_date(),
        "time": "18:30",
        "required_level": "Intermediate",
        "max_players": maximum,
    }
    payload.update(overrides)
    return payload


def create_game(client, title="Friday Padel", maximum=4, **overrides):
    return api(client, "POST", "/api/games", game_payload(title, maximum, **overrides))


def registered_client(app, name, phone, skill="Intermediate"):
    new_client = app.test_client()
    assert register(new_client, name, phone, skill).status_code == 201
    assert login(new_client, phone).status_code == 200
    return new_client


def my_id(client) -> int:
    response = client.get("/api/profile")
    assert response.status_code == 200
    return response.get_json()["data"]["id"]
