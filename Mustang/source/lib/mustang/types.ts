export type System =
  | "body"
  | "glass"
  | "chassis"
  | "suspension"
  | "brake"
  | "engine"
  | "driveline"
  | "exhaust"
  | "cooling"
  | "fuel"
  | "interior"
  | "electrical";

export type Circuit =
  | "power"
  | "ground"
  | "start"
  | "ignition"
  | "fuel"
  | "sensor"
  | "lamps";

export type Trans = "t5" | "4r70w";
export type Mode = "car" | "sheet" | "both";
export type Vec3 = [number, number, number];

export type Spec = { label: string; value: string };
export type Fastener = {
  name: string;
  thread: string;
  torque?: string;
  qty?: string;
};

export type PartInfo = {
  id: string;
  name: string;
  system: System;
  stage: number;
  ex: Vec3;
  parent?: string;
  circuit?: Circuit;
  blurb: string;
  specs: Spec[];
  fasteners: Fastener[];
  checks: string[];
  keywords: string[];
  alt?: {
    when: Trans;
    name: string;
    blurb: string;
    specs: Spec[];
    checks: string[];
  };
};

export const UNVERIFIED = "not verified, see EVTM" as const;
export type SourceNote = { file: string; line: number; quote: string }; // a quote from app code, never invented
export type Seeded<T> =
  | { value: T; source: SourceNote }
  | { value: null; source: null } // null renders UNVERIFIED
  | { value: T; source: null; user: true }; // typed in by the owner, never shown as verified

export type PinRole = "power" | "ground" | "signal" | "control" | "unknown";
export type ConnectorPin = {
  key: string;               // stable local id, e.g. "p1". NOT a cavity number
  cavity: Seeded<string>;    // real cavity label, only if verified
  role: PinRole;
  label: string;             // e.g. "Relay output"
  color: Seeded<string>;     // wire colour as text
  circuit: Seeded<string>;   // Ford circuit number
  expect: Seeded<string>;    // expected reading, as text
  to?: string;               // partId at the other end, from the diagram WIRES
};
export type ConnectorParts = { shell: Seeded<string>; seal: Seeded<string>; lock: Seeded<string>; terminal: Seeded<string> };
export type Connector = {
  id: string;                // `${partId}:main`, or a seeded id
  partId: string;
  name: string;
  cNumber: Seeded<string>;
  pinCount: Seeded<number>;
  pins: ConnectorPin[];
  parts: ConnectorParts;
  flows: string[];           // flow ids that touch this part
  stub: boolean;             // true = generated at runtime
  origin: "seed" | "stub" | "user";
};
export type FuseSlot = {
  key: string;               // grid id, e.g. "r1c1"
  row: number; col: number;  // layout cell only, not a Ford position number
  position: Seeded<string>;
  kind: Seeded<"fuse" | "maxi" | "relay" | "diode">;
  amps: Seeded<string>;
  protects: Seeded<string>;
  connectors: string[];      // Connector ids
  flows: string[];
};
export type FuseBox = { id: "pdb" | "fuse-panel" | "ccrm"; partId: string; name: string; rows: number; cols: number; slots: FuseSlot[]; origin: "stub" | "user" };
export type UserConnectorData = { v: 1; connectors: Record<string, Connector>; boxes: Record<string, FuseBox> };

export type PaintId = "red" | "black" | "silver" | "white";

export const PAINTS: { id: PaintId; name: string; hex: string }[] = [
  { id: "red", name: "Laser Red", hex: "#8f1d22" },
  { id: "black", name: "Black", hex: "#1a1a1e" },
  { id: "silver", name: "Silver", hex: "#c5c8ce" },
  { id: "white", name: "Oxford White", hex: "#e4e0d8" },
];

export const STAGES: { id: number; name: string; hint: string }[] = [
  { id: 0, name: "Whole", hint: "Car together" },
  { id: 1, name: "Body", hint: "Panels and lamps" },
  { id: 2, name: "Cabin", hint: "Interior and wheels" },
  { id: 3, name: "Drivetrain", hint: "Powertrain drops out" },
  { id: 4, name: "Engine", hint: "Covers and accessories" },
  { id: 5, name: "Internals", hint: "Rotating assembly" },
];

export const SYSTEM_LABEL: Record<System, string> = {
  body: "Body",
  glass: "Glass",
  chassis: "Chassis",
  suspension: "Suspension",
  brake: "Brakes",
  engine: "Engine",
  driveline: "Driveline",
  exhaust: "Exhaust",
  cooling: "Cooling",
  fuel: "Fuel",
  interior: "Interior",
  electrical: "Electrical",
};

export const CIRCUIT_LABEL: Record<Circuit, string> = {
  power: "Charging",
  ground: "Grounds",
  start: "Start",
  ignition: "Ignition",
  fuel: "Fuel",
  sensor: "Sensors",
  lamps: "Lamps",
};

/** Muted service colors — shared by the sheet and the looms on the car. */
export const CIRCUIT_COLOR: Record<Circuit, string> = {
  power: "#a45a56",
  ground: "#8a8a90",
  start: "#b3a288",
  ignition: "#c2b6a4",
  fuel: "#7d8e78",
  sensor: "#8c98a3",
  lamps: "#a89880",
};

export const VEHICLE = {
  title: "2001 Mustang coupe",
  trim: "Base",
  engine: "3.8L OHV V6",
  vin: "",
  power: "193 hp @ 5,500 · 225 lb-ft @ 2,800",
  trans: "T-5 5-speed, 4R70W optional",
  axle: "7.5-inch open",
  brakes: "Disc / drum, ABS optional",
};
