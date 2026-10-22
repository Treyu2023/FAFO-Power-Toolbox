import { WIRES } from "./diagram";
import { flowById } from "./flows";
import { PARTS } from "./parts";
import type { Connector, ConnectorParts, ConnectorPin, FuseBox, FuseSlot, PinRole, Seeded, UserConnectorData } from "./types";

// Every seeded value is a verbatim quote from flows.ts. Anything else stays null and renders UNVERIFIED.
const FLOWS_FILE = "lib/mustang/flows.ts";
const FLOW_IDS = ["fuel-pump-power", "evap"];

function q(line: number, quote: string): Seeded<string> {
  return { value: quote, source: { file: FLOWS_FILE, line, quote } };
}
function nil<T>(): Seeded<T> {
  return { value: null, source: null };
}
function noParts(): ConnectorParts {
  return { shell: nil(), seal: nil(), lock: nil(), terminal: nil() };
}
function pin(key: string, role: PinRole, label: string, extra: Partial<ConnectorPin> = {}): ConnectorPin {
  return { key, cavity: nil(), role, label, color: nil(), circuit: nil(), expect: nil(), ...extra };
}

export function flowsFor(partId: string): string[] {
  return FLOW_IDS.filter((id) => flowById(id)?.steps.some((s) => s.partId === partId));
}

function seed(id: string, partId: string, name: string, pins: ConnectorPin[]): Connector {
  return { id, partId, name, cNumber: nil(), pinCount: nil(), pins, parts: noParts(), flows: flowsFor(partId), stub: false, origin: "seed" };
}

export const SEEDS: Connector[] = [
  seed("ccrm:fuel-pump", "ccrm", "CCRM fuel-pump relay", [
    pin("p1", "power", "Relay output", { color: q(86, "Dark green / yellow"), expect: q(94, "battery voltage for about one second"), to: "inertia-switch" }),
    pin("p2", "power", "Battery feed", { color: q(90, "Light blue / orange") }),
    pin("p3", "control", "Relay coil control"),
  ]),
  seed("inertia-switch:main", "inertia-switch", "Inertia switch connector", [
    pin("p1", "power", "In from the CCRM", { color: q(122, "Dark green / yellow"), to: "ccrm" }),
    pin("p2", "power", "Out to the tank", { to: "fuel-pump" }),
  ]),
  seed("fuel-pump:hat", "fuel-pump", "Pump and sender connector", [
    pin("p1", "power", "Pump power", { expect: q(151, "within about half a volt of the battery"), to: "inertia-switch" }),
    pin("p2", "ground", "Pump ground", { color: q(160, "Black") }),
  ]),
];

export function hasWiring(partId: string): boolean {
  return WIRES.some((w) => w.ends.includes(partId)) || Boolean(PARTS[partId]?.circuit);
}

function stub(partId: string): Connector {
  const pins: ConnectorPin[] = [];
  for (const w of WIRES) {
    const i = w.ends.indexOf(partId);
    if (i < 0) continue;
    const to = w.ends[i + 1] ?? w.ends[i - 1];
    const role: PinRole = w.circuit === "power" ? "power" : w.circuit === "ground" ? "ground" : "signal";
    pins.push(pin(`p${pins.length + 1}`, role, `${w.id} to ${PARTS[to]?.name ?? to}`, { to }));
  }
  return {
    id: `${partId}:main`,
    partId,
    name: `${PARTS[partId]?.name ?? partId} connector`,
    cNumber: nil(),
    pinCount: nil(),
    pins,
    parts: noParts(),
    flows: flowsFor(partId),
    stub: true,
    origin: "stub",
  };
}

export function baseConnectors(partId: string): Connector[] {
  const seeded = SEEDS.filter((c) => c.partId === partId);
  if (seeded.length) return seeded;
  return hasWiring(partId) ? [stub(partId)] : [];
}

export function connectorsFor(partId: string, user: UserConnectorData = loadUser()): Connector[] {
  return baseConnectors(partId).map((c) => mergeConnector(c, user.connectors[c.id]));
}

const BOXES: Record<string, FuseBox["id"]> = { pdb: "pdb", "fuse-panel": "fuse-panel", ccrm: "ccrm" };

export function isBox(partId: string | null): boolean {
  return Boolean(partId && BOXES[partId]);
}

export function fuseBoxBase(partId: string): FuseBox | null {
  const id = BOXES[partId];
  if (!id) return null;
  const linked: string[] = [];
  for (const w of WIRES) {
    if (!w.ends.includes(partId)) continue;
    for (const end of w.ends) {
      if (end === partId) continue;
      for (const c of baseConnectors(end)) if (!linked.includes(c.id)) linked.push(c.id);
    }
  }
  const rows = 4;
  const cols = 6;
  const slots: FuseSlot[] = [];
  for (let r = 1; r <= rows; r++) {
    for (let c = 1; c <= cols; c++) {
      slots.push({ key: `r${r}c${c}`, row: r, col: c, position: nil(), kind: nil(), amps: nil(), protects: nil(), connectors: linked, flows: flowsFor(partId) });
    }
  }
  return { id, partId, name: PARTS[partId]?.name ?? partId, rows, cols, slots, origin: "stub" };
}

export function fuseBoxFor(partId: string, user: UserConnectorData = loadUser()): FuseBox | null {
  const base = fuseBoxBase(partId);
  return base ? mergeBox(base, user.boxes[base.id]) : null;
}

// ---- merge: user data wins field by field ----
function pick<T>(base: Seeded<T>, mine: Seeded<T> | undefined): Seeded<T> {
  return mine && mine.value !== null ? mine : base;
}
export function isUser<T>(s: Seeded<T>): boolean {
  return s.value !== null && s.source === null;
}

export function mergeConnector(base: Connector, mine: Connector | undefined): Connector {
  if (!mine) return base;
  const pins = base.pins.map((p) => {
    const u = mine.pins.find((x) => x.key === p.key);
    if (!u) return p;
    return { ...p, cavity: pick(p.cavity, u.cavity), color: pick(p.color, u.color), circuit: pick(p.circuit, u.circuit), expect: pick(p.expect, u.expect) };
  });
  const parts: ConnectorParts = {
    shell: pick(base.parts.shell, mine.parts.shell),
    seal: pick(base.parts.seal, mine.parts.seal),
    lock: pick(base.parts.lock, mine.parts.lock),
    terminal: pick(base.parts.terminal, mine.parts.terminal),
  };
  return { ...base, cNumber: pick(base.cNumber, mine.cNumber), pinCount: pick(base.pinCount, mine.pinCount), pins, parts };
}

export function mergeBox(base: FuseBox, mine: FuseBox | undefined): FuseBox {
  if (!mine) return base;
  const slots = base.slots.map((s) => {
    const u = mine.slots.find((x) => x.key === s.key);
    if (!u) return s;
    return { ...s, position: pick(s.position, u.position), kind: pick(s.kind, u.kind), amps: pick(s.amps, u.amps), protects: pick(s.protects, u.protects) };
  });
  return { ...base, slots };
}

// ---- user store ----
export const USER_KEY = "mustang.connectors.v1";
export const MAX_IMPORT_CHARS = 1_000_000;

export function emptyUser(): UserConnectorData {
  return { v: 1, connectors: {}, boxes: {} };
}

type Obj = Record<string, unknown>;
const isObj = (o: unknown): o is Obj => typeof o === "object" && o !== null && !Array.isArray(o);
const onlyKeys = (o: Obj, keys: string[]) => Object.keys(o).every((k) => keys.includes(k));
const str = (s: unknown, max: number): s is string => typeof s === "string" && s.length <= max;

function vSeeded(o: unknown, kinds: readonly string[] | null = null, num = false): Seeded<never> | null {
  if (!isObj(o) || !onlyKeys(o, ["value", "source", "user"])) return null;
  if (o.value === null || o.value === undefined) return { value: null, source: null };
  if (num) {
    if (typeof o.value !== "number" || !Number.isInteger(o.value) || o.value < 0 || o.value > 999) return null;
  } else if (!str(o.value, 400) || (kinds && !kinds.includes(o.value))) return null;
  // imported values are never treated as verified, whatever source they claim
  return { value: o.value as never, source: null, user: true };
}

function vPin(o: unknown): ConnectorPin | null {
  const keys = ["key", "cavity", "role", "label", "color", "circuit", "expect", "to"];
  if (!isObj(o) || !onlyKeys(o, keys) || !str(o.key, 64) || !str(o.label, 400)) return null;
  const roles = ["power", "ground", "signal", "control", "unknown"];
  if (!str(o.role, 16) || !roles.includes(o.role)) return null;
  if (o.to !== undefined && !str(o.to, 64)) return null;
  const cavity = vSeeded(o.cavity), color = vSeeded(o.color), circuit = vSeeded(o.circuit), expect = vSeeded(o.expect);
  if (!cavity || !color || !circuit || !expect) return null;
  return { key: o.key, cavity, role: o.role as PinRole, label: o.label, color, circuit, expect, ...(o.to ? { to: o.to as string } : {}) };
}

function vIds(o: unknown, max: number): string[] | null {
  return Array.isArray(o) && o.length <= max && o.every((x) => str(x, 64)) ? (o as string[]) : null;
}

function vConnector(o: unknown): Connector | null {
  const keys = ["id", "partId", "name", "cNumber", "pinCount", "pins", "parts", "flows", "stub", "origin"];
  if (!isObj(o) || !onlyKeys(o, keys) || !str(o.id, 64) || !str(o.partId, 64) || !str(o.name, 400)) return null;
  if (!Array.isArray(o.pins) || o.pins.length > 64) return null;
  const pins = o.pins.map(vPin);
  if (pins.some((p) => !p)) return null;
  const p = o.parts;
  if (!isObj(p) || !onlyKeys(p, ["shell", "seal", "lock", "terminal"])) return null;
  const shell = vSeeded(p.shell), seal = vSeeded(p.seal), lock = vSeeded(p.lock), terminal = vSeeded(p.terminal);
  const cNumber = vSeeded(o.cNumber), pinCount = vSeeded(o.pinCount, null, true);
  const flows = vIds(o.flows ?? [], 16);
  if (!shell || !seal || !lock || !terminal || !cNumber || !pinCount || !flows) return null;
  return { id: o.id, partId: o.partId, name: o.name, cNumber, pinCount, pins: pins as ConnectorPin[], parts: { shell, seal, lock, terminal }, flows, stub: false, origin: "user" };
}

function vSlot(o: unknown): FuseSlot | null {
  const keys = ["key", "row", "col", "position", "kind", "amps", "protects", "connectors", "flows"];
  if (!isObj(o) || !onlyKeys(o, keys) || !str(o.key, 64)) return null;
  const n = (x: unknown) => typeof x === "number" && Number.isInteger(x) && x >= 1 && x <= 64;
  if (!n(o.row) || !n(o.col)) return null;
  const position = vSeeded(o.position), amps = vSeeded(o.amps), protects = vSeeded(o.protects);
  const kind = vSeeded(o.kind, ["fuse", "maxi", "relay", "diode"]);
  const connectors = vIds(o.connectors ?? [], 64), flows = vIds(o.flows ?? [], 16);
  if (!position || !amps || !protects || !kind || !connectors || !flows) return null;
  return { key: o.key, row: o.row as number, col: o.col as number, position, kind, amps, protects, connectors, flows };
}

function vBox(o: unknown): FuseBox | null {
  const keys = ["id", "partId", "name", "rows", "cols", "slots", "origin"];
  if (!isObj(o) || !onlyKeys(o, keys) || !str(o.id, 64) || !BOXES[o.id] || !str(o.partId, 64) || !str(o.name, 400)) return null;
  const n = (x: unknown) => typeof x === "number" && Number.isInteger(x) && x >= 1 && x <= 64;
  if (!n(o.rows) || !n(o.cols) || !Array.isArray(o.slots) || o.slots.length > 512) return null;
  const slots = o.slots.map(vSlot);
  if (slots.some((s) => !s)) return null;
  return { id: o.id as FuseBox["id"], partId: o.partId, name: o.name, rows: o.rows as number, cols: o.cols as number, slots: slots as FuseSlot[], origin: "user" };
}

export function validate(o: unknown): UserConnectorData | null {
  if (!isObj(o) || !onlyKeys(o, ["v", "connectors", "boxes"]) || o.v !== 1) return null;
  const cs = o.connectors ?? {};
  const bs = o.boxes ?? {};
  if (!isObj(cs) || !isObj(bs)) return null;
  const ck = Object.keys(cs);
  const bk = Object.keys(bs);
  if (ck.length > 500 || bk.length > 3) return null;
  const out = emptyUser();
  for (const k of ck) {
    const c = vConnector(cs[k]);
    if (!str(k, 64) || !c || c.id !== k) return null;
    out.connectors[k] = c;
  }
  for (const k of bk) {
    const b = vBox(bs[k]);
    if (!b || b.id !== k) return null;
    out.boxes[k] = b;
  }
  return out;
}

export function loadUser(): UserConnectorData {
  try {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw || raw.length > MAX_IMPORT_CHARS) return emptyUser();
    return validate(JSON.parse(raw)) ?? emptyUser();
  } catch {
    return emptyUser();
  }
}

export function saveUser(data: UserConnectorData): boolean {
  try {
    localStorage.setItem(USER_KEY, JSON.stringify(data));
    return true;
  } catch {
    return false;
  }
}

export function exportJson(data: UserConnectorData = loadUser()) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "mustang-connectors.v1.json";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

// Returns null when the import was written, or an error / cancel message. Storage is untouched on failure.
export function importJson(text: string, ask: (msg: string) => boolean = (m) => window.confirm(m)): string | null {
  if (text.length > MAX_IMPORT_CHARS) return "That file is too large to be connector data.";
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    return "That file is not valid JSON.";
  }
  const data = validate(parsed);
  if (!data) return "That file is not mustang-connectors v1 data.";
  const n = Object.keys(data.connectors).length;
  const m = Object.keys(data.boxes).length;
  if (!ask(`${n} connectors, ${m} boxes. Replace?`)) return "Import cancelled.";
  return saveUser(data) ? null : "Could not save. Storage is full or blocked.";
}

// Keep only what the owner typed: an entry with every user value, nothing seeded.
export function userEntryFrom(base: Connector, existing: Connector | undefined): Connector {
  return existing ?? { ...base, cNumber: nil(), pinCount: nil(), pins: base.pins.map((p) => pin(p.key, p.role, p.label, p.to ? { to: p.to } : {})), parts: noParts(), stub: false, origin: "user" };
}
export function userBoxFrom(base: FuseBox, existing: FuseBox | undefined): FuseBox {
  return existing ?? { ...base, slots: base.slots.map((s) => ({ ...s, position: nil(), kind: nil(), amps: nil(), protects: nil() })), origin: "user" };
}
export function typed(value: string): Seeded<string> {
  const v = value.trim().slice(0, 400);
  return v ? { value: v, source: null, user: true } : nil();
}
