import { useEffect, useRef, useState } from "react";
import {
  baseConnectors,
  exportJson,
  fuseBoxBase,
  importJson,
  loadUser,
  mergeBox,
  mergeConnector,
  saveUser,
  typed,
  userBoxFrom,
  userEntryFrom,
} from "@/lib/mustang/connectors";
import { useMustang } from "@/lib/mustang/store";
import type { ConnectorPin, FuseSlot, Seeded } from "@/lib/mustang/types";
import { ExplodedConnector } from "./exploded";
import { FuseBoxDiagram } from "./fusebox";
import { PartPhoto } from "./photo";
import { PinoutOverlay } from "./pinout";

type PinField = "color" | "circuit" | "expect" | "cavity";
type SlotField = "position" | "amps" | "protects";

export function ConnectorPanel({ partId }: { partId: string }) {
  const pin = useMustang((s) => s.pin);
  const setPin = useMustang((s) => s.setPin);
  const select = useMustang((s) => s.select);
  const startFlow = useMustang((s) => s.startFlow);
  const [user, setUser] = useState(loadUser);
  const [slot, setSlot] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    (window as { FafoChrome?: { initFold?: () => void } }).FafoChrome?.initFold?.();
  }, [partId]);
  useEffect(() => {
    setSlot(null);
    setMsg(null);
  }, [partId]);

  const bases = baseConnectors(partId);
  const connectors = bases.map((c) => mergeConnector(c, user.connectors[c.id]));
  const conn = connectors[0] ?? null;
  const boxBase = fuseBoxBase(partId);
  const box = boxBase ? mergeBox(boxBase, user.boxes[boxBase.id]) : null;

  const commit = (next: typeof user) => {
    if (saveUser(next)) {
      setUser(next);
      setMsg(null);
    } else setMsg("Could not save. Storage is full or blocked.");
  };
  const editPin = (key: string, field: PinField, value: string) => {
    if (!conn) return;
    const entry = userEntryFrom(bases[0], user.connectors[conn.id]);
    const pins: ConnectorPin[] = entry.pins.map((p) => (p.key === key ? { ...p, [field]: typed(value) } : p));
    commit({ ...user, connectors: { ...user.connectors, [conn.id]: { ...entry, pins } } });
  };
  const editSlot = (key: string, field: SlotField, value: string) => {
    if (!boxBase) return;
    const entry = userBoxFrom(boxBase, user.boxes[boxBase.id]);
    const slots: FuseSlot[] = entry.slots.map((s) => (s.key === key ? { ...s, [field]: typed(value) } : s));
    commit({ ...user, boxes: { ...user.boxes, [boxBase.id]: { ...entry, slots } } });
  };
  const reset = () => {
    const connectorsNext = { ...user.connectors };
    if (conn) delete connectorsNext[conn.id];
    const boxesNext = { ...user.boxes };
    if (boxBase) delete boxesNext[boxBase.id];
    commit({ ...user, connectors: connectorsNext, boxes: boxesNext });
  };
  const onFile = async (file: File | undefined) => {
    if (!file) return;
    const err = importJson(await file.text());
    if (err) setMsg(err);
    else {
      setUser(loadUser());
      setMsg(null);
    }
    if (fileRef.current) fileRef.current.value = "";
  };
  const own = (s: Seeded<string>) => ("user" in s && s.user ? String(s.value) : "");
  const activePin = conn?.pins.find((p) => p.key === pin) ?? conn?.pins[0] ?? null;
  const activeSlot = box?.slots.find((s) => s.key === slot) ?? null;
  const editKey = `${conn?.id ?? ""}|${activePin?.key ?? ""}|${activeSlot?.key ?? ""}|${JSON.stringify(user).length}`;

  return (
    <section className="conn-panel" aria-label="Connectors">
      {conn ? (
        <details className="fafo-fold" data-fafo-fold="pinout">
          <summary>Pinout</summary>
          <p className="fine">
            {conn.name}
            {conn.stub ? " (generated from the wiring sheet)" : ""}. Pin positions are a layout schematic, not a cavity map.
          </p>
          <PinoutOverlay connector={conn} activePin={pin} onPin={setPin} />
          <PartPhoto id={conn.id} partId={partId} alt={`${conn.name}, context photo`} />
        </details>
      ) : null}
      {conn ? (
        <details className="fafo-fold" data-fafo-fold="connector-exploded" data-collapsed-default>
          <summary>Exploded view</summary>
          <ExplodedConnector connector={conn} activePin={pin} onPin={setPin} />
        </details>
      ) : null}
      {box ? (
        <details className="fafo-fold" data-fafo-fold="fusebox">
          <summary>Fuse map</summary>
          <FuseBoxDiagram
            box={box}
            activeSlot={slot}
            onSlot={setSlot}
            onConnector={(id) => select(id.split(":")[0], true)}
            onFlow={startFlow}
          />
        </details>
      ) : null}
      <details className="fafo-fold" data-fafo-fold="connector-edit" data-collapsed-default>
        <summary>Edit pin/slot data</summary>
        <div className="conn-edit" key={editKey}>
          <p className="fine">Only type what you read off the EVTM, the box lid or the car. Your entries are marked &ldquo;you entered this&rdquo; and stay in this browser.</p>
          {conn && activePin ? (
            <>
              <label className="field">
                <span>Pin</span>
                <select value={activePin.key} onChange={(e) => setPin(e.target.value)}>
                  {conn.pins.map((p) => (
                    <option key={p.key} value={p.key}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </label>
              {(["color", "circuit", "expect", "cavity"] as PinField[]).map((f) => (
                <label className="field" key={f}>
                  <span>{f === "color" ? "Wire colour" : f === "circuit" ? "Circuit number" : f === "expect" ? "Expected reading" : "Cavity label"}</span>
                  <input type="text" maxLength={400} defaultValue={own(activePin[f])} onBlur={(e) => editPin(activePin.key, f, e.target.value)} />
                </label>
              ))}
            </>
          ) : null}
          {box && activeSlot ? (
            (["position", "amps", "protects"] as SlotField[]).map((f) => (
              <label className="field" key={f}>
                <span>Slot {activeSlot.key}: {f === "amps" ? "rating" : f}</span>
                <input type="text" maxLength={400} defaultValue={own(activeSlot[f])} onBlur={(e) => editSlot(activeSlot.key, f, e.target.value)} />
              </label>
            ))
          ) : box ? (
            <p className="fine">Pick a slot in the fuse map to edit it.</p>
          ) : null}
          <div className="conn-grid">
            <button type="button" className="btn" onClick={() => exportJson(user)}>
              Export
            </button>
            <button type="button" className="btn" onClick={() => fileRef.current?.click()}>
              Import
            </button>
            <button type="button" className="btn" onClick={reset}>
              Reset my edits for this connector
            </button>
            <input ref={fileRef} className="sr" type="file" accept="application/json,.json" aria-label="Import connector data" onChange={(e) => onFile(e.target.files?.[0])} />
          </div>
          {msg ? <p className="error" role="alert">{msg}</p> : null}
        </div>
      </details>
    </section>
  );
}
