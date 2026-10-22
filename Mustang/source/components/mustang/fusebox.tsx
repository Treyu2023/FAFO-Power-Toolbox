import { flowById } from "@/lib/mustang/flows";
import type { FuseBox } from "@/lib/mustang/types";
import { SeededText } from "./pinout";

export function FuseBoxDiagram({
  box,
  activeSlot,
  onSlot,
  onConnector,
  onFlow,
}: {
  box: FuseBox;
  activeSlot?: string | null;
  onSlot: (key: string) => void;
  onConnector: (id: string) => void;
  onFlow: (id: string) => void;
}) {
  const cw = 300 / box.cols;
  const ch = 170 / box.rows;
  const slot = box.slots.find((s) => s.key === activeSlot) ?? null;
  return (
    <div className="fusebox">
      <svg className="conn-svg" viewBox="0 0 320 200" role="group" aria-label={`${box.name} slots`}>
        {box.slots.map((s) => {
          const x = 10 + (s.col - 1) * cw;
          const y = 6 + (s.row - 1) * ch;
          const on = s.key === activeSlot;
          const label = s.position.value ?? s.amps.value ?? "?";
          return (
            <g
              key={s.key}
              role="button"
              tabIndex={0}
              aria-label={`Slot ${s.key}, ${s.position.value ?? "position unknown"}`}
              aria-pressed={on}
              className="pin-cell"
              onClick={() => onSlot(s.key)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSlot(s.key);
                }
              }}
            >
              <rect x={x + 3} y={y + 3} width={cw - 6} height={ch - 6} rx="4" fill="var(--color-surface-2)" stroke={on ? "var(--color-accent)" : "var(--color-line)"} strokeWidth={on ? 3 : 1} />
              <text x={x + cw / 2} y={y + ch / 2} textAnchor="middle" dominantBaseline="central" fill="var(--color-muted)" fontSize="12">
                {String(label).slice(0, 8)}
              </text>
            </g>
          );
        })}
        <text x="160" y="192" textAnchor="middle" fill="var(--color-muted)" fontSize="11">
          {box.origin === "stub" ? "grid only, not the real box layout" : "layout from your entries"}
        </text>
      </svg>
      {slot ? (
        <div className="fuse-detail">
          <dl className="spec-list">
            <div><dt>Position</dt><dd><SeededText s={slot.position} /></dd></div>
            <div><dt>Kind</dt><dd><SeededText s={slot.kind} /></dd></div>
            <div><dt>Rating</dt><dd><SeededText s={slot.amps} /></dd></div>
            <div><dt>Protects</dt><dd><SeededText s={slot.protects} /></dd></div>
          </dl>
          {slot.connectors.length ? (
            <>
              <p className="fine">Connectors wired to this box (not slot-specific):</p>
              <div className="conn-grid">
                {slot.connectors.map((id) => (
                  <button key={id} type="button" className="chip" onClick={() => onConnector(id)}>
                    {id}
                  </button>
                ))}
              </div>
            </>
          ) : null}
          {slot.flows.length ? (
            <div className="conn-grid">
              {slot.flows.map((id) => (
                <button key={id} type="button" className="btn" onClick={() => onFlow(id)}>
                  Walk: {flowById(id)?.title ?? id}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      ) : (
        <p className="fine">Pick a slot.</p>
      )}
    </div>
  );
}
