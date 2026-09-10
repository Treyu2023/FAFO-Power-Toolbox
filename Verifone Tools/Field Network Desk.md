# Field Network Desk

**Launcher:** Verifone & Field → **Field Network Desk**  
**Path:** `Verifone Tools/Field Network Desk.html`  
**Needs S1:** hop probes + cmd.exe launch (identify still works from pasted ipconfig)

Technician Swiss army knife. It does **not** replace the C-Site interview — it decides which desks to open.

1. Identify the LAN (S1 fingerprint or paste `ipconfig /all`).
2. Color hops as TCP/ping/DNS run: green/black pass, amber/black warn, red/black fail. Stamp a hop if you ran it in cmd instead.
3. **Open needed desks** launches C-Site Diagnostic, Status HUD, and Phone Assist when the laptop is on POS LAN.
4. **Launch Command Prompt** starts a new `cmd.exe` with a whitelisted kit (`ipconfig /all`, `arp -a`, ping, tracert, nslookup, netstat). If S1 is down, downloads the same kit as a `.bat`.
5. **Add command** on the Cmd kit tab — clickable custom commands saved on this laptop so the kit can match the store.
6. **Unique hosts** on Forecourt / MNSP / ISP — odd DCR IPs, extra boxes, VLANs that are not the template. Each one becomes a hop and a copyable ping.
7. In-page desks: Forecourt / CRIND, MNSP (Cybera, Hughes+FortiGate, Acumera, Mako), ISP (Brightspeed, Spectrum/TWC, Starlink).

## Gateway cheat sheet

| Gateway | You are on | Open |
|---|---|---|
| `192.168.31.31` | Verifone POS / Cybera LAN | Forecourt + MNSP + C-Site |
| `192.168.1.99` | FortiGate mgmt (Hughes) | MNSP, then ISP if WAN down |
| `10.96.10.1` | Acumera | MNSP + C-Site (Chevron inject) |
| `192.168.0.1` | Brightspeed-style modem | ISP first |
| `192.168.1.1` | Spectrum / SOHO | ISP first |
| `192.168.100.1` | Starlink | ISP first |

Published factory logins (Cybera `zonerouter` / `cyberasca`, FortiGate `admin` / blank, Brightspeed `admin` / sticker) are starting points only — sites rotate them.

C-Site path map: `Verifone Tools/C-Site Management Diagnostic.html`
