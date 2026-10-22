import { isUser } from "@/lib/mustang/connectors";
import type { Connector, PinRole, Seeded } from "@/lib/mustang/types";
import { UNVERIFIED } from "@/lib/mustang/types";

export const ROLE_FILL: Record<PinRole, string> = {
  power: "#b4463f",
  ground: "#3f3f46",
  signal: "#3f6fb4",
  control: "#b48a3f",
  unknown: "#52525b",
};

export function SeededText({ s }: { s: Seeded<string | number> }) {
  if (s.value === null) return <span className="unverified">{UNVERIFIED}</span>;
  if (isUser(s)) {
    return (
      <span>
        {String(s.value)} <span className="badge-user">you entered this</span>
      </span>
    );
  }
  return (
    <span title={s.source ? `${s.source.file}:${s.source.line}` : undefined}>
      {String(s.value)} <span className="fine">(from {s.source?.file.split("/").pop()}:{s.source?.line})</span>
    </span>
  );
}

export function pinGrid(n: number, w: number, h: number) {
  const cols = Math.max(1, Math.ceil(Math.sqrt(n * (w / h))));
  const rows = Math.max(1, Math.ceil(n / cols));
  const cell = Math.min(w / cols, h / rows);
  return { cols, rows, cell };
}

export function PinoutOverlay({ connector, activePin, onPin }: { connector: Connector; activePin?: string | null; onPin: (key: string) => void }) {
  const pins = connector.pins;
  const W = 300;
  const H = 150;
  const { cols, rows, cell } = pinGrid(pins.length, W, H);
  const ox = 10 + (W - cols * cell) / 2;
  const oy = 10 + (H - rows * cell) / 2;
  const active = pins.find((p) => p.key === activePin) ?? null;
  return (
    <div className="pinout">
      {pins.length ? (
        <svg className="conn-svg" viewBox="0 0 320 200" role="group" aria-label={`${connector.name} pins`}>
          <rect x="4" y="4" width="312" height="162" rx="10" fill="var(--color-surface-2)" stroke="var(--color-line)" />
          {pins.map((p, i) => {
            const x = ox + (i % cols) * cell;
            const y = oy + Math.floor(i / cols) * cell;
            const pad = cell * 0.12;
            const on = p.key === activePin;
            return (
              <g
                key={p.key}
                role="button"
                tabIndex={0}
                aria-label={`${p.label}, ${p.role}`}
                aria-pressed={on}
                className="pin-cell"
                onClick={() => onPin(p.key)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onPin(p.key);
                  }
                }}
              >
                <rect x={x + pad} y={y + pad} width={cell - 2 * pad} height={cell - 2 * pad} rx="6" fill={ROLE_FILL[p.role]} stroke={on ? "var(--color-accent)" : "transparent"} strokeWidth="3" />
                {p.color.value === null ? (
                  <text x={x + cell / 2} y={y + cell / 2} textAnchor="middle" dominantBaseline="central" fill="#fff" fontSize={Math.min(28, cell * 0.4)}>
                    ?
                  </text>
                ) : (
                  <text x={x + cell / 2} y={y + cell / 2} textAnchor="middle" dominantBaseline="central" fill="#fff" fontSize={Math.min(12, cell * 0.14)}>
                    {p.color.value.slice(0, 14)}
                  </text>
                )}
              </g>
            );
          })}
          <text x="160" y="188" textAnchor="middle" fill="var(--color-muted)" fontSize="11">
            layout schematic, not cavity map
          </text>
        </svg>
      ) : (
        <p className="unverified">Pins {UNVERIFIED}</p>
      )}
      <ul className="pin-list">
        {pins.map((p) => (
          <li key={p.key} className={p.key === activePin ? "on" : undefined}>
            <button type="button" className="chip" aria-pressed={p.key === activePin} onClick={() => onPin(p.key)}>
              {p.label}
            </button>
            {p.key === activePin || !active ? (
              <dl className="spec-list">
                <div><dt>Role</dt><dd>{p.role}</dd></div>
                <div><dt>Colour</dt><dd><SeededText s={p.color} /></dd></div>
                <div><dt>Expect</dt><dd><SeededText s={p.expect} /></dd></div>
                <div><dt>Circuit</dt><dd><SeededText s={p.circuit} /></dd></div>
                <div><dt>Cavity</dt><dd><SeededText s={p.cavity} /></dd></div>
                {p.to ? <div><dt>Runs to</dt><dd>{p.to}</dd></div> : null}
              </dl>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
