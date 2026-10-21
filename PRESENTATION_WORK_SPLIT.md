# Padeli Hyeti Presentation Work Split

## Source analysis

The available source material is:

- The Padeli Hyeti project brief in the chat
- The implemented Flask/SQLite application
- [README.md](README.md), which documents startup, APIs, HTTP statuses, testing, and the end-to-end demo
- [NETWORK_LAB.md](NETWORK_LAB.md), which documents the future three-device LAN and Wireshark phase
- The email from Ikram supplied in the chat, which defines the final presentation and evaluation requirements

The email does not specify a presentation date, named slide template, or detailed marking rubric. It does specify the following requirements.

## Email requirements analysis

| Email requirement | Consequence for the team |
|---|---|
| At least one server and two clients | The presentation must show a centralized server plus two independent browser clients. The clients may be physical machines or virtual machines. |
| Working implementation is essential | The live application and its core workflow must be ready before polishing slides. A non-working mock-up earns zero. |
| Required HTTP scenarios and proper error handling | Show actual requests and response status codes, not only screenshots of success pages. |
| Wireshark captures and analysis | Capture traffic and explain source/destination addresses, TCP port, HTTP methods/paths, and status codes. |
| HTTP QUERY and Man-in-the-Middle experiment | Optional bonus work; do not displace the mandatory implementation, HTTP scenarios, or Wireshark evidence. |
| Jury of 2–3 members | Every presenter must be able to explain the code and answer implementation questions. |
| Maximum 20 minutes including presentation, live demo, code review, and discussion | The deck and demo need a timed run-through. Keep the prepared slide narrative concise and reserve time for code review and questions. |
| 5–7 slides | Use one shared deck with five to seven slides covering overview, architecture, implementation, HTTP scenarios, and Wireshark analysis. |

The two prompts below turn those email requirements into two coordinated work packages. They are written so they can be pasted into separate planning or presentation-writing tasks.

## Deliverables that should appear in the presentation

1. The problem and Padeli Hyeti solution
2. HTTP client-server architecture and centralized SQLite persistence
3. Authentication, profile, player-finder, game, join, and feedback workflows
4. Database structure and security/validation decisions
5. Demonstrable HTTP status-code scenarios
6. Automated testing and browser end-to-end evidence
7. Future LAN topology and Wireshark plan
8. Startup instructions, repository link, limitations, division of speaking roles, and evidence that the app is ready for code review

## Part 1 — Application, API, database, and product demonstration

### Full structured prompt

```text
You are responsible for Part 1 of the Padeli Hyeti Computer Networks presentation.

ROLE
Act as the software/application lead. Explain the working localhost application in clear university-level language, with enough technical detail to prove that this is a real HTTP client-server system rather than a mock interface.

SOURCE MATERIAL
- Project: Padeli Hyeti, a Flask + SQLite padel player finder.
- Repository: https://github.com/bvbvbv54/Paddelni
- Local implementation: Flask application factory in padeli/__init__.py; JSON API in padeli/api.py; SQLite schema in padeli/schema.sql; Jinja templates in padeli/templates; tests in tests/test_app.py.
- Documentation: README.md and NETWORK_LAB.md.
- Email requirements to follow: the group must demonstrate at least one server and two clients (physical machines or VMs), working implementation is mandatory, HTTP scenarios/error handling and Wireshark capture/analysis are required, HTTP QUERY and MITM are optional bonus features, the session is at most 20 minutes including demo/code review/discussion, and the shared presentation must contain 5–7 slides.

OBJECTIVE
Produce a polished 5–7 minute presentation section that fits into a shared 5–7 slide deck and a 20-minute session that also includes the live demo, code review, and discussion. Demonstrate:
1. The problem: padel players need a simple way to discover players and shared sessions.
2. The solution: a browser client sends real HTTP requests to one Flask server, which validates input and stores shared data in SQLite.
3. The principal workflow: register → log in → create a game → another player discovers and joins it → both players see the shared participant list → feedback is recorded.
4. The technical evidence: API endpoints, database tables, actual HTTP status codes, automated tests, and browser verification.

REQUIRED CONTENT
- Introduce the application name and target users.
- Show a simple architecture diagram in words or a slide-ready diagram: Browser Client 1 and Browser Client 2 → Flask HTTP Server → SQLite database.
- Explain that both browsers use the same backend and database, so Athlete 2 can discover a game created by Athlete 1.
- Explain the core endpoints with examples:
  GET /api/players
  POST /api/register
  POST /api/login
  GET /api/games
  POST /api/games
  POST /api/games/<id>/join
  POST /api/feedback
- Explain the database tables: users, games, game_participants, feedback.
- Explain password hashing, sessions, CSRF tokens, parameterized SQL, foreign keys, unique constraints, and server-side validation without claiming production-grade security.
- Demonstrate the required statuses using actual requests/results:
  200 successful retrieval,
  201 registration or game creation,
  400 invalid/missing input,
  401 invalid login or protected request,
  404 missing player/game,
  409 duplicate registration/join/full game.
- Mention the controlled 500 test path only as an automated-test concern; do not break the live app.
- Report the verified test result: 21 pytest tests passed.
- Include screenshots or a live-demo script for registration, game creation, game joining, participant visibility, player search, and feedback.
- State clearly which browser is Client 1, which is Client 2, and which computer/VM runs the server. Do not present a single-browser mock as proof of the two-client requirement.
- Keep optional HTTP QUERY and MITM experiments in a clearly labeled “bonus” section only if the team has time and safe evidence.

DEMO SCRIPT
1. Register Athlete 1 and log in.
2. Create a future-dated game.
3. Use a separate browser session for Athlete 2, register, and log in.
4. Find the game and join it.
5. Return to Athlete 1 and refresh the game details.
6. Show Athlete 2 in the participant list.
7. Search for a player and open the public profile.
8. Submit feedback after the shared game and show it on the receiver's profile.

OUTPUT FORMAT
Return:
- A slide-by-slide outline with 5–7 slides.
- Speaker notes for each slide, written as natural spoken language.
- One concise architecture diagram specification.
- A table mapping each required HTTP status to its request and visible evidence.
- A 90-second fallback demo narration in case the live browser or server is unavailable.
- A checklist of screenshots/logs that should be captured before presentation day.

CONSTRAINTS
- Do not invent performance metrics, cloud infrastructure, or features not implemented. Treat the email requirements above as authoritative.
- Do not call the app a REST API in a strict academic sense; say “REST-style JSON endpoints” where appropriate.
- Do not expose passwords, session cookies, or real personal data in screenshots.
- Keep the explanation simple enough for a computer-networks audience.
```

## Part 2 — Networking, testing evidence, and future LAN demonstration

### Full structured prompt

```text
You are responsible for Part 2 of the Padeli Hyeti Computer Networks presentation.

ROLE
Act as the networking, testing, and demonstration lead. Connect the working localhost application to the course concepts of HTTP request/response communication, ports, clients, a centralized server, status codes, LAN access, and Wireshark analysis.

SOURCE MATERIAL
- Project: Padeli Hyeti, currently validated on localhost at 127.0.0.1:8000.
- Repository: https://github.com/bvbvbv54/Paddelni
- Documentation: README.md and NETWORK_LAB.md.
- Tests: tests/test_app.py; the verified suite contains 21 passing tests.
- Future network plan: one server PC and two teammate browser clients on the same private LAN.
- Email requirements to follow: demonstrate at least one server and two clients using physical machines or VMs; show the working implementation, required HTTP scenarios, proper error handling, and Wireshark captures/analysis; treat HTTP QUERY and MITM as optional bonus features; stay within the 20-minute maximum including presentation, live demo, code review, and discussion; and use 5–7 slides covering overview, architecture, implementation, HTTP scenarios, and Wireshark analysis.

OBJECTIVE
Produce a polished 5–7 minute presentation section for the shared 5–7-slide deck. It must leave room inside the 20-minute total session for the live demo, code review, and jury discussion. Prove how the application will be used as a Computer Networks project:
1. The localhost phase is complete and validated.
2. Browser clients communicate with a centralized Flask server over HTTP on port 8000.
3. The future LAN phase can use the server computer's private IPv4 address without changing application source code.
4. Wireshark can reveal source/destination IP addresses, TCP port 8000, HTTP methods, request paths, and response status codes.
5. The team understands the security and operational limitations of plain HTTP.

REQUIRED CONTENT
- Explain the request path for a normal action:
  Browser → TCP connection → server port 8000 → Flask route → SQLite query/transaction → HTTP response → browser UI.
- Explain the difference between localhost testing and future LAN testing.
- Describe environment configuration:
  PADELI_HOST=127.0.0.1 for current local work;
  PADELI_HOST=0.0.0.0 only during the approved private-LAN lab;
  PADELI_PORT=8000.
- Present the future topology: server PC running Flask and SQLite, Teammate 1 browser, Teammate 2 browser, all on one trusted private LAN.
- Explain that the final classroom demonstration must use one server plus two clients on physical machines or virtual machines. The current localhost validation proves application behavior; the LAN step must still be executed and captured before the final presentation.
- Explain that both teammates must access http://SERVER_IPV4:8000 and must not use 127.0.0.1 on their own computers.
- Explain the connectivity checks: /api/health, Test-NetConnection SERVER_IPV4 -Port 8000, same-LAN verification, and narrow Private-profile firewall approval only if needed.
- Explain a Wireshark capture plan with the display filter tcp.port == 8000 and the fields to record: source IP, destination IP, source ephemeral port, destination port 8000, TCP, HTTP method/path, and status code.
- Explain why dummy accounts are mandatory: plain HTTP exposes credentials and cookies in transit.
- Explain what the automated suite proves: 200/201/400/401/404/409 scenarios, shared database behavior, duplicate/full-game prevention, feedback rules, and controlled 500 handling.
- State that firewall, router, VM, WSL, and port-forwarding changes are outside the current phase.
- Make clear that HTTP QUERY and the Man-in-the-Middle experiment are optional bonus features and should only be attempted after all mandatory evidence is complete.

PRESENTATION EVIDENCE
Prepare a checklist containing:
- A screenshot of the application home page.
- A terminal or browser-devtools capture of GET /api/health returning 200.
- A Network-tab example showing POST /api/games returning 201.
- A duplicate/full-game example returning 409.
- A two-client screen or screenshots proving Athlete 2 can see Athlete 1's game, with the server and both clients labeled as physical machines or VMs.
- A test-run screenshot showing “21 passed”.
- A labeled LAN topology diagram.
- A Wireshark packet screenshot with sensitive values redacted.

OUTPUT FORMAT
Return:
- A slide-by-slide outline with 5–7 slides.
- Speaker notes for each slide.
- One LAN topology diagram specification.
- One HTTP request/response sequence diagram specification.
- A Wireshark analysis table with columns: event, source, destination, protocol, port, HTTP method/path, status, interpretation.
- A live-demo runbook with exact commands and an explicit stop/cleanup step.
- A 90-second fallback explanation for when LAN access or Wireshark is unavailable.
- A final division-of-speaking-roles checklist for two teammates.
- A timing plan that keeps the full session under 20 minutes, including slides, live demo, code review, and discussion.

CONSTRAINTS
- Do not claim that LAN access, firewall approval, or Wireshark capture has already been performed; those belong to the future phase.
- Do not expose the development server publicly.
- Do not use real passwords, phone numbers, cookies, or personal data in captures.
- Do not disable Windows Firewall or recommend router port forwarding.
- Keep plain HTTP limitations explicit: acceptable for controlled localhost/dummy-account demonstration, unsuitable for real credentials without HTTPS.
```

## Coordination checklist

- Part 1 owns application behavior, API/database explanation, and the primary user workflow.
- Part 2 owns network concepts, status-code evidence, testing proof, LAN preparation, and Wireshark methodology.
- Both presenters should use the same terminology: browser client, Flask server, SQLite database, HTTP request/response, port 8000, and shared persistent state.
- Use one shared 5–7-slide deck. Do not create 5–7 slides per person.
- Recommended timing: 8–10 minutes for the slides, 4–5 minutes for the live demo, 3–4 minutes for code review, and the remaining time for jury discussion. Adjust after a timed rehearsal while staying below 20 minutes total.
- Before presentation day, replace the localhost-only validation with an approved one-server/two-client physical-machine or VM demonstration and capture the Wireshark evidence required by the email.
- Treat HTTP QUERY and MITM as optional bonus experiments only after the mandatory demo and captures are complete.
- Re-run `python -m pytest` before presenting and record the current result in the deck.
