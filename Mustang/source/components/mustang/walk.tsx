import { useState } from "react";
import { askMustang } from "@/lib/mustang/grok.functions";
import { flowById, verdict } from "@/lib/mustang/flows";
import { PARTS } from "@/lib/mustang/parts";
import { useMustang } from "@/lib/mustang/store";

export function Walkthrough() {
  const flowId = useMustang((s) => s.flowId);
  const stepIndex = useMustang((s) => s.step);
  const marks = useMustang((s) => s.marks);
  const reading = useMustang((s) => s.reading);
  const setReading = useMustang((s) => s.setReading);
  const markStep = useMustang((s) => s.markStep);
  const setStep = useMustang((s) => s.setStep);
  const clearWalk = useMustang((s) => s.clearWalk);
  const trans = useMustang((s) => s.trans);
  const flow = flowById(flowId);

  if (!flow) {
    return (
      <div className="walk">
        <p className="eyebrow">Reference</p>
        <h2>No walkthrough yet</h2>
        <p className="lede">Right-click a part and choose Troubleshoot. Fuel-pump power is the one that is written out wire by wire.</p>
      </div>
    );
  }

  const step = flow.steps[Math.min(stepIndex, flow.steps.length - 1)];
  const found = verdict(flow, marks);
  const partName = PARTS[step.partId]?.name ?? step.partId;

  return (
    <div className="walk">
      <p className="eyebrow">
        Walkthrough · step {stepIndex + 1} of {flow.steps.length}
      </p>
      <h2>{flow.title}</h2>
      <p className="lede">{flow.lead}</p>
      <div className="step-pips" role="tablist" aria-label="Steps">
        {flow.steps.map((item, index) => (
          <button
            key={item.id}
            type="button"
            className={index === stepIndex ? "pip pip-on" : marks[item.id] === "fail" ? "pip pip-bad" : marks[item.id] === "pass" ? "pip pip-good" : "pip"}
            onClick={() => setStep(index)}
            aria-label={item.title}
          />
        ))}
      </div>
      <button type="button" className="btn" onClick={clearWalk}>
        Reset walkthrough
      </button>
      <article className="step-card">
        <h3>{step.title}</h3>
        <p className="step-part">{partName}</p>
        <dl className="step-facts">
          <div>
            <dt>Where</dt>
            <dd>{step.where}</dd>
          </div>
          <div>
            <dt>Harness</dt>
            <dd>{step.harness}</dd>
          </div>
        </dl>
        {step.wires.length > 0 ? (
          <ul className="wire-list">
            {step.wires.map((wire) => (
              <li key={wire.role}>
                <span className="fast-name">{wire.role}</span>
                <span className="fast-thread">{wire.color}</span>
              </li>
            ))}
          </ul>
        ) : null}
        <p>{step.action}</p>
        <div className="row-actions">
          <button type="button" className="btn btn-solid" onClick={() => markStep(step.id, "pass")}>
            This checks out
          </button>
          <button type="button" className="btn" onClick={() => markStep(step.id, "fail")}>
            This failed
          </button>
        </div>
        <p className="fine">{marks[step.id] === "fail" ? step.fail : step.pass}</p>
      </article>
      <label className="field">
        <span>What you measured</span>
        <textarea
          rows={3}
          maxLength={400}
          value={reading}
          onChange={(e) => setReading(e.target.value)}
          placeholder="Example: DG/YE at the CCRM jumps to 12.4 V for a second. Battery is 12.6."
        />
      </label>
      <Verify partId={step.partId} trans={trans} prompt={verifyPrompt(flow.title, step.title, step.action, reading)} />
      {found ? (
        <p className="note" role="status">
          {found}
        </p>
      ) : null}
      <div className="row-actions">
        <button type="button" className="btn" disabled={stepIndex === 0} onClick={() => setStep(stepIndex - 1)}>
          Back
        </button>
        <button type="button" className="btn" disabled={stepIndex >= flow.steps.length - 1} onClick={() => setStep(stepIndex + 1)}>
          Next step
        </button>
      </div>
    </div>
  );
}

function verifyPrompt(title: string, step: string, action: string, reading: string) {
  return `${title}. Step: ${step}. Instruction: ${action}. What I measured: ${reading || "I have not written a reading yet."} Tell me what that means and whether the pump is condemned. Do not invent wire colors or pin numbers.`;
}

function Verify({ partId, trans, prompt }: { partId: string; trans: "t5" | "4r70w"; prompt: string }) {
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function ask() {
    setPending(true);
    setError(null);
    try {
      const res = await askMustang({ data: { partId, symptom: prompt, trans } });
      if (!res.ok) {
        setError(res.error);
        setText(null);
      } else {
        setText(res.text);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Grok did not answer");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="grok">
      <button type="button" className="btn" onClick={ask} disabled={pending}>
        {pending ? "Checking the reading…" : "Ask Grok to check this step"}
      </button>
      {error ? <p className="error">{error}</p> : null}
      {text ? <p className="note">{text}</p> : null}
    </div>
  );
}
