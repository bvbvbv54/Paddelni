# Padeli Hyeti: Future LAN Networking Lab

This procedure is for the **next phase only**, after localhost validation. The final demonstration will use **three physical computers**: one server computer and two teammate client computers. None of these network or firewall changes are performed by the application.

## Safety and scope

- Use a trusted private classroom/home LAN, never a public Wi-Fi network.
- Use three physical computers on the same private LAN: one Flask server and two browser clients.
- Each teammate should clone the same GitHub repository and install the same dependencies on their own computer.
- Use dummy accounts and dummy phone numbers. Plain HTTP does not encrypt passwords or session cookies in transit.
- Do not expose Flask's development server to the public internet or configure router port forwarding.
- Do not substitute a single computer with multiple browser tabs for the final physical-client demonstration. Separate browser sessions are still required on the two client computers.
- Keep Flask debug mode disabled.
- Get permission before changing Windows Firewall rules or capturing another person's traffic.

## 1. Prepare the server computer

Connect all three computers to the same local network. On the server PC, open PowerShell and find the active adapter's IPv4 address:

```powershell
ipconfig
```

Look under the connected Wi-Fi or Ethernet adapter for a private address such as `192.168.1.25` or `10.0.0.15`. Do not use the default gateway, `127.0.0.1`, a disconnected adapter, or an IPv6 address for this exercise.

Test that the application still works locally before exposing it to the LAN:

```powershell
.\.venv\Scripts\Activate.ps1
$env:PADELI_SECRET_KEY = "the-same-long-private-lab-secret"
python app.py
```

Open `http://127.0.0.1:8000`, then stop the server with `Ctrl+C`.

## 2. Bind Flask to the LAN interface

For the lab session only:

```powershell
.\.venv\Scripts\Activate.ps1
$env:PADELI_HOST = "0.0.0.0"
$env:PADELI_PORT = "8000"
$env:PADELI_SECRET_KEY = "the-same-long-private-lab-secret"
python app.py
```

`0.0.0.0` means Flask listens on all local interfaces. Teammates do not browse to `0.0.0.0`; they use the server's IPv4 address, for example `http://192.168.1.25:8000`.

Environment-variable configuration means no source-code change is required. Closing this PowerShell window or resetting `PADELI_HOST` to `127.0.0.1` restores the localhost-only default for later runs.

## 3. Handle Windows Firewall only if required

The first LAN-bound run may display a Windows Defender Firewall prompt. Do not allow public-network access. If your instructor/administrator approves, allow Python only on **Private networks**.

If no prompt appears and teammates cannot connect, first verify the server is running, the address is correct, and all devices are on the same LAN. Only then ask the computer owner or administrator to create a narrowly scoped inbound TCP rule for port 8000 on the Private profile. Remove or disable that rule after the lab.

Do not disable Windows Firewall. Do not create a rule for all ports or the Public profile.

## 4. Test the three-device workflow

1. On each teammate PC, clone the repository and install dependencies:

```powershell
git clone https://github.com/bvbvbv54/Paddelni.git
cd Paddelni
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

2. On the server PC, open `http://127.0.0.1:8000/api/health`.
3. On each teammate PC, open `http://SERVER_IPV4:8000/api/health`. Expect status `200` and JSON with `"status": "healthy"`.
4. Teammate 1 registers and creates a game from Client Computer 1.
5. Teammate 2 registers, finds that game, and joins it from Client Computer 2.
6. Teammate 1 refreshes the game details and confirms Teammate 2 appears.
7. Demonstrate player search and feedback after both accounts share the game.

The `networking/two_client_smoke_test.py` script is a useful HTTP preflight because it creates independent cookie sessions, but it does not replace the required three-physical-computer browser demonstration.

If clients cannot connect:

- Confirm the Flask terminal says it is listening on `0.0.0.0:8000`.
- Recheck the server IPv4 address with `ipconfig`; DHCP addresses can change.
- Confirm all devices use the same Wi-Fi/Ethernet LAN and client isolation is not enabled.
- Try `Test-NetConnection SERVER_IPV4 -Port 8000` from an approved Windows client.
- Check that the firewall rule is limited to TCP 8000 and the Private profile.
- Check the Flask terminal for incoming request lines and errors.

## 5. Capture and analyze HTTP with Wireshark

Capture only traffic authorized for the class exercise.

1. Start Wireshark on the server PC and select the active Wi-Fi or Ethernet interface.
2. Start capture before a teammate loads Padeli Hyeti.
3. Use the display filter `tcp.port == 8000` to isolate application traffic.
4. Perform a small sequence: health check, login with a dummy account, retrieve games, and join a game.
5. Stop the capture promptly.
6. Select a packet and record:
   - Client source IPv4 address and ephemeral source port
   - Server destination IPv4 address and destination port `8000`
   - Transport protocol TCP
   - HTTP request method and path, such as `GET /api/games`
   - HTTP response status, such as `200`, `201`, `401`, `404`, or `409`
7. Use **Follow → HTTP Stream** or **Follow → TCP Stream** only for the authorized dummy traffic.

Because this lab uses HTTP, Wireshark can expose submitted dummy credentials and session cookies. This visibly demonstrates why real deployments require HTTPS. Do not capture or share real credentials. Redact phone numbers, cookie values, and passwords from screenshots or reports.

## 6. Optional QUERY and passive MITM/security bonus

Padeli Hyeti also includes a read-only non-standard HTTP method for the bonus discussion:

```powershell
curl.exe -X QUERY "http://SERVER_IPV4:8000/api/query?resource=games"
```

The server returns the public game catalogue in the normal JSON envelope and adds `"method": "QUERY"`. In Wireshark, filter on `tcp.port == 8000` and look for `QUERY /api/query?resource=games`.

The security bonus is demonstrated with passive capture: the HTTP request line, headers and response code are visible to an observer on the path. Do not perform ARP spoofing or active interception on a shared Wi-Fi network. An active MITM experiment is only appropriate on an isolated lab network containing devices you own and have explicit permission to test. Use dummy accounts and redact session cookies in every screenshot.

## 7. End the lab safely

1. Stop Flask with `Ctrl+C`.
2. Close Wireshark and save only the capture your instructor requires.
3. Remove or disable any temporary inbound firewall rule through the approved Windows Firewall interface.
4. Return future application runs to the default localhost binding by starting normally with no `PADELI_HOST` value, or set it explicitly:

```powershell
$env:PADELI_HOST = "127.0.0.1"
python app.py
```

For use beyond a controlled demonstration, place the application behind an HTTPS-capable production server before handling real credentials.
