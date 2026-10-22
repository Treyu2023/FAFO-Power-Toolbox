import * as THREE from "three";
import type { Trans } from "./types";

/** Side-profile coupe, extruded to width. Nose points toward -Z. */
export function createCoupeGeometry() {
  const shape = new THREE.Shape();
  shape.moveTo(-2.18, 0.2);
  shape.lineTo(-2.12, 0.38);
  shape.bezierCurveTo(-2.08, 0.62, -1.95, 0.8, -1.62, 0.84);
  shape.lineTo(-0.58, 0.88);
  shape.lineTo(-0.08, 1.2);
  shape.lineTo(0.58, 1.2);
  shape.lineTo(0.98, 0.98);
  shape.lineTo(1.62, 0.93);
  shape.lineTo(1.98, 0.58);
  shape.lineTo(2.08, 0.32);
  shape.lineTo(2.08, 0.2);
  shape.lineTo(-2.18, 0.2);

  for (const z of [-1.26, 1.28]) {
    const hole = new THREE.Path();
    hole.absarc(z, 0.33, 0.4, 0, Math.PI * 2, true);
    shape.holes.push(hole);
  }

  const geo = new THREE.ExtrudeGeometry(shape, {
    depth: 1.68,
    bevelEnabled: false,
    curveSegments: 10,
  });
  geo.translate(0, 0, -0.84);
  geo.rotateY(-Math.PI / 2);
  geo.computeVertexNormals();
  return geo;
}

const _coupe = { geo: null as THREE.BufferGeometry | null };
export function coupeGeometry() {
  if (!_coupe.geo) _coupe.geo = createCoupeGeometry();
  return _coupe.geo;
}

export type Prim = {
  id: string;
  shape: "box" | "cyl" | "sph" | "torus";
  args: number[];
  pos: [number, number, number];
  rot?: [number, number, number];
  color: string;
  paint?: boolean;
  opacity?: number;
  emissive?: string;
  emissiveIntensity?: number;
  rough?: number;
  metal?: number;
  radius?: number;
  shadow?: boolean;
  only?: Trans;
};

const RUBBER = "#1c1c1e";
const BLACK = "#121214";
const STEEL = "#9aa0a8";
const IRON = "#5c6168";
const GLASS = "#8ea6b6";
const CHROME = "#d7dbe2";
const RED = "#9a2424";
const AMBER = "#c47a32";
const PAINT = "#8f1d22";

type V3 = [number, number, number];
type Extra = Partial<Omit<Prim, "id" | "shape" | "args" | "pos" | "color">>;

function box(id: string, pos: V3, size: V3, color: string, extra: Extra = {}): Prim {
  return { id, shape: "box", pos, args: size, color, shadow: true, ...extra };
}
function cyl(id: string, pos: V3, args: number[], color: string, extra: Extra = {}): Prim {
  return { id, shape: "cyl", pos, args, color, ...extra };
}
function sph(id: string, pos: V3, r: number, color: string, extra: Extra = {}): Prim {
  return { id, shape: "sph", pos, args: [r, 16, 12], color, ...extra };
}
function torus(id: string, pos: V3, args: number[], color: string, extra: Extra = {}): Prim {
  return { id, shape: "torus", pos, args, color, ...extra };
}

function wheel(id: string, x: number, z: number): Prim[] {
  const y = 0.33;
  const rot: V3 = [0, 0, Math.PI / 2];
  return [
    cyl(id, [x, y, z], [0.325, 0.325, 0.2, 28], RUBBER, { rot, rough: 0.92, metal: 0.04, shadow: true }),
    cyl(id, [x, y, z], [0.2, 0.2, 0.16, 24], STEEL, { rot, metal: 0.72, rough: 0.32, shadow: true }),
    cyl(id, [x, y, z], [0.07, 0.07, 0.18, 12], "#2a2c30", { rot, metal: 0.4, rough: 0.5 }),
  ];
}

function tribar(id: string, x: number): Prim[] {
  const bars = [0.78, 0.7, 0.62];
  return bars.map((y, i) =>
    box(id, [x, y, 2.02], [0.42 - i * 0.04, 0.045, 0.06], RED, {
      emissive: RED,
      emissiveIntensity: 0.55,
      metal: 0.2,
      rough: 0.35,
      radius: 0.012,
    }),
  );
}

function headlamp(id: string, x: number): Prim[] {
  const s = Math.sign(x) || 1;
  return [
    box(id, [x, 0.62, -2.14], [0.34, 0.12, 0.08], "#e7eef6", {
      emissive: "#c5d0dc",
      emissiveIntensity: 0.55,
      metal: 0.15,
      rough: 0.25,
      radius: 0.02,
    }),
    box(id, [x + s * 0.2, 0.5, -2.12], [0.1, 0.07, 0.05], AMBER, {
      emissive: AMBER,
      emissiveIntensity: 0.35,
      radius: 0.01,
    }),
  ];
}

const P: Prim[] = [
  box("floor", [0, 0.22, 0.05], [1.4, 0.035, 3.55], "#3a3c40", { metal: 0.35, rough: 0.7, radius: 0.01 }),
  box("firewall", [0, 0.72, -0.18], [1.42, 0.72, 0.04], "#3e4146", { metal: 0.3, rough: 0.65 }),
  box("tunnel", [0, 0.34, 0.55], [0.32, 0.22, 1.7], "#3a3c40", { metal: 0.3, rough: 0.7, radius: 0.04 }),
  box("tower-l", [-0.5, 0.88, -1.26], [0.26, 0.28, 0.26], "#45484e", { metal: 0.35, rough: 0.55, radius: 0.02 }),
  box("tower-r", [0.5, 0.88, -1.26], [0.26, 0.28, 0.26], "#45484e", { metal: 0.35, rough: 0.55, radius: 0.02 }),
  box("core-support", [0, 0.58, -1.92], [1.45, 0.1, 0.06], IRON, { metal: 0.45, rough: 0.5 }),

  box("rocker-l", [-0.8, 0.32, 0.15], [0.08, 0.14, 2.15], PAINT, { paint: true, radius: 0.02 }),
  box("rocker-r", [0.8, 0.32, 0.15], [0.08, 0.14, 2.15], PAINT, { paint: true, radius: 0.02 }),
  box("hood", [0, 0.9, -1.2], [1.42, 0.04, 1.2], PAINT, { paint: true, radius: 0.02 }),
  box("fender-fl", [-0.74, 0.62, -1.25], [0.1, 0.32, 1.05], PAINT, { paint: true, radius: 0.02 }),
  box("fender-fr", [0.74, 0.62, -1.25], [0.1, 0.32, 1.05], PAINT, { paint: true, radius: 0.02 }),
  box("door-l", [-0.82, 0.72, 0.12], [0.05, 0.58, 1.05], PAINT, { paint: true, radius: 0.015 }),
  box("door-r", [0.82, 0.72, 0.12], [0.05, 0.58, 1.05], PAINT, { paint: true, radius: 0.015 }),
  box("door-l", [-0.86, 0.68, 0.42], [0.03, 0.06, 0.12], BLACK, { metal: 0.4, rough: 0.4, radius: 0.01 }),
  box("door-r", [0.86, 0.68, 0.42], [0.03, 0.06, 0.12], BLACK, { metal: 0.4, rough: 0.4, radius: 0.01 }),
  box("glass-door-l", [-0.86, 0.98, 0.12], [0.02, 0.26, 0.72], GLASS, { opacity: 0.45, metal: 0.2, rough: 0.08 }),
  box("glass-door-r", [0.86, 0.98, 0.12], [0.02, 0.26, 0.72], GLASS, { opacity: 0.45, metal: 0.2, rough: 0.08 }),
  box("quarter-l", [-0.76, 0.72, 1.15], [0.08, 0.42, 0.85], PAINT, { paint: true, radius: 0.02 }),
  box("quarter-r", [0.76, 0.72, 1.15], [0.08, 0.42, 0.85], PAINT, { paint: true, radius: 0.02 }),
  box("scoop-l", [-0.7, 0.96, 1.35], [0.16, 0.06, 0.28], BLACK, { radius: 0.015 }),
  box("scoop-r", [0.7, 0.96, 1.35], [0.16, 0.06, 0.28], BLACK, { radius: 0.015 }),
  box("roof", [0, 1.22, 0.28], [1.18, 0.04, 0.85], PAINT, { paint: true, radius: 0.02 }),
  box("windshield", [0, 1.02, -0.22], [1.2, 0.02, 0.58], GLASS, { rot: [0.5, 0, 0], opacity: 0.35, metal: 0.3, rough: 0.05 }),
  box("rear-glass", [0, 1.05, 0.9], [1.12, 0.02, 0.42], GLASS, { rot: [-0.55, 0, 0], opacity: 0.35, metal: 0.3, rough: 0.05 }),
  box("trunk", [0, 0.98, 1.5], [1.25, 0.04, 0.62], PAINT, { paint: true, radius: 0.015 }),
  box("fuel-door", [-0.78, 0.62, 1.55], [0.02, 0.12, 0.16], PAINT, { paint: true, radius: 0.01 }),
  box("bumper-f", [0, 0.36, -2.16], [1.55, 0.16, 0.1], PAINT, { paint: true, radius: 0.03 }),
  box("bumper-r", [0, 0.42, 2.08], [1.5, 0.16, 0.1], PAINT, { paint: true, radius: 0.03 }),
  box("grille", [0, 0.46, -2.16], [0.7, 0.16, 0.04], BLACK, { radius: 0.01 }),
  box("grille", [0, 0.5, -2.175], [0.62, 0.012, 0.02], "#2a2a2e"),
  box("grille", [0, 0.46, -2.175], [0.62, 0.012, 0.02], "#2a2a2e"),
  box("grille", [0, 0.42, -2.175], [0.62, 0.012, 0.02], "#2a2a2e"),

  ...headlamp("headlamp-l", -0.52),
  ...headlamp("headlamp-r", 0.52),
  ...tribar("taillamp-l", -0.55),
  ...tribar("taillamp-r", 0.55),

  box("mirror-l", [-0.98, 0.98, 0.02], [0.14, 0.08, 0.18], PAINT, { paint: true, radius: 0.02 }),
  box("mirror-l", [-1.06, 0.98, 0.02], [0.02, 0.06, 0.1], GLASS, { metal: 0.6, rough: 0.1 }),
  box("mirror-r", [0.98, 0.98, 0.02], [0.14, 0.08, 0.18], PAINT, { paint: true, radius: 0.02 }),
  box("mirror-r", [1.06, 0.98, 0.02], [0.02, 0.06, 0.1], GLASS, { metal: 0.6, rough: 0.1 }),

  ...wheel("wheel-fl", -0.84, -1.26),
  ...wheel("wheel-fr", 0.84, -1.26),
  ...wheel("wheel-rl", -0.84, 1.28),
  ...wheel("wheel-rr", 0.84, 1.28),

  cyl("rotor-fl", [-0.72, 0.33, -1.26], [0.14, 0.14, 0.02, 20], STEEL, { rot: [0, 0, Math.PI / 2], metal: 0.75, rough: 0.3 }),
  cyl("rotor-fr", [0.72, 0.33, -1.26], [0.14, 0.14, 0.02, 20], STEEL, { rot: [0, 0, Math.PI / 2], metal: 0.75, rough: 0.3 }),
  box("caliper-fl", [-0.7, 0.46, -1.26], [0.08, 0.08, 0.16], RED, { metal: 0.4, rough: 0.45, radius: 0.01 }),
  box("caliper-fr", [0.7, 0.46, -1.26], [0.08, 0.08, 0.16], RED, { metal: 0.4, rough: 0.45, radius: 0.01 }),
  cyl("drum-rl", [-0.7, 0.33, 1.28], [0.15, 0.15, 0.08, 20], IRON, { rot: [0, 0, Math.PI / 2], metal: 0.55, rough: 0.45 }),
  cyl("drum-rr", [0.7, 0.33, 1.28], [0.15, 0.15, 0.08, 20], IRON, { rot: [0, 0, Math.PI / 2], metal: 0.55, rough: 0.45 }),

  cyl("strut-fl", [-0.5, 0.62, -1.26], [0.04, 0.04, 0.48, 12], STEEL, { metal: 0.6, rough: 0.35 }),
  cyl("strut-fr", [0.5, 0.62, -1.26], [0.04, 0.04, 0.48, 12], STEEL, { metal: 0.6, rough: 0.35 }),
  box("lca-fl", [-0.55, 0.22, -1.05], [0.08, 0.04, 0.42], IRON, { rot: [0, 0.4, 0], metal: 0.45 }),
  box("lca-fr", [0.55, 0.22, -1.05], [0.08, 0.04, 0.42], IRON, { rot: [0, -0.4, 0], metal: 0.45 }),
  cyl("swaybar", [0, 0.28, -1.45], [0.012, 0.012, 1.2, 10], STEEL, { rot: [0, 0, Math.PI / 2], metal: 0.6 }),
  box("rack", [0, 0.32, -1.35], [1.05, 0.06, 0.06], IRON, { metal: 0.5, radius: 0.015 }),

  torus("spring-rl", [-0.48, 0.32, 1.28], [0.07, 0.012, 8, 16], STEEL, { metal: 0.55, rough: 0.4 }),
  torus("spring-rr", [0.48, 0.32, 1.28], [0.07, 0.012, 8, 16], STEEL, { metal: 0.55, rough: 0.4 }),
  cyl("shock-rl", [-0.62, 0.42, 1.35], [0.025, 0.025, 0.36, 10], STEEL, { metal: 0.55 }),
  cyl("shock-rr", [0.62, 0.42, 1.35], [0.025, 0.025, 0.36, 10], STEEL, { metal: 0.55 }),
  box("quad-l", [-0.35, 0.28, 1.15], [0.04, 0.04, 0.32], IRON, { rot: [0.2, 0.5, 0] }),
  box("quad-r", [0.35, 0.28, 1.15], [0.04, 0.04, 0.32], IRON, { rot: [0.2, -0.5, 0] }),
  box("uca-l", [-0.42, 0.42, 1.15], [0.05, 0.04, 0.28], IRON, { rot: [0, 0.6, 0] }),
  box("uca-r", [0.42, 0.42, 1.15], [0.05, 0.04, 0.28], IRON, { rot: [0, -0.6, 0] }),
  cyl("axle", [0, 0.33, 1.28], [0.045, 0.045, 1.35, 12], IRON, { rot: [0, 0, Math.PI / 2], metal: 0.5 }),
  sph("axle", [0, 0.34, 1.28], 0.14, IRON, { metal: 0.45, rough: 0.5 }),
  cyl("driveshaft", [0, 0.36, 0.45], [0.03, 0.03, 1.35, 12], STEEL, { rot: [Math.PI / 2, 0, 0], metal: 0.6 }),

  box("trans", [0, 0.4, -0.28], [0.28, 0.26, 0.48], "#3c4046", { only: "t5", metal: 0.4, rough: 0.55, radius: 0.02 }),
  box("trans", [0, 0.4, -0.22], [0.32, 0.28, 0.55], "#3c4046", { only: "4r70w", metal: 0.4, rough: 0.55, radius: 0.02 }),
  cyl("clutch", [0, 0.48, -0.55], [0.12, 0.12, 0.03, 20], STEEL, { only: "t5", rot: [Math.PI / 2, 0, 0], metal: 0.55 }),
  cyl("flywheel", [0, 0.48, -0.62], [0.14, 0.14, 0.025, 20], IRON, { only: "t5", rot: [Math.PI / 2, 0, 0], metal: 0.5 }),
  cyl("torque-converter", [0, 0.46, -0.55], [0.12, 0.12, 0.1, 18], STEEL, { only: "4r70w", rot: [Math.PI / 2, 0, 0], metal: 0.55 }),
  box("vss", [0.12, 0.32, 0.02], [0.04, 0.04, 0.06], BLACK, { radius: 0.008 }),

  box("engine-block", [0.06, 0.52, -0.95], [0.38, 0.32, 0.52], IRON, { metal: 0.48, rough: 0.48, radius: 0.02 }),
  box("head-l", [-0.22, 0.7, -0.95], [0.12, 0.1, 0.48], IRON, { rot: [0, 0, 0.4], metal: 0.45, radius: 0.01 }),
  box("head-r", [0.34, 0.66, -0.95], [0.12, 0.1, 0.48], IRON, { rot: [0, 0, -0.35], metal: 0.45, radius: 0.01 }),
  box("valve-cover-l", [-0.28, 0.78, -0.95], [0.1, 0.05, 0.46], BLACK, { radius: 0.012 }),
  box("valve-cover-r", [0.4, 0.74, -0.95], [0.1, 0.05, 0.46], BLACK, { radius: 0.012 }),
  box("intake-gasket", [0.06, 0.7, -0.95], [0.22, 0.015, 0.4], "#6a5a48", { rough: 0.9, metal: 0 }),
  box("intake-lower", [0.06, 0.76, -0.95], [0.24, 0.08, 0.4], ALUM(), { radius: 0.012 }),
  box("intake-upper", [0.04, 0.88, -1.02], [0.2, 0.1, 0.32], ALUM(), { radius: 0.015 }),
  box("throttle-body", [0.02, 0.86, -1.28], [0.1, 0.1, 0.1], ALUM(), { radius: 0.015 }),
  box("iac", [-0.08, 0.92, -1.22], [0.04, 0.04, 0.06], BLACK),
  box("thermostat", [0.06, 0.78, -1.22], [0.08, 0.06, 0.06], ALUM()),
  box("oil-pan", [0.06, 0.32, -0.95], [0.32, 0.08, 0.42], STEEL, { metal: 0.55, rough: 0.4, radius: 0.015 }),
  cyl("oil-filter", [-0.18, 0.28, -0.85], [0.045, 0.045, 0.1, 12], "#1e3a28", { rough: 0.7 }),
  box("front-cover", [0.06, 0.52, -1.24], [0.32, 0.28, 0.04], ALUM()),
  cyl("balancer", [0.06, 0.48, -1.32], [0.08, 0.08, 0.05, 16], IRON, { rot: [Math.PI / 2, 0, 0], metal: 0.5 }),
  box("water-pump", [0.06, 0.58, -1.3], [0.14, 0.14, 0.08], ALUM(), { radius: 0.01 }),
  cyl("fan-clutch", [0.06, 0.58, -1.48], [0.16, 0.16, 0.04, 6], BLACK, { rot: [Math.PI / 2, 0, 0] }),
  box("ckp", [0.22, 0.4, -1.22], [0.03, 0.03, 0.05], BLACK),
  box("alternator", [0.42, 0.58, -1.15], [0.12, 0.12, 0.12], ALUM(), { radius: 0.015 }),
  box("ps-pump", [-0.22, 0.62, -1.18], [0.1, 0.1, 0.1], ALUM(), { radius: 0.012 }),
  box("ac-compressor", [0.38, 0.4, -1.15], [0.12, 0.12, 0.14], STEEL, { metal: 0.5, radius: 0.012 }),
  cyl("starter", [0.32, 0.34, -0.78], [0.05, 0.05, 0.16, 12], STEEL, { rot: [0, 0, Math.PI / 2], metal: 0.55 }),
  box("coil-pack", [0.22, 0.9, -1.12], [0.16, 0.06, 0.22], BLACK, { radius: 0.01 }),
  box("manifold-l", [-0.38, 0.58, -0.95], [0.08, 0.08, 0.4], IRON, { metal: 0.4, rough: 0.55 }),
  box("manifold-r", [0.48, 0.52, -0.95], [0.08, 0.08, 0.4], IRON, { metal: 0.4, rough: 0.55 }),
  cyl("dipstick", [-0.05, 0.7, -0.7], [0.008, 0.008, 0.28, 6], "#c2a15a", { rot: [0.4, 0, 0.2] }),
  box("pcv", [0.4, 0.8, -0.78], [0.03, 0.03, 0.04], BLACK),
  torus("belt", [0.16, 0.55, -1.28], [0.16, 0.012, 8, 20], RUBBER, { rot: [Math.PI / 2, 0, 0], rough: 0.8 }),
  cyl("tensioner", [0.22, 0.48, -1.26], [0.03, 0.03, 0.04, 10], STEEL, { rot: [Math.PI / 2, 0, 0] }),

  cyl("crank", [0.06, 0.46, -0.95], [0.04, 0.04, 0.46, 12], STEEL, { rot: [Math.PI / 2, 0, 0], metal: 0.7 }),
  ...[ -1.12, -0.95, -0.78].flatMap((z) => [
    cyl("pistons", [-0.08, 0.62, z], [0.04, 0.04, 0.06, 12], ALUM(), { metal: 0.6 }),
    cyl("pistons", [0.2, 0.58, z], [0.04, 0.04, 0.06, 12], ALUM(), { metal: 0.6 }),
    cyl("rods", [-0.02, 0.52, z], [0.012, 0.012, 0.12, 8], STEEL, { metal: 0.65 }),
    cyl("rods", [0.14, 0.5, z], [0.012, 0.012, 0.12, 8], STEEL, { metal: 0.65 }),
  ]),
  cyl("cam", [0.06, 0.58, -0.95], [0.02, 0.02, 0.46, 10], STEEL, { rot: [Math.PI / 2, 0, 0], metal: 0.7 }),
  torus("timing-chain", [0.06, 0.52, -1.18], [0.06, 0.008, 8, 16], STEEL, { rot: [Math.PI / 2, 0, 0], metal: 0.6 }),
  box("oil-pump", [0.06, 0.38, -1.16], [0.08, 0.06, 0.06], ALUM()),
  box("valves-l", [-0.22, 0.74, -0.95], [0.04, 0.06, 0.36], STEEL, { metal: 0.7 }),
  box("valves-r", [0.34, 0.7, -0.95], [0.04, 0.06, 0.36], STEEL, { metal: 0.7 }),
  cyl("pushrods", [0.02, 0.64, -0.95], [0.006, 0.006, 0.2, 6], STEEL, { metal: 0.7 }),
  box("rockers-l", [-0.24, 0.8, -0.95], [0.06, 0.03, 0.36], ALUM()),
  box("rockers-r", [0.38, 0.76, -0.95], [0.06, 0.03, 0.36], ALUM()),
  cyl("plugs-l", [-0.34, 0.76, -1.12], [0.012, 0.012, 0.06, 8], CHROME, { rot: [0, 0, Math.PI / 2], metal: 0.8 }),
  cyl("plugs-l", [-0.34, 0.76, -0.95], [0.012, 0.012, 0.06, 8], CHROME, { rot: [0, 0, Math.PI / 2], metal: 0.8 }),
  cyl("plugs-l", [-0.34, 0.76, -0.78], [0.012, 0.012, 0.06, 8], CHROME, { rot: [0, 0, Math.PI / 2], metal: 0.8 }),
  cyl("plugs-r", [0.46, 0.7, -1.12], [0.012, 0.012, 0.06, 8], CHROME, { rot: [0, 0, Math.PI / 2], metal: 0.8 }),
  cyl("plugs-r", [0.46, 0.7, -0.95], [0.012, 0.012, 0.06, 8], CHROME, { rot: [0, 0, Math.PI / 2], metal: 0.8 }),
  cyl("plugs-r", [0.46, 0.7, -0.78], [0.012, 0.012, 0.06, 8], CHROME, { rot: [0, 0, Math.PI / 2], metal: 0.8 }),

  box("airbox", [-0.42, 0.78, -1.45], [0.28, 0.18, 0.32], BLACK, { radius: 0.02 }),
  cyl("maf", [-0.22, 0.82, -1.35], [0.04, 0.04, 0.1, 12], BLACK, { rot: [0, 0, Math.PI / 2] }),
  box("tps", [0.08, 0.9, -1.28], [0.03, 0.03, 0.03], BLACK),
  box("ect", [0.16, 0.74, -1.18], [0.03, 0.03, 0.04], "#2a3a32"),
  box("radiator", [0, 0.58, -1.78], [1.15, 0.42, 0.06], "#2a3036", { metal: 0.45, rough: 0.4 }),
  box("dpfe", [0.28, 0.82, -0.7], [0.06, 0.04, 0.08], BLACK),

  box("exhaust-l", [-0.38, 0.28, -0.4], [0.06, 0.06, 0.9], IRON, { metal: 0.35, rough: 0.6, radius: 0.02 }),
  box("exhaust-r", [0.42, 0.26, -0.4], [0.06, 0.06, 0.9], IRON, { metal: 0.35, rough: 0.6, radius: 0.02 }),
  box("cat", [0.05, 0.24, 0.35], [0.16, 0.12, 0.28], IRON, { metal: 0.3, rough: 0.65, radius: 0.02 }),
  box("muffler", [0.15, 0.22, 1.55], [0.22, 0.14, 0.45], STEEL, { metal: 0.4, rough: 0.5, radius: 0.02 }),
  cyl("muffler", [0.28, 0.24, 1.9], [0.025, 0.025, 0.22, 10], CHROME, { rot: [Math.PI / 2, 0, 0], metal: 0.8, rough: 0.2 }),
  cyl("o2-up", [0.12, 0.36, 0.15], [0.015, 0.015, 0.06, 8], STEEL, { metal: 0.6 }),
  cyl("o2-down", [0.12, 0.34, 0.55], [0.015, 0.015, 0.06, 8], STEEL, { metal: 0.6 }),

  box("fuel-tank", [0, 0.26, 1.18], [1.2, 0.22, 0.82], "#1a1c1e", { metal: 0.12, rough: 0.74, radius: 0.04 }),
  box("tank-shield", [0, 0.13, 1.18], [1.28, 0.02, 0.92], STEEL, { metal: 0.4, rough: 0.55 }),
  box("tank-strap-l", [-0.38, 0.38, 1.18], [0.04, 0.3, 0.07], STEEL, { metal: 0.55, rough: 0.4 }),
  box("tank-strap-r", [0.38, 0.38, 1.18], [0.04, 0.3, 0.07], STEEL, { metal: 0.55, rough: 0.4 }),
  cyl("filler-neck", [-0.62, 0.5, 1.34], [0.038, 0.03, 0.52, 12], BLACK, { rot: [0.15, 0, 0.85], rough: 0.7 }),
  torus("filler-grommet", [-0.5, 0.34, 1.22], [0.055, 0.016, 8, 16], RUBBER, { rot: [Math.PI / 2, 0, 0.4], rough: 0.9 }),
  cyl("fuel-cap", [-0.8, 0.7, 1.48], [0.05, 0.05, 0.028, 14], BLACK, { rot: [0, 0, Math.PI / 2], rough: 0.55 }),
  cyl("fuel-pump", [0.08, 0.42, 1.16], [0.075, 0.075, 0.05, 16], BLACK, { rough: 0.6 }),
  cyl("pump-gasket", [0.08, 0.385, 1.16], [0.095, 0.095, 0.012, 16], RUBBER, { rough: 0.92 }),
  cyl("pump-sock", [0.08, 0.28, 1.16], [0.028, 0.022, 0.1, 8], "#c2b48a", { rough: 0.95 }),
  box("tank-pressure", [0.28, 0.46, 1.28], [0.035, 0.03, 0.035], "#243028", { radius: 0.006 }),
  box("vapor-valve", [0.2, 0.42, 1.32], [0.1, 0.04, 0.16], BLACK, { radius: 0.01 }),
  box("evap-canister", [-0.52, 0.32, 0.78], [0.18, 0.14, 0.26], BLACK, { radius: 0.02, rough: 0.82 }),
  box("evap-vent", [-0.52, 0.42, 0.64], [0.06, 0.04, 0.07], BLACK, { radius: 0.008 }),
  cyl("evap-canister", [-0.32, 0.4, 0.96], [0.012, 0.012, 0.28, 8], BLACK, { rot: [0.4, 0.5, 0.2] }),
  box("evap-purge", [0.72, 0.5, -1.38], [0.08, 0.05, 0.1], BLACK, { radius: 0.01 }),
  cyl("evap-purge", [0.62, 0.52, -1.22], [0.01, 0.01, 0.24, 8], BLACK, { rot: [0.3, 0.5, 0.2] }),
  cyl("fuel-filter", [-0.55, 0.32, -0.15], [0.025, 0.025, 0.12, 10], STEEL, { rot: [0, 0, Math.PI / 2], metal: 0.5 }),
  cyl("fuel-line", [0, 0.42, 0.2], [0.008, 0.008, 1.6, 8], STEEL, { rot: [Math.PI / 2, 0, 0], metal: 0.55 }),
  box("fuel-rail", [0.06, 0.82, -0.95], [0.06, 0.04, 0.4], STEEL, { metal: 0.6, radius: 0.008 }),
  box("injectors", [0.06, 0.78, -0.95], [0.08, 0.04, 0.36], BLACK),
  box("inertia-switch", [-0.42, 0.55, 1.55], [0.08, 0.05, 0.1], RED, { radius: 0.01 }),

  box("battery", [0.58, 0.72, -1.52], [0.22, 0.16, 0.32], BLACK, { radius: 0.015 }),
  box("battery", [0.58, 0.81, -1.62], [0.04, 0.03, 0.04], RED),
  box("pdb", [0.32, 0.78, -1.78], [0.22, 0.1, 0.16], BLACK, { radius: 0.012 }),
  box("ccrm", [0.55, 0.62, -1.72], [0.1, 0.06, 0.12], BLACK, { radius: 0.008 }),
  box("starter-relay", [0.32, 0.86, -1.78], [0.05, 0.04, 0.05], BLACK),
  box("fuse-panel", [-0.48, 0.55, -0.22], [0.16, 0.08, 0.06], BLACK, { radius: 0.008 }),
  box("pcm", [0.55, 0.48, -0.15], [0.16, 0.04, 0.12], BLACK, { radius: 0.008 }),
  box("ignition-switch", [-0.28, 0.62, -0.35], [0.04, 0.04, 0.05], BLACK),
  box("clutch-switch", [-0.18, 0.28, -0.35], [0.03, 0.03, 0.04], BLACK),
  box("brake-switch", [-0.12, 0.32, -0.38], [0.03, 0.04, 0.03], BLACK),
  box("headlamp-switch", [-0.42, 0.7, -0.42], [0.06, 0.04, 0.04], BLACK),

  box("seat-l", [-0.32, 0.48, 0.25], [0.42, 0.12, 0.45], "#2a2c30", { radius: 0.04 }),
  box("seat-l", [-0.32, 0.72, 0.42], [0.4, 0.4, 0.1], "#2a2c30", { radius: 0.04 }),
  box("seat-r", [0.32, 0.48, 0.25], [0.42, 0.12, 0.45], "#2a2c30", { radius: 0.04 }),
  box("seat-r", [0.32, 0.72, 0.42], [0.4, 0.4, 0.1], "#2a2c30", { radius: 0.04 }),
  box("dash", [0, 0.78, -0.42], [1.3, 0.16, 0.28], "#1a1c20", { radius: 0.03 }),
  box("cluster", [-0.32, 0.84, -0.48], [0.28, 0.1, 0.04], "#0e1014", { emissive: "#8a9aaa", emissiveIntensity: 0.15 }),
  cyl("column", [-0.28, 0.7, -0.4], [0.025, 0.025, 0.28, 10], BLACK, { rot: [0.9, 0, 0] }),
  torus("steer-wheel", [-0.32, 0.78, -0.22], [0.16, 0.018, 8, 20], BLACK, { rot: [0.5, 0, 0], rough: 0.6 }),
  cyl("shifter", [0.05, 0.48, 0.15], [0.012, 0.012, 0.22, 8], BLACK),
  sph("shifter", [0.05, 0.6, 0.15], 0.03, BLACK),
  box("console", [0.05, 0.42, 0.15], [0.22, 0.1, 0.55], "#1a1c20", { radius: 0.02 }),
  box("pedals", [-0.22, 0.22, -0.4], [0.16, 0.04, 0.12], STEEL, { metal: 0.4 }),
  box("heater-core", [0.35, 0.55, -0.32], [0.18, 0.12, 0.08], ALUM(), { metal: 0.4 }),
];

function ALUM(): string {
  return "#b7bdc6";
}

export const PRIMS: Prim[] = P;

const focusCache = new Map<string, [number, number, number]>();

export function focusPoint(id: string): [number, number, number] {
  const hit = focusCache.get(id);
  if (hit) return hit;
  const list = PRIMS.filter((p) => p.id === id);
  if (!list.length) return [0, 0.6, 0];
  let x = 0;
  let y = 0;
  let z = 0;
  for (const p of list) {
    x += p.pos[0];
    y += p.pos[1];
    z += p.pos[2];
  }
  const n = list.length;
  const point: [number, number, number] = [x / n, y / n, z / n];
  focusCache.set(id, point);
  return point;
}
