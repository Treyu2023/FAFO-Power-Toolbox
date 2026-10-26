import type { CarSpec } from "@/lib/auto/resolve";
import type { SystemId } from "@/lib/auto/scene-types";
import { PRIMS, type Prim } from "@/lib/auto/geometry";
import { runsFor, runById } from "@/lib/auto/hoses";

export type GroupInfo = {
  id: string;
  name: string;
  system: Exclude<SystemId, "all">;
  parent: string | null;
  stage: number;
  explode: [number, number, number];
  extra: [number, number, number];
};

type Sys = GroupInfo["system"];
const Z: [number, number, number] = [0, 0, 0];

function g(
  id: string,
  name: string,
  system: Sys,
  parent: string | null,
  stage: number,
  explode: [number, number, number],
  extra: [number, number, number] = Z,
): GroupInfo {
  return { id, name, system, parent, stage, explode, extra };
}

export const GROUPS: GroupInfo[] = [
  g("unibody", "Body shell", "chassis", null, 4, [0, -0.35, 0]),
  g("hood", "Hood", "body", null, 1, [0, 1.55, -0.4]),
  g("fender-fl", "Left front fender", "body", null, 1, [-1.4, 0.45, -0.2]),
  g("fender-fr", "Right front fender", "body", null, 1, [1.4, 0.45, -0.2]),
  g("door-l", "Left door", "body", null, 1, [-1.65, 0.2, 0]),
  g("door-r", "Right door", "body", null, 1, [1.65, 0.2, 0]),
  g("quarter-l", "Left quarter", "body", null, 1, [-1.3, 0.45, 0.3]),
  g("quarter-r", "Right quarter", "body", null, 1, [1.3, 0.45, 0.3]),
  g("roof", "Roof and glass", "body", null, 1, [0, 1.75, 0.05]),
  g("trunk", "Trunk lid", "body", null, 1, [0, 1.2, 0.95]),
  g("bumper-f", "Front bumper and lamps", "body", null, 1, [0, 0.15, -1.35]),
  g("bumper-r", "Rear bumper and lamps", "body", null, 1, [0, 0.25, 1.2]),
  g("mirror-l", "Left mirror", "body", null, 1, [-0.75, 0.75, 0.1]),
  g("mirror-r", "Right mirror", "body", null, 1, [0.75, 0.75, 0.1]),
  g("rocker-l", "Left rocker", "body", null, 1, [-0.9, -0.15, 0]),
  g("rocker-r", "Right rocker", "body", null, 1, [0.9, -0.15, 0]),
  g("engine", "Engine", "drivetrain", null, 2, [0.2, 1.85, -1.55], [0, 0.35, -0.35]),
  g("head-l", "Left head", "drivetrain", "engine", 3, [-0.75, 0.3, 0]),
  g("head-r", "Right head", "drivetrain", "engine", 3, [0.8, 0.25, 0]),
  g("intake", "Intake", "drivetrain", "engine", 3, [0, 1.15, -0.2], [0, 0.35, 0]),
  g("pcv", "PCV valve", "drivetrain", "head-l", 4, [-0.2, 0.25, 0.1]),
  g("pcv-fresh", "PCV fresh air", "drivetrain", "head-r", 4, [0.25, 0.2, 0.1]),
  g("egr", "EGR valve", "drivetrain", "intake", 4, [0.3, 0.15, 0.25]),
  g("evr", "EGR vacuum solenoid", "drivetrain", "intake", 4, [0.4, 0.3, 0.05]),
  g("dpfe", "DPFE sensor", "drivetrain", "intake", 4, [0.35, 0.35, 0.15]),
  g("pan", "Oil pan", "drivetrain", "engine", 3, [0, -0.8, 0]),
  g("oil-filter", "Oil filter", "drivetrain", "pan", 4, [-0.35, -0.35, 0.1]),
  g("oil-fill", "Oil fill", "drivetrain", "head-l", 4, [-0.25, 0.35, 0]),
  g("belt", "Serpentine belt", "drivetrain", "engine", 4, [0, 0.2, -0.85]),
  g("plug-1", "Plug 1", "drivetrain", "engine", 4, [0.55, 0.2, -0.15]),
  g("plug-2", "Plug 2", "drivetrain", "engine", 4, [0.55, 0.15, 0]),
  g("plug-3", "Plug 3", "drivetrain", "engine", 4, [0.55, 0.1, 0.15]),
  g("plug-4", "Plug 4", "drivetrain", "engine", 4, [-0.55, 0.2, -0.15]),
  g("plug-5", "Plug 5", "drivetrain", "engine", 4, [-0.55, 0.15, 0]),
  g("plug-6", "Plug 6", "drivetrain", "engine", 4, [-0.55, 0.1, 0.15]),
  g("plug-7", "Plug 7", "drivetrain", "engine", 4, [0.6, 0.05, 0.25]),
  g("plug-8", "Plug 8", "drivetrain", "engine", 4, [-0.6, 0.05, 0.25]),
  g("rotating", "Crank and pistons", "drivetrain", "engine", 4, [0.9, 0.15, 0.15]),
  g("trans", "Transmission", "drivetrain", "engine", 3, [0, -0.1, 1.75], [0, -0.15, 0.45]),
  g("trans-fill", "Transmission fill", "drivetrain", "trans", 4, [-0.45, 0.15, 0]),
  g("driveshaft", "Driveshaft", "drivetrain", "trans", 4, [0, -0.55, 0.85]),
  g("ujoint-f", "Front u-joint", "drivetrain", "driveshaft", 4, [0, -0.2, -0.25]),
  g("ujoint-r", "Rear u-joint", "drivetrain", "driveshaft", 4, [0, -0.2, 0.25]),
  g("radiator", "Radiator", "drivetrain", null, 2, [0, 0.4, -1.25]),
  g("rad-cap", "Radiator cap", "drivetrain", "radiator", 3, [0, 0.45, -0.15]),
  g("coolant-tank", "Coolant reservoir", "drivetrain", "radiator", 3, [0.45, 0.35, 0.2]),
  g("airbox", "Air box", "drivetrain", null, 2, [-1.2, 0.6, -0.25]),
  g("air-element", "Engine air filter", "drivetrain", "airbox", 3, [0, 0.45, 0]),
  g("cabin-filter", "Cabin filter slot", "body", null, 2, [0.4, 0.9, -0.2]),
  g("axle", "Rear axle", "drivetrain", null, 2, [0, -1.05, 0.6]),
  g("exhaust", "Exhaust", "drivetrain", null, 2, [0.95, -0.5, 0]),
  g("booster", "Brake booster", "brakes", null, 2, [-0.9, 0.45, -0.15]),
  g("suspension-f", "Front suspension", "brakes", null, 2, [0, -0.9, -0.35]),
  g("boot-fl", "Left ball-joint boot", "brakes", "suspension-f", 4, [-0.35, -0.25, 0]),
  g("boot-fr", "Right ball-joint boot", "brakes", "suspension-f", 4, [0.35, -0.25, 0]),
  g("boot-tie-l", "Left tie-rod boot", "brakes", "suspension-f", 4, [-0.3, -0.15, -0.2]),
  g("boot-tie-r", "Right tie-rod boot", "brakes", "suspension-f", 4, [0.3, -0.15, -0.2]),
  g("suspension-r", "Rear suspension", "brakes", null, 2, [0, -0.75, 0.45]),
  g("wheel-fl", "Left front wheel", "brakes", null, 2, [-1.4, 0, 0]),
  g("wheel-fr", "Right front wheel", "brakes", null, 2, [1.4, 0, 0]),
  g("wheel-rl", "Left rear wheel", "brakes", null, 2, [-1.4, 0, 0]),
  g("wheel-rr", "Right rear wheel", "brakes", null, 2, [1.4, 0, 0]),
  g("brake-fl", "Left front brake", "brakes", "wheel-fl", 3, [0.25, 0.8, 0]),
  g("brake-fr", "Right front brake", "brakes", "wheel-fr", 3, [-0.25, 0.8, 0]),
  g("brake-rl", "Left rear brake", "brakes", "wheel-rl", 3, [0.25, 0.8, 0]),
  g("brake-rr", "Right rear brake", "brakes", "wheel-rr", 3, [-0.25, 0.8, 0]),
  g("fuel-tank", "Fuel tank", "fuel", null, 2, [0, -1.3, 0.5]),
  g("fuel-pump", "Fuel pump", "fuel", "fuel-tank", 3, [0, 1.0, 0]),
  g("fuel-line", "Fuel line and filter", "fuel", null, 2, [-0.2, 0.85, 0]),
  g("evap-canister", "EVAP canister", "fuel", null, 2, [-1.15, 0.4, 0.1]),
  g("evap-purge", "Purge valve", "fuel", null, 2, [1.05, 0.65, -0.15]),
  g("inertia-switch", "Inertia switch", "fuel", null, 2, [-0.95, 0.75, 0.4]),
  g("battery", "Battery", "electrical", null, 2, [1.2, 0.95, -0.25]),
  g("pdb", "Under-hood fuse box", "electrical", null, 2, [0.45, 1.35, -0.55]),
  g("cabin-electric", "Dash electrical", "electrical", null, 3, [-0.2, 1.35, -0.15]),
  g("interior", "Interior", "body", null, 3, [0, 1.65, 0.15]),
];

const CLAIM: Record<string, string> = {
  floor: "unibody",
  firewall: "unibody",
  tunnel: "unibody",
  "tower-l": "unibody",
  "tower-r": "unibody",
  "core-support": "unibody",
  "glass-door-l": "door-l",
  "glass-door-r": "door-r",
  "scoop-l": "quarter-l",
  "scoop-r": "quarter-r",
  "fuel-door": "quarter-l",
  windshield: "roof",
  "rear-glass": "roof",
  grille: "bumper-f",
  "headlamp-l": "bumper-f",
  "headlamp-r": "bumper-f",
  "taillamp-l": "bumper-r",
  "taillamp-r": "bumper-r",
  "engine-block": "engine",
  "front-cover": "engine",
  balancer: "engine",
  "water-pump": "engine",
  "fan-clutch": "engine",
  ckp: "engine",
  alternator: "engine",
  "ps-pump": "engine",
  "ac-compressor": "engine",
  starter: "engine",
  "pulley-alt": "belt",
  "pulley-crank": "belt",
  "pulley-wp": "belt",
  "pulley-ps": "belt",
  "pulley-ac": "belt",
  "pulley-idler": "belt",
  belt: "belt",
  tensioner: "belt",
  "timing-chain": "engine",
  "oil-pump": "engine",
  dipstick: "engine",
  "valve-cover-l": "head-l",
  "valves-l": "head-l",
  "rockers-l": "head-l",
  "plugs-l": "head-l",
  "manifold-l": "head-l",
  "valve-cover-r": "head-r",
  "valves-r": "head-r",
  "rockers-r": "head-r",
  "plugs-r": "head-r",
  "manifold-r": "head-r",
  "intake-gasket": "intake",
  "intake-lower": "intake",
  "intake-upper": "intake",
  "throttle-body": "intake",
  iac: "intake",
  thermostat: "intake",
  "fuel-rail": "intake",
  injectors: "intake",
  "coil-pack": "intake",
  tps: "intake",
  ect: "intake",
  "oil-pan": "pan",
  crank: "rotating",
  pistons: "rotating",
  rods: "rotating",
  cam: "rotating",
  pushrods: "rotating",
  clutch: "trans",
  flywheel: "trans",
  "torque-converter": "trans",
  vss: "trans",
  "exhaust-l": "exhaust",
  "exhaust-r": "exhaust",
  cat: "exhaust",
  muffler: "exhaust",
  "o2-up": "exhaust",
  "o2-down": "exhaust",
  "strut-fl": "suspension-f",
  "strut-fr": "suspension-f",
  "lca-fl": "suspension-f",
  "lca-fr": "suspension-f",
  swaybar: "suspension-f",
  rack: "suspension-f",
  "spring-rl": "suspension-r",
  "spring-rr": "suspension-r",
  "shock-rl": "suspension-r",
  "shock-rr": "suspension-r",
  "quad-l": "suspension-r",
  "quad-r": "suspension-r",
  "uca-l": "suspension-r",
  "uca-r": "suspension-r",
  "rotor-fl": "brake-fl",
  "caliper-fl": "brake-fl",
  "rotor-fr": "brake-fr",
  "caliper-fr": "brake-fr",
  "drum-rl": "brake-rl",
  "drum-rr": "brake-rr",
  "rotor-rl": "brake-rl",
  "rotor-rr": "brake-rr",
  "tank-shield": "fuel-tank",
  "tank-strap-l": "fuel-tank",
  "tank-strap-r": "fuel-tank",
  "filler-neck": "fuel-tank",
  "filler-grommet": "fuel-tank",
  "fuel-cap": "fuel-tank",
  "tank-pressure": "fuel-tank",
  "vapor-valve": "fuel-tank",
  "pump-gasket": "fuel-pump",
  "pump-sock": "fuel-pump",
  "fuel-filter": "fuel-line",
  "evap-vent": "evap-canister",
  ccrm: "pdb",
  "starter-relay": "pdb",
  "fuse-panel": "cabin-electric",
  pcm: "cabin-electric",
  "ignition-switch": "cabin-electric",
  "clutch-switch": "cabin-electric",
  "brake-switch": "cabin-electric",
  "headlamp-switch": "cabin-electric",
  "seat-l": "interior",
  "seat-r": "interior",
  dash: "interior",
  cluster: "interior",
  column: "interior",
  "steer-wheel": "interior",
  shifter: "interior",
  console: "interior",
  pedals: "interior",
  "zerk-fl": "boot-fl",
  "zerk-fr": "boot-fr",
  "zerk-shaft": "ujoint-f",
  "coolant-cap": "coolant-tank",
};

const V6_ONLY = new Set([
  "pushrods",
  "rockers-l",
  "rockers-r",
  "cam",
  "coil-pack",
]);

export function groupIdOf(primId: string) {
  return CLAIM[primId] ?? primId;
}

function alum(): string {
  return "#b7bdc6";
}

function engineAlt(spec: CarSpec): Prim[] {
  const v8 = spec.engine === "v8-2v" || spec.engine === "v8-4v";
  const wide = v8 ? 0.62 : 0.34;
  const tall = spec.engine === "v8-4v" ? 0.16 : 0.1;
  const block: Prim = {
    id: "engine-block",
    shape: "box",
    pos: [0.06, 0.55, -0.95],
    args: [wide, v8 ? 0.36 : 0.28, v8 ? 0.58 : 0.46],
    color: v8 ? alum() : "#5c6168",
    metal: 0.55,
    rough: 0.4,
  };
  const covers: Prim[] = v8
    ? [
        { id: "valve-cover-l", shape: "box", pos: [-0.28, 0.78, -0.95], args: [0.1, 0.06, 0.5], color: "#1a1c20", rough: 0.45 },
        { id: "valve-cover-r", shape: "box", pos: [0.4, 0.78, -0.95], args: [0.1, 0.06, 0.5], color: "#1a1c20", rough: 0.45 },
        { id: "head-l", shape: "box", pos: [-0.22, 0.7, -0.95], args: [0.14, 0.1, 0.52], color: alum(), metal: 0.5, rough: 0.4 },
        { id: "head-r", shape: "box", pos: [0.34, 0.7, -0.95], args: [0.14, 0.1, 0.52], color: alum(), metal: 0.5, rough: 0.4 },
      ]
    : [
        { id: "head-l", shape: "box", pos: [0.06, 0.72, -0.95], args: [0.22, 0.08, 0.4], color: alum(), metal: 0.45, rough: 0.4 },
        { id: "valve-cover-l", shape: "box", pos: [0.06, 0.78, -0.95], args: [0.18, 0.04, 0.36], color: "#1a1c20" },
      ];
  return [
    block,
    ...covers,
    { id: "intake-upper", shape: "box", pos: [0.06, 0.86 + tall, -1.0], args: [0.22, 0.1 + tall * 0.3, 0.34], color: alum(), metal: 0.4, rough: 0.35 },
    { id: "throttle-body", shape: "box", pos: [0.06, 0.84, -1.28], args: [0.1, 0.1, 0.1], color: alum() },
    { id: "oil-pan", shape: "box", pos: [0.06, 0.32, -0.95], args: [wide * 0.8, 0.08, 0.42], color: "#9aa0a8", metal: 0.55, rough: 0.4 },
    { id: "alternator", shape: "box", pos: [0.46, 0.58, -1.15], args: [0.12, 0.12, 0.12], color: alum() },
    { id: "starter", shape: "cyl", pos: [0.32, 0.34, -0.78], args: [0.05, 0.05, 0.16, 12], color: "#9aa0a8", rot: [0, 0, Math.PI / 2], metal: 0.55 },
    { id: "water-pump", shape: "box", pos: [0.06, 0.58, -1.3], args: [0.16, 0.14, 0.08], color: alum() },
    { id: "oil-fill", shape: "cyl", pos: [0.06, 0.84, -1.05], args: [0.03, 0.03, 0.02, 12], color: "#c4a24a" },
    { id: "belt", shape: "torus", pos: [0.1, 0.55, -1.32], args: [0.18, 0.012, 8, 20], color: "#1c1c1e", rot: [Math.PI / 2, 0, 0], rough: 0.8 },
    ...[0, 1, 2, 3].map((index) => ({
      id: `plug-${index + 1}`,
      shape: "cyl" as const,
      pos: [0.2, 0.84, -1.15 + index * 0.12] as [number, number, number],
      args: [0.012, 0.012, 0.05, 8],
      color: "#d7dbe2",
      rot: [0, 0, Math.PI / 2] as [number, number, number],
      metal: 0.8,
    })),
    ...(v8
      ? [4, 5, 6, 7].map((index) => ({
          id: `plug-${index + 1}`,
          shape: "cyl" as const,
          pos: [-0.22, 0.84, -1.15 + (index - 4) * 0.12] as [number, number, number],
          args: [0.012, 0.012, 0.05, 8],
          color: "#d7dbe2",
          rot: [0, 0, Math.PI / 2] as [number, number, number],
          metal: 0.8,
        }))
      : []),
  ];
}

export function primsFor(spec: CarSpec): Prim[] {
  const manual = spec.trans !== "auto";
  const drums = spec.pack === "mustang" && spec.engine === "v6";
  const v6 = spec.pack === "mustang" && spec.engine === "v6";
  const list = PRIMS.filter((prim) => {
    if (prim.only === "t5" && !manual) return false;
    if (prim.only === "4r70w" && manual) return false;
    if (!spec.scoop && (prim.id === "scoop-l" || prim.id === "scoop-r")) return false;
    if (spec.body === "convertible" && (prim.id === "roof" || prim.id === "rear-glass")) return false;
    if (!drums && (prim.id === "drum-rl" || prim.id === "drum-rr")) return false;
    if (!v6 && (V6_ONLY.has(prim.id) || ["engine-block", "head-l", "head-r", "valve-cover-l", "valve-cover-r", "intake-gasket", "intake-lower", "intake-upper", "throttle-body", "oil-pan", "oil-fill", "alternator", "starter", "water-pump", "pistons", "rods", "crank", "manifold-l", "manifold-r", "plug-1", "plug-2", "plug-3", "plug-4", "plug-5", "plug-6", "belt", "pulley-crank", "pulley-wp", "pulley-alt", "pulley-ps", "pulley-ac", "pulley-idler", "tensioner"].includes(prim.id))) return false;
    if (spec.pack === "common" && (prim.id === "inertia-switch" || prim.id.startsWith("taillamp") || prim.id === "ccrm")) return false;
    return true;
  });
  if (!v6) list.push(...engineAlt(spec));
  if (!drums) {
    list.push(
      { id: "rotor-rl", shape: "cyl", pos: [-0.7, 0.33, 1.28], args: [0.14, 0.14, 0.02, 20], color: "#9aa0a8", rot: [0, 0, Math.PI / 2], metal: 0.75, rough: 0.3 },
      { id: "rotor-rr", shape: "cyl", pos: [0.7, 0.33, 1.28], args: [0.14, 0.14, 0.02, 20], color: "#9aa0a8", rot: [0, 0, Math.PI / 2], metal: 0.75, rough: 0.3 },
    );
  }
  return list;
}

export function groupsFor(spec: CarSpec): GroupInfo[] {
  const prims = primsFor(spec);
  const runs = runsFor(spec);
  const extra = runs.map((run) => g(run.id, run.name, run.system, run.parent, run.kind === "wire" ? 4 : 3, run.kind === "wire" ? [0, 0.28, 0] : [0, 0.4, 0]));
  const all = [...GROUPS, ...extra];
  const used = new Set(prims.map((prim) => groupIdOf(prim.id)));
  used.add("unibody");
  for (const run of runs) used.add(run.id);
  const keep = new Set<string>();
  for (const id of used) {
    let current: string | null = id;
    while (current) {
      keep.add(current);
      current = all.find((item) => item.id === current)?.parent ?? null;
    }
  }
  return all.filter((item) => keep.has(item.id));
}

export function partBlurb(id: string, spec: CarSpec): { name: string; checks: string[] } {
  const run = runById(spec, id);
  if (run) return { name: run.name, checks: [run.note] };
  const found = GROUPS.find((item) => item.id === id);
  const name = found?.name ?? id;
  if (spec.pack === "mustang" && (id === "fuel-pump" || id === "inertia-switch" || id === "pdb")) {
    return { name, checks: ["Use the fuel-pump power walk. Do not drop the tank until a step says the pump is dead."] };
  }
  if (id === "engine") {
    return {
      name,
      checks: [
        spec.engine === "v6"
          ? "This is the 3.8 pushrod V6. The upper intake and the coil pack sit on top."
          : spec.engine === "v8-4v"
            ? "This is the 4.6 4-valve. The intake is taller than the GT's 2-valve."
            : spec.engine === "v8-2v"
              ? "This is the 4.6 2-valve. It is not the 3.8, and it does not use that intake."
              : "Inline four. Do not order a V6 or V8 part for it.",
      ],
    };
  }
  if (id === "trans") {
    return {
      name,
      checks: [
        spec.trans === "auto"
          ? "Automatic. On the 2001 Mustang that is the 4R70W."
          : spec.engine === "v6"
            ? "Manual. On the V6 that is the T-5."
            : "Manual. On the GT that is the TR-3650, unless the car was built before about February 2001, when it may be a T-45.",
      ],
    };
  }
  if (id === "axle") {
    return {
      name,
      checks: [
        spec.axle === "irs"
          ? "Independent rear. Do not order a solid-axle bearing."
          : spec.engine === "v6"
            ? "7.5-inch solid axle on the V6."
            : "8.8-inch solid axle on the GT and the Bullitt.",
      ],
    };
  }
  if (id === "oil-fill") return { name, checks: ["Driver valve cover, toward the front. The cap is the yellow one. Wipe the neck before the new oil goes in."] };
  if (id === "oil-filter") return { name, checks: ["Driver side of the block, low. It is easier from underneath. Oil the new gasket and do not double-gasket the old one."] };
  if (id === "rad-cap" || id === "coolant-tank") return { name, checks: ["Do not open either cap hot. The radiator cap is the pressure cap. The bottle on the passenger side is the reservoir."] };
  if (id === "trans-fill") {
    return {
      name,
      checks: [
        spec.trans === "auto"
          ? "4R70W. The dipstick tube is the fill and the check. Check it hot, idling, in Park. A cold reading lies."
          : "T-5. The side plug is both the fill and the check. Fluid should be at the hole. There is no dipstick.",
      ],
    };
  }
  if (id.startsWith("boot-") || id.startsWith("ujoint")) return { name, checks: ["The stock joint is often sealed. Inspect the boot. Grease it only if a fitting is actually on it."] };
  if (id === "air-element" || id === "airbox") return { name, checks: ["Engine filter is in the box on the driver side. Hold it up to a light. If you cannot see light, it is done."] };
  if (id === "cabin-filter") {
    return {
      name,
      checks: [
        spec.pack === "mustang"
          ? "A 2001 Mustang has no factory cabin filter. This mark is the cowl, which is where people go looking."
          : "Under the cowl at the base of the windshield. That is the usual cabin-filter slot on a common car.",
      ],
    };
  }
  if (id.startsWith("plug-")) {
    return {
      name,
      checks: [
        spec.pack === "mustang" && spec.engine === "v6"
          ? "Passenger bank is 1, 2, 3 from the front. Driver bank is 4, 5, 6 from the front. Firing order is 1-4-2-5-3-6."
          : "The numbers start at the front. Do not guess the firing order from the number alone.",
      ],
    };
  }
  if (id === "belt" || id === "alternator") return { name, checks: ["The belt sketch is the front drive: crank, water pump, alternator, power steering, A/C, and the tensioner. Use the decal on the radiator support if it is still there."] };
  return { name, checks: ["Look at the part, the connector, and the fastener before you replace it."] };
}
