import type { CarSpec } from "@/lib/auto/resolve";

export type CareLog = { miles: number; done: Record<string, number> };

const KEY = "fafo-auto-care";

export function loadCare(): CareLog {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { miles: 0, done: {} };
    const parsed = JSON.parse(raw) as Partial<CareLog>;
    return { miles: Number(parsed.miles) || 0, done: parsed.done ?? {} };
  } catch {
    return { miles: 0, done: {} };
  }
}

export function saveCare(log: CareLog) {
  localStorage.setItem(KEY, JSON.stringify(log));
}

export type CareJob = { id: string; name: string; every: number; parts: string[]; note: string };

export function careJobs(spec: CarSpec): CareJob[] {
  const v6 = spec.pack === "mustang" && spec.engine === "v6";
  const v8 = spec.engine === "v8-2v" || spec.engine === "v8-4v";
  const plugCount = v6 ? 6 : v8 ? 8 : 4;
  return [
    { id: "oil", name: "Oil and filter", every: 5000, parts: ["oil-fill", "oil-filter"], note: "The 2001 book is about 5,000 miles on normal use. Severe use is sooner. Five quarts of 5W-20 with the filter on the Mustang." },
    { id: "coolant", name: "Coolant", every: 50000, parts: ["rad-cap", "coolant-tank"], note: "Radiator cap is the pressure cap. The bottle is the reservoir." },
    {
      id: "trans",
      name: "Transmission fluid",
      every: 30000,
      parts: ["trans-fill"],
      note: spec.trans === "auto" ? "Check hot, idling, in Park." : "The fill plug is the level. There is no dipstick.",
    },
    { id: "air", name: "Engine air filter", every: 15000, parts: ["air-element"], note: "In the air box on the driver side. Sooner in dust." },
    { id: "fuel-filter", name: "Fuel filter", every: 30000, parts: ["fuel-filter"], note: "Low pressure under load is the reason to change it early." },
    { id: "tires", name: "Tires and brakes", every: 5000, parts: ["wheel-fl", "brake-fl"], note: "Pressures are on the door sticker. Look at the tread and the pad thickness." },
    {
      id: "cabin",
      name: "Cabin filter",
      every: spec.pack === "mustang" ? 0 : 15000,
      parts: ["cabin-filter"],
      note: spec.pack === "mustang" ? "This Mustang has no factory cabin filter." : "Under the cowl.",
    },
    {
      id: "plugs",
      name: "Spark plugs",
      every: v6 ? 100000 : 30000,
      parts: Array.from({ length: plugCount }, (_, index) => `plug-${index + 1}`),
      note: v6 ? "Passenger bank 1-2-3, driver bank 4-5-6, front to back." : "Numbered from the front.",
    },
    { id: "belt", name: "Belt, pulleys, alternator", every: 60000, parts: ["belt", "alternator"], note: "Inspect the belt, the tensioner, and the alternator. The decal on the radiator support is the routing, if it is still there." },
    {
      id: "grease",
      name: "Boots and fittings",
      every: 10000,
      parts: ["boot-fl", "boot-fr", "boot-tie-l", "boot-tie-r", "ujoint-f", "ujoint-r"],
      note: "Inspect the boots. Grease a joint only when it actually has a fitting.",
    },
  ];
}

export function careState(miles: number, last: number | undefined, every: number) {
  if (every <= 0) return "skip" as const;
  if (last == null) return "unset" as const;
  const left = every - (miles - last);
  if (left <= 0) return "due" as const;
  if (left <= 500) return "soon" as const;
  return "ok" as const;
}
