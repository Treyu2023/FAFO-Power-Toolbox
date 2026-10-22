import { useEffect, useState } from "react";
import { connectorsFor, isBox } from "@/lib/mustang/connectors";
import { askMustang } from "@/lib/mustang/grok.functions";
import { partView } from "@/lib/mustang/parts";
import { useMustang } from "@/lib/mustang/store";
import { CIRCUIT_LABEL, STAGES, SYSTEM_LABEL } from "@/lib/mustang/types";
import { ConnectorPanel } from "./connectorpanel";

const JOBS: { label: string; id: string; symptom: string }[] = [
  { label: "Cranks, no start", id: "inertia-switch", symptom: "Cranks but will not fire" },
  { label: "Milkshake oil", id: "intake-gasket", symptom: "Oil looks like milkshake and coolant is low" },
  { label: "Miss under load", id: "coil-pack", symptom: "Misfire when you ask it for power" },
  { label: "Battery light", id: "alternator", symptom: "Battery light on, voltage looks low" },
  { label: "Oil and filter", id: "oil-pan", symptom: "Oil and filter service" },
  { label: "Hot in traffic", id: "fan-clutch", symptom: "Temperature climbs sitting still, fine on the highway" },
  { label: "Door sag", id: "door-l", symptom: "Driver door dropped onto the striker" },
  { label: "Wet carpet", id: "heater-core", symptom: "Sweet smell and a wet passenger floor" },
];

export function Inspector() {
  const selected = useMustang((s) => s.selected);
  const trans = useMustang((s) => s.trans);
  const select = useMustang((s) => s.select);
  const showOnCar = useMustang((s) => s.showOnCar);
  const showOnSheet = useMustang((s) => s.showOnSheet);

  if (!selected) {
    return (
      <aside className="inspector">
        <p className="eyebrow">FAFO Toolbox</p>
        <h2 className="inspector-title">2001 Mustang coupe</h2>
        <p className="lede">
          Base car, 3.8L OHV V6, iron heads, EDIS, returnless fuel, disc/drum brakes, 7.5-inch axle. Scroll in and the body comes apart in stages, down to the rotating assembly.
        </p>
        <dl className="spec-list">
          <div><dt>Power</dt><dd>193 hp · 225 lb-ft</dd></div>
          <div><dt>Oil</dt><dd>5W-20 · 5.0 qt with filter</dd></div>
          <div><dt>Plugs</dt><dd>AWSF-42EE · 0.052–0.056 in</dd></div>
          <div><dt>Order</dt><dd>1-4-2-5-3-6</dd></div>
        </dl>
        <h3>Start from a complaint</h3>
        <div className="job-grid">
          {JOBS.map((job) => (
            <button key={job.id + job.label} type="button" className="job" onClick={() => select(job.id, true)}>
              {job.label}
            </button>
          ))}
        </div>
        <p className="fine">
          Capacities are from the 2001 owner’s manual. Threads are the common sizes for this car. If a torque is missing, that is on purpose — confirm it in the Ford shop manual. The sheet is a service map, not the EVTM.
        </p>
      </aside>
    );
  }

  const part = partView(selected, trans);
  const stage = STAGES.find((s) => s.id === part.stage);

  return (
    <aside className="inspector">
      <p className="eyebrow">
        {SYSTEM_LABEL[part.system]}
        {part.circuit ? ` · ${CIRCUIT_LABEL[part.circuit]}` : ""}
        {stage ? ` · opens at ${stage.name}` : ""}
      </p>
      <h2 className="inspector-title">{part.name}</h2>
      <p className="lede">{part.blurb}</p>
      <div className="row-actions">
        <button type="button" className="btn" onClick={showOnCar}>
          Show on car
        </button>
        <button type="button" className="btn" onClick={showOnSheet}>
          Show on sheet
        </button>
      </div>
      {part.fasteners.length > 0 ? (
        <>
          <h3>Fasteners</h3>
          <ul className="fastener-list">
            {part.fasteners.map((f) => (
              <li key={f.name}>
                <span className="fast-name">{f.name}</span>
                <span className="fast-thread">{f.thread}</span>
                {f.torque ? <span className="fast-torque">{f.torque}</span> : null}
                {f.qty ? <span className="fast-qty">{f.qty}</span> : null}
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {part.specs.length > 0 ? (
        <dl className="spec-list">
          {part.specs.map((s) => (
            <div key={s.label}>
              <dt>{s.label}</dt>
              <dd>{s.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {connectorsFor(selected).length || isBox(selected) ? <ConnectorPanel partId={selected} /> : null}
      <h3>Check it like this</h3>
      <ol className="checks">
        {part.checks.map((c) => (
          <li key={c}>{c}</li>
        ))}
      </ol>
      <GrokNote partId={selected} symptomHint={JOBS.find((j) => j.id === selected)?.symptom ?? ""} />
    </aside>
  );
}

function GrokNote({ partId, symptomHint }: { partId: string; symptomHint: string }) {
  const trans = useMustang((s) => s.trans);
  const [symptom, setSymptom] = useState(symptomHint);
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    (window as { FafoChrome?: { initFold?: () => void } }).FafoChrome?.initFold?.();
  }, []);

  useEffect(() => {
    setSymptom(symptomHint);
    setText(null);
    setError(null);
  }, [partId, symptomHint, trans]);

  async function ask() {
    const key = `fafo-mustang-note:v1:${trans}:${partId}:${symptom.trim().toLowerCase()}`;
    try {
      const cached = localStorage.getItem(key);
      if (cached) {
        setText(cached);
        setError(null);
        return;
      }
    } catch {
      /* private mode */
    }
    setPending(true);
    setError(null);
    try {
      const res = await askMustang({ data: { partId, symptom, trans } });
      if (!res.ok) {
        setError(res.error);
        setText(null);
      } else {
        setText(res.text);
        try {
          localStorage.setItem(key, res.text);
        } catch {
          /* ignore quota */
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Grok did not answer");
    } finally {
      setPending(false);
    }
  }

  return (
    <details className="fafo-fold" data-fafo-fold="ask-grok" data-collapsed-default>
      <summary>Ask Grok (offline in toolbox)</summary>
      <div className="grok">
        <h3>Ask Grok (offline in toolbox)</h3>
        <p className="fine">This toolbox copy never sends anything. Ask Grok works only in the online bay.</p>
        <label className="field">
          <span>What is it doing?</span>
          <textarea
            value={symptom}
            onChange={(e) => setSymptom(e.target.value)}
            rows={2}
            maxLength={400}
            placeholder="Optional. Example: ticks when cold, quiet when hot."
          />
        </label>
        <button type="button" className="btn btn-solid" onClick={ask} disabled={pending}>
          {pending ? "Writing the note…" : "Ask Grok (offline)"}
        </button>
        {error ? <p className="error">{error}</p> : null}
        {text ? <p className="note">{text}</p> : null}
      </div>
    </details>
  );
}
