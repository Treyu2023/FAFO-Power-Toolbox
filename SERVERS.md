# FAFO servers — simple rules

| Code | Product | Endpoint |
|------|---------|----------|
| **S1** | HTML Toolbox Server | `http://127.0.0.87:18765` |
| **S2** | Ultimate Tab / Local Media Tagger | `http://127.0.0.1:8765` |

## Auto (background)

| Server | Starts when | Stops when |
|--------|-------------|------------|
| **S1** | You open **AI HTML Toolbox** | Tray → **Sleep S1** |
| **S2** | **Google Chrome** is running | Chrome exits (if not manually held) · or **Sleep S2** |

## Manual (any Start button)

If you click **any** of these, the named server(s) **start immediately** —  
Chrome / Toolbox do **not** need to be open:

- Toolbox **▶ Start All Servers** / **Relaunch**
- Toolbox **▶ Start S1** / **▶ Start S2**
- Desktop / Start Menu **Start Servers**
- Tray **Start / wake S1** or **S2**
- Watchdog-related start / recover actions
- `aitoolbox://start` · `aitoolbox://restart`
- `0-Start-ALL-Servers.bat` · `1-Start-…` · `2-Start-…`

Manual start sets a short **manual hold** so the auto Chrome lifecycle does not kill S2 the next second. **Sleep** clears the hold.

## One-liners

```text
S1 auto  = Toolbox open
S2 auto  = Chrome open
Any Start button = run that server now, no host app required
```
