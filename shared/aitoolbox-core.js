/**
 * AIToolbox Core — shared IndexedDB catalog for media, tags, pairs, thumbnails.
 * Used by Media Library Manager and comparator tools (Chrome/Edge recommended).
 */
(function (global) {
    'use strict';

    const DB_NAME = 'AIToolboxMedia';
    // v2: create launcherIcons on DBs that were already at v1 (media library)
    // before tool-thumbnail assignment existed. Without this bump, put() throws
    // NotFoundError and Edit Icons silently fails.
    const DB_VER = 2;

    const STORES = {
        dirs: 'directories',
        media: 'media',
        pairs: 'pairs',
        thumbs: 'thumbnails',
        history: 'renameHistory',
        settings: 'settings',
        launcher: 'launcherIcons'
    };

    let dbPromise = null;

    function openDB() {
        if (!dbPromise) {
            dbPromise = new Promise((resolve, reject) => {
                const req = indexedDB.open(DB_NAME, DB_VER);
                req.onupgradeneeded = e => {
                    const db = e.target.result;
                    if (!db.objectStoreNames.contains(STORES.dirs)) {
                        db.createObjectStore(STORES.dirs, { keyPath: 'id' });
                    }
                    if (!db.objectStoreNames.contains(STORES.media)) {
                        const ms = db.createObjectStore(STORES.media, { keyPath: 'id' });
                        ms.createIndex('dirId', 'dirId', { unique: false });
                        ms.createIndex('name', 'name', { unique: false });
                        ms.createIndex('type', 'type', { unique: false });
                    }
                    if (!db.objectStoreNames.contains(STORES.pairs)) {
                        db.createObjectStore(STORES.pairs, { keyPath: 'id' });
                    }
                    if (!db.objectStoreNames.contains(STORES.thumbs)) {
                        db.createObjectStore(STORES.thumbs, { keyPath: 'mediaId' });
                    }
                    if (!db.objectStoreNames.contains(STORES.history)) {
                        db.createObjectStore(STORES.history, { keyPath: 'id' });
                    }
                    if (!db.objectStoreNames.contains(STORES.settings)) {
                        db.createObjectStore(STORES.settings);
                    }
                    if (!db.objectStoreNames.contains(STORES.launcher)) {
                        db.createObjectStore(STORES.launcher, { keyPath: 'toolId' });
                    }
                };
                req.onsuccess = () => {
                    const db = req.result;
                    db.onversionchange = () => {
                        try { db.close(); } catch { /* ignore */ }
                        dbPromise = null;
                    };
                    db.onclose = () => { dbPromise = null; };
                    resolve(db);
                };
                req.onerror = () => {
                    dbPromise = null;
                    reject(req.error);
                };
                req.onblocked = () => {
                    // Another tab holds the old version open; still wait for success.
                };
            });
        }
        return dbPromise.then(
            (db) => db,
            (err) => {
                dbPromise = null;
                throw err;
            }
        );
    }

    async function txStore(store, mode = 'readonly') {
        const db = await openDB();
        return db.transaction(store, mode).objectStore(store);
    }

    async function get(store, key) {
        const os = await txStore(store);
        return new Promise((res, rej) => {
            const r = os.get(key);
            r.onsuccess = () => res(r.result);
            r.onerror = () => rej(r.error);
        });
    }

    async function put(store, value, key) {
        const db = await openDB();
        if (!db.objectStoreNames.contains(store)) {
            throw new Error('IndexedDB store missing: ' + store + ' (reload after toolbox update)');
        }
        return new Promise((res, rej) => {
            const tx = db.transaction(store, 'readwrite');
            const os = tx.objectStore(store);
            const req = (key !== undefined) ? os.put(value, key) : os.put(value);
            req.onerror = () => rej(req.error);
            tx.oncomplete = () => res();
            tx.onerror = () => rej(tx.error);
            tx.onabort = () => rej(tx.error || new Error('IndexedDB write aborted'));
        });
    }

    async function getAll(store) {
        const os = await txStore(store);
        return new Promise((res, rej) => {
            const r = os.getAll();
            r.onsuccess = () => res(r.result || []);
            r.onerror = () => rej(r.error);
        });
    }

    async function remove(store, key) {
        const db = await openDB();
        return new Promise((res, rej) => {
            const tx = db.transaction(store, 'readwrite');
            tx.objectStore(store).delete(key);
            tx.oncomplete = res;
            tx.onerror = () => rej(tx.error);
        });
    }

    async function ensurePermission(handle, mode = 'read') {
        if (!handle) return false;
        if (await handle.queryPermission({ mode }) === 'granted') return true;
        return (await handle.requestPermission({ mode })) === 'granted';
    }

    async function ensureRW(handle) {
        return ensurePermission(handle, 'readwrite');
    }

    function mediaId(dirId, relativePath) {
        return `${dirId}::${relativePath}`;
    }

    const VIDEO_EXT = new Set(['.mp4', '.mkv', '.webm', '.mov', '.avi', '.m4v', '.wmv', '.flv']);
    const IMAGE_EXT = new Set(['.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tiff', '.tif']);

    function extOf(name) {
        const i = name.lastIndexOf('.');
        return i >= 0 ? name.slice(i).toLowerCase() : '';
    }

    function fileType(name) {
        const ext = extOf(name);
        if (VIDEO_EXT.has(ext)) return 'video';
        if (IMAGE_EXT.has(ext)) return 'image';
        return null;
    }

    function baseName(name) {
        const ext = extOf(name);
        return ext ? name.slice(0, -ext.length) : name;
    }

    // --- Directories ---
    async function listDirectories() {
        return getAll(STORES.dirs);
    }

    async function addDirectory(handle) {
        if (!(await ensureRW(handle))) throw new Error('Directory permission denied');
        const entry = {
            id: `dir-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
            name: handle.name,
            handle,
            addedAt: Date.now(),
            lastScanned: 0
        };
        await put(STORES.dirs, entry);
        return entry;
    }

    async function removeDirectory(dirId) {
        const all = await getAllMedia();
        for (const m of all) {
            if (m.dirId === dirId) {
                await remove(STORES.media, m.id);
                await remove(STORES.thumbs, m.id).catch(() => {});
            }
        }
        await remove(STORES.dirs, dirId);
    }

    // --- Scanning ---
    async function scanDirectory(dirEntry, onProgress, recursive = true) {
        if (!(await ensureRW(dirEntry.handle))) throw new Error('Permission denied');
        const found = [];
        let count = 0;

        async function walk(handle, prefix = '') {
            for await (const entry of handle.values()) {
                const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
                if (entry.kind === 'file') {
                    const type = fileType(entry.name);
                    if (type) {
                        found.push({ handle: entry, name: entry.name, relativePath: rel, type });
                        count++;
                        if (onProgress) onProgress(count, rel);
                    }
                } else if (entry.kind === 'directory' && recursive) {
                    await walk(entry, rel);
                }
            }
        }

        await walk(dirEntry.handle);
        const now = Date.now();
        for (const f of found) {
            const id = mediaId(dirEntry.id, f.relativePath);
            const existing = await get(STORES.media, id);
            await put(STORES.media, {
                id,
                dirId: dirEntry.id,
                name: f.name,
                relativePath: f.relativePath,
                type: f.type,
                tags: existing?.tags || [],
                notes: existing?.notes || '',
                pairRole: existing?.pairRole || null,
                pairId: existing?.pairId || null,
                fileHandle: f.handle,
                indexedAt: now
            });
        }
        dirEntry.lastScanned = now;
        await put(STORES.dirs, dirEntry);
        return found.length;
    }

    // --- Media ---
    async function getAllMedia() {
        return getAll(STORES.media);
    }

    async function getMedia(id) {
        return get(STORES.media, id);
    }

    async function updateMedia(record) {
        await put(STORES.media, record);
        return record;
    }

    async function queryMedia({ search = '', tags = [], type = null, dirId = null, sort = 'name' } = {}) {
        let items = await getAllMedia();
        const q = search.trim().toLowerCase();
        if (q) {
            items = items.filter(m =>
                m.name.toLowerCase().includes(q) ||
                m.relativePath.toLowerCase().includes(q) ||
                (m.tags || []).some(t => t.toLowerCase().includes(q)) ||
                (m.notes || '').toLowerCase().includes(q)
            );
        }
        if (tags.length) {
            items = items.filter(m => tags.every(t => (m.tags || []).includes(t)));
        }
        if (type) items = items.filter(m => m.type === type);
        if (dirId) items = items.filter(m => m.dirId === dirId);

        const cmp = (a, b) => {
            if (sort === 'name') return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' });
            if (sort === 'path') return a.relativePath.localeCompare(b.relativePath);
            if (sort === 'type') return a.type.localeCompare(b.type) || a.name.localeCompare(b.name);
            if (sort === 'tags') return (a.tags?.length || 0) - (b.tags?.length || 0);
            return 0;
        };
        items.sort(cmp);
        return items;
    }

    async function getAllTags() {
        const items = await getAllMedia();
        const set = new Set();
        items.forEach(m => (m.tags || []).forEach(t => set.add(t)));
        return [...set].sort((a, b) => a.localeCompare(b));
    }

    // --- Rename on disk ---
    async function renameMedia(record, newName, addToHistory = true) {
        if (!(await ensureRW(record.fileHandle))) throw new Error('File permission denied');
        const ext = extOf(record.name);
        if (!newName.toLowerCase().endsWith(ext)) newName += ext;

        const dir = await get(STORES.dirs, record.dirId);
        if (!dir) throw new Error('Source directory missing from index');

        const newHandle = await record.fileHandle.move(dir.handle, newName);
        const newRel = record.relativePath.includes('/')
            ? record.relativePath.replace(/[^/]+$/, newName)
            : newName;
        const newId = mediaId(record.dirId, newRel);

        const thumb = await get(STORES.thumbs, record.id);
        if (thumb) {
            thumb.mediaId = newId;
            await put(STORES.thumbs, thumb);
            await remove(STORES.thumbs, record.id);
        }

        await remove(STORES.media, record.id);
        record.id = newId;
        record.name = newName;
        record.relativePath = newRel;
        record.fileHandle = newHandle;
        record.renamedAt = Date.now();
        await put(STORES.media, record);

        if (addToHistory) await pushRenameHistory(newName);
        return record;
    }

    async function applyBatchRename(records, pattern, onProgress) {
        const results = [];
        let n = 1;
        for (const rec of records) {
            const ext = extOf(rec.name);
            const orig = baseName(rec.name);
            const tagStr = (rec.tags || []).join('_');
            let newBase = pattern
                .replace(/\{orig\}/gi, orig)
                .replace(/\{name\}/gi, orig)
                .replace(/\{tags\}/gi, tagStr)
                .replace(/\{tag\}/gi, (rec.tags || [])[0] || '')
                .replace(/\{n\}/gi, String(n).padStart(3, '0'))
                .replace(/\{ext\}/gi, ext.slice(1));
            newBase = newBase.replace(/[<>:"/\\|?*]/g, '_').trim();
            if (!newBase) { n++; continue; }
            try {
                const updated = await renameMedia(rec, newBase + ext, false);
                results.push(updated);
                if (onProgress) onProgress(n, records.length, updated.name);
            } catch (e) {
                console.warn('Rename failed:', rec.name, e);
            }
            n++;
        }
        if (pattern) await pushRenameHistory(pattern);
        return results;
    }

    // --- Rename history (up-arrow recall) ---
    async function getRenameHistory() {
        const row = await get(STORES.history, 'patterns');
        return row?.patterns || [];
    }

    async function pushRenameHistory(pattern) {
        let patterns = await getRenameHistory();
        patterns = patterns.filter(p => p !== pattern);
        patterns.unshift(pattern);
        patterns = patterns.slice(0, 50);
        await put(STORES.history, { id: 'patterns', patterns });
    }

    // --- Tags batch ---
    async function batchAddTags(records, newTags) {
        const tags = newTags.map(t => t.trim()).filter(Boolean);
        for (const rec of records) {
            const merged = [...new Set([...(rec.tags || []), ...tags])];
            rec.tags = merged;
            await put(STORES.media, rec);
        }
    }

    async function batchRemoveTags(records, removeTags) {
        for (const rec of records) {
            rec.tags = (rec.tags || []).filter(t => !removeTags.includes(t));
            await put(STORES.media, rec);
        }
    }

    // --- Pairs ---
    async function listPairs() {
        const pairs = await getAll(STORES.pairs);
        return pairs.sort((a, b) => b.createdAt - a.createdAt);
    }

    async function savePair({
        name, beforeMediaId, afterMediaId, kind = 'video',
        beforeHandle, afterHandle, beforeName, afterName
    }) {
        let before = beforeMediaId ? await getMedia(beforeMediaId) : null;
        let after = afterMediaId ? await getMedia(afterMediaId) : null;

        if (!before && beforeHandle) {
            before = { name: beforeName || 'before', fileHandle: beforeHandle };
        }
        if (!after && afterHandle) {
            after = { name: afterName || 'after', fileHandle: afterHandle };
        }
        if (!before || !after) throw new Error('Media records or file handles required');

        const pair = {
            id: `pair-${Date.now()}`,
            name: name || `${before.name} ↔ ${after.name}`,
            kind,
            beforeMediaId: beforeMediaId || null,
            afterMediaId: afterMediaId || null,
            beforeName: before.name,
            afterName: after.name,
            beforeHandle: before.fileHandle,
            afterHandle: after.fileHandle,
            createdAt: Date.now()
        };
        await put(STORES.pairs, pair);

        if (beforeMediaId && before.id) {
            before.pairId = pair.id;
            before.pairRole = 'before';
            await put(STORES.media, before);
        }
        if (afterMediaId && after.id) {
            after.pairId = pair.id;
            after.pairRole = 'after';
            await put(STORES.media, after);
        }
        return pair;
    }

    async function getPair(id) {
        return get(STORES.pairs, id);
    }

    async function deletePair(id) {
        const pair = await getPair(id);
        if (pair) {
            for (const mid of [pair.beforeMediaId, pair.afterMediaId]) {
                const m = await getMedia(mid);
                if (m) {
                    m.pairId = null;
                    m.pairRole = null;
                    await put(STORES.media, m);
                }
            }
        }
        await remove(STORES.pairs, id);
    }

    async function resolvePairFiles(pair) {
        if (!(await ensurePermission(pair.beforeHandle)) || !(await ensurePermission(pair.afterHandle))) {
            throw new Error('Re-open pair to grant file permissions');
        }
        return {
            beforeFile: await pair.beforeHandle.getFile(),
            afterFile: await pair.afterHandle.getFile(),
            beforeHandle: pair.beforeHandle,
            afterHandle: pair.afterHandle
        };
    }

    // --- Thumbnails ---
    async function saveThumbnail(mediaId, blob, source = 'capture') {
        await put(STORES.thumbs, { mediaId, blob, source, savedAt: Date.now() });
    }

    async function getThumbnail(mediaId) {
        const row = await get(STORES.thumbs, mediaId);
        return row?.blob || null;
    }

    async function exportThumbnailToDisk(mediaRecord, blob, settings) {
        const dir = await get(STORES.dirs, mediaRecord.dirId);
        if (!dir || !(await ensureRW(dir.handle))) return false;
        const ext = settings?.thumbExt || '.thumb.jpg';
        const fname = baseName(mediaRecord.name) + ext;
        try {
            const fh = await dir.handle.getFileHandle(fname, { create: true });
            const w = await fh.createWritable();
            await w.write(blob);
            await w.close();
            return fname;
        } catch (e) {
            console.warn('Sidecar thumb export failed', e);
            return false;
        }
    }

    // --- Settings ---
    async function getSettings() {
        const row = await get(STORES.settings, 'global');
        return row || {
            thumbShortcut: 'KeyT',
            thumbExportSidecar: true,
            thumbExt: '.thumb.jpg',
            screenshotDir: null,
            comparatorVideo: '../Video Tools/Video Comparison Slider Tool.html',
            comparatorImage: '../Image tools/Image Comparitor With Slider.html'
        };
    }

    async function saveSettings(settings) {
        await put(STORES.settings, { ...settings, id: 'global' }, 'global');
    }

    // --- Launcher icons (personal IndexedDB + shared assets/tool-icons) ---
    let _sharedIconManifest = null;
    let _sharedIconManifestAt = 0;

    function toolboxRootFromCore() {
        try {
            const scripts = document.getElementsByTagName('script');
            for (let i = scripts.length - 1; i >= 0; i--) {
                const src = scripts[i].src || '';
                if (src.includes('aitoolbox-core.js')) {
                    return new URL('..', src).href.replace(/\/?$/, '/');
                }
            }
        } catch { /* ignore */ }
        try {
            return new URL('../', window.location.href).href;
        } catch {
            return '';
        }
    }

    function normalizeIconManifest(data) {
        if (!data || typeof data !== 'object') {
            return { ok: true, icons: {}, app: null };
        }
        // Already API-shaped?
        if (data.icons && typeof data.icons === 'object') {
            const first = Object.values(data.icons)[0];
            if (first && typeof first === 'object' && first.url) {
                return data;
            }
        }
        const icons = {};
        const raw = data.icons || {};
        for (const [tid, fname] of Object.entries(raw)) {
            if (!fname) continue;
            const file = typeof fname === 'string' ? fname : (fname.file || '');
            if (!file) continue;
            icons[tid] = {
                file,
                url: 'assets/tool-icons/' + file,
                exists: true
            };
        }
        let app = null;
        if (data.app) {
            const file = typeof data.app === 'string' ? data.app : (data.app.file || '');
            if (file) {
                app = { file, url: 'assets/tool-icons/' + file, exists: true };
            }
        }
        return {
            ok: true,
            version: data.version || 1,
            updatedAt: data.updatedAt || null,
            app,
            icons
        };
    }

    async function loadSharedIconManifest(force = false) {
        const now = Date.now();
        if (!force && _sharedIconManifest && now - _sharedIconManifestAt < 15000) {
            return _sharedIconManifest;
        }
        // 1) Prefer server (always fresh)
        try {
            if (global.AIToolboxAPI?.isOnline) {
                const online = await global.AIToolboxAPI.isOnline(false, 800);
                if (online) {
                    const base = (global.AIToolboxAPI.getApiBase && global.AIToolboxAPI.getApiBase())
                        || global.AITOOLBOX_API_BASE
                        || 'http://127.0.0.87:18765/api';
                    const r = await fetch(`${base}/icons/manifest`, {
                        signal: AbortSignal.timeout(2000)
                    });
                    if (r.ok) {
                        const data = await r.json();
                        _sharedIconManifest = normalizeIconManifest(data);
                        _sharedIconManifestAt = now;
                        return _sharedIconManifest;
                    }
                }
            }
        } catch { /* fall through */ }

        // 2) Script-injected manifest (works on file://)
        if (global.AITOOLBOX_ICON_MANIFEST) {
            _sharedIconManifest = normalizeIconManifest(global.AITOOLBOX_ICON_MANIFEST);
            _sharedIconManifestAt = now;
            return _sharedIconManifest;
        }

        // 3) Fetch JSON next to assets (may fail on file://)
        try {
            const root = toolboxRootFromCore();
            const url = new URL('assets/tool-icons/manifest.json', root).href + '?t=' + now;
            const r = await fetch(url, { cache: 'no-store' });
            if (r.ok) {
                const data = await r.json();
                _sharedIconManifest = normalizeIconManifest(data);
                _sharedIconManifestAt = now;
                return _sharedIconManifest;
            }
        } catch { /* ignore */ }

        _sharedIconManifest = { ok: true, icons: {}, app: null };
        _sharedIconManifestAt = now;
        return _sharedIconManifest;
    }

    function sharedIconUrl(toolId, manifest) {
        const m = manifest || _sharedIconManifest;
        if (!m) return null;
        const root = toolboxRootFromCore();
        const entry = toolId === 'app'
            ? (m.app || (m.icons && m.icons.app))
            : (m.icons && m.icons[toolId]);
        if (!entry || !entry.url) return null;
        try {
            const href = new URL(entry.url, root).href;
            const bust = encodeURIComponent(String(m.updatedAt || _sharedIconManifestAt || Date.now()));
            return href + (href.includes('?') ? '&' : '?') + 'v=' + bust;
        } catch {
            return entry.url;
        }
    }

    const ICON_MIME_BY_EXT = {
        png: 'image/png',
        jpg: 'image/jpeg',
        jpeg: 'image/jpeg',
        gif: 'image/gif',
        webp: 'image/webp',
        ico: 'image/x-icon',
        svg: 'image/svg+xml',
        bmp: 'image/bmp'
    };

    /**
     * Windows often reports .ico/.bmp as application/octet-stream (or empty).
     * Those data URLs cannot be shown in <img> or loaded by the cropper.
     */
    function normalizeImageDataUrl(dataUrl, filename) {
        if (!dataUrl || typeof dataUrl !== 'string') return dataUrl;
        const m = dataUrl.match(/^data:([^;,]+)?(;base64)?,/i);
        if (!m) return dataUrl;
        const mime = (m[1] || '').trim().toLowerCase();
        const usable = /^image\//.test(mime) && mime !== 'image/jpg';
        if (usable) {
            return dataUrl;
        }
        let ext = '';
        if (filename) {
            const i = String(filename).lastIndexOf('.');
            if (i >= 0) ext = String(filename).slice(i + 1).toLowerCase();
        }
        if (!ext) {
            if (/icon/i.test(mime)) ext = 'ico';
            else if (/bmp/i.test(mime)) ext = 'bmp';
            else if (/svg/i.test(mime)) ext = 'svg';
        }
        const next = ICON_MIME_BY_EXT[ext] || 'image/png';
        return dataUrl.replace(/^data:[^,]*,/, 'data:' + next + ';base64,');
    }

    async function getLauncherIcon(toolId) {
        // 1) Personal override (this browser)
        try {
            const row = await get(STORES.launcher, toolId);
            if (row?.dataUrl) {
                return { src: normalizeImageDataUrl(row.dataUrl, row.filename || toolId), source: 'personal', toolId };
            }
        } catch { /* store missing / IDB closed — fall through to shared */ }
        // 2) Shared repo icon
        const man = await loadSharedIconManifest(false);
        const url = sharedIconUrl(toolId, man);
        if (url) return { src: url, source: 'shared', toolId };
        return null;
    }

    async function setLauncherIcon(toolId, dataUrl, opts = {}) {
        if (dataUrl == null) {
            await remove(STORES.launcher, toolId).catch(async () => {
                const db = await openDB();
                await new Promise((resolve, reject) => {
                    if (!db.objectStoreNames.contains(STORES.launcher)) {
                        resolve();
                        return;
                    }
                    const tx = db.transaction(STORES.launcher, 'readwrite');
                    tx.objectStore(STORES.launcher).delete(toolId);
                    tx.oncomplete = () => resolve();
                    tx.onerror = () => reject(tx.error);
                });
            });
            return { personal: false, shared: null };
        }
        const normalized = normalizeImageDataUrl(dataUrl, opts.filename);
        let personal = false;
        let personalError = null;
        const row = {
            toolId,
            dataUrl: normalized,
            updatedAt: Date.now(),
            filename: opts.filename || null,
            mime: (String(normalized).match(/^data:([^;]+);/) || [])[1] || null
        };
        try {
            await put(STORES.launcher, row);
            personal = true;
        } catch (e) {
            personalError = e && (e.message || e.name) ? (e.message || e.name) : String(e);
            // One retry after dropping a stale connection (versionchange / close)
            try {
                dbPromise = null;
                await put(STORES.launcher, row);
                personal = true;
                personalError = null;
            } catch (e2) {
                personalError = e2 && (e2.message || e2.name) ? (e2.message || e2.name) : String(e2);
            }
        }

        let shared = null;
        if (opts.publish !== false) {
            try {
                if (global.AIToolboxAPI?.publishToolIcon) {
                    shared = await global.AIToolboxAPI.publishToolIcon(toolId, normalized, {
                        filename: opts.filename || null,
                        asAppIcon: !!opts.asAppIcon
                    });
                    await loadSharedIconManifest(true);
                }
            } catch (e) {
                shared = { ok: false, error: e.message || String(e) };
            }
        }
        return { personal, personalError, shared };
    }

    async function listPersonalLauncherIcons() {
        const rows = await getAll(STORES.launcher);
        return (rows || []).filter(r => r && r.toolId && r.dataUrl);
    }

    async function clearPersonalLauncherIcons(toolIds) {
        const ids = toolIds && toolIds.length
            ? toolIds
            : (await listPersonalLauncherIcons()).map(r => r.toolId);
        const db = await openDB();
        await new Promise((resolve, reject) => {
            const tx = db.transaction(STORES.launcher, 'readwrite');
            const store = tx.objectStore(STORES.launcher);
            ids.forEach(id => store.delete(id));
            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error);
        });
    }

    global.AIToolbox = {
        STORES,
        openDB,
        ensurePermission,
        ensureRW,
        mediaId,
        fileType,
        baseName,
        extOf,
        listDirectories,
        addDirectory,
        removeDirectory,
        scanDirectory,
        getAllMedia,
        getMedia,
        updateMedia,
        queryMedia,
        getAllTags,
        renameMedia,
        applyBatchRename,
        getRenameHistory,
        pushRenameHistory,
        batchAddTags,
        batchRemoveTags,
        listPairs,
        savePair,
        getPair,
        deletePair,
        resolvePairFiles,
        saveThumbnail,
        getThumbnail,
        exportThumbnailToDisk,
        getSettings,
        saveSettings,
        getLauncherIcon,
        setLauncherIcon,
        normalizeImageDataUrl,
        loadSharedIconManifest,
        sharedIconUrl,
        listPersonalLauncherIcons,
        clearPersonalLauncherIcons
    };
})(typeof window !== 'undefined' ? window : globalThis);