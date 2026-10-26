import type { CarSpec } from "@/lib/auto/resolve";

export type HoseKind = "coolant" | "heater" | "vacuum" | "pcv" | "evap" | "fuel" | "steer" | "wire";

export type ServiceRun = {
  id: string;
  name: string;
  system: "drivetrain" | "fuel" | "brakes";
  parent: string | null;
  color: string;
  kind: HoseKind;
  note: string;
  points: [number, number, number][];
  number?: number;
};

export const HOSE_KEY: { kind: HoseKind; color: string; label: string }[] = [
  { kind: "coolant", color: "#2f9d6a", label: "Coolant" },
  { kind: "heater", color: "#e08a3c", label: "Heater" },
  { kind: "vacuum", color: "#e2c14d", label: "Vacuum" },
  { kind: "pcv", color: "#c2a36a", label: "PCV" },
  { kind: "evap", color: "#7eb0d6", label: "EVAP" },
  { kind: "fuel", color: "#c45a4a", label: "Fuel" },
  { kind: "steer", color: "#6b4a32", label: "Power steering" },
];

export const WIRE_COLORS = ["#e24b4b", "#e08a3c", "#e6c84a", "#3d9a6a", "#3d7ec4", "#8a5cc4", "#eeeae2", "#c46b8a"];

export const VACUUM_TREE = [
  "The source is three ports on the back of the upper intake.",
  "The large hose is the brake booster.",
  "The center port is the PCV valve, in the driver valve cover. That is the draw.",
  "The passenger cover is fresh air only. Hose, no valve, toward the throttle body.",
  "One port tees to the firewall. That feed is the climate-control reservoir. The colored door lines are a separate dash diagram.",
  "The EGR solenoid takes manifold vacuum. The red hose from it goes to the EGR diaphragm. The solenoid fails more often than the valve.",
  "DPFE HI is the larger hose, upstream, toward the exhaust. REF is smaller and closer to the intake. Those taps are exhaust pressure, not vacuum.",
  "The purge valve is behind the passenger front liner. Its hose ends at the throttle body.",
];

const V6: [number, number, number][] = [
  [0.5, 0.74, -1.12],
  [0.5, 0.74, -0.95],
  [0.5, 0.74, -0.78],
  [-0.38, 0.8, -1.12],
  [-0.38, 0.8, -0.95],
  [-0.38, 0.8, -0.78],
];

function wire(n: number, end: [number, number, number], coil: [number, number, number]): ServiceRun {
  const mid: [number, number, number] = [(coil[0] + end[0]) / 2 + (n % 2 ? 0.04 : -0.04), Math.max(coil[1], end[1]) + 0.14 + n * 0.012, (coil[2] + end[2]) / 2];
  return {
    id: `wire-${n}`,
    name: `Plug wire ${n}`,
    system: "drivetrain",
    parent: "engine",
    color: WIRE_COLORS[n - 1] ?? "#f4f4f2",
    kind: "wire",
    number: n,
    note: `Spark lead ${n}. The number at each end matches the plug. On the 3.8, passenger bank is 1-2-3 and driver bank is 4-5-6, front to back.`,
    points: [coil, mid, end],
  };
}

const HOSES: ServiceRun[] = [
  {
    id: "hose-upper",
    name: "Upper radiator hose",
    system: "drivetrain",
    parent: null,
    color: "#2f9d6a",
    kind: "coolant",
    note: "Coolant, green. Radiator neck to the thermostat housing. This is a route, not a molded Ford hose.",
    points: [
      [0.12, 0.8, -1.74],
      [0.1, 0.86, -1.5],
      [0.06, 0.8, -1.22],
    ],
  },
  {
    id: "hose-lower",
    name: "Lower radiator hose",
    system: "drivetrain",
    parent: null,
    color: "#1f7a52",
    kind: "coolant",
    note: "Coolant, dark green. Bottom of the radiator to the water pump.",
    points: [
      [0.02, 0.4, -1.74],
      [0.06, 0.4, -1.5],
      [0.06, 0.52, -1.32],
    ],
  },
  {
    id: "hose-overflow",
    name: "Overflow hose",
    system: "drivetrain",
    parent: null,
    color: "#8fd0b0",
    kind: "coolant",
    note: "Coolant, pale green. Radiator neck to the reservoir. Do not open the caps hot.",
    points: [
      [0.16, 0.84, -1.74],
      [0.4, 0.9, -1.5],
      [0.58, 0.8, -1.28],
    ],
  },
  {
    id: "hose-heater-in",
    name: "Heater inlet",
    system: "drivetrain",
    parent: null,
    color: "#e08a3c",
    kind: "heater",
    note: "Heater, amber. From the intake side of the cooling circuit back to the firewall.",
    points: [
      [0.12, 0.74, -1.16],
      [0.2, 0.7, -0.8],
      [0.16, 0.58, -0.38],
    ],
  },
  {
    id: "hose-heater-out",
    name: "Heater outlet",
    system: "drivetrain",
    parent: null,
    color: "#a85a28",
    kind: "heater",
    note: "Heater return, dark amber. Firewall back toward the water pump.",
    points: [
      [-0.02, 0.52, -0.38],
      [0.02, 0.48, -0.85],
      [0.04, 0.5, -1.24],
    ],
  },
  {
    id: "hose-booster",
    name: "Booster vacuum",
    system: "brakes",
    parent: null,
    color: "#e2c14d",
    kind: "vacuum",
    note: "Large manifold-vacuum hose. Rear of the upper intake to the brake booster. A leak here is a big idle miss, not a small one.",
    points: [
      [0.04, 0.9, -0.88],
      [-0.16, 0.82, -0.7],
      [-0.34, 0.72, -0.5],
    ],
  },
  {
    id: "hose-hvac",
    name: "Firewall vacuum feed",
    system: "drivetrain",
    parent: null,
    color: "#f0e2a0",
    kind: "vacuum",
    note: "One port on the back of the upper intake tees toward the firewall. That feed is the climate-control reservoir, not an engine sensor. The door colors live on the dash harness, which is a separate diagram.",
    points: [
      [0.08, 0.92, -0.84],
      [0.18, 0.78, -0.6],
      [0.12, 0.62, -0.36],
    ],
  },
  {
    id: "hose-pcv",
    name: "PCV draw",
    system: "drivetrain",
    parent: "engine",
    color: "#c2a36a",
    kind: "pcv",
    note: "Driver valve cover. This is the valve, the metered draw, and it goes to the center port on the upper intake.",
    points: [
      [-0.3, 0.86, -0.86],
      [-0.08, 0.96, -0.9],
      [0.04, 0.92, -0.95],
    ],
  },
  {
    id: "hose-pcv-fresh",
    name: "PCV fresh air",
    system: "drivetrain",
    parent: "engine",
    color: "#e6d3a8",
    kind: "pcv",
    note: "Passenger valve cover. Hose only, no valve. It is the fresh-air side and runs toward the throttle body.",
    points: [
      [0.42, 0.84, -0.8],
      [0.22, 0.92, -1.05],
      [0.04, 0.88, -1.26],
    ],
  },
  {
    id: "hose-egr-source",
    name: "EGR source vacuum",
    system: "drivetrain",
    parent: "engine",
    color: "#d6c15a",
    kind: "vacuum",
    note: "Manifold vacuum into the EGR vacuum solenoid. The solenoid, not the valve, is the usual failure.",
    points: [
      [0.06, 0.9, -0.9],
      [0.18, 0.94, -0.84],
      [0.28, 0.9, -0.78],
    ],
  },
  {
    id: "hose-egr-control",
    name: "EGR control hose",
    system: "drivetrain",
    parent: "engine",
    color: "#c44a4a",
    kind: "vacuum",
    note: "Solenoid to the EGR diaphragm. On these cars the original control tube is red. If the red tube is gone, follow the port, not the color.",
    points: [
      [0.3, 0.88, -0.76],
      [0.24, 0.84, -0.74],
      [0.18, 0.8, -0.72],
    ],
  },
  {
    id: "hose-dpfe-hi",
    name: "DPFE HI hose",
    system: "drivetrain",
    parent: "engine",
    color: "#e07a3c",
    kind: "vacuum",
    note: "Exhaust reference, not manifold vacuum. HI is the upstream tap, the one closer to the exhaust. It is the larger of the two hoses.",
    points: [
      [0.3, 0.8, -0.68],
      [0.36, 0.68, -0.6],
      [0.4, 0.56, -0.52],
    ],
  },
  {
    id: "hose-dpfe-ref",
    name: "DPFE REF hose",
    system: "drivetrain",
    parent: "engine",
    color: "#f4f4f2",
    kind: "vacuum",
    note: "REF is the downstream tap, closer to the intake. Smaller hose than HI. Exhaust pressure, so do not tee it into a vacuum line.",
    points: [
      [0.26, 0.8, -0.72],
      [0.24, 0.7, -0.78],
      [0.2, 0.62, -0.86],
    ],
  },
  {
    id: "hose-evap",
    name: "EVAP purge hose",
    system: "fuel",
    parent: null,
    color: "#7eb0d6",
    kind: "evap",
    note: "EVAP, blue. The purge valve on a 1999–2004 Mustang sits behind the passenger front liner, not on the intake. This hose is the run from that valve to the throttle body.",
    points: [
      [0.7, 0.52, -1.36],
      [0.4, 0.7, -1.3],
      [0.08, 0.86, -1.26],
    ],
  },
  {
    id: "hose-fuel",
    name: "Fuel supply hose",
    system: "fuel",
    parent: null,
    color: "#c45a4a",
    kind: "fuel",
    note: "Fuel, red so it stands apart from the steel line. Filter toward the rail.",
    points: [
      [-0.48, 0.36, -0.15],
      [-0.1, 0.55, -0.55],
      [0.06, 0.8, -0.95],
    ],
  },
  {
    id: "hose-ps-high",
    name: "Power-steering pressure",
    system: "drivetrain",
    parent: null,
    color: "#6b4a32",
    kind: "steer",
    note: "Power steering, brown. Pump to the rack. The high side is the firmer hose.",
    points: [
      [-0.22, 0.62, -1.16],
      [-0.15, 0.5, -1.28],
      [0, 0.36, -1.34],
    ],
  },
  {
    id: "hose-ps-return",
    name: "Power-steering return",
    system: "drivetrain",
    parent: null,
    color: "#8a6a48",
    kind: "steer",
    note: "Power steering return, lighter brown. Rack back to the pump reservoir.",
    points: [
      [0.15, 0.36, -1.32],
      [-0.05, 0.48, -1.22],
      [-0.18, 0.58, -1.16],
    ],
  },
];

export function runsFor(spec: CarSpec): ServiceRun[] {
  const v6 = spec.pack === "mustang" && spec.engine === "v6";
  const v8 = spec.engine === "v8-2v" || spec.engine === "v8-4v";
  const count = v6 ? 6 : v8 ? 8 : 4;
  const coil: [number, number, number] = v6 ? [0.22, 0.94, -1.08] : [0.06, 0.98, -1.05];
  const wires = Array.from({ length: count }, (_, index) => {
    const end = v6 ? V6[index]! : ([0.2 - (index > 3 ? 0.42 : 0), 0.86, -1.15 + (index % 4) * 0.12] as [number, number, number]);
    return wire(index + 1, end, [coil[0] + (index - count / 2) * 0.015, coil[1], coil[2]]);
  });
  return [...HOSES, ...wires];
}

export function runById(spec: CarSpec, id: string) {
  return runsFor(spec).find((run) => run.id === id) ?? null;
}
