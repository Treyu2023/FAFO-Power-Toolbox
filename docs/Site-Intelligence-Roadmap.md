# FAFO Site Intelligence — product roadmap

**Goal:** Every Verifone / Commander site you touch becomes a living dossier (layout, equipment, network, passwords scheme, call notes). Over time this becomes **invaluable to technicians** and a product you can sell.

---

## What ships now (Phase 1 foundation)

| Feature | Where |
|--------|--------|
| **⚡ Quick Start** | Commander Site Console toolbar |
| Always-create **site registry** files | `%LOCALAPPDATA%\FAFO\site-registry\` |
| Liferaft shell even when data is thin | `%LOCALAPPDATA%\FAFO\site-profiles\` |
| Ingest all SMS backups into registry | Quick Start / `POST /api/verifone/registry/ingest-backups` |
| Import **Windows Sticky Notes** → site stubs | Quick Start / `import-sticky-notes` |
| Aerial layout **seed from backup** (pumps, tanks, regs, CRIND by pump) | Layout tab + Quick Start |
| Hot/cold **cache policy** stub | `site-registry/cache-policy.json` |

### Quick Start does

1. Sync watched SMS folders  
2. Create/update a durable registry record per export  
3. Ensure Liferaft master profile shells  
4. Scan Sticky Notes for IPs / store-ish lines → stubs  
5. Seed empty aerial layouts from backup equipment  

---

## Recommended next build order

### A. Layout tool (cooking)

1. **Palette dock** of unplaced items from backup still missing on canvas  
2. **Island templates** (2×4, 3×3) snap-align pumps  
3. **Photo underlay** (parking lot satellite / phone photo) with opacity  
4. **Per-site revision history** of layout JSON (last 10)  
5. Export layout PNG into field pack  

### B. Knowledge gather (intelligence)

1. **Paste call notes** → NLP-lite extract IP, phone, Manager password pattern, brand  
2. **Web research assist** (manual confirm only): address / hours for brand + city  
3. **Greensboro / triad scraper** only as *leads* (name + address), never invent passwords  
4. Every new lead → `ensure_site()` stub immediately  

### C. Hot / cold storage (scale)

| Tier | Default | Purpose |
|------|---------|---------|
| **Hot local** | 14 days / configurable GB | Active sites, full survey + layout |
| **Cold** | OneDrive / Google / external | Full catalog; pull pack when needed |
| **Evict** | After idle (2 weeks) | Drop heavy blobs locally; keep registry index + keys |

**Tech override:** slider for max local GB + “pin this site forever” + optional external drive path (whole mirror).

### D. Anti-theft without encrypting daily work

- Daily tech use: **plain local files** (fast, no drama).  
- **Bulk catalog ZIP** (the “steal the whole company” artifact):  
  - AES zip password **not stored in the app**  
  - App requests short-lived **unlock token** from your license/server  
  - Offline copy of the ZIP alone is useless  
- Do **not** DRM every site file — techs will hate it and work around it.

### E. Sellable multi-tech (later)

- Seats: owner / tech / investor (Sumran already separate portal)  
- Shared cold catalog; credentials stay per-org vault  
- Audit: who opened which site  

---

## Privacy (inventory vs cost)

Investor Portal + FAFO Petro:

- Public inventory may show **sell price**  
- **Our cost / COGS never** goes public  

Site Intelligence dossiers for techs may include costs internally — that is **not** the public web catalog.

---

## API cheatsheet

```
GET  /api/verifone/registry
POST /api/verifone/registry/quick-start
POST /api/verifone/registry/ensure
POST /api/verifone/registry/ingest-backups
POST /api/verifone/registry/import-sticky-notes
POST /api/verifone/registry/seed-area
GET  /api/verifone/registry/roadmap
GET  /api/verifone/registry/policy
PUT  /api/verifone/registry/policy
```

---

## Why this sells

A tech who never used FAFO walks up cold.  
A tech with FAFO already has pumps placed, Manager letter cycle, last visit notes, and the layout from the last person who cared.  
**That gap is the product.**

---

## Gear knowledge + 3D CAD-lite (field-learned, not textbook)

### Today
- Tab **Gear knowledge** on Site Console  
- Techs edit **pros / cons / compat / day-zero** per site  
- Default scope = **this site only**  
- **Promote multi-site** only after short **Yes** checklist (OEM family, not unique wiring, etc.)  
- Cookie-cutter chain flag + copy library tip onto another site  
- Layout: **Tip from selection** seeds a tip from selected pump/CRIND  

### 3D explode (CAD-lite — in Site Console now)
Commercial service software is expensive; we do **not** ship their CAD.  

**Now (Aerial layout → 🕹 3D view):**
- Three.js island built from the same layout items as 2D  
- Orbit / zoom, click unit → gear knowledge side panel  
- **Explode / Assemble** for inspection  
- File: `Verifone Tools/site-layout-3d.js`  

**Next:** low-poly glTF brand kits (`view3d.modelKey`), richer explode groups, photo ground plane.

### Promote criteria (current)
1. Same equipment family / manufacturer class?  
2. Not only this store’s unique wiring/IP?  
3. Useful beyond one weird customer preference (or chain cookie-cutter)?  
4. Compat brands/models listed (or N/A)?  
5. Would trust on a second similar site?  

All Yes → library. Otherwise stays site-only.
