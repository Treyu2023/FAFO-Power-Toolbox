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
