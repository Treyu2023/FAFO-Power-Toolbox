import { useEffect } from "react";
import { NODES, WIRES } from "@/lib/mustang/diagram";
import { useMustang } from "@/lib/mustang/store";
import { CIRCUIT_COLOR, CIRCUIT_LABEL, type Circuit } from "@/lib/mustang/types";

const CIRCUITS: (Circuit | "all")[] = ["all", "power", "ground", "start", "ignition", "fuel", "sensor", "lamps"];

export function WiringSheet() {
  const selected = useMustang((s) => s.selected);
  const trace = useMustang((s) => s.trace);
  const circuit = useMustang((s) => s.circuit);
  const select = useMustang((s) => s.select);
  const setCircuit = useMustang((s) => s.setCircuit);

  useEffect(() => {
    if (!selected) return;
    const node = document.querySelector(`[data-node="${CSS.escape(selected)}"]`);
    node?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [selected]);

  return (
    <div className="sheet">
      <div className="sheet-head">
        <div>
          <p className="eyebrow">Power map</p>
          <h2>Wires, same names as the car</h2>
        </div>
        <p className="sheet-note">
          Simplified service map for the base 3.8. Not the full Ford EVTM. Click a box or a line and the car opens to that part. Click the same thing on the car and it lights up here.
        </p>
      </div>
      <div className="chip-row" role="tablist" aria-label="Circuits">
        {CIRCUITS.map((id) => (
          <button
            key={id}
            type="button"
            className={circuit === id ? "chip chip-on" : "chip"}
            onClick={() => setCircuit(id)}
          >
            {id === "all" ? "All circuits" : CIRCUIT_LABEL[id]}
          </button>
        ))}
      </div>
      <div className="sheet-scroll">
        <svg viewBox="0 0 880 520" className="sheet-svg" role="img" aria-label="Mustang wiring map">
          {WIRES.map((wire) => {
            const hot = trace.includes(wire.id) || selected === wire.id;
            const dim = !hot && circuit !== "all" && circuit !== wire.circuit;
            return wire.routes.map((route, i) => {
              const d = route.map((p, n) => `${n === 0 ? "M" : "L"}${p[0]} ${p[1]}`).join(" ");
              const pick = (e: { stopPropagation: () => void }) => {
                e.stopPropagation();
                select(wire.id, true);
              };
              return (
                <g key={`${wire.id}-${i}`}>
                  <path d={d} fill="none" stroke="transparent" strokeWidth={14} className="wire-path" onClick={pick} />
                  <path
                    d={d}
                    fill="none"
                    stroke={hot ? "#f4f4f5" : CIRCUIT_COLOR[wire.circuit]}
                    strokeWidth={hot ? 3.5 : 1.75}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    opacity={dim ? 0.18 : 1}
                    pointerEvents="none"
                  />
                </g>
              );
            });
          })}
          {NODES.map((node) => {
            const hot = selected === node.id || trace.includes(node.id);
            const partCircuit = WIRES.find((w) => w.ends.includes(node.id) || w.id === node.id)?.circuit;
            const dim = !hot && circuit !== "all" && partCircuit && partCircuit !== circuit;
            return (
              <g
                key={node.id}
                data-node={node.id}
                className="wire-node"
                opacity={dim ? 0.35 : 1}
                onClick={(e) => {
                  e.stopPropagation();
                  select(node.id, true);
                  useMustang.getState().setRailOpen(true);
                }}
              >
                <rect
                  x={node.x}
                  y={node.y}
                  width={node.w}
                  height={node.h}
                  rx={8}
                  fill={hot ? "#2a2a2e" : "#1a1a1d"}
                  stroke={hot ? "#f4f4f5" : "#3a3a40"}
                  strokeWidth={hot ? 1.75 : 1}
                />
                <text x={node.x + 10} y={node.y + 18} className="node-label">
                  {node.label}
                </text>
                {node.sub ? (
                  <text x={node.x + 10} y={node.y + 34} className="node-sub">
                    {node.sub}
                  </text>
                ) : null}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
