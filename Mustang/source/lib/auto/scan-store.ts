const DB = "fafo-auto-scan";
const STORE = "files";

function openDb() {
  return new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDB.open(DB, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function saveScanFile(name: string, data: ArrayBuffer) {
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).put({ name, data }, "body");
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  db.close();
}

export async function loadScanFile(): Promise<{ name: string; data: ArrayBuffer } | null> {
  const db = await openDb();
  const row = await new Promise<{ name: string; data: ArrayBuffer } | undefined>((resolve, reject) => {
    const tx = db.transaction(STORE, "readonly");
    const request = tx.objectStore(STORE).get("body");
    request.onsuccess = () => resolve(request.result as { name: string; data: ArrayBuffer } | undefined);
    request.onerror = () => reject(request.error);
  });
  db.close();
  return row?.data ? row : null;
}

export async function clearScanFile() {
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).delete("body");
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  db.close();
}
