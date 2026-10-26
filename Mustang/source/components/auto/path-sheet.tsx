import { useEffect } from "react";
import { connectorsFor, type PinRole } from "@/lib/auto/connectors";
import { CIRCUIT_COLOR, CIRCUIT_LABEL, NODES, WIRES, traceOf, type Circuit } from "@/lib/auto/diagram";
import { groupIdOf } from "@/lib/auto/model";
import type { Flow } from "@/lib/auto/flows";

const CIRCUITS: (Circuit | "all")[] = ["all", "power", "ground", "start", "ignition", "fuel", "sensor", "lamps"];

const ROLE: Record<PinRole, string> = {
  power: "Power",
  ground: "Ground",
  signal: "Signal",
  control: "Control",
  unknown: "Unknown",
};

export const JOBS = [
  { label: "Cranks, no start", part: "inertia-switch", flow: "fuel-pump-power" },
  { label: "No pump prime", part: "fuel-pump", flow: "fuel-pump-power" },
  { label: "EVAP", part: "evap-purge", flow: "evap" },
  { label: "Miss under load", part: "coil-pack" },
  { label: "Battery light", part: "alternator" },
] as const;

export function groupsOnCircuit(circuit: Circuit) {
  const ids = new Set<string>();
  for (const wire of WIRES) {
    if (wire.circuit !== circuit) continue;
    ids.add(groupIdOf(wire.id));
    for (const end of wire.ends) ids.add(groupIdOf(end));
  }
  return [...ids];
}

export function PathSheet({
  selected,
  circuit,
  mustang,
  flow,
  stepIndex,
  onCircuit,
  onPick,
  onJob,
  onStep,
}: {
  selected: string | null;
  circuit: Circuit | "all";
  mustang: boolean;
  flow: Flow | null;
  stepIndex: number;
  onCircuit: (circuit: Circuit | "all") => void;
  onPick: (id: string) => void;
  onJob: (part: string, flowId?: string) => void;
  onStep: (index: number) => void;
}) {
  const trace = new Set(traceOf(selected));
  const step = flow?.steps[Math.min(stepIndex, Math.max(flow.steps.length - 1, 0))];
  const connectors = connectorsFor(selected);

  useEffect(() => {
    if (!selected) return;
    const node = document.querySelector(`[data-node="${CSS.escape(selected)}"]`);
    node?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [selected]);

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm leading-relaxed text-muted">
        {mustang
          ? "Service map for the base 3.8. Not the full Ford EVTM. A lit line is the trace for the part you picked."
          : "This map is the 2001 Mustang 3.8. It is not the wiring for the common car."}
      </p>
      <div className="flex flex-wrap gap-2">
        {JOBS.map((job) => (
          <button key={job.label} type="button" onClick={() => onJob(job.part, "flow" in job ? job.flow : undefined)} className="h-11 rounded-md border border-line px-3 text-sm text-fg">
            {job.label}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Circuits">
        {CIRCUITS.map((id) => (
          <button key={id} type="button" onClick={() => onCircuit(id)} className={`h-11 rounded-md px-3 text-sm ${circuit === id ? "bg-accent font-medium text-accent-fg" : "border border-line text-fg"}`}>
            {id === "all" ? "All circuits" : CIRCUIT_LABEL[id]}
          </button>
        ))}
      </div>
      <div className="overflow-auto rounded-md border border-line bg-bg">
        <svg viewBox="0 0 880 520" className="h-auto min-w-[52rem]" role="img" aria-label="Wiring map">
          {WIRES.map((wire) => {
            const hot = trace.has(wire.id) || selected === wire.id;
            const dim = !hot && circuit !== "all" && circuit !== wire.circuit;
            return wire.routes.map((route, index) => {
              const d = route.map((point, n) => `${n === 0 ? "M" : "L"}${point[0]} ${point[1]}`).join(" ");
              return (
                <g key={`${wire.id}-${index}`}>
                  <path d={d} fill="none" stroke="transparent" strokeWidth={14} onClick={() => onPick(wire.id)} />
                  <path d={d} fill="none" stroke={hot ? "#f4f4f2" : CIRCUIT_COLOR[wire.circuit]} strokeWidth={hot ? 3.5 : 1.75} strokeLinecap="round" strokeLinejoin="round" opacity={dim ? 0.16 : 1} pointerEvents="none" />
                </g>
              );
            });
          })}
          {NODES.map((node) => {
            const hot = selected === node.id || trace.has(node.id);
            const partCircuit = WIRES.find((wire) => wire.ends.includes(node.id) || wire.id === node.id)?.circuit;
            const dim = !hot && circuit !== "all" && partCircuit && partCircuit !== circuit;
            return (
              <g key={node.id} data-node={node.id} opacity={dim ? 0.28 : 1} onClick={() => onPick(node.id)} className="cursor-pointer">
                <rect x={node.x} y={node.y} width={node.w} height={node.h} rx={8} fill={hot ? "#2a2a2e" : "#1a1a1d"} stroke={hot ? "#f4f4f2" : "#3a3a40"} strokeWidth={hot ? 1.75 : 1} />
                <text x={node.x + 10} y={node.y + 18} fill="#f4f4f2" fontSize="12">
                  {node.label}
                </text>
                {node.sub ? (
                  <text x={node.x + 10} y={node.y + 34} fill="#a1a1aa" fontSize="10">
                    {node.sub}
                  </text>
                ) : null}
              </g>
            );
          })}
        </svg>
      </div>
      {flow && step ? (
        <div className="flex flex-col gap-2">
          <p className="text-sm text-fg">
            {flow.title} · step {stepIndex + 1} of {flow.steps.length}: {step.title}
          </p>
          <div className="flex gap-2">
            <button type="button" disabled={stepIndex === 0} onClick={() => onStep(stepIndex - 1)} className="h-11 rounded-md border border-line px-3 text-sm text-fg disabled:opacity-40">
              Back
            </button>
            <button type="button" disabled={stepIndex >= flow.steps.length - 1} onClick={() => onStep(stepIndex + 1)} className="h-11 rounded-md border border-line px-3 text-sm text-fg disabled:opacity-40">
              Next on the path
            </button>
          </div>
        </div>
      ) : null}
      {connectors.map((connector) => (
        <section key={connector.id} className="flex flex-col gap-2">
          <h3 className="text-sm font-medium text-fg">{connector.name}</h3>
          <p className="text-sm text-muted">{connector.stub ? "Trace only. The cavity number is not verified." : "Colors below are the ones written into the fuel-pump walk. A blank color means it was not verified."}</p>
          <ul className="flex flex-col gap-2">
            {connector.pins.map((pin) => (
              <li key={pin.key} className="rounded-md bg-elevated px-3 py-2 text-sm">
                <p className="text-fg">
                  {pin.label} · {ROLE[pin.role]}
                </p>
                <p className="text-muted">Color: {pin.color ?? "not verified"}</p>
                {pin.expect ? <p className="text-muted">Expect: {pin.expect}</p> : null}
                {pin.to ? <p className="text-muted">Runs toward {pin.to}</p> : null}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
