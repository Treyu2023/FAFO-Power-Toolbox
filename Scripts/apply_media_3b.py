#!/usr/bin/env python3
"""Media-desk 3.0.2 — P0 TDZ/races + remaining XSS, abort, iframe timeout, convert batches."""
from __future__ import annotations

from pathlib import Path

ROOT = Path("/tmp/fafo-toolbox")


def patch(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        if new in text or new.strip() in text:
            print("skip (already)", label)
            return
        print("MISS", label)
        return
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("ok", label)


def main() -> None:
    # ------------------------------------------------------------------
    # P0 Duplicate File Manager — TDZ `const el = el(...)`
    # ------------------------------------------------------------------
    patch(
        ROOT / "File Tools/Duplicate File Manager.html",
        "            serverStarting = true;\n"
        "            const el = el('serverStatus');\n"
        "            const btn = el('btnStartServer');\n"
        "            el.textContent = '◌ Starting…';",
        "            serverStarting = true;\n"
        "            const statusEl = el('serverStatus');\n"
        "            const btn = el('btnStartServer');\n"
        "            if (statusEl) statusEl.textContent = '◌ Starting…';",
        "dup TDZ start server",
    )
    patch(
        ROOT / "File Tools/Duplicate File Manager.html",
        "        function refreshOpsTally() {\n"
        "            const el = el('opsTally');\n"
        "            if (!el || !window.FAFOOpsStats) return;\n"
        "            try {\n"
        "                const snap = FAFOOpsStats.snapshot({ limit: 1 });\n"
        "                const open = snap.openSession && snap.openSession.tool === 'duplicate-file-manager'\n"
        "                    ? snap.openSession\n"
        "                    : null;\n"
        "                const life = snap.lifetime || {};\n"
        "                const sessFiles = open ? (open.filesRemoved || 0) : 0;\n"
        "                const sessBytes = open ? (open.bytesFreed || 0) : 0;\n"
        "                el.textContent = sessFiles || sessBytes\n"
        "                    ? `Session ${sessFiles} · ${FAFOOpsStats.formatBytes(sessBytes)}  ·  Σ ${FAFOOpsStats.formatBytes(life.bytesFreed || 0)}`\n"
        "                    : `Σ freed ${FAFOOpsStats.formatBytes(life.bytesFreed || 0)}`;\n"
        "                el.title = `This session: ${sessFiles} files, ${FAFOOpsStats.formatBytes(sessBytes)}\\nLifetime: ${(life.filesRemoved || 0)} files, ${FAFOOpsStats.formatBytes(life.bytesFreed || 0)} — open Ops Stats for charts`;",
        "        function refreshOpsTally() {\n"
        "            const tally = el('opsTally');\n"
        "            if (!tally || !window.FAFOOpsStats) return;\n"
        "            try {\n"
        "                const snap = FAFOOpsStats.snapshot({ limit: 1 });\n"
        "                const open = snap.openSession && snap.openSession.tool === 'duplicate-file-manager'\n"
        "                    ? snap.openSession\n"
        "                    : null;\n"
        "                const life = snap.lifetime || {};\n"
        "                const sessFiles = open ? (open.filesRemoved || 0) : 0;\n"
        "                const sessBytes = open ? (open.bytesFreed || 0) : 0;\n"
        "                tally.textContent = sessFiles || sessBytes\n"
        "                    ? `Session ${sessFiles} · ${FAFOOpsStats.formatBytes(sessBytes)}  ·  Σ ${FAFOOpsStats.formatBytes(life.bytesFreed || 0)}`\n"
        "                    : `Σ freed ${FAFOOpsStats.formatBytes(life.bytesFreed || 0)}`;\n"
        "                tally.title = `This session: ${sessFiles} files, ${FAFOOpsStats.formatBytes(sessBytes)}\\nLifetime: ${(life.filesRemoved || 0)} files, ${FAFOOpsStats.formatBytes(life.bytesFreed || 0)} — open Ops Stats for charts`;",
        "dup TDZ opsTally",
    )
    patch(
        ROOT / "File Tools/Duplicate File Manager.html",
        "            const on = await (API()?.isOnline?.() ?? false);",
        "            const on = await (API()?.isOnline?.(false, 1500) ?? false);",
        "dup poll isOnline probe-less",
    )

    # ------------------------------------------------------------------
    # P0 Pair Review — autoload only once (not every health poll)
    # ------------------------------------------------------------------
    patch(
        ROOT / "Movie File Manager/Pair Review Queue.html",
        "        onOnline: () => {\n"
        "          // Auto-load if navigated with source query\n"
        "          if (params.get('source') || params.get('autoload') === '1') loadQueue();\n"
        "        },",
        "        onOnline: () => {\n"
        "          if (window.__pairReviewAutoloaded) return;\n"
        "          if (params.get('source') || params.get('autoload') === '1') {\n"
        "            window.__pairReviewAutoloaded = true;\n"
        "            loadQueue();\n"
        "          }\n"
        "        },",
        "pair review autoload once",
    )

    # ------------------------------------------------------------------
    # P0 Guided Pair Match — candidate gen + withBusy on reject/skip
    # ------------------------------------------------------------------
    patch(
        ROOT / "Movie File Manager/Guided Pair Match.html",
        "    async function loadCandidatesForAnchor() {\n"
        "      const anchor = currentAnchor();\n"
        "      if (!anchor) return;\n",
        "    let _candGen = 0;\n"
        "    async function loadCandidatesForAnchor() {\n"
        "      const gen = ++_candGen;\n"
        "      const anchor = currentAnchor();\n"
        "      if (!anchor) return;\n",
        "guided cand gen start",
    )
    patch(
        ROOT / "Movie File Manager/Guided Pair Match.html",
        "      });\n"
        "      // Client-side safety: drop same-size / not-larger when option is on\n"
        "      let cands = data?.candidates || [];\n",
        "      });\n"
        "      if (gen !== _candGen) return;\n"
        "      // Client-side safety: drop same-size / not-larger when option is on\n"
        "      let cands = data?.candidates || [];\n",
        "guided cand gen apply",
    )
    patch(
        ROOT / "Movie File Manager/Guided Pair Match.html",
        "    function rejectCandidate() {\n"
        "      if (busy) return;\n"
        "      const cand = currentCandidate();\n"
        "      const anchor = currentAnchor();\n"
        "      if (!cand || !anchor) return;\n",
        "    function rejectCandidate() {\n"
        "      return withBusy(async () => {\n"
        "      const cand = currentCandidate();\n"
        "      const anchor = currentAnchor();\n"
        "      if (!cand || !anchor) return;\n",
        "guided reject withBusy open",
    )
    patch(
        ROOT / "Movie File Manager/Guided Pair Match.html",
        "        loadCandidatesForAnchor().then(() => {\n"
        "          if (historyCursor >= 0 && history[historyCursor]?.type === 'exhaust') {\n"
        "            history[historyCursor].after = snapshotCore();\n"
        "          }\n"
        "        }).catch(e => toast(e.message || String(e), 'warn'));\n"
        "        return;\n"
        "      }\n\n"
        "      const after = snapshotCore();\n"
        "      pushHistory({\n"
        "        type: 'reject',\n"
        "        label: `Reject ${cand.candidate_name}`,\n"
        "        before,\n"
        "        after,\n"
        "        pairId: null,\n"
        "        pairPayload: null,\n"
        "      });\n"
        "      render();\n"
        "    }",
        "        try {\n"
        "          await loadCandidatesForAnchor();\n"
        "          if (historyCursor >= 0 && history[historyCursor]?.type === 'exhaust') {\n"
        "            history[historyCursor].after = snapshotCore();\n"
        "          }\n"
        "        } catch (e) { toast(e.message || String(e), 'warn'); }\n"
        "        return;\n"
        "      }\n\n"
        "      const after = snapshotCore();\n"
        "      pushHistory({\n"
        "        type: 'reject',\n"
        "        label: `Reject ${cand.candidate_name}`,\n"
        "        before,\n"
        "        after,\n"
        "        pairId: null,\n"
        "        pairPayload: null,\n"
        "      });\n"
        "      render();\n"
        "      });\n"
        "    }",
        "guided reject withBusy close",
    )
    patch(
        ROOT / "Movie File Manager/Guided Pair Match.html",
        "    function skipAnchor() {\n"
        "      if (busy) return;\n"
        "      const anchor = currentAnchor();\n"
        "      if (!anchor) return;\n",
        "    function skipAnchor() {\n"
        "      return withBusy(async () => {\n"
        "      const anchor = currentAnchor();\n"
        "      if (!anchor) return;\n",
        "guided skip withBusy open",
    )
    patch(
        ROOT / "Movie File Manager/Guided Pair Match.html",
        "      loadCandidatesForAnchor().then(() => {\n"
        "        if (historyCursor >= 0 && history[historyCursor]?.type === 'skip') {\n"
        "          history[historyCursor].after = snapshotCore();\n"
        "        }\n"
        "      }).catch(e => toast(e.message || String(e), 'warn'));\n"
        "    }",
        "      try {\n"
        "        await loadCandidatesForAnchor();\n"
        "        if (historyCursor >= 0 && history[historyCursor]?.type === 'skip') {\n"
        "          history[historyCursor].after = snapshotCore();\n"
        "        }\n"
        "      } catch (e) { toast(e.message || String(e), 'warn'); }\n"
        "      });\n"
        "    }",
        "guided skip withBusy close",
    )

    # ------------------------------------------------------------------
    # Library remaining XSS + in-place select
    # ------------------------------------------------------------------
    lib = ROOT / "Movie File Manager/Media Library Manager.html"
    patch(
        lib,
        "                    div.innerHTML = `<span style=\"overflow:hidden;text-overflow:ellipsis;\"><span style=\"color:#ffb347\">${code || 'pair'}</span> ${p.before_name || '?'} ↔ ${p.after_name || '?'}</span>`;",
        "                    div.innerHTML = `<span style=\"overflow:hidden;text-overflow:ellipsis;\"><span style=\"color:#ffb347\">${escHtml(code || 'pair')}</span> ${escHtml(p.before_name || '?')} ↔ ${escHtml(p.after_name || '?')}</span>`;",
        "library pair list XSS",
    )
    # smart-chip title uses HTML entity; build needle at runtime
    tlib = lib.read_text(encoding="utf-8")
    qent = "&" + "quot;"
    old_chip = (
        '                    return `<button type="button" class="smart-chip ${activeSmartId === s.id ? \'active\' : \'\'}"'
        ' data-ss="${s.id}" title="${tip.replace(/"/g, \'' + qent + '\')}">${s.name}</button>`;'
    )
    new_chip = (
        '                    return `<button type="button" class="smart-chip ${activeSmartId === s.id ? \'active\' : \'\'}"'
        ' data-ss="${escHtml(s.id)}" title="${escHtml(tip)}">${escHtml(s.name)}</button>`;'
    )
    if old_chip in tlib:
        lib.write_text(tlib.replace(old_chip, new_chip, 1), encoding="utf-8")
        print("ok library smart chip XSS")
    elif new_chip in tlib:
        print("skip (already) library smart chip XSS")
    else:
        print("MISS library smart chip XSS")
        idx = tlib.find("smart-chip")
        print(" nearby:", repr(tlib[idx:idx+220] if idx >= 0 else "no smart-chip"))

    patch(
        lib,
        "                    hdr.innerHTML = `<span>${label}</span><span class=\"group-count\">${items.length} files</span>`;",
        "                    hdr.innerHTML = `<span>${escHtml(label)}</span><span class=\"group-count\">${items.length} files</span>`;",
        "library group header XSS",
    )
    patch(
        lib,
        "                    <h4><span>${group.items[0]?.name || 'Group'} · ${group.count} copies</span>",
        "                    <h4><span>${escHtml(group.items[0]?.name || 'Group')} · ${group.count} copies</span>",
        "library dup group XSS",
    )
    patch(
        lib,
        "                        <div><div>${escHtml(item.name)}</div><div class=\"dup-path\">${item.path}</div></div>",
        "                        <div><div>${escHtml(item.name)}</div><div class=\"dup-path\">${escHtml(item.path)}</div></div>",
        "library dup path XSS",
    )
    patch(
        lib,
        "                        badge.innerHTML = `★ Locked pair <strong>${code}</strong> — shared tags can apply to both sides`;",
        "                        badge.innerHTML = `★ Locked pair <strong>${escHtml(code)}</strong> — shared tags can apply to both sides`;",
        "library pair code XSS",
    )
    patch(
        lib,
        "                    return `<div data-pair=\"${p.id}\">${code ? `<span style=\"color:#ffb347\">${code}</span> · ` : ''}${p.name}</div>`;",
        "                    return `<div data-pair=\"${escHtml(p.id)}\">${code ? `<span style=\"color:#ffb347\">${escHtml(code)}</span> · ` : ''}${escHtml(p.name)}</div>`;",
        "library mini pairs XSS",
    )
    patch(
        lib,
        "                btn.innerHTML = `${p.name || ('Preset ' + (i + 1))}<small>${preview}</small>`;",
        "                btn.innerHTML = `${escHtml(p.name || ('Preset ' + (i + 1)))}<small>${escHtml(preview)}</small>`;",
        "library preset XSS",
    )
    patch(
        lib,
        "                    els.tagSuggestions.innerHTML = `<div class=\"hint\">Press Enter to create “${q}”</div>`;",
        "                    els.tagSuggestions.innerHTML = `<div class=\"hint\">Press Enter to create “${escHtml(q)}”</div>`;",
        "library tag create XSS",
    )
    patch(
        lib,
        "                    els.tagSuggestions.innerHTML = top.map((t, i) =>\n"
        "                        `<div data-tag=\"${t}\" class=\"${i === mlTagSuggestIdx ? 'active' : ''}\">${t}</div>`\n"
        "                    ).join('');",
        "                    els.tagSuggestions.innerHTML = top.map((t, i) =>\n"
        "                        `<div data-tag=\"${escHtml(t)}\" class=\"${i === mlTagSuggestIdx ? 'active' : ''}\">${escHtml(t)}</div>`\n"
        "                    ).join('');",
        "library tag top XSS",
    )
    patch(
        lib,
        "            els.tagSuggestions.innerHTML = matches.map((t, i) =>\n"
        "                `<div data-tag=\"${t}\" class=\"${i === mlTagSuggestIdx ? 'active' : ''}\">${t}</div>`\n"
        "            ).join('');",
        "            els.tagSuggestions.innerHTML = matches.map((t, i) =>\n"
        "                `<div data-tag=\"${escHtml(t)}\" class=\"${i === mlTagSuggestIdx ? 'active' : ''}\">${escHtml(t)}</div>`\n"
        "            ).join('');",
        "library tag match XSS",
    )
    patch(
        lib,
        "            const row = (p, extra = '') =>\n"
        "                `<div><strong>${p.pair_code || p.id || ''}</strong> ${p.before_name || '?'} ↔ ${p.after_name || '?'} ${extra}\n"
        "                ${p.id ? `<button class=\"btn btn-sm\" data-open=\"${p.id}\">Compare</button>` : ''}\n"
        "                ${p.id ? `<button class=\"btn btn-sm orange\" data-arch=\"${p.id}\">Archive…</button>` : ''}</div>`;",
        "            const row = (p, extra = '') =>\n"
        "                `<div><strong>${escHtml(p.pair_code || p.id || '')}</strong> ${escHtml(p.before_name || '?')} ↔ ${escHtml(p.after_name || '?')} ${extra}\n"
        "                ${p.id ? `<button class=\"btn btn-sm\" data-open=\"${escHtml(p.id)}\">Compare</button>` : ''}\n"
        "                ${p.id ? `<button class=\"btn btn-sm orange\" data-arch=\"${escHtml(p.id)}\">Archive…</button>` : ''}</div>`;",
        "library health row XSS",
    )
    patch(
        lib,
        "                ...(data.orphan_tagged || []).map(o => `<div>Orphan <code>${o.pair_code}</code> · ${o.name} (${o.role || '?'})</div>`),\n"
        "                ...(data.unpaired_upscale_named || []).slice(0, 40).map(o => `<div>Unpaired upscale name · ${o.name}</div>`),",
        "                ...(data.orphan_tagged || []).map(o => `<div>Orphan <code>${escHtml(o.pair_code)}</code> · ${escHtml(o.name)} (${escHtml(o.role || '?')})</div>`),\n"
        "                ...(data.unpaired_upscale_named || []).slice(0, 40).map(o => `<div>Unpaired upscale name · ${escHtml(o.name)}</div>`),",
        "library health orphan XSS",
    )
    patch(
        lib,
        "            el('verifyList').innerHTML = (r.mismatches || []).slice(0, 80).map(m =>\n"
        "                `<div><strong>${m.name}</strong><br>cat: ${(m.catalog_tags||[]).join(', ')||'—'} ★${m.catalog_rank}<br>disk: ${(m.disk_tags||[]).join(', ')||'—'} ★${m.disk_rank}${m.has_sidecar ? ' · sidecar' : ''}</div>`\n"
        "            ).join('') || '<div class=\"hint-box\">No mismatches in sample</div>';",
        "            el('verifyList').innerHTML = (r.mismatches || []).slice(0, 80).map(m =>\n"
        "                `<div><strong>${escHtml(m.name)}</strong><br>cat: ${escHtml((m.catalog_tags||[]).join(', ')||'—')} ★${escHtml(m.catalog_rank)}<br>disk: ${escHtml((m.disk_tags||[]).join(', ')||'—')} ★${escHtml(m.disk_rank)}${m.has_sidecar ? ' · sidecar' : ''}</div>`\n"
        "            ).join('') || '<div class=\"hint-box\">No mismatches in sample</div>';",
        "library verify mismatch XSS",
    )
    patch(
        lib,
        "        function toggleSelect(id) {\n"
        "            if (selected.has(id)) selected.delete(id);\n"
        "            else selected.add(id);\n"
        "            DBG()?.log('library', 'event', `Select toggle ${id} (${selected.size} selected)`);\n"
        "            renderPage();\n"
        "        }",
        "        function toggleSelect(id) {\n"
        "            if (selected.has(id)) selected.delete(id);\n"
        "            else selected.add(id);\n"
        "            DBG()?.log('library', 'event', `Select toggle ${id} (${selected.size} selected)`);\n"
        "            const root = els.mediaList;\n"
        "            const safe = (typeof CSS !== 'undefined' && CSS.escape) ? CSS.escape(String(id)) : String(id).replace(/\\\\/g, '\\\\\\\\').replace(/\"/g, '');\n"
        "            const node = root && root.querySelector('[data-id=\"' + safe + '\"]');\n"
        "            if (node) {\n"
        "                node.classList.toggle('selected', selected.has(id));\n"
        "                const cb = node.querySelector('input[type=\"checkbox\"]');\n"
        "                if (cb) cb.checked = selected.has(id);\n"
        "                const selOrder = [...selected];\n"
        "                root.querySelectorAll('.media-row, .grid-tile').forEach(row => {\n"
        "                    row.classList.toggle('select-1', row.dataset.id === selOrder[0]);\n"
        "                    row.classList.toggle('select-2', row.dataset.id === selOrder[1]);\n"
        "                });\n"
        "                updateBatchBar();\n"
        "            } else {\n"
        "                renderPage();\n"
        "            }\n"
        "        }",
        "library toggleSelect in-place",
    )

    # ------------------------------------------------------------------
    # Companion — probe-less poll, preview error, applyStage try/catch
    # ------------------------------------------------------------------
    patch(
        ROOT / "Movie File Manager/Mismatched Source Companion.html",
        "            const on = await API().isOnline();",
        "            const on = await API().isOnline(false, 1500);",
        "companion isOnline probe-less",
    )
    patch(
        ROOT / "Movie File Manager/Mismatched Source Companion.html",
        "        function renderPreview(data) {\n"
        "            data = data || {};\n"
        "            lastPreview = data;\n",
        "        function renderPreview(data) {\n"
        "            data = data || {};\n"
        "            if (data.error) {\n"
        "                lastPreview = null;\n"
        "                const stErr = el('previewStatus');\n"
        "                if (stErr) {\n"
        "                    stErr.className = 'status-box warn';\n"
        "                    stErr.textContent = String(data.error);\n"
        "                }\n"
        "                toast(String(data.error), 'warn');\n"
        "                return;\n"
        "            }\n"
        "            lastPreview = data;\n",
        "companion preview data.error",
    )
    patch(
        ROOT / "Movie File Manager/Mismatched Source Companion.html",
            "            const r = await API()?.vsrApply?.(stage, false) || {};\n"
            "            toast(\n"
            "                result.skipped ? `✓ ${r.count||0} renamed (trusted — no prompt)` : `✓ ${r.count||0} files renamed`,\n"
            "                result.skipped ? 'warn' : 'ok'\n"
            "            );",
            "            let r = {};\n"
            "            try {\n"
            "                r = await API()?.vsrApply?.(stage, false) || {};\n"
            "            } catch (e) {\n"
            "                toast('Apply failed: ' + (e.message || e), 'warn');\n"
            "                return;\n"
            "            }\n"
            "            if (r.error) { toast(String(r.error), 'warn'); return; }\n"
            "            toast(\n"
            "                result.skipped ? `✓ ${r.count||0} renamed (trusted — no prompt)` : `✓ ${r.count||0} files renamed`,\n"
            "                result.skipped ? 'warn' : 'ok'\n"
            "            );",
        "companion applyStage try/catch",
    )

    # ------------------------------------------------------------------
    # Compare Hub + Media Hub — cross-origin timeout is a fail, not loaded
    # ------------------------------------------------------------------
    for rel, label in (
        ("Movie File Manager/Compare Hub.html", "compare hub iframe timeout"),
        ("Movie File Manager/Media Hub.html", "media hub iframe timeout"),
    ):
        patch(
            ROOT / rel,
            "          } catch (_) {\n"
            "            if (frame.getAttribute('src')) {\n"
            "              if (loading) loading.classList.add('hide');\n"
            "              return;\n"
            "            }\n"
            "          }",
            "          } catch (_) {\n"
            "            // Cross-origin: onload already hid the overlay if it succeeded.\n"
            "            // Reaching the timeout without onload is a real fail.\n"
            "            showLoadFail(t.title, src);\n"
            "            return;\n"
            "          }",
            label,
        )

    # ------------------------------------------------------------------
    # File Organizer — in-place select (no full table rebuild)
    # ------------------------------------------------------------------
    patch(
        ROOT / "Movie File Manager/File Organizer.html",
        "                const tr = document.createElement('tr');\n"
        "                tr.tabIndex = 0;\n"
        "                tr.className = (selected.has(item.id) ? 'selected ' : '') + (current?.id === item.id ? 'active-row' : '');",
        "                const tr = document.createElement('tr');\n"
        "                tr.tabIndex = 0;\n"
        "                tr.dataset.id = item.id;\n"
        "                tr.className = (selected.has(item.id) ? 'selected ' : '') + (current?.id === item.id ? 'active-row' : '');",
        "organizer row data-id",
    )
    patch(
        ROOT / "Movie File Manager/File Organizer.html",
        "        function toggleSel(id) {\n"
        "            if (selected.has(id)) selected.delete(id); else selected.add(id);\n"
        "            renderTable();\n"
        "        }",
        "        function toggleSel(id) {\n"
        "            if (selected.has(id)) selected.delete(id); else selected.add(id);\n"
        "            const body = el('fileTableBody');\n"
        "            const safe = (typeof CSS !== 'undefined' && CSS.escape) ? CSS.escape(String(id)) : String(id).replace(/\"/g, '');\n"
        "            const tr = body && body.querySelector('tr[data-id=\"' + safe + '\"]');\n"
        "            if (tr) {\n"
        "                tr.classList.toggle('selected', selected.has(id));\n"
        "                const cb = tr.querySelector('input[type=\"checkbox\"]');\n"
        "                if (cb) cb.checked = selected.has(id);\n"
        "            } else {\n"
        "                renderTable();\n"
        "            }\n"
        "        }",
        "organizer toggleSel in-place",
    )

    # ------------------------------------------------------------------
    # Batch convert — auto-continue remaining files after GET URL cap
    # ------------------------------------------------------------------
    patch(
        ROOT / "System Tools/Batch Media Converter.html",
        "function stopConvert() {\n"
        "  if (es) { try { es.close(); } catch (_) {} es = null; }\n",
        "let convertStopped = false;\n"
        "function stopConvert() {\n"
        "  convertStopped = true;\n"
        "  if (es) { try { es.close(); } catch (_) {} es = null; }\n",
        "batch convertStopped flag",
    )
    patch(
        ROOT / "System Tools/Batch Media Converter.html",
        "    let batch = chosen.slice();\n"
        "    let url = apiBase() + '/convert/stream?files=' + encodeURIComponent(batch.join('|')) + '&preset=' + encodeURIComponent(preset);\n"
        "    if (outDir) url += '&output_dir=' + encodeURIComponent(outDir);\n"
        "    while (url.length > 1800 && batch.length > 1) {\n"
        "      batch = batch.slice(0, Math.max(1, Math.floor(batch.length / 2)));\n"
        "      url = apiBase() + '/convert/stream?files=' + encodeURIComponent(batch.join('|')) + '&preset=' + encodeURIComponent(preset);\n"
        "      if (outDir) url += '&output_dir=' + encodeURIComponent(outDir);\n"
        "    }\n"
        "    if (batch.length < chosen.length) {\n"
        "      log('URL limit — converting first ' + batch.length + ' of ' + chosen.length + ' this pass. Run again for the rest.');\n"
        "    }\n"
        "    if (es) try { es.close(); } catch (_) {}\n"
        "    es = new EventSource(url);\n"
        "    await new Promise(resolve => {\n"
        "      convertWaitResolve = resolve;\n"
        "      const finish = () => { try { stopConvert(); } catch (_) {} };\n",
        "    convertStopped = false;\n"
        "    let remaining = chosen.slice();\n"
        "    let pass = 0;\n"
        "    let okSum = 0, failSum = 0;\n"
        "    while (remaining.length && !convertStopped) {\n"
        "    pass += 1;\n"
        "    let batch = remaining.slice();\n"
        "    let url = apiBase() + '/convert/stream?files=' + encodeURIComponent(batch.join('|')) + '&preset=' + encodeURIComponent(preset);\n"
        "    if (outDir) url += '&output_dir=' + encodeURIComponent(outDir);\n"
        "    while (url.length > 1800 && batch.length > 1) {\n"
        "      batch = batch.slice(0, Math.max(1, Math.floor(batch.length / 2)));\n"
        "      url = apiBase() + '/convert/stream?files=' + encodeURIComponent(batch.join('|')) + '&preset=' + encodeURIComponent(preset);\n"
        "      if (outDir) url += '&output_dir=' + encodeURIComponent(outDir);\n"
        "    }\n"
        "    remaining = remaining.slice(batch.length);\n"
        "    if (remaining.length) log('Pass ' + pass + ' — ' + batch.length + ' files (URL cap). ' + remaining.length + ' queued next.');\n"
        "    if (es) try { es.close(); } catch (_) {}\n"
        "    es = new EventSource(url);\n"
        "    await new Promise(resolve => {\n"
        "      convertWaitResolve = resolve;\n"
        "      const finish = () => { try { if (es) { es.close(); es = null; } } catch (_) {} try { resolve(); } catch (_) {} convertWaitResolve = null; };\n",
        "batch convert loop open",
    )
    patch(
        ROOT / "System Tools/Batch Media Converter.html",
        "          log('Done: ' + (r.succeeded || 0) + '/' + (r.total || chosen.length) + ' succeeded'\n"
        "            + (r.failed ? ' · ' + r.failed + ' failed' : '') + ' · ' + elapsed + 's');",
        "          okSum += Number(r.succeeded) || 0;\n"
        "          failSum += Number(r.failed) || 0;\n"
        "          log('Pass ' + pass + ' done: ' + (r.succeeded || 0) + '/' + (r.total || batch.length) + ' succeeded'\n"
        "            + (r.failed ? ' · ' + r.failed + ' failed' : '') + ' · ' + elapsed + 's'\n"
        "            + (remaining.length ? ' · ' + remaining.length + ' left' : ''));",
        "batch convert pass log",
    )
    patch(
        ROOT / "System Tools/Batch Media Converter.html",
        "      es.onerror = () => {\n"
        "        log('Convert stream failed — is the server online and ffmpeg installed?');\n"
        "        finish();\n"
        "      };\n"
        "    });\n"
        "  }, 'btnConvert');\n"
        "}",
        "      es.onerror = () => {\n"
        "        log('Convert stream failed — is the server online and ffmpeg installed?');\n"
        "        convertStopped = true;\n"
        "        finish();\n"
        "      };\n"
        "    });\n"
        "    } // while remaining\n"
        "    if (!convertStopped && (okSum || failSum)) {\n"
        "      log('All passes: ' + okSum + ' succeeded' + (failSum ? ' · ' + failSum + ' failed' : '') + ' of ' + chosen.length);\n"
        "    }\n"
        "    try { stopConvert(); } catch (_) {}\n"
        "  }, 'btnConvert');\n"
        "}",
        "batch convert loop close",
    )

    # ------------------------------------------------------------------
    # VID TRIM — abortable browser encode + clamp max side
    # ------------------------------------------------------------------
    patch(
        ROOT / "Video Tools/FAFO_VID_TRIM.html",
        "  async function exportBrowser(fileOverride, opts = {}) {\n",
        "  let browserExportAbort = false;\n"
        "  async function exportBrowser(fileOverride, opts = {}) {\n"
        "    browserExportAbort = false;\n",
        "vid trim abort flag",
    )
    patch(
        ROOT / "Video Tools/FAFO_VID_TRIM.html",
        "    const maxSide = parseInt(maxSideEl.value, 10) || 3840;\n"
        "    const wantMp4 = currentFmt() === 'mp4';\n"
        "    const mime = pickRecorderMime(wantMp4);",
        "    const maxSide = Math.min(1920, parseInt(maxSideEl.value, 10) || 1920);\n"
        "    const wantMp4 = currentFmt() === 'mp4';\n"
        "    const mime = pickRecorderMime(wantMp4);",
        "vid trim browser maxSide 1920",
    )
    patch(
        ROOT / "Video Tools/FAFO_VID_TRIM.html",
        "      const draw = () => {\n"
        "        try { ctx.drawImage(v, 0, 0, t.w, t.h); } catch (_) { /* frame skip */ }\n",
        "      const draw = () => {\n"
        "        if (browserExportAbort) { try { v.pause(); } catch (_) {} resolve(); return; }\n"
        "        try { ctx.drawImage(v, 0, 0, t.w, t.h); } catch (_) { /* frame skip */ }\n",
        "vid trim draw abort",
    )
    patch(
        ROOT / "Video Tools/FAFO_VID_TRIM.html",
        "    const blob = new Blob(chunks, { type: mime.split(';')[0] || 'video/webm' });\n"
        "    if (!blob.size) throw new Error('Export produced empty file');",
        "    if (browserExportAbort) throw new Error('Export cancelled');\n"
        "    const blob = new Blob(chunks, { type: mime.split(';')[0] || 'video/webm' });\n"
        "    if (!blob.size) throw new Error('Export produced empty file');",
        "vid trim abort throw",
    )
    patch(
        ROOT / "Video Tools/FAFO_VID_TRIM.html",
        "  btnQStop?.addEventListener('click', () => {\n"
        "    if (!queueRunning) return;\n"
        "    queueStopAfter = true;\n"
        "    toast('Pausing after the current job — remaining stay queued', 'ok');\n"
        "    renderQueue();\n"
        "  });",
        "  btnQStop?.addEventListener('click', () => {\n"
        "    if (!queueRunning) return;\n"
        "    queueStopAfter = true;\n"
        "    browserExportAbort = true;\n"
        "    toast('Stopping current encode — remaining stay queued', 'ok');\n"
        "    renderQueue();\n"
        "  });\n"
        "  window.addEventListener('pagehide', () => { browserExportAbort = true; });",
        "vid trim stop aborts encode",
    )

    print("done")


if __name__ == "__main__":
    main()
