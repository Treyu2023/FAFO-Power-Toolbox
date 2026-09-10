# C-Site Management Diagnostic

**Launcher:** Verifone & Field → **C-Site Management Diagnostic**  
**Path:** `Verifone Tools/C-Site Management Diagnostic.html`  
**Also linked from:** Commander Status HUD, Phone Assist Navigator, Commander Site Console  
**Needs S1:** live TCP probes + live connection watch (interview / path map work offline)

C-Site / Commander Central is **not** the card-processing path. Three pipes:

| Pipe | Path | MNSP? |
|---|---|---|
| Pump / CRIND | Forecourt device ↔ Commander on store LAN (often 192.168.31.x) | No |
| Cards | Commander → MNSP → processor (Buypass, etc.) outbound TCP | Yes, payment allow-list |
| C-Site | Commander → LAN Config → MNSP → VAM/VIC/GSC, then MQTT 443 heartbeat | Yes, **different** allow-list |

If one store of a fleet stays Offline in the portal while host routes already match a working sister site, this tool ranks the real outliers and **marks the likely break** on the path map (Config Client vs MNSP vs C-Site account).

## Host route vs network route vs default route

These are three different objects on **Config Client → Initial Setup → LAN Configuration**. Mixing them up is the usual “routes already match the sister store” miss.

| Kind | What you type | Mask | Means |
|---|---|---|---|
| **Host route** | One published C-Site IP (e.g. `23.23.135.174`) | `255.255.255.255` | Send **only this IP** via gateway `192.168.31.31` |
| **Network route** | A block (e.g. `23.23.135.0`) | `255.255.255.0` (256 addresses) | Will **not** hit `18.213.229.217` just because you typed `23.23.135.0`. C-Site AWS hosts live in different networks. |
| **Default route** | `0.0.0.0` | owned by whichever NIC is Default | Everything that did not match a more specific host/network row |

Read the **Subnet** column out loud. `255.255.255.255` = Host. Anything else is a Network route.

## Usual outliers

1. DNS disabled (official hard fail — URLs never resolve; host routes cannot replace DNS)
2. Wrong brand playbook (BP/Sunoco/Chevron MNSP-inject vs Exxon/Buypass typed table vs Shell DNS-only)
3. Payment NIC not default when the brand requires it (Chevron / Exxon-style)
4. C-Site IPs entered as a **network** route instead of **host** routes
5. Serial / Service ID mapping or leftover other-merchant onboard (Helpdesk 888-777-3536)
6. Onboarded but Not Connected — MQTT 443 blocked by MNSP while payments still work
7. Portal Pending authorization (not a network fault)

## Field use

1. Start toolbox servers (S1 pill green).
2. Open this tool from the Verifone page, or from HUD / Phone Assist / Site Console.
3. Fill site facts, including **host vs network** and the processor host (for card watches).
4. Read the path map: the ringed node is the likely break. Stay in Config Client until that node is clean; only then ticket MNSP.
5. **Watch ports**
   - Penny / void: you should see ESTABLISHED 443 to the **processor** host. That is cards, not C-Site.
   - Idle 30–60s, no card: you should see ESTABLISHED 443 to MQTT (`184.73.231.196`, `3.212.149.223`, `52.6.28.56`). That is stay-online.
6. **Live TCP probes** from this laptop to VAM / VIC / GSC / MQTT `:443` and DNS for `us.live.verifone.cloud`. Laptop must be on the store LAN (or the same MNSP path). ICMP may lie; 443 is the test that matters.

Gateway for typed host routes: `192.168.31.31` / `255.255.255.255`. Config Client only accepts **one host-route row at a time** — use **Copy next IP** / **Copy IP** on each row, plus **Copy gateway** and **Copy subnet** once. Do not paste the whole table.
