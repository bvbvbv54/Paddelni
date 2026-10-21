"""Exercise Padeli Hyeti over HTTP with independent cookie sessions.

This script uses only Python's standard library. It creates dummy accounts and
one game, so run it against a development database only. It never prints
passwords, cookies, or full phone numbers.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from http.cookiejar import CookieJar
from typing import Any


class ApiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.cookies = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))
        self.csrf_token = ""

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None):
        headers = {"Accept": "application/json"}
        body = None
        if method != "GET":
            headers["X-CSRF-Token"] = self.csrf_token
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=body, headers=headers, method=method
        )
        try:
            with self.opener.open(request, timeout=10) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                body = {"raw": raw}
            return exc.code, body
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Could not reach {self.base_url}: {exc.reason}") from exc

    def refresh_csrf(self):
        status, body = self.request("GET", "/api/csrf-token")
        assert_status(status, 200, "GET /api/csrf-token")
        self.csrf_token = body["data"]["csrf_token"]

    def register(self, name: str, phone: str, password: str):
        status, body = self.request(
            "POST",
            "/api/register",
            {
                "name": name,
                "phone": phone,
                "skill_level": "Intermediate",
                "password": password,
                "confirm_password": password,
            },
        )
        assert_status(status, 201, "POST /api/register")
        return body["data"]["id"]

    def login(self, phone: str, password: str):
        status, _body = self.request(
            "POST", "/api/login", {"identifier": phone, "password": password}
        )
        assert_status(status, 200, "POST /api/login")
        # Login rotates the session CSRF token, so retrieve the new token.
        self.refresh_csrf()


def assert_status(actual: int, expected: int, operation: str):
    if actual != expected:
        raise AssertionError(f"{operation}: expected HTTP {expected}, received HTTP {actual}")


def parse_args():
    parser = argparse.ArgumentParser(description="Validate Padeli Hyeti with two independent HTTP clients.")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Padeli Hyeti server URL (default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--suffix",
        help="Unique numeric suffix for dummy phone numbers; defaults to the current time",
    )
    parser.add_argument(
        "--password",
        default="DemoPass123!",
        help="Password for the temporary dummy accounts (never printed)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    suffix = args.suffix or str(time.time_ns())[-8:]
    if not suffix.isdigit() or not 5 <= len(suffix) <= 8:
        raise ValueError("--suffix must contain between 5 and 8 digits")
    # Seven-to-fifteen digit values accepted by the application's validator.
    phone_one = f"081{suffix}01"
    phone_two = f"081{suffix}02"
    phone_three = f"081{suffix}03"

    client_one = ApiClient(args.base_url)
    client_two = ApiClient(args.base_url)
    client_three = ApiClient(args.base_url)

    client_one.refresh_csrf()
    client_two.refresh_csrf()
    client_three.refresh_csrf()

    status, _body = client_one.request("GET", "/api/health")
    assert_status(status, 200, "GET /api/health")

    status, _body = client_two.request("GET", "/api/games/999999999")
    assert_status(status, 404, "GET missing game")

    status, _body = client_two.request("POST", "/api/games", {})
    assert_status(status, 401, "unauthenticated POST /api/games")

    status, _body = client_one.request("POST", "/api/register", {})
    assert_status(status, 400, "invalid POST /api/register")

    client_one.register("Network Athlete One", phone_one, args.password)
    client_two.register("Network Athlete Two", phone_two, args.password)
    client_three.register("Network Athlete Three", phone_three, args.password)
    client_one.login(phone_one, args.password)
    client_two.login(phone_two, args.password)
    client_three.login(phone_three, args.password)

    game_date = (date.today() + timedelta(days=2)).isoformat()
    status, body = client_one.request(
        "POST",
        "/api/games",
        {
            "title": "Two-client network smoke test",
            "location": "Approved Padel Lab Court",
            "date": game_date,
            "time": "18:00",
            "required_level": "Intermediate",
            "max_players": 2,
        },
    )
    assert_status(status, 201, "POST /api/games")
    game_id = body["data"]["id"]

    status, body = client_two.request("GET", "/api/games")
    assert_status(status, 200, "GET /api/games from Client 2")
    if not any(game["id"] == game_id for game in body["data"]["games"]):
        raise AssertionError("Client 2 could not discover Client 1's game")

    status, body = client_two.request("POST", f"/api/games/{game_id}/join")
    assert_status(status, 200, "Client 2 joins the game")
    if body["data"]["participant_count"] != 2:
        raise AssertionError("Participant count did not become 2 after Client 2 joined")

    status, _body = client_two.request("POST", f"/api/games/{game_id}/join")
    assert_status(status, 409, "duplicate join")

    status, _body = client_three.request("POST", f"/api/games/{game_id}/join")
    assert_status(status, 409, "full-game join")

    status, body = client_one.request("GET", f"/api/games/{game_id}")
    assert_status(status, 200, "Client 1 retrieves shared game")
    participants = {participant["name"] for participant in body["data"]["participants"]}
    if participants != {"Network Athlete One", "Network Athlete Two"}:
        raise AssertionError(f"Unexpected shared participants: {sorted(participants)}")

    organizer_id = body["data"]["organizer"]["id"]
    status, _body = client_two.request(
        "POST",
        "/api/feedback",
        {
            "game_id": game_id,
            "reviewed_user_id": organizer_id,
            "rating": 5,
            "comment": "Network smoke-test feedback",
        },
    )
    assert_status(status, 201, "feedback submission")

    print("Padeli Hyeti two-client HTTP smoke test passed.")
    print(f"Base URL: {args.base_url}")
    print("Verified statuses: 200, 201, 400, 401, 404, 409")
    print("Verified shared state: Client 2 discovered and joined Client 1's game.")
    print("Verified participant visibility, duplicate/full-game protection, and feedback.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, RuntimeError, KeyError, ValueError) as exc:
        print(f"SMOKE TEST FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)

