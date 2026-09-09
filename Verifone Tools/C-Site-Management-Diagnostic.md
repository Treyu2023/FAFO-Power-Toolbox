# C-Site Management Diagnostic

**Launcher:** Verifone & Field → **C-Site Management Diagnostic**  
**Path:** `Verifone Tools/C-Site Management Diagnostic.html`  
**Needs S1:** live TCP probes only (interview works offline)

C-Site / Commander Central is **not** the card-processing path. If one store of a fleet stays Offline in the portal while host routes already match a working sister site, this tool ranks the real outliers:

1. DNS disabled (official hard fail — URLs never resolve)
2. Wrong brand playbook (BP/Sunoco/Chevron MNSP-inject vs Exxon/Buypass typed table vs Shell DNS-only)
3. Payment NIC not default when the brand requires it (Chevron / Exxon-style)
4. Serial / Service ID mapping or leftover other-merchant onboard (Helpdesk 888-777-3536)
5. Onboarded but Not Connected — MQTT 443 blocked by MNSP while payments still work
6. Portal Pending authorization (not a network fault)

## Field use

1. Start toolbox servers (S1 pill green).
2. Open this tool from the Verifone page.
3. Fill site facts (software, brand, DNS, default NIC, onboard/portal, error text).
4. Read the verdict + next steps. Copy the C-Site host-route table if the brand actually needs it.
5. **Live TCP probes** from this laptop to VAM / VIC / GSC / MQTT `:443` and DNS for `us.live.verifone.cloud`. Laptop must be on the store LAN (or the same MNSP path). ICMP may lie; 443 is the test that matters.

Gateway for typed host routes: `192.168.31.31` / `255.255.255.255`.
