/**
 * IndexedDB scan cache — large duplicate/library results survive tab switches
 * and the 1.5MB localStorage cap that used to drop groups.
 *
 * window.AIToolboxScanCache.put / get / del / meta
 */
(function (global) {
    'use strict';

    const DB_NAME = 'fafo-scan-cache';
    const DB_VER = 1;
    const STORE = 'scans';

    function openDB() {
        return new Promise(function (resolve, reject) {
            if (!global.indexedDB) {
                reject(new Error('IndexedDB unavailable'));
                return;
            }
            const req = indexedDB.open(DB_NAME, DB_VER);
            req.onupgradeneeded = function () {
                const db = req.result;
                if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE);
            };
            req.onsuccess = function () { resolve(req.result); };
            req.onerror = function () { reject(req.error || new Error('IDB open failed')); };
        });
    }

    function txDone(tx, req) {
        return new Promise(function (resolve, reject) {
            if (req) {
                req.onsuccess = function () { resolve(req.result); };
                req.onerror = function () { reject(req.error); };
            }
            tx.oncomplete = function () { if (!req) resolve(true); };
            tx.onerror = function () { reject(tx.error); };
            tx.onabort = function () { reject(tx.error || new Error('IDB aborted')); };
        });
    }

    async function put(key, value) {
        const db = await openDB();
        const tx = db.transaction(STORE, 'readwrite');
        tx.objectStore(STORE).put(value, String(key));
        await txDone(tx);
        return true;
    }

    async function get(key) {
        const db = await openDB();
        const tx = db.transaction(STORE, 'readonly');
        const req = tx.objectStore(STORE).get(String(key));
        const val = await new Promise(function (resolve, reject) {
            req.onsuccess = function () { resolve(req.result); };
            req.onerror = function () { reject(req.error); };
        });
        return val == null ? null : val;
    }

    async function del(key) {
        const db = await openDB();
        const tx = db.transaction(STORE, 'readwrite');
        tx.objectStore(STORE).delete(String(key));
        await txDone(tx);
        return true;
    }

    function stampMs(v) {
        const n = Number(v || 0);
        if (!n) return 0;
        return n < 1e12 ? n * 1000 : n;
    }

    function relativeTime(v) {
        const ms = stampMs(v);
        if (!ms) return 'never';
        const d = Date.now() - ms;
        if (d < 45000) return 'just now';
        if (d < 3600000) return Math.round(d / 60000) + ' min ago';
        if (d < 86400000) return Math.round(d / 3600000) + ' h ago';
        if (d < 86400000 * 14) return Math.round(d / 86400000) + ' d ago';
        try { return new Date(ms).toLocaleDateString(); } catch (_) { return 'earlier'; }
    }

    function pointer(payload, extra) {
        const p = payload || {};
        const r = p.result || {};
        return Object.assign({
            v: 2,
            idb: true,
            savedAt: p.savedAt || Date.now(),
            folder: p.folder || r.folder || '',
            summaryOnly: false,
            scanned: r.scanned,
            duplicate_groups: r.duplicate_groups || (r.groups || []).length,
            wasted_bytes: r.wasted_bytes,
        }, extra || {});
    }

    global.AIToolboxScanCache = {
        put: put,
        get: get,
        del: del,
        stampMs: stampMs,
        relativeTime: relativeTime,
        pointer: pointer,
        openDB: openDB,
    };
})(typeof window !== 'undefined' ? window : globalThis);
