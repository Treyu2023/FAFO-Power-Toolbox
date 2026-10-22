import { PARTS } from "@/lib/mustang/parts";
import { UNVERIFIED, type Connector } from "@/lib/mustang/types";
import { ROLE_FILL } from "./pinout";

// Drawn only from the connector's own pins (which come from the diagram WIRES). Nothing is added here.
export function WiringMini({ connector, onPart }: { connector: Connector; onPart: (id: string) => void }) {
  const pins = connector.pins;
  const title = PARTS[connector.partId]?.name ?? connector.partId;
  if (!pins.length) {
    return (
      <figure className="conn-photo wire-mini" data-wires="0">
        <svg className="conn-svg" viewBox="0 0 320 90" role="img" aria-label={`${title}: no wiring recorded`}>
          <rect x="10" y="20" width="120" height="50" rx="8" fill="var(--color-surface-2)" stroke="var(--color-line)" />
          <text x="70" y="45" textAnchor="middle" dominantBaseline="central" fill="currentColor" fontSize="12">{title.slice(0, 18)}</text>
          <line x1="130" y1="45" x2="220" y2="45" stroke="var(--color-muted)" strokeDasharray="4 4" />
          <text x="226" y="45" dominantBaseline="central" fill="var(--color-muted)" fontSize="12">?</text>
        </svg>
        <figcaption className="fine unverified">No wiring recorded, not verified. {UNVERIFIED}.</figcaption>
      </figure>
    );
  }
  const row = 34;
  const h = Math.max(90, pins.length * row + 20);
  const cy = h / 2;
  return (
    <figure className="conn-photo wire-mini" data-wires={pins.length}>
      <svg className="conn-svg" viewBox={`0 0 320 ${h}`} role="img" aria-label={`${title} wiring`}>
        <rect x="10" y={cy - 25} width="110" height="50" rx="8" fill="var(--color-surface-2)" stroke="var(--color-line)" />
        <text x="65" y={cy} textAnchor="middle" dominantBaseline="central" fill="currentColor" fontSize="11">{title.slice(0, 18)}</text>
        {pins.map((p, i) => {
          const y = 10 + row / 2 + i * row;
          const end = p.to ? (PARTS[p.to]?.name ?? p.to) : null;
          return (
            <g key={p.key}>
              <path d={`M120 ${cy} C160 ${cy} 160 ${y} 200 ${y}`} fill="none" stroke={ROLE_FILL[p.role]} strokeWidth="2.5" strokeDasharray={end ? undefined : "4 4"} />
              {end ? (
                <g role="button" tabIndex={0} aria-label={`Go to ${end}`} style={{ cursor: "pointer" }} onClick={() => onPart(p.to as string)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onPart(p.to as string); }}>
                  <rect x="200" y={y - 12} width="112" height="24" rx="6" fill="var(--color-surface-2)" stroke="var(--color-line)" />
                  <text x="256" y={y} textAnchor="middle" dominantBaseline="central" fill="currentColor" fontSize="10">{end.slice(0, 19)}</text>
                </g>
              ) : (
                <text x="204" y={y} dominantBaseline="central" fill="var(--color-muted)" fontSize="10">end not recorded</text>
              )}
            </g>
          );
        })}
      </svg>
      <ul className="pin-list fine">
        {pins.map((p) => (
          <li key={p.key}>{p.label}{p.to ? "" : ", other end not verified"}</li>
        ))}
      </ul>
      <figcaption className="fine">Wiring from the sheet, not a harness route.</figcaption>
    </figure>
  );
}
