import type { Circuit } from "./types";

export type DiagramNode = {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  label: string;
  sub?: string;
};

export type DiagramWire = {
  id: string;
  circuit: Circuit;
  ends: string[];
  routes: [number, number][][];
};

export const NODES: DiagramNode[] = [
  { id: "battery", x: 16, y: 28, w: 132, h: 48, label: "Battery", sub: "BXT-59" },
  { id: "cable-neg", x: 16, y: 92, w: 132, h: 40, label: "Negative", sub: "Body ground" },
  { id: "ignition-switch", x: 16, y: 168, w: 132, h: 44, label: "Ignition switch", sub: "Column" },
  { id: "clutch-switch", x: 16, y: 224, w: 132, h: 44, label: "Clutch switch", sub: "Pedal" },
  { id: "fuse-panel", x: 16, y: 292, w: 132, h: 44, label: "Dash fuses", sub: "Left knee" },
  { id: "headlamp-switch", x: 16, y: 352, w: 132, h: 44, label: "Lamp switch", sub: "Dash" },
  { id: "brake-switch", x: 16, y: 412, w: 132, h: 44, label: "Brake switch", sub: "Pedal" },

  { id: "pdb", x: 196, y: 28, w: 140, h: 48, label: "Power box", sub: "Radiator support" },
  { id: "starter-relay", x: 196, y: 92, w: 140, h: 40, label: "Starter relay", sub: "In the power box" },
  { id: "ccrm", x: 196, y: 156, w: 140, h: 48, label: "CCRM", sub: "Pump & PCM relays" },
  { id: "pcm", x: 196, y: 228, w: 140, h: 56, label: "PCM", sub: "EEC-V, kick panel" },
  { id: "dpfe", x: 196, y: 304, w: 140, h: 40, label: "DPFE", sub: "EGR hoses" },
  { id: "maf", x: 196, y: 360, w: 140, h: 40, label: "MAF", sub: "Air duct" },
  { id: "tps", x: 196, y: 412, w: 140, h: 36, label: "TPS", sub: "Throttle" },
  { id: "ect", x: 196, y: 458, w: 140, h: 36, label: "ECT", sub: "Coolant" },

  { id: "alternator", x: 392, y: 28, w: 136, h: 44, label: "Alternator", sub: "B+ stud" },
  { id: "starter", x: 392, y: 88, w: 136, h: 44, label: "Starter", sub: "Passenger block" },
  { id: "ckp", x: 392, y: 148, w: 136, h: 40, label: "Crank sensor", sub: "Front cover" },
  { id: "coil-pack", x: 392, y: 204, w: 136, h: 44, label: "Coil pack", sub: "EDIS" },
  { id: "inertia-switch", x: 392, y: 268, w: 136, h: 48, label: "Inertia switch", sub: "Trunk, driver" },
  { id: "fuel-rail", x: 392, y: 332, w: 136, h: 40, label: "Fuel rail", sub: "Schrader" },
  { id: "o2-up", x: 392, y: 388, w: 136, h: 36, label: "O2 upstream", sub: "M18×1.5" },
  { id: "o2-down", x: 392, y: 434, w: 136, h: 36, label: "O2 downstream", sub: "After the cat" },

  { id: "fuel-pump", x: 584, y: 268, w: 140, h: 48, label: "Fuel pump", sub: "In the tank" },
  { id: "plugs-r", x: 584, y: 188, w: 140, h: 40, label: "Plugs 1-2-3", sub: "Passenger bank" },
  { id: "plugs-l", x: 584, y: 140, w: 140, h: 40, label: "Plugs 4-5-6", sub: "Driver bank" },
  { id: "injectors", x: 584, y: 332, w: 140, h: 40, label: "Injectors", sub: "Six, sequential" },
  { id: "iac", x: 584, y: 388, w: 140, h: 36, label: "IAC", sub: "Idle air" },
  { id: "vss", x: 584, y: 434, w: 140, h: 36, label: "VSS", sub: "Tailshaft" },
  { id: "headlamp-l", x: 584, y: 28, w: 140, h: 36, label: "Headlamp L", sub: "Driver" },
  { id: "headlamp-r", x: 740, y: 28, w: 120, h: 36, label: "Headlamp R", sub: "Passenger" },
  { id: "taillamp-l", x: 584, y: 78, w: 140, h: 36, label: "Tail lamp L", sub: "Tri-bar" },
  { id: "taillamp-r", x: 740, y: 78, w: 120, h: 36, label: "Tail lamp R", sub: "Tri-bar" },
  { id: "cluster", x: 740, y: 228, w: 120, h: 44, label: "Cluster", sub: "Gauges" },
];

export const WIRES: DiagramWire[] = [
  {
    id: "cable-pos",
    circuit: "power",
    ends: ["battery", "pdb", "alternator"],
    routes: [
      [
        [148, 52],
        [196, 52],
      ],
      [
        [336, 52],
        [392, 50],
      ],
    ],
  },
  {
    id: "cable-start",
    circuit: "start",
    ends: ["pdb", "starter-relay", "starter"],
    routes: [
      [
        [266, 76],
        [266, 92],
      ],
      [
        [336, 112],
        [392, 110],
      ],
    ],
  },
  {
    id: "cable-neg",
    circuit: "ground",
    ends: ["battery", "ground-engine"],
    routes: [
      [
        [82, 76],
        [82, 92],
      ],
    ],
  },
  {
    id: "harness-pcm",
    circuit: "power",
    ends: ["ccrm", "pcm"],
    routes: [
      [
        [266, 204],
        [266, 228],
      ],
    ],
  },
  {
    id: "harness-fuel",
    circuit: "fuel",
    ends: ["ccrm", "inertia-switch", "fuel-pump"],
    routes: [
      [
        [336, 180],
        [392, 292],
      ],
      [
        [528, 292],
        [584, 292],
      ],
    ],
  },
  {
    id: "harness-edis",
    circuit: "ignition",
    ends: ["pcm", "ckp", "coil-pack"],
    routes: [
      [
        [336, 256],
        [364, 256],
        [364, 168],
        [392, 168],
      ],
      [
        [364, 226],
        [392, 226],
      ],
    ],
  },
  {
    id: "plug-wires",
    circuit: "ignition",
    ends: ["coil-pack", "plugs-l", "plugs-r"],
    routes: [
      [
        [528, 220],
        [556, 220],
        [556, 160],
        [584, 160],
      ],
      [
        [556, 208],
        [584, 208],
      ],
    ],
  },
  {
    id: "harness-inj",
    circuit: "fuel",
    ends: ["pcm", "fuel-rail", "injectors"],
    routes: [
      [
        [336, 270],
        [392, 352],
      ],
      [
        [528, 352],
        [584, 352],
      ],
    ],
  },
  {
    id: "harness-sensors",
    circuit: "sensor",
    ends: ["pcm", "maf", "tps", "ect", "iac", "o2-up", "o2-down", "dpfe", "vss"],
    routes: [
      [
        [266, 284],
        [266, 304],
      ],
      [
        [236, 284],
        [196, 380],
      ],
      [
        [250, 300],
        [196, 430],
      ],
      [
        [250, 300],
        [196, 476],
      ],
      [
        [336, 270],
        [520, 406],
        [584, 406],
      ],
      [
        [336, 256],
        [392, 406],
      ],
      [
        [392, 452],
        [470, 452],
      ],
      [
        [336, 270],
        [520, 452],
        [584, 452],
      ],
    ],
  },
  {
    id: "harness-start",
    circuit: "start",
    ends: ["ignition-switch", "clutch-switch", "starter-relay"],
    routes: [
      [
        [148, 190],
        [172, 190],
        [172, 246],
        [148, 246],
      ],
      [
        [172, 190],
        [196, 112],
      ],
    ],
  },
  {
    id: "harness-lamps",
    circuit: "lamps",
    ends: ["headlamp-switch", "fuse-panel", "headlamp-l", "headlamp-r"],
    routes: [
      [
        [82, 336],
        [82, 352],
      ],
      [
        [148, 374],
        [760, 374],
        [760, 64],
        [654, 46],
      ],
      [
        [760, 46],
        [740, 46],
      ],
    ],
  },
  {
    id: "harness-tails",
    circuit: "lamps",
    ends: ["brake-switch", "taillamp-l", "taillamp-r"],
    routes: [
      [
        [148, 434],
        [760, 434],
        [760, 114],
        [654, 96],
      ],
      [
        [760, 96],
        [740, 96],
      ],
    ],
  },
  {
    id: "pigtail-cluster",
    circuit: "sensor",
    ends: ["fuse-panel", "cluster"],
    routes: [
      [
        [148, 314],
        [800, 314],
        [800, 272],
      ],
    ],
  },
  {
    id: "fuel-line",
    circuit: "fuel",
    ends: ["fuel-pump", "fuel-filter", "fuel-rail"],
    routes: [
      [
        [654, 316],
        [654, 332],
        [528, 352],
      ],
    ],
  },
];

const WIRE_BY_ID = new Map(WIRES.map((w) => [w.id, w]));

export function traceOf(id: string | null): string[] {
  if (!id) return [];
  const hit = new Set<string>([id]);
  const wire = WIRE_BY_ID.get(id);
  if (wire) {
    for (const end of wire.ends) hit.add(end);
    return [...hit];
  }
  for (const item of WIRES) {
    if (item.ends.includes(id)) hit.add(item.id);
  }
  return [...hit];
}

export function wireCircuit(id: string): Circuit | undefined {
  return WIRE_BY_ID.get(id)?.circuit;
}
