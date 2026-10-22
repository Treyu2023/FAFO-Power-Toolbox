import type { Connector, ConnectorParts } from "@/lib/mustang/types";
import { UNVERIFIED } from "@/lib/mustang/types";
import { ROLE_FILL } from "./pinout";

const LAYERS: { k: keyof ConnectorParts; label: string }[] = [
  { k: "shell", label: "Shell" },
  { k: "seal", label: "Seal" },
  { k: "terminal", label: "Terminals" },
  { k: "lock", label: "Lock" },
];

export function ExplodedConnector({ connector, activePin, onPin }: { connector: Connector; activePin?: string | null; onPin: (key: string) => void }) {
  const pins = connector.pins;
  return (
    <div className="exploded">
      <svg className="conn-svg" viewBox="0 0 320 200" role="group" aria-label={`${connector.name} exploded view`}>
        {LAYERS.map((layer, i) => {
          const y = 10 + i * 46;
          const val = connector.parts[layer.k].value;
          return (
            <g key={layer.k} className="explode-layer" style={{ transform: `translateX(${i * 10}px)` }}>
              {layer.k === "terminal" ? (
                pins.length ? (
                  pins.map((p, j) => {
                    const w = Math.min(28, 150 / pins.length);
                    const x = 14 + j * (150 / pins.length);
                    return (
                      <rect
                        key={p.key}
                        role="button"
                        tabIndex={0}
                        aria-label={`Terminal for ${p.label}`}
                        x={x}
                        y={y + 6}
                        width={w}
                        height="24"
                        rx="3"
                        fill={ROLE_FILL[p.role]}
                        stroke={p.key === activePin ? "var(--color-accent)" : "transparent"}
                        strokeWidth="3"
                        className="pin-cell"
                        onClick={() => onPin(p.key)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            onPin(p.key);
                          }
                        }}
                      />
                    );
                  })
                ) : (
                  <rect x="14" y={y + 6} width="150" height="24" rx="3" fill="none" stroke="var(--color-muted)" strokeDasharray="4 3" />
                )
              ) : (
                <rect x="14" y={y} width="150" height="36" rx="8" fill="var(--color-surface-2)" stroke="var(--color-line)" />
              )}
              <line x1="166" y1={y + 18} x2="182" y2={y + 18} stroke="var(--color-muted)" />
              <text x="186" y={y + 14} fill="var(--color-fg)" fontSize="11">{layer.label}</text>
              <text x="186" y={y + 28} fill="var(--color-muted)" fontSize="9">{val === null ? UNVERIFIED : String(val).slice(0, 22)}</text>
            </g>
          );
        })}
      </svg>
      <dl className="spec-list">
        {LAYERS.map((layer) => (
          <div key={layer.k}>
            <dt>{layer.label}</dt>
            <dd>{connector.parts[layer.k].value ?? UNVERIFIED}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
