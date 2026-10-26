import type { Answers, PackId } from "@/lib/auto/resolve";
import type { ShopOptions } from "@/lib/auto/shop";

const KEY = "fafo.auto.garage.v1";

export type JournalEntry = { id: string; miles: number; text: string; at: number };

export type GarageCar = {
  id: string;
  name: string;
  pack: PackId;
  answers: Answers;
  miles: number;
  journal: JournalEntry[];
  override: Partial<ShopOptions> | null;
  vin?: string;
  service?: Record<string, number>;
};

export function loadGarage(): GarageCar[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as GarageCar[];
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((car) => car && (car.pack === "mustang" || car.pack === "common") && typeof car.name === "string" && typeof car.id === "string")
      .map((car) => ({ ...car, miles: Number(car.miles) || 0, journal: Array.isArray(car.journal) ? car.journal : [], service: car.service ?? {} }));
  } catch {
    return [];
  }
}

export function saveGarage(cars: GarageCar[]) {
  localStorage.setItem(KEY, JSON.stringify(cars));
  return cars;
}

export function newCar(pack: PackId, name: string): GarageCar {
  return {
    id: crypto.randomUUID(),
    name: name.trim() || (pack === "mustang" ? "Mustang" : "Coupe"),
    pack,
    answers: {},
    miles: 0,
    journal: [],
    override: null,
  };
}
