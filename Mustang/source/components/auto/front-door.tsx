import { useState } from "react";
import { newCar, type GarageCar, type JournalEntry } from "@/lib/auto/garage";
import { DEFAULT_SHOP, type ShopOptions } from "@/lib/auto/shop";
import type { PackId } from "@/lib/auto/resolve";

type Door = "title" | "garage" | "dealer" | "options";

const PACKS: { id: PackId; name: string; detail: string }[] = [
  { id: "mustang", name: "2001 Mustang", detail: "Coupe or convertible. V6, GT, Bullitt, or Cobra. You finish the build sheet after it is in the garage." },
  { id: "common", name: "Common coupe", detail: "A generic gas car for when the Mustang pack is the wrong one. No Ford pins and no Ford torque." },
];

export function FrontDoor({
  door,
  shop,
  cars,
  onShop,
  onCars,
  onOpen,
  onDoor,
}: {
  door: Door;
  shop: ShopOptions;
  cars: GarageCar[];
  onShop: (next: ShopOptions) => void;
  onCars: (next: GarageCar[]) => void;
  onOpen: (car: GarageCar) => void;
  onDoor: (door: Door) => void;
}) {
  if (door === "title") {
    return (
      <div className="mx-auto flex min-h-[70vh] w-full max-w-lg flex-col justify-center gap-3">
        <div className="mb-3">
          <p className="text-sm text-faint">FAFO</p>
          <h2 className="text-3xl font-medium tracking-tight text-fg">Auto Tech</h2>
          <p className="mt-2 text-sm leading-relaxed text-muted">Pick a car you already keep, add a pack from the dealers, or set the shop defaults.</p>
        </div>
        <button type="button" onClick={() => onDoor("garage")} className="h-12 rounded-md bg-accent text-sm font-medium text-accent-fg">
          Garage
        </button>
        <button type="button" onClick={() => onDoor("dealer")} className="h-12 rounded-md border border-line text-sm text-fg">
          The Auto Dealers
        </button>
        <button type="button" onClick={() => onDoor("options")} className="h-12 rounded-md border border-line text-sm text-fg">
          Options
        </button>
      </div>
    );
  }
  if (door === "garage") return <Garage shop={shop} cars={cars} onCars={onCars} onOpen={onOpen} onDoor={onDoor} />;
  if (door === "dealer") return <Dealer cars={cars} onCars={onCars} onOpen={onOpen} onDoor={onDoor} />;
  return <Options shop={shop} onShop={onShop} onDoor={onDoor} />;
}

function Back({ onDoor }: { onDoor: (door: Door) => void }) {
  return (
    <button type="button" onClick={() => onDoor("title")} className="h-11 self-start rounded-md border border-line px-4 text-sm text-fg">
      Title
    </button>
  );
}

function Garage({ shop, cars, onCars, onOpen, onDoor }: { shop: ShopOptions; cars: GarageCar[]; onCars: (next: GarageCar[]) => void; onOpen: (car: GarageCar) => void; onDoor: (door: Door) => void }) {
  const [editId, setEditId] = useState<string | null>(null);
  const [pendingRemove, setPendingRemove] = useState<string | null>(null);
  const editing = cars.find((car) => car.id === editId) ?? null;

  function update(next: GarageCar) {
    onCars(cars.map((car) => (car.id === next.id ? next : car)));
  }

  function remove(id: string) {
    if (shop.confirmRemove && pendingRemove !== id) {
      setPendingRemove(id);
      return;
    }
    onCars(cars.filter((car) => car.id !== id));
    setPendingRemove(null);
    if (editId === id) setEditId(null);
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      <Back onDoor={onDoor} />
      <h2 className="text-xl font-medium text-fg">Garage</h2>
      {cars.length === 0 ? <p className="text-sm text-muted">No cars yet. The Auto Dealers has the packs on this computer.</p> : null}
      <ul className="flex flex-col gap-2">
        {cars.map((car) => (
          <li key={car.id} className="rounded-md border border-line p-3">
            <p className="text-sm font-medium text-fg">{car.name}</p>
            <p className="text-sm text-muted">
              {car.pack === "mustang" ? "2001 Mustang" : "Common coupe"} · {car.miles.toLocaleString()} {shop.unit}
              {car.override ? " · own settings" : " · shop settings"}
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              <button type="button" onClick={() => onOpen(car)} className="h-11 rounded-md bg-accent px-3 text-sm font-medium text-accent-fg">
                Open
              </button>
              <button type="button" onClick={() => setEditId(editId === car.id ? null : car.id)} className="h-11 rounded-md border border-line px-3 text-sm text-fg">
                Edit
              </button>
              <button type="button" onClick={() => remove(car.id)} className="h-11 rounded-md border border-line px-3 text-sm text-fg">
                {pendingRemove === car.id ? "Remove this car" : "Remove"}
              </button>
            </div>
          </li>
        ))}
      </ul>
      {editing ? <CarEdit car={editing} shop={shop} onChange={update} /> : null}
    </div>
  );
}

function CarEdit({ car, shop, onChange }: { car: GarageCar; shop: ShopOptions; onChange: (car: GarageCar) => void }) {
  const [note, setNote] = useState("");
  const [noteMiles, setNoteMiles] = useState(String(car.miles || ""));
  const custom = car.override !== null;

  function addNote() {
    const text = note.trim();
    if (!text) return;
    const entry: JournalEntry = { id: crypto.randomUUID(), miles: Math.max(0, Number(noteMiles) || car.miles), text, at: Date.now() };
    onChange({ ...car, journal: [entry, ...car.journal] });
    setNote("");
  }

  return (
    <section className="flex flex-col gap-3 rounded-md bg-elevated p-3">
      <h3 className="text-sm font-medium text-fg">Edit {car.name}</h3>
      <label className="flex flex-col gap-1 text-sm text-fg">
        Name
        <input value={car.name} onChange={(event) => onChange({ ...car, name: event.target.value })} className="h-11 rounded-md border border-line bg-bg px-3" />
      </label>
      <label className="flex flex-col gap-1 text-sm text-fg">
        Miles on this car
        <input type="number" min={0} value={car.miles || ""} onChange={(event) => onChange({ ...car, miles: Math.max(0, Number(event.target.value) || 0) })} className="h-11 rounded-md border border-line bg-bg px-3" />
      </label>
      <label className="flex items-center gap-2 text-sm text-fg">
        <input type="checkbox" checked={custom} onChange={(event) => onChange({ ...car, override: event.target.checked ? { ...shop } : null })} />
        This car overrides the shop
      </label>
      {custom && car.override ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <ColorField label="Body paint" value={car.override.newCarPaint ?? shop.newCarPaint} onChange={(newCarPaint) => onChange({ ...car, override: { ...car.override, newCarPaint } })} />
          <ColorField label="Accent" value={car.override.accent ?? shop.accent} onChange={(accent) => onChange({ ...car, override: { ...car.override, accent } })} />
          <ColorField label="Ink" value={car.override.ink ?? shop.ink} onChange={(ink) => onChange({ ...car, override: { ...car.override, ink } })} />
          <ColorField label="Paper" value={car.override.paper ?? shop.paper} onChange={(paper) => onChange({ ...car, override: { ...car.override, paper } })} />
          <label className="flex flex-col gap-1 text-sm text-fg">
            Demo minutes
            <input type="number" min={1} max={30} value={car.override.idleMinutes ?? shop.idleMinutes} onChange={(event) => onChange({ ...car, override: { ...car.override, idleMinutes: Number(event.target.value) } })} className="h-11 rounded-md border border-line bg-bg px-3" />
          </label>
          <Choice label="Type" value={car.override.font ?? shop.font} options={[["plain", "Plain"], ["serif", "Serif"], ["mono", "Mono"]]} onChange={(font) => onChange({ ...car, override: { ...car.override, font: font as ShopOptions["font"] } })} />
        </div>
      ) : (
        <p className="text-sm text-muted">Unchecked means this car uses the shop colors, type, and demo timer.</p>
      )}
      <div className="flex flex-col gap-2">
        <p className="text-sm font-medium text-fg">Journal</p>
        <label className="flex flex-col gap-1 text-sm text-fg">
          What you did
          <input value={note} onChange={(event) => setNote(event.target.value)} className="h-11 rounded-md border border-line bg-bg px-3" />
        </label>
        <label className="flex flex-col gap-1 text-sm text-fg">
          At miles
          <input value={noteMiles} onChange={(event) => setNoteMiles(event.target.value)} className="h-11 rounded-md border border-line bg-bg px-3" />
        </label>
        <button type="button" onClick={addNote} className="h-11 self-start rounded-md border border-line px-3 text-sm text-fg">
          Add to this car
        </button>
        <ul className="flex flex-col gap-2">
          {car.journal.map((entry) => (
            <li key={entry.id} className="text-sm text-fg">
              {entry.miles.toLocaleString()} {shop.unit} · {entry.text}
              <button type="button" onClick={() => onChange({ ...car, journal: car.journal.filter((item) => item.id !== entry.id) })} className="ml-2 text-muted">
                Delete
              </button>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function Dealer({ cars, onCars, onOpen, onDoor }: { cars: GarageCar[]; onCars: (next: GarageCar[]) => void; onOpen: (car: GarageCar) => void; onDoor: (door: Door) => void }) {
  const [name, setName] = useState("");
  const [pack, setPack] = useState<PackId>("mustang");
  const [openNow, setOpenNow] = useState(true);

  function add() {
    const car = newCar(pack, name);
    onCars([car, ...cars]);
    setName("");
    if (openNow) onOpen(car);
    else onDoor("garage");
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      <Back onDoor={onDoor} />
      <h2 className="text-xl font-medium text-fg">The Auto Dealers</h2>
      <p className="text-sm leading-relaxed text-muted">These packs are already on this computer. Adding one puts a car in your garage. It does not download a car we do not have.</p>
      <div className="grid gap-2 sm:grid-cols-2">
        {PACKS.map((item) => (
          <button key={item.id} type="button" onClick={() => setPack(item.id)} className={`rounded-md border p-3 text-left ${pack === item.id ? "border-accent bg-elevated" : "border-line"}`}>
            <p className="text-sm font-medium text-fg">{item.name}</p>
            <p className="mt-1 text-sm leading-relaxed text-muted">{item.detail}</p>
          </button>
        ))}
      </div>
      <label className="flex flex-col gap-1 text-sm text-fg">
        Name this car
        <input value={name} onChange={(event) => setName(event.target.value)} placeholder={pack === "mustang" ? "Mustang" : "Coupe"} className="h-11 rounded-md border border-line bg-bg px-3" />
      </label>
      <label className="flex items-center gap-2 text-sm text-fg">
        <input type="checkbox" checked={openNow} onChange={(event) => setOpenNow(event.target.checked)} />
        Open it after adding
      </label>
      <button type="button" onClick={add} className="h-12 self-start rounded-md bg-accent px-4 text-sm font-medium text-accent-fg">
        Add to the garage
      </button>
    </div>
  );
}

function Options({ shop, onShop, onDoor }: { shop: ShopOptions; onShop: (next: ShopOptions) => void; onDoor: (door: Door) => void }) {
  function set<K extends keyof ShopOptions>(key: K, value: ShopOptions[K]) {
    onShop({ ...shop, [key]: value });
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      <Back onDoor={onDoor} />
      <h2 className="text-xl font-medium text-fg">Options</h2>
      <p className="text-sm leading-relaxed text-muted">These are the shop defaults. A car can override them from the garage.</p>
      <section className="flex flex-col gap-3">
        <h3 className="text-sm font-medium text-fg">Demo</h3>
        <label className="flex flex-col gap-1 text-sm text-fg">
          Comes back after, minutes
          <input type="number" min={1} max={30} value={shop.idleMinutes} onChange={(event) => set("idleMinutes", Number(event.target.value))} className="h-11 max-w-40 rounded-md border border-line bg-bg px-3" />
        </label>
        <Toggle on={shop.demoOnOpen} label="Play the demo when a car opens" onChange={(demoOnOpen) => set("demoOnOpen", demoOnOpen)} />
        <Toggle on={shop.idleDemo} label="Play it again after you leave the car alone" onChange={(idleDemo) => set("idleDemo", idleDemo)} />
      </section>
      <section className="flex flex-col gap-3">
        <h3 className="text-sm font-medium text-fg">Type</h3>
        <Choice label="Font" value={shop.font} options={[["plain", "Plain"], ["serif", "Serif"], ["mono", "Mono"]]} onChange={(font) => set("font", font as ShopOptions["font"])} />
        <Choice label="Size" value={shop.scale} options={[["100", "100"], ["110", "110"], ["125", "125"]]} onChange={(scale) => set("scale", scale as ShopOptions["scale"])} />
        <Choice label="Spacing" value={shop.density} options={[["roomy", "Roomy"], ["tight", "Tight"]]} onChange={(density) => set("density", density as ShopOptions["density"])} />
      </section>
      <section className="grid gap-3 sm:grid-cols-2">
        <h3 className="text-sm font-medium text-fg sm:col-span-2">Color</h3>
        <ColorField label="Accent" value={shop.accent} onChange={(accent) => set("accent", accent)} />
        <ColorField label="Ink" value={shop.ink} onChange={(ink) => set("ink", ink)} />
        <ColorField label="Paper" value={shop.paper} onChange={(paper) => set("paper", paper)} />
        <ColorField label="New car paint" value={shop.newCarPaint} onChange={(newCarPaint) => set("newCarPaint", newCarPaint)} />
      </section>
      <section className="flex flex-col gap-3">
        <h3 className="text-sm font-medium text-fg">Shop</h3>
        <Choice label="Distance" value={shop.unit} options={[["mi", "Miles"], ["km", "Kilometers"]]} onChange={(unit) => set("unit", unit as ShopOptions["unit"])} />
        <Toggle on={shop.hoverNotes} label="Notes when you hover a part" onChange={(hoverNotes) => set("hoverNotes", hoverNotes)} />
        <Toggle on={shop.showHoseKey} label="Show the hose colors" onChange={(showHoseKey) => set("showHoseKey", showHoseKey)} />
        <Toggle on={shop.showVacuumOnOpen} label="Open the vacuum tree with the car" onChange={(showVacuumOnOpen) => set("showVacuumOnOpen", showVacuumOnOpen)} />
        <Toggle on={shop.confirmRemove} label="Ask again before a car leaves the garage" onChange={(confirmRemove) => set("confirmRemove", confirmRemove)} />
        <button type="button" onClick={() => onShop({ ...DEFAULT_SHOP })} className="h-11 self-start rounded-md border border-line px-3 text-sm text-fg">
          Reset shop defaults
        </button>
      </section>
    </div>
  );
}

function Toggle({ on, label, onChange }: { on: boolean; label: string; onChange: (on: boolean) => void }) {
  return (
    <button type="button" onClick={() => onChange(!on)} className="flex h-11 items-center justify-between gap-3 rounded-md border border-line px-3 text-left text-sm text-fg">
      {label}
      <span className="text-muted">{on ? "On" : "Off"}</span>
    </button>
  );
}

function Choice({ label, value, options, onChange }: { label: string; value: string; options: [string, string][]; onChange: (value: string) => void }) {
  return (
    <div className="flex flex-col gap-1">
      <p className="text-sm text-fg">{label}</p>
      <div className="flex flex-wrap gap-2">
        {options.map(([id, name]) => (
          <button key={id} type="button" onClick={() => onChange(id)} className={`h-11 rounded-md px-3 text-sm ${value === id ? "bg-accent font-medium text-accent-fg" : "border border-line text-fg"}`}>
            {name}
          </button>
        ))}
      </div>
    </div>
  );
}

function ColorField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="flex flex-col gap-1 text-sm text-fg">
      {label}
      <input type="color" value={value} onChange={(event) => onChange(event.target.value)} className="h-11 w-full rounded-md border border-line bg-bg" />
    </label>
  );
}
