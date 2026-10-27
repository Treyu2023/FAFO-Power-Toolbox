import type { SavedView, Shift } from "@/lib/auto/scene-types";

const VIEWS_KEY = "fafo.auto.views.v1";
const SHIFTS_KEY = "fafo.auto.shifts.v1";

export function loadViews(): (SavedView | null)[] {
  const empty: (SavedView | null)[] = [null, null, null];
  try {
    const raw = localStorage.getItem(VIEWS_KEY);
    if (!raw) return empty;
    const parsed = JSON.parse(raw) as (SavedView | null)[];
    if (!Array.isArray(parsed)) return empty;
    return [parsed[0] ?? null, parsed[1] ?? null, parsed[2] ?? null];
  } catch {
    return empty;
  }
}

export function writeViews(views: (SavedView | null)[]) {
  const next: (SavedView | null)[] = [views[0] ?? null, views[1] ?? null, views[2] ?? null];
  localStorage.setItem(VIEWS_KEY, JSON.stringify(next));
  return next;
}

export function loadShifts(): Record<string, Shift> {
  try {
    const raw = localStorage.getItem(SHIFTS_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, Shift>;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

export function saveShifts(shifts: Record<string, Shift>) {
  localStorage.setItem(SHIFTS_KEY, JSON.stringify(shifts));
  return shifts;
}

const HOMES_KEY = "fafo.auto.homes.v1";

export type Home = { x: number; y: number; z: number };

export function loadHomes(): Record<string, Home> {
  try {
    const raw = localStorage.getItem(HOMES_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, Home>;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

export function saveHomes(homes: Record<string, Home>) {
  localStorage.setItem(HOMES_KEY, JSON.stringify(homes));
  return homes;
}

export function writeHome(id: string, home: Home) {
  const all = loadHomes();
  all[id] = home;
  localStorage.setItem(HOMES_KEY, JSON.stringify(all));
  return all;
}

export function writeShift(id: string, shift: Shift) {
  const all = loadShifts();
  all[id] = shift;
  localStorage.setItem(SHIFTS_KEY, JSON.stringify(all));
  return all;
}
