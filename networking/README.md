# Padeli Hyeti Part 2: Network Validation

This folder contains the networking deliverables only. It does not modify the Flask application or the Part 1 feature modules.

The final demonstration is planned for three physical computers on one private LAN:

- Server computer: runs Flask and owns the shared SQLite database.
- Client computer 1: teammate browser session for Athlete 1.
- Client computer 2: teammate browser session for Athlete 2.

The smoke test below is an automated preflight. It uses independent cookie sessions in one Python process; it is not a substitute for the final two-physical-client browser demonstration.

## Teammate clone setup

Each teammate should clone the same repository onto their own physical computer:

```powershell
git clone https://github.com/bvbvbv54/Paddelni.git
cd Paddelni
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Only the server computer runs `python app.py`. Client computers use a browser and connect to the server computer's private IPv4 address.

## Two-client smoke test

The standard-library script creates three dummy accounts, runs the required HTTP status scenarios, and proves that two independent cookie sessions share the same game database.

Run it against a development database only:

```powershell
.\.venv\Scripts\Activate.ps1
python networking\two_client_smoke_test.py --base-url http://127.0.0.1:8000
```

For a LAN server, replace the URL with the server computer's private IPv4 address:

```powershell
python networking\two_client_smoke_test.py --base-url http://192.168.1.25:8000
```

The script does not print passwords, cookies, or full phone numbers. It does create dummy database records, so use a development database and a unique suffix when repeating a run:

```powershell
python networking\two_client_smoke_test.py --suffix 20261021
```

Expected final output includes:

```text
Padeli Hyeti two-client HTTP smoke test passed.
Verified statuses: 200, 201, 400, 401, 404, 409
Verified shared state: Client 2 discovered and joined Client 1's game.
```

## LAN execution order

1. Run the normal pytest suite before leaving localhost.
2. On the server PC, identify the private IPv4 address with `ipconfig`.
3. Start Flask for the approved private LAN only:

```powershell
$env:PADELI_HOST = "0.0.0.0"
$env:PADELI_PORT = "8000"
python app.py
```

4. From each client, open `http://SERVER_IPV4:8000/api/health` and confirm HTTP 200.
5. Run the smoke test against `http://SERVER_IPV4:8000`.
6. Perform the browser workflow with two independent sessions.
7. Capture the approved traffic in Wireshark.
8. Stop Flask and restore localhost mode after the lab.

Do not use `127.0.0.1` from a teammate computer. Do not browse to `0.0.0.0`. Do not disable Windows Firewall, configure router port forwarding, or expose the server publicly.

## Wireshark evidence checklist

Use the active Wi-Fi/Ethernet interface and display filter:

```text
tcp.port == 8000
```

Capture at least:

| Evidence | What to record |
|---|---|
| Health check | Client IP, server IP, TCP destination port 8000, `GET /api/health`, HTTP 200 |
| Registration | `POST /api/register`, HTTP 201; redact request data |
| Invalid request | HTTP 400 and its error code |
| Login failure or protected request | HTTP 401 |
| Missing resource | `GET /api/games/999999999`, HTTP 404 |
| Duplicate/full join | HTTP 409 |
| Shared game | Client 2 `GET /api/games`, join request, Client 1 refresh |

Record source IPv4, destination IPv4, source ephemeral port, destination port, TCP, HTTP method/path, response status, and interpretation. Redact passwords, session cookies, phone numbers, and other personal information. Plain HTTP is acceptable only for this controlled dummy-account demonstration because it exposes credentials and cookies in transit.

## Evidence handoff

Part 2 should provide Part 1/presentation owners with:

- Smoke-test terminal output.
- HTTP status evidence.
- Two-client screenshots or screen recording.
- Wireshark capture file if permitted by the course.
- A redacted packet-analysis table.
- The exact server/client setup and cleanup steps.

HTTP QUERY and the Man-in-the-Middle experiment are optional bonus work. Attempt them only after the mandatory two-client workflow, status scenarios, and Wireshark evidence are complete.
