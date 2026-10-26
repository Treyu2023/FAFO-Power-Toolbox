export type SystemId = "all" | "body" | "drivetrain" | "brakes" | "fuel" | "electrical" | "chassis";

export type GhostStyle = "wire" | "translucent" | "both";
export type Place = "color" | "garage" | "showroom";
export type PartPaint = { color: string; to: string; gradient: boolean };

export type Look = {
  paint: string;
  paintTo: string;
  gradient: boolean;
  direction: "height" | "length";
  finish: "gloss" | "satin" | "metal";
  ghost: GhostStyle;
  metal: string;
  background: string;
  backgroundTo: string;
  backgroundGradient: boolean;
  bayDirection: "height" | "length";
  place: Place;
  light: number;
  paintMode: "car" | "part";
  partPaints: Record<string, PartPaint>;
};

export type Shift = { x: number; y: number; z: number; from: number };

export type SavedView = {
  stage: number;
  camera: [number, number, number];
  target: [number, number, number];
  shifts: Record<string, Shift>;
  focus: SystemId;
  hidden: string[];
  look: Look;
};

export const STAGE_NAMES = ["Together", "Panels", "Assemblies", "Parts", "Detail"] as const;

export const DEFAULT_LOOK: Look = {
  paint: "#8f1d22",
  paintTo: "#3a0d10",
  gradient: false,
  direction: "length",
  finish: "gloss",
  ghost: "wire",
  metal: "#8a8680",
  background: "#12110f",
  backgroundTo: "#3a342c",
  backgroundGradient: false,
  bayDirection: "height",
  place: "color",
  light: 40,
  paintMode: "car",
  partPaints: {},
};
