const KEY = "fafo.auto.shop.v1";

export type ShopOptions = {
  idleMinutes: number;
  demoOnOpen: boolean;
  idleDemo: boolean;
  font: "plain" | "serif" | "mono";
  scale: "100" | "110" | "125";
  density: "roomy" | "tight";
  accent: string;
  ink: string;
  paper: string;
  unit: "mi" | "km";
  hoverNotes: boolean;
  newCarPaint: string;
  confirmRemove: boolean;
  showHoseKey: boolean;
  showVacuumOnOpen: boolean;
  framePick: boolean;
  frameMode: "still" | "orbit";
  frameDistance: number;
  frameOrbit: number;
  frameTransit: number;
  markColor: string;
  markTo: string;
  markGradient: boolean;
};

export const DEFAULT_SHOP: ShopOptions = {
  idleMinutes: 3,
  demoOnOpen: true,
  idleDemo: true,
  font: "plain",
  scale: "100",
  density: "roomy",
  accent: "#f3f1ea",
  ink: "#f3f1ea",
  paper: "#0e0e0c",
  unit: "mi",
  hoverNotes: true,
  newCarPaint: "#8f1d22",
  confirmRemove: true,
  showHoseKey: true,
  showVacuumOnOpen: false,
  framePick: true,
  frameMode: "orbit",
  frameDistance: 2.4,
  frameOrbit: 0.55,
  frameTransit: 4,
  markColor: "#e7c07a",
  markTo: "#8f1d22",
  markGradient: false,
};

function clampNum(value: unknown, min: number, max: number, fallback: number) {
  const n = Number(value);
  if (!Number.isFinite(n)) return fallback;
  return Math.min(max, Math.max(min, n));
}

function hex(value: unknown, fallback: string) {
  return typeof value === "string" && /^#[0-9a-fA-F]{6}$/.test(value) ? value : fallback;
}

function clampMinutes(value: unknown) {
  const minutes = Number(value);
  if (!Number.isFinite(minutes)) return DEFAULT_SHOP.idleMinutes;
  return Math.min(30, Math.max(1, Math.round(minutes)));
}

function oneOf<T extends string>(value: unknown, allowed: readonly T[], fallback: T): T {
  return allowed.includes(value as T) ? (value as T) : fallback;
}

export function sanitizeShop(raw: Partial<ShopOptions> | null | undefined): ShopOptions {
  const source = raw ?? {};
  return {
    idleMinutes: clampMinutes(source.idleMinutes),
    demoOnOpen: source.demoOnOpen !== false,
    idleDemo: source.idleDemo !== false,
    font: oneOf(source.font, ["plain", "serif", "mono"] as const, "plain"),
    scale: oneOf(source.scale, ["100", "110", "125"] as const, "100"),
    density: oneOf(source.density, ["roomy", "tight"] as const, "roomy"),
    accent: typeof source.accent === "string" && source.accent.startsWith("#") ? source.accent : DEFAULT_SHOP.accent,
    ink: typeof source.ink === "string" && source.ink.startsWith("#") ? source.ink : DEFAULT_SHOP.ink,
    paper: typeof source.paper === "string" && source.paper.startsWith("#") ? source.paper : DEFAULT_SHOP.paper,
    unit: source.unit === "km" ? "km" : "mi",
    hoverNotes: source.hoverNotes !== false,
    newCarPaint: typeof source.newCarPaint === "string" && source.newCarPaint.startsWith("#") ? source.newCarPaint : DEFAULT_SHOP.newCarPaint,
    confirmRemove: source.confirmRemove !== false,
    showHoseKey: source.showHoseKey !== false,
    showVacuumOnOpen: source.showVacuumOnOpen === true,
    framePick: source.framePick !== false,
    frameMode: source.frameMode === "still" ? "still" : "orbit",
    frameDistance: clampNum(source.frameDistance, 0.4, 8, DEFAULT_SHOP.frameDistance),
    frameOrbit: clampNum(source.frameOrbit, 0.1, 2.5, DEFAULT_SHOP.frameOrbit),
    frameTransit: clampNum(source.frameTransit, 1, 14, DEFAULT_SHOP.frameTransit),
    markColor: hex(source.markColor, DEFAULT_SHOP.markColor),
    markTo: hex(source.markTo, DEFAULT_SHOP.markTo),
    markGradient: source.markGradient === true,
  };
}

export function loadShop(): ShopOptions {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { ...DEFAULT_SHOP };
    return sanitizeShop(JSON.parse(raw) as Partial<ShopOptions>);
  } catch {
    return { ...DEFAULT_SHOP };
  }
}

export function saveShop(next: ShopOptions): ShopOptions {
  const saved = sanitizeShop(next);
  localStorage.setItem(KEY, JSON.stringify(saved));
  return saved;
}

export function mergeShop(shop: ShopOptions, override: Partial<ShopOptions> | null): ShopOptions {
  if (!override) return shop;
  const next: ShopOptions = { ...shop };
  for (const [key, value] of Object.entries(override)) {
    if (value !== undefined) next[key as keyof ShopOptions] = value as never;
  }
  return sanitizeShop(next);
}

export function themeStyle(shop: ShopOptions): Record<string, string> {
  const font = shop.font === "serif" ? "Georgia, 'Iowan Old Style', serif" : shop.font === "mono" ? "ui-monospace, 'IBM Plex Mono', monospace" : "inherit";
  const size = shop.scale === "125" ? "1.12rem" : shop.scale === "110" ? "1.06rem" : "1rem";
  return {
    fontFamily: font,
    fontSize: size,
    color: shop.ink,
    "--color-bg": shop.paper,
    "--color-fg": shop.ink,
    "--color-accent": shop.accent,
    "--color-accent-fg": shop.paper,
  };
}
