#!/usr/bin/env python3
"""Media-desk 3.0 production pass — quieter polls, search races, XSS, video pause."""
from __future__ import annotations

from pathlib import Path

ROOT = Path("/tmp/fafo-toolbox")

MEDIA_HTML = [
    "Movie File Manager/Media Hub.html",
    "Movie File Manager/Compare Hub.html",
    "Movie File Manager/Guided Pair Match.html",
    "Movie File Manager/Media Library Manager.html",
    "Movie File Manager/File Organizer.html",
    "Movie File Manager/Mismatched Source Companion.html",
    "Movie File Manager/Pair Review Queue.html",
    "File Tools/Duplicate File Manager.html",
    "System Tools/ImagineTracker/Imagine Tracker.html",
    "Video Tools/Video Comparison Slider Tool.html",
    "Image tools/Image Comparitor With Slider.html",
    "Video Tools/GEMPlayHTML.html",
    "Video Tools/FAFO_VID_TRIM.html",
    "Image tools/image Converter_Cropper for chrome store resolution.html",
    "System Tools/Batch Media Converter.html",
]


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


def inject_media_js() -> None:
    needle = "aitoolbox-runtime.js?v=3.0.0"
    tag = '<script src="../shared/aitoolbox-media.js?v=3.0.0"></script>'
    tag_deep = '<script src="../../shared/aitoolbox-media.js?v=3.0.0"></script>'
    for rel in MEDIA_HTML:
        p = ROOT / rel
        t = p.read_text(encoding="utf-8")
        if "aitoolbox-media.js" in t:
            print("skip inject", rel)
            continue
        if needle not in t:
            print("MISS runtime tag", rel)
            continue
        depth = rel.count("/")
        ins = tag_deep if depth >= 2 else tag
        # Imagine Tracker lives two folders down
        if rel.startswith("System Tools/ImagineTracker"):
            ins = tag_deep
        # Keep indent of the runtime line
        t = t.replace(
            f'<script src="../shared/{needle}"></script>',
            f'<script src="../shared/{needle}"></script>\n    {ins}',
            1,
        )
        t = t.replace(
            f'<script src="../../shared/{needle}"></script>',
            f'<script src="../../shared/{needle}"></script>\n    {ins}',
            1,
        )
        # some files omit indent / use no quotes variation already handled
        if "aitoolbox-media.js" not in t:
            print("MISS inject still", rel)
            continue
        p.write_text(t, encoding="utf-8")
        print("ok inject", rel)


def main() -> None:
    inject_media_js()

    # --- hubs: 20s poll → watchServer ---
    patch(
        ROOT / "Movie File Manager/Media Hub.html",
        "      pingServer();\n      setInterval(pingServer, 20000);",
        "      if (window.AIToolboxMedia && AIToolboxMedia.watchServer) {\n"
        "        AIToolboxMedia.watchServer(pingServer, { onlineMs: 20000, offlineMs: 8000, iframeMs: 30000 });\n"
        "      } else {\n"
        "        pingServer();\n"
        "        setInterval(pingServer, 20000);\n"
        "      }",
        "media hub watchServer",
    )
    patch(
        ROOT / "Movie File Manager/Compare Hub.html",
        "      pingServer();\n      setInterval(pingServer, 20000);",
        "      if (window.AIToolboxMedia && AIToolboxMedia.watchServer) {\n"
        "        AIToolboxMedia.watchServer(pingServer, { onlineMs: 20000, offlineMs: 8000, iframeMs: 30000 });\n"
        "      } else {\n"
        "        pingServer();\n"
        "        setInterval(pingServer, 20000);\n"
        "      }",
        "compare hub watchServer",
    )

    # --- library health ---
    patch(
        ROOT / "Movie File Manager/Media Library Manager.html",
        "            await updateServerStatus();\n            setInterval(updateServerStatus, 5000);",
        "            if (window.AIToolboxMedia && AIToolboxMedia.watchServer) {\n"
        "                AIToolboxMedia.watchServer(updateServerStatus);\n"
        "            } else {\n"
        "                await updateServerStatus();\n"
        "                setInterval(updateServerStatus, 5000);\n"
        "            }",
        "library watchServer",
    )
    patch(
        ROOT / "Movie File Manager/Media Library Manager.html",
        "        async function applyFilters() {\n"
        "            updatePathHint();\n"
        "            const searching = els.searchInput.value.trim().length > 0;",
        "        let _filterGen = 0;\n"
        "        async function applyFilters() {\n"
        "            const gen = ++_filterGen;\n"
        "            updatePathHint();\n"
        "            const searching = els.searchInput.value.trim().length > 0;",
        "library filter gen",
    )
    patch(
        ROOT / "Movie File Manager/Media Library Manager.html",
        "                filtered = result.items || [];\n"
        "                totalCount = result.total || 0;\n"
        "                await refreshTags();\n"
        "                renderPage();\n"
        "                updateBatchBar();",
        "                if (gen !== _filterGen) return;\n"
        "                filtered = result.items || [];\n"
        "                totalCount = result.total || 0;\n"
        "                await refreshTags();\n"
        "                if (gen !== _filterGen) return;\n"
        "                renderPage();\n"
        "                updateBatchBar();",
        "library filter gen apply",
    )
    patch(
        ROOT / "Movie File Manager/Media Library Manager.html",
        "            el('verifyList').innerHTML = (r.fixed || []).slice(0, 40).map(m =>\n"
        "                `<div>Fixed <strong>${m.name}</strong></div>`\n"
        "            ).join('') || '<div class=\"hint-box\">Nothing fixed</div>';",
        "            el('verifyList').innerHTML = (r.fixed || []).slice(0, 40).map(m =>\n"
        "                `<div>Fixed <strong>${escHtml(m.name)}</strong></div>`\n"
        "            ).join('') || '<div class=\"hint-box\">Nothing fixed</div>';",
        "library verify XSS",
    )

    # --- organizer ---
    patch(
        ROOT / "Movie File Manager/File Organizer.html",
        "            await updateServer();\n            setInterval(updateServer, 5000);",
        "            if (window.AIToolboxMedia && AIToolboxMedia.watchServer) {\n"
        "                AIToolboxMedia.watchServer(updateServer);\n"
        "            } else {\n"
        "                await updateServer();\n"
        "                setInterval(updateServer, 5000);\n"
        "            }",
        "organizer watchServer",
    )
    patch(
        ROOT / "Movie File Manager/File Organizer.html",
        "        async function loadItems() {\n            try {\n                const res = await API()?.queryMedia?.({",
        "        let _loadGen = 0;\n"
        "        async function loadItems() {\n"
        "            const gen = ++_loadGen;\n"
        "            try {\n"
        "                const res = await API()?.queryMedia?.({",
        "organizer loadGen",
    )
    patch(
        ROOT / "Movie File Manager/File Organizer.html",
        "                items = Array.isArray(res.items) ? res.items : [];\n"
        "                total = Number(res.total) || 0;",
        "                if (gen !== _loadGen) return;\n"
        "                items = Array.isArray(res.items) ? res.items : [];\n"
        "                total = Number(res.total) || 0;",
        "organizer loadGen apply",
    )
    patch(
        ROOT / "Movie File Manager/File Organizer.html",
        "        bind('searchInput', 'input', () => { page = 0; saveOrgSettings(); loadItems(); });",
        "        bind('searchInput', 'input', (window.AIToolboxMedia && AIToolboxMedia.bindSearch)\n"
        "            ? AIToolboxMedia.bindSearch(() => { page = 0; saveOrgSettings(); loadItems(); }, 280)\n"
        "            : (() => { page = 0; saveOrgSettings(); loadItems(); }));",
        "organizer search debounce",
    )

    # --- companion ---
    patch(
        ROOT / "Movie File Manager/Mismatched Source Companion.html",
            "            updateVsrWorkflow();\n            setInterval(checkServer, 5000);",
            "            updateVsrWorkflow();\n"
            "            if (window.AIToolboxMedia && AIToolboxMedia.watchServer) {\n"
            "                AIToolboxMedia.watchServer(checkServer);\n"
            "            } else {\n"
            "                setInterval(checkServer, 5000);\n"
            "            }",
        "companion watchServer",
    )

    # --- duplicates ---
    patch(
        ROOT / "File Tools/Duplicate File Manager.html",
        "        pollServer();\n        setInterval(pollServer, 5000);",
        "        if (window.AIToolboxMedia && AIToolboxMedia.watchServer) {\n"
        "            AIToolboxMedia.watchServer(pollServer);\n"
        "        } else {\n"
        "            pollServer();\n"
        "            setInterval(pollServer, 5000);\n"
        "        }",
        "dup watchServer",
    )
    patch(
        ROOT / "File Tools/Duplicate File Manager.html",
        "            if (!(await tryScan())) {\n"
        "                const iv = setInterval(async () => {\n"
        "                    if (await tryScan()) clearInterval(iv);\n"
        "                }, 2000);\n"
        "                setTimeout(() => clearInterval(iv), 120000);\n"
        "            }",
        "            if (!(await tryScan())) {\n"
        "                const iv = setInterval(async () => {\n"
        "                    if (await tryScan()) clearInterval(iv);\n"
        "                }, 2000);\n"
        "                setTimeout(() => clearInterval(iv), 120000);\n"
        "                window.addEventListener('pagehide', () => clearInterval(iv), { once: true });\n"
        "            }",
        "dup autoscan pagehide",
    )

    # --- imagine vault ---
    patch(
        ROOT / "System Tools/ImagineTracker/Imagine Tracker.html",
        "      startVault();\n"
        "      setInterval(function () {\n"
        "        if (vaultOn) refresh();\n"
        "        else startVault();\n"
        "      }, 12000);",
        "      startVault();\n"
        "      const vaultTick = function () { if (vaultOn) refresh(); else startVault(); };\n"
        "      if (window.AIToolboxMedia && AIToolboxMedia.watchServer) {\n"
        "        AIToolboxMedia.watchServer(vaultTick, { onlineMs: 20000, offlineMs: 8000, iframeMs: 40000 });\n"
        "      } else {\n"
        "        setInterval(vaultTick, 12000);\n"
        "      }",
        "imagine watchServer",
    )

    # --- batch converter ---
    patch(
        ROOT / "System Tools/Batch Media Converter.html",
        "bind('filter', 'input', render);",
        "bind('filter', 'input', (window.AIToolboxMedia && AIToolboxMedia.bindSearch)\n"
        "  ? AIToolboxMedia.bindSearch(render, 160)\n"
        "  : render);",
        "batch filter debounce",
    )
    patch(
        ROOT / "System Tools/Batch Media Converter.html",
        "window.addEventListener('pagehide', revokeBlobs);",
        "window.addEventListener('pagehide', function () {\n"
        "  revokeBlobs();\n"
        "  try { stopConvert(); } catch (_) {}\n"
        "});",
        "batch pagehide stop",
    )

    # --- video comparator reverse rAF + probe-less health ---
    patch(
        ROOT / "Video Tools/Video Comparison Slider Tool.html",
        "                let last = performance.now();\n"
        "                reverseInterval = setInterval(() => {\n"
        "                    const dt = (performance.now() - last) / 1000;\n"
        "                    last = performance.now();\n"
        "                    let t = elAfter.currentTime - dt * parseFloat(document.getElementById('sel-speed').value);\n"
        "                    if (t <= 0) t = elAfter.duration;\n"
        "                    elAfter.currentTime = t;\n"
        "                    elBefore.currentTime = t;\n"
        "                    timeline.value = (t / elAfter.duration) * 100;\n"
        "                    formatTime();\n"
        "                }, 1000 / 60);",
        "                let last = performance.now();\n"
        "                const stepRev = () => {\n"
        "                    if (!reverseInterval) return;\n"
        "                    if (document.hidden) { reverseInterval = requestAnimationFrame(stepRev); return; }\n"
        "                    const dt = (performance.now() - last) / 1000;\n"
        "                    last = performance.now();\n"
        "                    let t = elAfter.currentTime - dt * parseFloat(document.getElementById('sel-speed').value);\n"
        "                    if (t <= 0) t = elAfter.duration;\n"
        "                    elAfter.currentTime = t;\n"
        "                    elBefore.currentTime = t;\n"
        "                    timeline.value = (t / elAfter.duration) * 100;\n"
        "                    formatTime();\n"
        "                    reverseInterval = requestAnimationFrame(stepRev);\n"
        "                };\n"
        "                reverseInterval = requestAnimationFrame(stepRev);",
        "video compare reverse rAF",
    )
    patch(
        ROOT / "Video Tools/Video Comparison Slider Tool.html",
        "            if (reverseInterval) {\n"
        "                clearInterval(reverseInterval);\n"
        "                reverseInterval = null;",
        "            if (reverseInterval) {\n"
        "                try { cancelAnimationFrame(reverseInterval); } catch (_) { try { clearInterval(reverseInterval); } catch (__) {} }\n"
        "                reverseInterval = null;",
        "video compare stop reverse",
    )
    patch(
        ROOT / "Video Tools/Video Comparison Slider Tool.html",
        "        timeline.addEventListener('input', () => {\n"
        "            if (!elAfter || !elBefore || !elAfter.duration) return;\n"
        "            isTimelineDragging = true;\n"
        "            stopReversePlay();\n"
        "            const t = (timeline.value / 100) * elAfter.duration;\n"
        "            elAfter.currentTime = t;\n"
        "            elBefore.currentTime = t;\n"
        "            formatTime();\n"
        "        });",
        "        const applyTimeline = (window.AIToolboxMedia && AIToolboxMedia.rafify)\n"
        "            ? AIToolboxMedia.rafify(() => {\n"
        "                if (!elAfter || !elBefore || !elAfter.duration) return;\n"
        "                const t = (timeline.value / 100) * elAfter.duration;\n"
        "                elAfter.currentTime = t;\n"
        "                elBefore.currentTime = t;\n"
        "                formatTime();\n"
        "            })\n"
        "            : (() => {\n"
        "                if (!elAfter || !elBefore || !elAfter.duration) return;\n"
        "                const t = (timeline.value / 100) * elAfter.duration;\n"
        "                elAfter.currentTime = t;\n"
        "                elBefore.currentTime = t;\n"
        "                formatTime();\n"
        "            });\n"
        "        timeline.addEventListener('input', () => {\n"
        "            if (!elAfter || !elBefore || !elAfter.duration) return;\n"
        "            isTimelineDragging = true;\n"
        "            stopReversePlay();\n"
        "            applyTimeline();\n"
        "        });",
        "video compare timeline rAF",
    )
    patch(
        ROOT / "Video Tools/Video Comparison Slider Tool.html",
        "        const on = window.AIToolboxAPI ? await AIToolboxAPI.isOnline(true) : false;",
        "        const on = window.AIToolboxAPI ? await AIToolboxAPI.isOnline(false, 1500) : false;",
        "video compare isOnline probe",
    )
    patch(
        ROOT / "Video Tools/Video Comparison Slider Tool.html",
        "      refresh(); setInterval(refresh, 8000);",
        "      if (window.AIToolboxMedia && AIToolboxMedia.watchServer) AIToolboxMedia.watchServer(refresh);\n"
        "      else { refresh(); setInterval(refresh, 20000); }",
        "video compare fallback poll",
    )

    patch(
        ROOT / "Image tools/Image Comparitor With Slider.html",
        "        const on = window.AIToolboxAPI ? await AIToolboxAPI.isOnline(true) : false;",
        "        const on = window.AIToolboxAPI ? await AIToolboxAPI.isOnline(false, 1500) : false;",
        "image compare isOnline probe",
    )
    patch(
        ROOT / "Image tools/Image Comparitor With Slider.html",
        "      refresh(); setInterval(refresh, 8000);",
        "      if (window.AIToolboxMedia && AIToolboxMedia.watchServer) AIToolboxMedia.watchServer(refresh);\n"
        "      else { refresh(); setInterval(refresh, 20000); }",
        "image compare fallback poll",
    )
    patch(
        ROOT / "Image tools/Image Comparitor With Slider.html",
        "        ['set-sharpen', 'set-contrast', 'set-saturate'].forEach(id => {\n"
        "            document.getElementById(id).addEventListener('input', applyImageFilters);\n"
        "        });",
        "        const applyFiltersLive = (window.AIToolboxMedia && AIToolboxMedia.rafify)\n"
        "            ? AIToolboxMedia.rafify(applyImageFilters)\n"
        "            : applyImageFilters;\n"
        "        ['set-sharpen', 'set-contrast', 'set-saturate'].forEach(id => {\n"
        "            document.getElementById(id).addEventListener('input', applyFiltersLive);\n"
        "        });",
        "image compare filter rAF",
    )

    # --- video wall cap ---
    patch(
        ROOT / "Video Tools/GEMPlayHTML.html",
        "        async function collectVideos(dirHandle, prefix = '', out = []) {\n"
        "            for await (const entry of dirHandle.values()) {\n"
        "                if (entry.kind === 'file') {",
        "        const WALL_FILE_CAP = 1500;\n"
        "        async function collectVideos(dirHandle, prefix = '', out = [], depth = 0) {\n"
        "            if (out.length >= WALL_FILE_CAP || depth > 12) return out;\n"
        "            for await (const entry of dirHandle.values()) {\n"
        "                if (out.length >= WALL_FILE_CAP) break;\n"
        "                if (entry.kind === 'file') {",
        "wall collect cap",
    )
    patch(
        ROOT / "Video Tools/GEMPlayHTML.html",
        "                    try {\n"
        "                        await collectVideos(entry, prefix ? prefix + '/' + entry.name : entry.name, out);\n"
        "                    } catch (_) { /* permission / locked */ }",
        "                    try {\n"
        "                        await collectVideos(entry, prefix ? prefix + '/' + entry.name : entry.name, out, depth + 1);\n"
        "                    } catch (_) { /* permission / locked */ }",
        "wall collect depth",
    )
    patch(
        ROOT / "Video Tools/GEMPlayHTML.html",
        "                videoEl.play().catch(() => { /* autoplay policy */ });",
        "                videoEl.dataset.fafoWantPlay = '1';\n"
        "                videoEl.play().catch(() => { /* autoplay policy */ });",
        "wall wantPlay",
    )

    # --- guided pair preload metadata ---
    patch(
        ROOT / "Movie File Manager/Guided Pair Match.html",
        ': `<video controls muted playsinline preload="auto" src="${esc(url)}" crossorigin="anonymous"></video>`;',
        ': `<video controls muted playsinline preload="metadata" src="${esc(url)}" crossorigin="anonymous"></video>`;',
        "guided preload metadata",
    )
    patch(
        ROOT / "Movie File Manager/Guided Pair Match.html",
        ': `<video controls muted playsinline preload="auto" src="${esc(url)}"></video>`;',
        ': `<video controls muted playsinline preload="metadata" src="${esc(url)}"></video>`;',
        "guided preload metadata retry",
    )

    print("done")


if __name__ == "__main__":
    main()
