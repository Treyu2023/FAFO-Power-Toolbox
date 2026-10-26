import { NODES, WIRES } from "@/lib/auto/diagram";

export type PinRole = "power" | "ground" | "signal" | "control" | "unknown";

export type Pin = {
  key: string;
  role: PinRole;
  label: string;
  color: string | null;
  expect: string | null;
  to?: string;
  verified: boolean;
};

export type Connector = {
  id: string;
  partId: string;
  name: string;
  pins: Pin[];
  stub: boolean;
};

function pin(key: string, role: PinRole, label: string, extra: Partial<Pin> = {}): Pin {
  return { key, role, label, color: null, expect: null, verified: false, ...extra };
}

const SEEDS: Connector[] = [
  {
    id: "ccrm:fuel-pump",
    partId: "ccrm",
    name: "CCRM fuel-pump relay",
    stub: false,
    pins: [
      pin("p1", "power", "Relay output", { color: "Dark green / yellow", expect: "Battery voltage for about one second, then it falls away.", to: "inertia-switch", verified: true }),
      pin("p2", "power", "Battery feed", { color: "Light blue / orange on the 99–04 CCRM. Confirm the stripe on your connector.", expect: "Hot with the key off.", verified: true }),
      pin("p3", "control", "Relay coil control", { expect: "The PCM grounds this. Do not guess the pin and ground it.", verified: false }),
    ],
  },
  {
    id: "inertia-switch:main",
    partId: "inertia-switch",
    name: "Inertia switch connector",
    stub: false,
    pins: [
      pin("p1", "power", "In from the CCRM", { color: "Dark green / yellow", to: "ccrm", verified: true }),
      pin("p2", "power", "Out to the tank", { color: null, expect: "Read the color on your car and write it down. Both wires should be hot during the prime if the switch is closed.", to: "fuel-pump", verified: false }),
    ],
  },
  {
    id: "fuel-pump:hat",
    partId: "fuel-pump",
    name: "Pump and sender connector",
    stub: false,
    pins: [
      pin("p1", "power", "Pump power", { expect: "During the prime, within about half a volt of the battery. Do not stab a sender wire.", to: "inertia-switch", verified: false }),
      pin("p2", "ground", "Pump ground", { color: "Black", expect: "Near 0 ohms to battery negative, and under about 0.2 V while the pump is commanded.", verified: true }),
    ],
  },
];

function nameOf(id: string) {
  return NODES.find((node) => node.id === id)?.label ?? id;
}

function stub(partId: string): Connector {
  const pins: Pin[] = [];
  for (const wire of WIRES) {
    const index = wire.ends.indexOf(partId);
    if (index < 0) continue;
    const to = wire.ends[index + 1] ?? wire.ends[index - 1];
    const role: PinRole = wire.circuit === "power" ? "power" : wire.circuit === "ground" ? "ground" : wire.circuit === "fuel" ? "power" : "signal";
    pins.push(pin(`p${pins.length + 1}`, role, `${nameOf(wire.id)} toward ${nameOf(to ?? wire.id)}`, { to, verified: false }));
  }
  return { id: `${partId}:main`, partId, name: `${nameOf(partId)} trace`, pins, stub: true };
}

export function connectorsFor(partId: string | null): Connector[] {
  if (!partId) return [];
  const seeded = SEEDS.filter((item) => item.partId === partId);
  if (seeded.length) return seeded;
  if (partId === "pdb") return SEEDS.filter((item) => item.partId === "ccrm");
  const traced = stub(partId);
  return traced.pins.length ? [traced] : [];
}
