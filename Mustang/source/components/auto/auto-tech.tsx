import { useEffect, useRef, useState } from "react";
import { buildSheet, carSpec, chosenPath, nextQuestion, type Answers, type PackId } from "@/lib/auto/resolve";
import { flowById, flowFor, verdict } from "@/lib/auto/flows";
import { groupIdOf, groupsFor, partBlurb } from "@/lib/auto/model";
import { DEFAULT_LOOK, STAGE_NAMES, type Look, type SavedView, type SystemId } from "@/lib/auto/scene-types";
import { WIRES, type Circuit } from "@/lib/auto/diagram";
import { loadHomes, loadShifts, loadViews, saveHomes, saveShifts, writeHome, writeShift, writeViews } from "@/lib/auto/views";
import { loadShop, mergeShop, saveShop, themeStyle, type ShopOptions } from "@/lib/auto/shop";
import { loadGarage, saveGarage, type GarageCar } from "@/lib/auto/garage";
import { clearPartFile, clearScanFile, loadPartFiles, loadScanFile, savePartFile, saveScanFile } from "@/lib/auto/scan-store";
import { FrontDoor } from "@/components/auto/front-door";
import { ShopDesk } from "@/components/auto/shop-desk";
import { PathSheet, groupsOnCircuit } from "@/components/auto/path-sheet";
import { HOSE_KEY, VACUUM_TREE, WIRE_COLORS } from "@/lib/auto/hoses";
import { careJobs, careState, loadCare, saveCare, type CareLog } from "@/lib/auto/care";
import type { CarHandle, MenuHit } from "@/components/auto/car-scene";

const SYSTEMS: { id: SystemId; label: string }[] = [
  { id: "all", label: "All" },
  { id: "body", label: "Body" },
  { id: "drivetrain", label: "Drivetrain" },
  { id: "brakes", label: "Brakes" },
  { id: "fuel", label: "Fuel" },
  { id: "electrical", label: "Electrical" },
];

export function AutoTech() {
  const [pack, setPack] = useState<PackId>("mustang");
  const [answers, setAnswers] = useState<Answers>({});
  const [lookOpen, setLookOpen] = useState(true);
  const [editing, setEditing] = useState(false);
  const [partNames, setPartNames] = useState<Record<string, string>>({});
  const [stage, setStage] = useState(0);
  const [explode, setExplode] = useState(0);
  const explodeDrag = useRef(false);
  const zoomDrag = useRef(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [focus, setFocus] = useState<SystemId>("all");
  const [look, setLook] = useState<Look>(DEFAULT_LOOK);
  const [menu, setMenu] = useState<MenuHit | null>(null);
  const [tab, setTab] = useState<"path" | "parts" | "walk" | "build" | "care" | "shop">("path");
  const [circuit, setCircuit] = useState<Circuit | "all">("all");
  const [sheetId, setSheetId] = useState<string | null>(null);
  const [flowId, setFlowId] = useState<string | null>(null);
  const [stepIndex, setStepIndex] = useState(0);
  const [marks, setMarks] = useState<Record<string, "pass" | "fail">>({});
  const [reading, setReading] = useState<Record<string, string>>({});
  const [partQuery, setPartQuery] = useState("");
  const [scanName, setScanName] = useState("");
  const [scanMode, setScanMode] = useState<"off" | "shell" | "both">("off");
  const stageNames = scanMode === "shell" && scanName ? ["Together", "Scan", "Panels", "Assemblies", "Parts", "Detail"] : [...STAGE_NAMES];
  const [scanUpright, setScanUpright] = useState(false);
  const [zoom, setZoom] = useState(9);
  const [phone, setPhone] = useState(false);
  const [deskOpen, setDeskOpen] = useState(false);
  const [deskHeight, setDeskHeight] = useState(320);
  const [pickOpen, setPickOpen] = useState(false);
  const [sectionMarks, setSectionMarks] = useState<Record<string, { color: string; to: string; gradient: boolean }>>({});
  const fileRef = useRef<HTMLInputElement>(null);
  const partFileRef = useRef<HTMLInputElement>(null);
  const replaceId = useRef<string | null>(null);
  const orbitRef = useRef<{ x: number; y: number } | null>(null);
  const deskDrag = useRef<{ y: number; h: number; moved: boolean } | null>(null);
  const framedIds = useRef<string[] | null>(null);
  const frameRef = useRef<(id: string | null) => void>(() => {});
  const selectedRef = useRef<string | null>(null);
  const [views, setViews] = useState<(SavedView | null)[]>([null, null, null]);
  const [notice, setNotice] = useState("");
  const [hover, setHover] = useState<MenuHit | null>(null);
  const [demo, setDemo] = useState(true);
  const [vacuumOpen, setVacuumOpen] = useState(false);
  const [door, setDoor] = useState<"title" | "garage" | "dealer" | "options" | "bay">("title");
  const [shop, setShop] = useState<ShopOptions>(loadShop());
  const [cars, setCars] = useState<GarageCar[]>([]);
  const [carId, setCarId] = useState<string | null>(null);
  const shopRef = useRef(shop);
  const carsRef = useRef(cars);
  const carIdRef = useRef(carId);
  shopRef.current = shop;
  carsRef.current = cars;
  carIdRef.current = carId;
  selectedRef.current = selected;
  const [care, setCare] = useState<CareLog>({ miles: 0, done: {} });
  const host = useRef<HTMLDivElement>(null);
  const handle = useRef<CarHandle | null>(null);
  const rowRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const question = nextQuestion(pack, answers);
  const spec = carSpec(pack, answers);
  const specKey = JSON.stringify(spec);
  const lookKey = JSON.stringify(look);
  const path = chosenPath(pack, answers);
  const groups = groupsFor(spec);
  const flow = flowById(flowId);
  const step = flow?.steps[Math.min(stepIndex, flow.steps.length - 1)];
  const specRef = useRef(spec);
  const lookRef = useRef(look);
  specRef.current = spec;
  lookRef.current = look;

  useEffect(() => {
    setShop(loadShop());
    setCars(loadGarage());
  }, []);

  useEffect(() => {
    const query = window.matchMedia("(max-width: 800px)");
    const apply = () => setPhone(query.matches);
    apply();
    query.addEventListener("change", apply);
    try {
      const raw = localStorage.getItem("fafo.auto.section-marks.v1");
      if (raw) setSectionMarks(JSON.parse(raw) as Record<string, { color: string; to: string; gradient: boolean }>);
    } catch {
      /* keep the defaults */
    }
    return () => query.removeEventListener("change", apply);
  }, []);

  useEffect(() => {
    if (door !== "bay") return;
    setViews(loadViews());
    setCare(loadCare());
    const el = host.current;
    if (!el) return;
    let dead = false;
    let current: CarHandle | null = null;
    void import("@/components/auto/car-scene").then(async (mod) => {
      if (dead) return;
      current = mod.mountCar(el, {
        onSelect: (id) => {
          setSelected(id);
          setSheetId(id);
          frameRef.current(id);
        },
        onMenu: (next) => setMenu(next),
        onStage: (next) => {
          setStage(Math.round(next));
          if (!explodeDrag.current) setExplode(next);
        },
        onHover: (hit) => setHover(hit),
        onPaint: (id) => {
          setLook((currentLook) => ({
            ...currentLook,
            partPaints: { ...currentLook.partPaints, [id]: { color: currentLook.paint, to: currentLook.paintTo, gradient: currentLook.gradient } },
          }));
          setSelected(id);
        },
        onDemo: (on) => setDemo(on),
        onShift: (id, shift) => writeShift(id, shift),
        onHome: (id, home) => writeHome(id, home),
        onDistance: (distance) => {
          if (!zoomDrag.current) setZoom(distance);
        },
      });
      current.setSpec(specRef.current);
      current.setLook(lookRef.current);
      current.applyShifts(loadShifts());
      current.applyHomes(loadHomes());
      const partFiles = await loadPartFiles().catch(() => []);
      const names: Record<string, string> = {};
      for (const file of partFiles) {
        await current.replacePart(file.id, file.data, file.name);
        names[file.id] = file.name;
      }
      if (Object.keys(names).length) setPartNames(names);
      const opened = carsRef.current.find((car) => car.id === carIdRef.current);
      const active = mergeShop(shopRef.current, opened?.override ?? null);
      current.setIdleSeconds(active.idleMinutes * 60);
      current.setIdleDemo(active.idleDemo);
      if (!active.demoOnOpen) current.setDemo(false);
      const saved = await loadScanFile().catch(() => null);
      let loaded = false;
      if (!dead && saved) {
        try {
          await current.loadScan(saved.data, saved.name);
          setScanName(saved.name);
          setScanMode("shell");
          loaded = true;
        } catch {
          /* a saved file that no longer parses should not hide the bundled body */
        }
      }
      if (!dead && !loaded && pack === "mustang") {
        const candidates = [
          new URL("models/roush-96-gt.glb", document.baseURI).href,
          new URL("./models/roush-96-gt.glb", document.baseURI).href,
        ];
        let data: ArrayBuffer | null = null;
        for (const url of candidates) {
          try {
            const response = await fetch(url);
            if (!response.ok) continue;
            const buffer = await response.arrayBuffer();
            const head = new Uint8Array(buffer, 0, 4);
            const magic = String.fromCharCode(head[0] ?? 0, head[1] ?? 0, head[2] ?? 0, head[3] ?? 0);
            if (magic !== "glTF") continue;
            data = buffer;
            break;
          } catch {
            /* try the next path */
          }
        }
        if (data) {
          await current.loadScan(data, "1996 Roush Mustang GT.glb");
          setScanName("1996 Roush Mustang GT");
          setScanMode("shell");
        }
      }
      handle.current = current;
      const picked = selectedRef.current;
      if (picked) current.select(picked);
    });
    return () => {
      dead = true;
      current?.dispose();
      handle.current = null;
    };
  }, [door]);

  useEffect(() => {
    const opened = cars.find((car) => car.id === carId);
    const active = mergeShop(shop, opened?.override ?? null);
    handle.current?.setIdleSeconds(active.idleMinutes * 60);
    handle.current?.setIdleDemo(active.idleDemo);
  }, [shop, cars, carId]);

  useEffect(() => {
    handle.current?.setSpec(specRef.current);
    setLook((current) => ({ ...current, paint: spec.paint }));
  }, [specKey, spec.paint]);

  useEffect(() => {
    handle.current?.setLook(look);
  }, [lookKey, look]);

  useEffect(() => {
    if (door !== "bay" || !carId) return;
    const current = carsRef.current.find((car) => car.id === carId);
    if (!current) return;
    if (current.pack === pack && JSON.stringify(current.answers) === JSON.stringify(answers)) return;
    setCars(saveGarage(carsRef.current.map((car) => (car.id === carId ? { ...car, pack, answers } : car))));
  }, [specKey, door, carId, pack, answers]);

  useEffect(() => {
    const node = selected ? rowRefs.current[selected] : null;
    node?.scrollIntoView({ block: "nearest" });
  }, [selected]);

  function applyVinBuild(body: "coupe" | "convertible", line: "v6" | "gt" | "cobra") {
    setPack("mustang");
    setAnswers({ body, line });
    setNotice(`${line === "v6" ? "V6" : line === "gt" ? "GT" : "Cobra"} ${body}. Finish trim, paint, and the transmission. The VIN does not say those.`);
  }

  function rememberVin(vin: string) {
    if (!carId) return;
    setCars(saveGarage(carsRef.current.map((car) => (car.id === carId ? { ...car, vin } : car))));
  }

  function choosePack(next: PackId) {
    setPack(next);
    setAnswers({});
    setLook((current) => ({ ...current, paint: next === "mustang" ? "#8f1d22" : "#6e726c" }));
  }

  function answer(id: string, choice: string) {
    setAnswers((current) => {
      const order = ["body", "line", "trim", "paint", "trans", "abs", "engine", "fuel", "ignition", "rear", "throttle"];
      const next = { ...current };
      if (choice) next[id] = choice;
      else delete next[id];
      const index = order.indexOf(id);
      for (const key of Object.keys(next)) {
        if (order.indexOf(key) > index) delete next[key];
      }
      return next;
    });
  }

  function prefs() {
    const car = cars.find((item) => item.id === carId);
    return mergeShop(shop, car?.override ?? null);
  }

  function markFor(circuitId?: string, shopNow = prefs()) {
    const saved = circuitId ? sectionMarks[circuitId] : undefined;
    if (saved) return saved;
    return { color: shopNow.markColor, to: shopNow.markTo, gradient: shopNow.markGradient };
  }

  function applyFrame(id: string, ids?: string[], circuitId?: string, shopNow = prefs()) {
    const circuitForPart = circuitId ?? WIRES.find((wire) => wire.ends.includes(id) || wire.id === id)?.circuit;
    const mark = markFor(circuitForPart, shopNow);
    const paint = ids && ids.length > 1 ? ids : null;
    if (paint) handle.current?.setIsolate(paint, mark.color, mark.gradient ? mark.to : null);
    else handle.current?.setIsolate(null);
    if (!shopNow.framePick) {
      handle.current?.framePart(id, null);
      return;
    }
    handle.current?.framePart(id, {
      mode: shopNow.frameMode,
      distance: shopNow.frameDistance,
      orbit: shopNow.frameOrbit,
      transit: shopNow.frameTransit,
    });
  }

  frameRef.current = (id) => {
    if (!id) {
      framedIds.current = null;
      handle.current?.setIsolate(null);
      handle.current?.framePart("", null);
      return;
    }
    const ids = framedIds.current && framedIds.current.includes(id) ? framedIds.current : [id];
    framedIds.current = ids;
    applyFrame(id, ids);
  };

  function choosePart(raw: string) {
    setSheetId(raw);
    const id = groups.some((item) => item.id === raw) ? raw : groupIdOf(raw);
    if (!groups.some((item) => item.id === id)) return;
    framedIds.current = [id];
    setSelected(id);
    handle.current?.select(id);
  }

  function restoreTextures() {
    framedIds.current = null;
    setFocus("all");
    setCircuit("all");
    setSelected(null);
    handle.current?.select(null);
    handle.current?.framePart("", null);
    handle.current?.restoreTextures();
  }

  function paintThese(ids: string[]) {
    setLook((current) => {
      const partPaints = { ...current.partPaints };
      for (const id of ids) partPaints[id] = { color: current.paint, to: current.paintTo, gradient: current.gradient };
      return { ...current, partPaints };
    });
  }

  function pickSystem(id: SystemId) {
    if (look.paintMode === "part" && focus !== id) {
      const ids = id === "all" ? groups.map((item) => item.id) : groups.filter((item) => item.system === id || (id === "body" && item.id === "unibody")).map((item) => item.id);
      paintThese(ids);
      setNotice(id === "all" ? "Painted every part." : `Painted ${id}.`);
      return;
    }
    if (focus === id && id !== "all") {
      framedIds.current = null;
      setFocus("all");
      handle.current?.setFocus("all");
      handle.current?.restoreTextures();
      return;
    }
    setCircuit("all");
    framedIds.current = null;
    setFocus(id);
    handle.current?.setFocus(id);
    if (id === "all") handle.current?.restoreTextures();
  }

  function pickCircuit(next: Circuit | "all") {
    if (look.paintMode === "part" && next !== "all") {
      paintThese(groupsOnCircuit(next));
      setNotice(`Painted the ${next} circuit.`);
      return;
    }
    setCircuit(next);
    if (next === "all") {
      framedIds.current = null;
      handle.current?.setIsolate(null);
      handle.current?.framePart("", null);
      return;
    }
    setFocus("all");
    const ids = groupsOnCircuit(next);
    framedIds.current = ids;
    const first = ids[0];
    if (first) handle.current?.select(first);
  }

  function troubleshoot(id: string) {
    const next = flowFor(spec, id);
    setFlowId(next.id);
    setStepIndex(0);
    setMarks({});
    setTab("walk");
    choosePart(next.steps[0]?.partId ?? id);
    setMenu(null);
  }

  function saveView(index: number) {
    const snap = handle.current?.getSnapshot();
    if (!snap) return;
    const next = writeViews(views.map((item, i) => (i === index ? { ...snap, look } : item)));
    setViews(next);
    setNotice(`Saved view ${index + 1}. It stays after a refresh.`);
  }

  function goView(index: number) {
    const view = views[index];
    if (!view) return;
    handle.current?.applyView(view);
    setLook({ ...DEFAULT_LOOK, ...view.look });
    setFocus(view.focus);
    setStage(Math.round(view.stage));
    setNotice(`View ${index + 1}.`);
  }

  function startJob(part: string, flowId?: string) {
    if (flowId) {
      const next = flowById(flowId);
      setFlowId(flowId);
      setStepIndex(0);
      setMarks({});
      choosePart(next?.steps[0]?.partId ?? part);
    } else {
      choosePart(part);
    }
    setTab("path");
  }

  function goStep(index: number) {
    if (!flow) return;
    setStepIndex(index);
    choosePart(flow.steps[index]?.partId ?? sheetId ?? "");
  }

  function visibleIds(parts: string[]) {
    const ids = [...new Set(parts.map((id) => (groups.some((item) => item.id === id) ? id : groupIdOf(id))))];
    return ids.filter((id) => groups.some((item) => item.id === id));
  }

  function showCare(parts: string[]) {
    const ids = visibleIds(parts);
    if (!ids.length) {
      setNotice("Those pieces sit inside a larger part on this model.");
      return;
    }
    setFocus("all");
    setCircuit("all");
    framedIds.current = ids;
    const stageNow = Math.max(2, ...ids.map((id) => groups.find((item) => item.id === id)?.stage ?? 2)) + (scanMode === "shell" && scanName ? 1 : 0);
    handle.current?.setStage(stageNow);
    if (ids[0]) handle.current?.select(ids[0]);
  }

  function writeCare(next: CareLog) {
    setCare(next);
    saveCare(next);
  }

  function patchCar(edit: (car: GarageCar) => GarageCar) {
    if (!carId) return;
    setCars(saveGarage(carsRef.current.map((car) => (car.id === carId ? edit(car) : car))));
  }

  const opened = cars.find((car) => car.id === carId) ?? null;
  const active = mergeShop(shop, opened?.override ?? null);
  const milesNow = opened?.miles ?? care.miles;
  const serviceDone = opened?.service ?? care.done;

  useEffect(() => {
    if (door !== "bay" || !selected || editing) {
      if (editing) handle.current?.framePart("", null);
      return;
    }
    const ids = framedIds.current && framedIds.current.includes(selected) ? framedIds.current : undefined;
    applyFrame(selected, ids);
  }, [door, selected, editing, active.framePick, active.frameMode, active.frameDistance, active.frameOrbit, active.frameTransit, active.markColor, active.markTo, active.markGradient, sectionMarks]);

  function setPref<K extends keyof ShopOptions>(key: K, value: ShopOptions[K]) {
    if (opened?.override) {
      setCars(saveGarage(cars.map((item) => (item.id === carId ? { ...item, override: { ...item.override, [key]: value } } : item))));
      return;
    }
    setShop(saveShop({ ...shop, [key]: value }));
  }

  function writeSectionMarks(next: Record<string, { color: string; to: string; gradient: boolean }>) {
    setSectionMarks(next);
    localStorage.setItem("fafo.auto.section-marks.v1", JSON.stringify(next));
  }

  function setMark(key: "color" | "to" | "gradient", value: string | boolean) {
    if (circuit !== "all" && sectionMarks[circuit]) {
      writeSectionMarks({ ...sectionMarks, [circuit]: { ...sectionMarks[circuit], [key]: value } });
      return;
    }
    if (key === "color") setPref("markColor", String(value));
    else if (key === "to") setPref("markTo", String(value));
    else setPref("markGradient", Boolean(value));
  }

  function setMiles(next: number) {
    if (opened) patchCar((car) => ({ ...car, miles: next }));
    else writeCare({ ...care, miles: next });
  }

  function setService(id: string, at: number | null) {
    if (opened) {
      patchCar((car) => {
        const service = { ...(car.service ?? {}) };
        if (at == null) delete service[id];
        else service[id] = at;
        return { ...car, service };
      });
      return;
    }
    const done = { ...care.done };
    if (at == null) delete done[id];
    else done[id] = at;
    writeCare({ ...care, done });
  }

  function beginEdit(on: boolean) {
    setEditing(on);
    handle.current?.setEditing(on);
    if (!on) return;
    setExplode(0);
    handle.current?.setStage(0);
    handle.current?.setDemo(false);
    handle.current?.framePart("", null);
    setNotice("Editing the model. Drag a part to move where it sits when the car is together.");
  }

  function askReplace(id: string) {
    replaceId.current = id;
    partFileRef.current?.click();
  }

  function defaultHome(id: string | null) {
    if (id) {
      handle.current?.clearHome(id);
      const homes = loadHomes();
      delete homes[id];
      saveHomes(homes);
      setNotice("That part is back on the shop spot.");
      return;
    }
    handle.current?.clearHomes();
    saveHomes({});
    setNotice("Every part is back on the shop spot.");
  }

  function openCar(car: GarageCar) {
    setCarId(car.id);
    setPack(car.pack);
    setAnswers(car.answers);
    setLook((current) => ({ ...current, paint: car.override?.newCarPaint || shop.newCarPaint }));
    setVacuumOpen(mergeShop(shop, car.override).showVacuumOnOpen);
    setDoor("bay");
  }

  if (door !== "bay") {
    return (
      <div style={themeStyle(shop)}>
        <FrontDoor door={door} shop={shop} cars={cars} onShop={(next) => setShop(saveShop(next))} onCars={(next) => setCars(saveGarage(next))} onOpen={openCar} onDoor={setDoor} />
      </div>
    );
  }
  const diagramSelected = sheetId === "pdb" ? "ccrm" : sheetId;
  const jobs = careJobs(spec);
  const due = jobs.filter((job) => careState(milesNow, serviceDone[job.id], job.every) === "due");
  const found = flow ? verdict(flow, marks) : null;
  const pickedMark = circuit !== "all" ? sectionMarks[circuit] : undefined;
  const markNow = pickedMark ?? { color: active.markColor, to: active.markTo, gradient: active.markGradient };

  return (
    <div style={themeStyle(active)} className={phone ? "fixed inset-0 z-30 flex h-[100dvh] flex-col overflow-hidden bg-bg" : `flex flex-col ${active.density === "tight" ? "gap-2" : "gap-4"}`}>
      <div className="flex shrink-0 flex-col gap-2 border-b border-line bg-bg px-3 py-2">
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" onClick={() => setDoor("title")} className="h-11 rounded-md bg-accent px-4 text-sm font-medium text-accent-fg">
            Title
          </button>
          <button type="button" onClick={() => beginEdit(!editing)} className={`h-11 rounded-md px-4 text-sm font-medium ${editing ? "bg-amber-500 text-black" : "border border-line text-fg"}`}>
            {editing ? "Done editing" : "Edit the model"}
          </button>
          <input
            ref={partFileRef}
            type="file"
            accept=".glb,.gltf,.stl,.obj"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              const id = replaceId.current ?? selected;
              event.target.value = "";
              if (!file || !id) return;
              void file.arrayBuffer().then(async (data) => {
                await savePartFile(id, file.name, data);
                await handle.current?.replacePart(id, data, file.name);
                setPartNames((names) => ({ ...names, [id]: file.name }));
                setNotice(`${file.name} is on that part, at the shop spot. Drag it if the spot is wrong.`);
              }).catch(() => setNotice("That file did not load. Use a .glb, .gltf, .stl, or .obj."));
            }}
          />
          <button type="button" onClick={() => setLookOpen((open) => !open)} className="h-11 rounded-md border border-line px-3 text-sm text-fg">
            {lookOpen ? "Hide colors, pictures, models" : "Colors, pictures, models"}
          </button>
          {scanName ? <span className="text-sm text-muted">{scanName}</span> : <span className="text-sm text-muted">No model loaded</span>}
        </div>
        {lookOpen ? (
          <div className="flex max-h-80 flex-col gap-2 overflow-auto">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm text-muted">Colors</span>
              <label className="flex h-11 items-center gap-2 text-sm text-fg">
                Paint
                <input type="color" value={look.paint} onChange={(event) => setLook({ ...look, paint: event.target.value })} className="h-9 w-12 bg-transparent" aria-label="Paint color" />
              </label>
              <label className="flex h-11 items-center gap-2 text-sm text-fg">
                To
                <input type="color" value={look.paintTo} onChange={(event) => setLook({ ...look, paintTo: event.target.value, gradient: true })} className="h-9 w-12 bg-transparent" aria-label="Paint gradient color" />
              </label>
              <button type="button" onClick={() => setLook({ ...look, gradient: !look.gradient })} className={`h-11 rounded-md px-3 text-sm ${look.gradient ? "bg-accent font-medium text-accent-fg" : "border border-line text-fg"}`}>
                Gradient
              </button>
              <button type="button" onClick={() => setLook({ ...look, direction: look.direction === "length" ? "height" : "length" })} className="h-11 rounded-md border border-line px-3 text-sm text-fg">
                {look.direction === "length" ? "Along the car" : "Up the car"}
              </button>
              {(["gloss", "satin", "metal"] as const).map((finish) => (
                <button key={finish} type="button" onClick={() => setLook({ ...look, finish })} className={`h-11 rounded-md px-3 text-sm capitalize ${look.finish === finish ? "bg-accent font-medium text-accent-fg" : "border border-line text-fg"}`}>
                  {finish}
                </button>
              ))}
              <button type="button" onClick={() => setLook({ ...look, paintMode: look.paintMode === "part" ? "car" : "part" })} className={`h-11 rounded-md px-3 text-sm ${look.paintMode === "part" ? "bg-accent font-medium text-accent-fg" : "border border-line text-fg"}`}>
                {look.paintMode === "part" ? "Painting parts" : "Paint the car"}
              </button>
              <button type="button" onClick={() => setLook({ ...look, partPaints: {} })} className="h-11 rounded-md border border-line px-3 text-sm text-fg">
                Clear part colors
              </button>
              <label className="flex h-11 items-center gap-2 text-sm text-fg">
                Bay
                <input type="color" value={look.background} onChange={(event) => setLook({ ...look, background: event.target.value })} className="h-9 w-12 bg-transparent" aria-label="Background color" />
              </label>
              <label className="flex h-11 items-center gap-2 text-sm text-fg">
                Bay to
                <input type="color" value={look.backgroundTo} onChange={(event) => setLook({ ...look, backgroundTo: event.target.value, backgroundGradient: true })} className="h-9 w-12 bg-transparent" aria-label="Background gradient color" />
              </label>
              <button type="button" onClick={() => setLook({ ...look, backgroundGradient: !look.backgroundGradient })} className={`h-11 rounded-md px-3 text-sm ${look.backgroundGradient ? "bg-accent font-medium text-accent-fg" : "border border-line text-fg"}`}>
                Bay gradient
              </button>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm text-muted">Pictures</span>
              {(["color", "garage", "showroom"] as const).map((place) => (
                <button key={place} type="button" onClick={() => setLook({ ...look, place })} className={`h-11 rounded-md px-3 text-sm capitalize ${look.place === place ? "bg-accent font-medium text-accent-fg" : "border border-line text-fg"}`}>
                  {place === "color" ? "Open bay" : place}
                </button>
              ))}
              <button type="button" onClick={() => setLook({ ...look, bayDirection: look.bayDirection === "height" ? "length" : "height" })} className="h-11 rounded-md border border-line px-3 text-sm text-fg">
                {look.bayDirection === "height" ? "Bay up" : "Bay across"}
              </button>
              <label className="flex h-11 items-center gap-2 text-sm text-fg">
                Light
                <input type="range" min={0} max={360} value={look.light} aria-label="Light angle" onChange={(event) => setLook({ ...look, light: Number(event.target.value) })} className="w-28" />
              </label>
              {(["wire", "translucent", "both"] as const).map((ghost) => (
                <button key={ghost} type="button" onClick={() => setLook({ ...look, ghost })} className={`h-11 rounded-md px-3 text-sm ${look.ghost === ghost ? "bg-accent font-medium text-accent-fg" : "border border-line text-fg"}`}>
                  {ghost === "wire" ? "Dotted ghost" : ghost === "translucent" ? "Clear ghost" : "Both ghosts"}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm text-muted">Models</span>
              <button type="button" onClick={() => fileRef.current?.click()} className="h-11 rounded-md border border-line px-3 text-sm text-fg">
                Import model
              </button>
              <input
                ref={fileRef}
                type="file"
                accept=".glb,.gltf,.stl,.obj"
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  event.target.value = "";
                  if (!file) return;
                  void file.arrayBuffer().then(async (data) => {
                    await saveScanFile(file.name, data);
                    await handle.current?.loadScan(data, file.name);
                    setScanName(file.name);
                    setScanMode("shell");
                    setNotice(`${file.name} is the body. The engine and the hoses stay the shop parts.`);
                  }).catch(() => setNotice("That file did not load. Use a .glb, .gltf, .stl, or .obj."));
                }}
              />
              {scanName ? (
                <>
                  {(["shell", "both", "off"] as const).map((mode) => (
                    <button
                      key={mode}
                      type="button"
                      onClick={() => {
                        setScanMode(mode);
                        handle.current?.setScanMode(mode);
                      }}
                      className={`h-11 rounded-md px-3 text-sm ${scanMode === mode ? "bg-accent font-medium text-accent-fg" : "border border-line text-fg"}`}
                    >
                      {mode === "shell" ? "Scan body" : mode === "both" ? "Scan and shop" : "Shop body"}
                    </button>
                  ))}
                  <button
                    type="button"
                    onClick={() => {
                      const next = !scanUpright;
                      setScanUpright(next);
                      handle.current?.setScanUpright(next);
                    }}
                    className="h-11 rounded-md border border-line px-3 text-sm text-fg"
                  >
                    {scanUpright ? "Scan is upright" : "Turn scan upright"}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      void clearScanFile();
                      handle.current?.clearScan();
                      setScanName("");
                      setScanMode("off");
                    }}
                    className="h-11 rounded-md border border-line px-3 text-sm text-fg"
                  >
                    Remove model
                  </button>
                </>
              ) : (
                <span className="text-sm text-muted">The shop loads the Roush body from Mustang/models when you are in the bay.</span>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm text-muted">Parts</span>
              <button
                type="button"
                onClick={() => {
                  handle.current?.clearShifts();
                  saveShifts({});
                  setNotice("Parts are back on their default positions.");
                }}
                className="h-11 rounded-md border border-line px-3 text-sm text-fg"
              >
                Default positions
              </button>
              <span className="text-sm text-muted">{editing ? "Editing. Drag moves the part, and the pieces on it, where the car is together." : "Drag a part. Pieces on it move with it, and it comes back to that spot at the same stage until you default it."}</span>
              {editing ? (
                <>
                  <button type="button" onClick={() => (selected ? askReplace(selected) : setNotice("Select a part, then bring in its model."))} className="h-11 rounded-md border border-line px-3 text-sm text-fg">
                    {selected ? `Replace ${partBlurb(selected, spec).name}` : "Replace a part"}
                  </button>
                  <button type="button" disabled={!selected || !partNames[selected]} onClick={() => {
                    if (!selected) return;
                    void clearPartFile(selected);
                    handle.current?.clearPartModel(selected);
                    setPartNames((names) => {
                      const next = { ...names };
                      delete next[selected];
                      return next;
                    });
                    setNotice("The shop part is back.");
                  }} className="h-11 rounded-md border border-line px-3 text-sm text-fg disabled:opacity-40">
                    Shop part
                  </button>
                  <button type="button" onClick={() => (selected ? defaultHome(selected) : setNotice("Select a part first."))} className="h-11 rounded-md border border-line px-3 text-sm text-fg">
                    Default place
                  </button>
                  <button type="button" onClick={() => defaultHome(null)} className="h-11 rounded-md border border-line px-3 text-sm text-fg">
                    Default every place
                  </button>
                </>
              ) : null}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm text-muted">Camera</span>
              <button type="button" onClick={() => setPref("framePick", !active.framePick)} className={`h-11 rounded-md px-3 text-sm ${active.framePick ? "bg-accent font-medium text-accent-fg" : "border border-line text-fg"}`}>
                {active.framePick ? "Moves to the part" : "Stays where it is"}
              </button>
              <button type="button" onClick={() => setPref("frameMode", "orbit")} className={`h-11 rounded-md px-3 text-sm ${active.frameMode === "orbit" ? "bg-accent font-medium text-accent-fg" : "border border-line text-fg"}`}>
                Orbit
              </button>
              <button type="button" onClick={() => setPref("frameMode", "still")} className={`h-11 rounded-md px-3 text-sm ${active.frameMode === "still" ? "bg-accent font-medium text-accent-fg" : "border border-line text-fg"}`}>
                Hold still
              </button>
              <label className="flex min-w-40 flex-1 items-center gap-2 text-sm text-fg">
                Distance {active.frameDistance.toFixed(1)}
                <input type="range" min={0.4} max={8} step={0.1} value={active.frameDistance} aria-label="Distance from the part" onChange={(event) => setPref("frameDistance", Number(event.target.value))} className="min-w-0 flex-1" />
              </label>
              <label className="flex min-w-40 flex-1 items-center gap-2 text-sm text-fg">
                Orbit speed {active.frameOrbit.toFixed(2)}
                <input type="range" min={0.1} max={2.5} step={0.05} value={active.frameOrbit} aria-label="Orbit speed" onChange={(event) => setPref("frameOrbit", Number(event.target.value))} className="min-w-0 flex-1" />
              </label>
              <label className="flex min-w-40 flex-1 items-center gap-2 text-sm text-fg">
                Travel speed {active.frameTransit.toFixed(1)}
                <input type="range" min={1} max={14} step={0.1} value={active.frameTransit} aria-label="Camera travel speed" onChange={(event) => setPref("frameTransit", Number(event.target.value))} className="min-w-0 flex-1" />
              </label>
            </div>
          </div>
        ) : null}
      </div>
      <p className={phone ? "hidden" : "max-w-2xl px-3 text-sm leading-relaxed text-muted"}>
        {opened ? `${opened.name}. ` : ""}Pick a part and it opens to that step, in your highlight color. Options can orbit that part, hold still on it, or leave the camera where it is. The wheel zooms closer than the zoom bar. Alt and the wheel opens the whole car. A pen button turns the view, and hovering the pen reads a part.
      </p>
      {active.showHoseKey ? (
        <div className={phone ? "hidden" : "flex flex-wrap gap-2"}>
        {HOSE_KEY.map((item) => (
          <span key={item.kind} className="inline-flex h-8 items-center gap-2 rounded-md border border-line px-2 text-sm text-fg">
            <span className="inline-block h-3 w-3 rounded-full" style={{ background: item.color }} />
            {item.label}
          </span>
        ))}
        <span className="inline-flex h-8 items-center gap-1 rounded-md border border-line px-2 text-sm text-fg">
          {WIRE_COLORS.slice(0, 6).map((color, index) => (
            <span key={color} className="inline-flex h-4 w-4 items-center justify-center rounded-full text-[10px] text-black" style={{ background: color }}>
              {index + 1}
            </span>
          ))}
          Plug wires
        </span>
        <button type="button" onClick={() => setVacuumOpen((open) => !open)} className={`h-8 rounded-md px-2 text-sm ${vacuumOpen ? "bg-accent font-medium text-accent-fg" : "border border-line text-fg"}`}>
          Vacuum tree
        </button>
        </div>
      ) : null}
      {vacuumOpen && !phone ? (
        <ol className="flex max-w-2xl flex-col gap-1 text-sm leading-relaxed text-fg">
          {VACUUM_TREE.map((line) => (
            <li key={line}>{line}</li>
          ))}
          <li className="text-muted">This is the 3.8 layout from the intake ports and the emissions diagram. It is not the climate-control door chart, and a replaced hose may not still be red.</li>
        </ol>
      ) : null}
      <div className={phone ? "hidden" : "flex flex-wrap gap-2"}>
        <button type="button" onClick={() => choosePack("mustang")} className={`h-11 rounded-md px-4 text-sm ${pack === "mustang" ? "bg-accent font-medium text-accent-fg" : "border border-line text-fg"}`}>
          2001 Mustang
        </button>
        <button type="button" onClick={() => choosePack("common")} className={`h-11 rounded-md px-4 text-sm ${pack === "common" ? "bg-accent font-medium text-accent-fg" : "border border-line text-fg"}`}>
          Common coupe
        </button>
      </div>
      {path.length > 0 ? (
        <div className={phone ? "hidden" : "flex flex-wrap gap-2"}>
          {path.map((item) => (
            <button key={item.id} type="button" onClick={() => answer(item.id, "")} className="h-11 rounded-md border border-line px-3 text-sm text-fg">
              {item.prompt}: {item.label}
            </button>
          ))}
        </div>
      ) : null}
      <div className={phone ? "relative min-h-0 flex-1" : "grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]"}>
        <div className={phone ? "absolute inset-0" : "flex flex-col gap-3"}>
          <div className={phone ? "absolute inset-0" : "relative"}>
            <div ref={host} className={phone ? "h-full w-full" : `h-80 w-full rounded-md border lg:h-[32rem] ${editing ? "border-amber-500" : "border-line"}`} style={{ background: look.place !== "color" ? "#12110f" : look.backgroundGradient ? `linear-gradient(${look.bayDirection === "height" ? "to top" : "to right"}, ${look.background}, ${look.backgroundTo})` : look.background }} />
            {editing ? <p className="pointer-events-none absolute left-3 top-3 max-w-sm rounded-md bg-amber-500 px-3 py-2 text-sm text-black">Editing the model. Drag a part to move where it sits. A model file starts on the shop spot.</p> : null}
            {demo ? <p className="pointer-events-none absolute left-3 top-3 rounded-md bg-elevated px-3 py-2 text-sm text-fg">Demo. Move the mouse or press a key to take over.</p> : null}
            <div className="absolute left-3 right-28 z-10 flex flex-col gap-2 rounded-md bg-bg/80 p-2" style={{ bottom: phone ? `calc(${deskOpen ? deskHeight : 48}px + 0.5rem)` : "0.75rem" }}>
              <label className="flex items-center gap-2 text-sm text-fg">
                Explode
                <input
                  type="range"
                  min={0}
                  max={Math.max(1, stageNames.length - 1)}
                  step={0.01}
                  value={explode}
                  aria-label="Explosion"
                  onPointerDown={() => {
                    explodeDrag.current = true;
                    handle.current?.framePart("", null);
                  }}
                  onPointerUp={() => {
                    explodeDrag.current = false;
                  }}
                  onChange={(event) => {
                    const next = Number(event.target.value);
                    setExplode(next);
                    handle.current?.setStage(next);
                  }}
                  className="h-11 min-w-0 flex-1"
                />
              </label>
              <label className="flex items-center gap-2 text-sm text-fg">
                Zoom
                <input
                  type="range"
                  min={0.16}
                  max={42}
                  step={0.05}
                  value={Math.min(42, Math.max(0.16, zoom))}
                  aria-label="Zoom"
                  onPointerDown={() => {
                    zoomDrag.current = true;
                    handle.current?.framePart("", null);
                  }}
                  onPointerUp={() => {
                    zoomDrag.current = false;
                  }}
                  onChange={(event) => {
                    const next = Number(event.target.value);
                    setZoom(next);
                    handle.current?.dollyTo(next);
                  }}
                  className="h-11 min-w-0 flex-1"
                />
                <span className="w-10 text-right text-muted">{zoom < 1.6 ? "Near" : zoom.toFixed(1)}</span>
              </label>
            </div>
            <div
              className={`absolute z-10 h-24 w-24 touch-none rounded-full border border-line bg-bg/80 ${phone ? "right-3 top-3" : "right-3"}`}
              style={phone ? { touchAction: "none" } : { bottom: "6rem", touchAction: "none" }}
              onPointerDown={(event) => {
                event.currentTarget.setPointerCapture(event.pointerId);
                orbitRef.current = { x: event.clientX, y: event.clientY };
              }}
              onPointerMove={(event) => {
                const last = orbitRef.current;
                if (!last || !event.currentTarget.hasPointerCapture(event.pointerId)) return;
                handle.current?.orbitBy(event.clientX - last.x, event.clientY - last.y);
                orbitRef.current = { x: event.clientX, y: event.clientY };
              }}
              onPointerUp={() => {
                orbitRef.current = null;
              }}
              aria-label="Orbit"
            >
              <span className="pointer-events-none absolute inset-0 flex items-center justify-center text-sm text-muted">Orbit</span>
            </div>
          </div>
          <div className={phone ? "hidden" : "flex flex-col gap-3"}>
          <p className="text-sm text-fg">
            Stage {stage} · {stageNames[stage] ?? "Detail"}
          </p>
          <div className="flex flex-wrap gap-2">
            {stageNames.map((name, index) => (
              <button key={name} type="button" onClick={() => { setExplode(index); handle.current?.setStage(index); }} className={`h-11 rounded-md px-3 text-sm ${stage === index ? "bg-accent font-medium text-accent-fg" : "border border-line text-fg"}`}>
                {name}
              </button>
            ))}
            <button
              type="button"
              onClick={() => {
                handle.current?.clearShifts();
                saveShifts({});
              }}
              className="h-11 rounded-md border border-line px-3 text-sm text-fg"
            >
              Default positions
            </button>
            <button type="button" onClick={() => handle.current?.setDemo(true)} className="h-11 rounded-md border border-line px-3 text-sm text-fg">
              Play demo
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {SYSTEMS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => pickSystem(item.id)}
                className={`h-11 rounded-md px-3 text-sm ${focus === item.id ? "bg-accent font-medium text-accent-fg" : "border border-line text-fg"}`}
              >
                {item.label}
              </button>
            ))}
            <button
              type="button"
              onClick={restoreTextures}
              className="h-11 rounded-md border border-line px-3 text-sm text-fg"
            >
              All textures
            </button>
          </div>
          {look.paintMode === "part" ? <p className="text-sm text-muted">Right-click one part to paint it. Body, Fuel, and the other categories paint every part in that group.</p> : null}
          <div className="flex flex-wrap gap-2">
            {[0, 1, 2].map((index) => (
              <div key={index} className="flex gap-2">
                <button type="button" disabled={!views[index]} onClick={() => goView(index)} className="h-11 rounded-md border border-line px-3 text-sm text-fg disabled:opacity-40">
                  View {index + 1}
                </button>
                <button type="button" onClick={() => saveView(index)} className="h-11 rounded-md border border-line px-3 text-sm text-fg">
                  Save {index + 1}
                </button>
              </div>
            ))}
          </div>
          {notice ? <p className="text-sm text-muted">{notice}</p> : null}
        </div>
        </div>
        <div
          className={phone ? "absolute inset-x-0 bottom-0 z-20 flex flex-col border-t border-line bg-bg" : "flex max-h-[32rem] flex-col gap-3 overflow-auto"}
          style={phone ? { height: deskOpen ? deskHeight : 48, paddingBottom: "env(safe-area-inset-bottom)" } : undefined}
        >
          {phone ? (
            <button
              type="button"
              className="flex h-12 w-full shrink-0 touch-none items-center justify-between px-3 text-sm text-fg"
              onPointerDown={(event) => {
                event.currentTarget.setPointerCapture(event.pointerId);
                deskDrag.current = { y: event.clientY, h: deskOpen ? deskHeight : 320, moved: false };
              }}
              onPointerMove={(event) => {
                const drag = deskDrag.current;
                if (!drag || !event.currentTarget.hasPointerCapture(event.pointerId)) return;
                const dy = drag.y - event.clientY;
                if (Math.abs(dy) > 6) drag.moved = true;
                if (!drag.moved) return;
                const max = Math.round(window.innerHeight * 0.78);
                setDeskOpen(true);
                setDeskHeight(Math.min(max, Math.max(168, drag.h + dy)));
              }}
              onPointerUp={() => {
                const drag = deskDrag.current;
                deskDrag.current = null;
                if (!drag?.moved) setDeskOpen((open) => !open);
              }}
            >
              <span>Desk</span>
              <span className="text-muted">{deskOpen ? "Hide" : "Show"}</span>
            </button>
          ) : null}
          <div className={phone ? (deskOpen ? "flex min-h-0 flex-1 flex-col gap-3 overflow-auto px-3 pb-3" : "hidden") : "contents"}>
          {phone ? (
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={() => choosePack("mustang")} className={`h-11 rounded-md px-3 text-sm ${pack === "mustang" ? "bg-accent font-medium text-accent-fg" : "border border-line text-fg"}`}>
                Mustang
              </button>
              <button type="button" onClick={() => choosePack("common")} className={`h-11 rounded-md px-3 text-sm ${pack === "common" ? "bg-accent font-medium text-accent-fg" : "border border-line text-fg"}`}>
                Common coupe
              </button>
              {path.map((item) => (
                <button key={item.id} type="button" onClick={() => answer(item.id, "")} className="h-11 rounded-md border border-line px-3 text-sm text-fg">
                  {item.label}
                </button>
              ))}
            </div>
          ) : null}
          <div className="flex flex-wrap gap-2">
            {(["path", "shop", "parts", "walk", "care", "build"] as const).map((id) => (
              <button key={id} type="button" onClick={() => setTab(id)} className={`h-11 rounded-md px-3 text-sm capitalize ${tab === id ? "bg-accent font-medium text-accent-fg" : "border border-line text-fg"}`}>
                {id === "walk" ? "Walkthrough" : id === "parts" ? "Parts" : id === "path" ? "Path" : id === "care" ? "Care" : id === "shop" ? "Shop" : "Build"}
              </button>
            ))}
          </div>
          <div className="flex flex-col gap-2 rounded-md border border-line p-3">
            <button type="button" onClick={() => setPickOpen((open) => !open)} className="flex h-11 items-center justify-between gap-3 text-left text-sm text-fg">
              When you pick a part
              <span className="text-muted">{active.framePick ? (active.frameMode === "orbit" ? "Orbit" : "Hold still") : "Camera stays"}</span>
            </button>
            {pickOpen ? (
            <>
            <button type="button" onClick={() => setPref("framePick", !active.framePick)} className="flex h-11 items-center justify-between gap-3 rounded-md border border-line px-3 text-left text-sm text-fg">
              Move the camera
              <span className="text-muted">{active.framePick ? "On" : "Off"}</span>
            </button>
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={() => setPref("frameMode", "orbit")} className={`h-11 rounded-md px-3 text-sm ${active.frameMode === "orbit" ? "bg-accent font-medium text-accent-fg" : "border border-line text-fg"}`}>
                Orbit the part
              </button>
              <button type="button" onClick={() => setPref("frameMode", "still")} className={`h-11 rounded-md px-3 text-sm ${active.frameMode === "still" ? "bg-accent font-medium text-accent-fg" : "border border-line text-fg"}`}>
                Hold still
              </button>
            </div>
            <label className="flex flex-col gap-1 text-sm text-fg">
              Distance {active.frameDistance.toFixed(1)}
              <input type="range" min={0.4} max={8} step={0.1} value={active.frameDistance} aria-label="Distance from the part" onChange={(event) => setPref("frameDistance", Number(event.target.value))} />
            </label>
            <label className="flex flex-col gap-1 text-sm text-fg">
              Orbit speed {active.frameOrbit.toFixed(2)}
              <input type="range" min={0.1} max={2.5} step={0.05} value={active.frameOrbit} aria-label="Orbit speed" onChange={(event) => setPref("frameOrbit", Number(event.target.value))} />
            </label>
            <label className="flex flex-col gap-1 text-sm text-fg">
              Travel speed {active.frameTransit.toFixed(1)}
              <input type="range" min={1} max={14} step={0.1} value={active.frameTransit} aria-label="Camera travel speed" onChange={(event) => setPref("frameTransit", Number(event.target.value))} />
            </label>
            <div className="flex flex-wrap gap-3">
              <label className="flex flex-col gap-1 text-sm text-fg">
                Highlight
                <input type="color" value={markNow.color} aria-label="Highlight color" onChange={(event) => setMark("color", event.target.value)} className="h-11 w-16 rounded-md border border-line bg-bg" />
              </label>
              <label className="flex flex-col gap-1 text-sm text-fg">
                Highlight to
                <input type="color" value={markNow.to} aria-label="Highlight gradient color" onChange={(event) => setMark("to", event.target.value)} className="h-11 w-16 rounded-md border border-line bg-bg" />
              </label>
            </div>
            <button type="button" onClick={() => setMark("gradient", !markNow.gradient)} className={`h-11 rounded-md px-3 text-sm ${markNow.gradient ? "bg-accent font-medium text-accent-fg" : "border border-line text-fg"}`}>
              {markNow.gradient ? "Gradient on" : "Gradient off"}
            </button>
            {circuit !== "all" ? (
              <button
                type="button"
                onClick={() => {
                  if (sectionMarks[circuit]) {
                    const next = { ...sectionMarks };
                    delete next[circuit];
                    writeSectionMarks(next);
                    return;
                  }
                  writeSectionMarks({ ...sectionMarks, [circuit]: { color: active.markColor, to: active.markTo, gradient: active.markGradient } });
                }}
                className="h-11 rounded-md border border-line px-3 text-left text-sm text-fg"
              >
                {sectionMarks[circuit] ? `Use the shop color on ${circuit}` : `Keep this color on ${circuit}`}
              </button>
            ) : (
              <p className="text-sm text-muted">Pick a circuit on the path if that section should keep its own color.</p>
            )}
            </>
            ) : null}
          </div>
          {tab === "shop" ? (
            <ShopDesk
              engine={spec.engine}
              miles={milesNow}
              jobs={jobs.map((job) => ({ ...job, last: serviceDone[job.id] }))}
              savedVin={opened?.vin ?? ""}
              onApplyVin={applyVinBuild}
              onRememberVin={rememberVin}
              onShow={(ids) => {
                const real = visibleIds(ids);
                if (!real.length) {
                  setNotice("Those pieces sit inside a larger part on this model.");
                  return;
                }
                const stageNow = Math.max(2, ...real.map((id) => groups.find((item) => item.id === id)?.stage ?? 2)) + (scanMode === "shell" && scanName ? 1 : 0);
                handle.current?.setStage(stageNow);
                framedIds.current = real;
                if (real[0]) handle.current?.select(real[0]);
              }}
              onWalk={(flowId, partId) => {
                const next = flowById(flowId);
                setFlowId(flowId);
                setStepIndex(0);
                setMarks({});
                setTab("walk");
                choosePart(next?.steps[0]?.partId ?? partId);
              }}
            />
          ) : null}
          {tab === "path" ? (
            <PathSheet
              selected={diagramSelected}
              circuit={circuit}
              mustang={pack === "mustang"}
              flow={flow}
              stepIndex={stepIndex}
              onCircuit={pickCircuit}
              onPick={choosePart}
              onJob={startJob}
              onStep={goStep}
            />
          ) : null}
          {tab === "care" ? (
            <div className="flex flex-col gap-3">
              <p className="text-sm leading-relaxed text-muted">{opened ? `This stays on ${opened.name}.` : "No garage car is open, so this stays on this computer only."}</p>
              {due.length ? <p className="text-sm text-fg">Due now: {due.map((job) => job.name).join(", ")}.</p> : <p className="text-sm text-muted">Nothing is due from the miles on this car.</p>}
              <label className="flex flex-col gap-1 text-sm text-fg">
                Current miles
                <input type="number" min={0} value={milesNow || ""} onChange={(event) => setMiles(Math.max(0, Number(event.target.value) || 0))} className="h-11 rounded-md border border-line bg-bg px-3" />
              </label>
              <ul className="flex flex-col gap-2">
                {jobs.map((job) => {
                  const state = careState(milesNow, serviceDone[job.id], job.every);
                  const label = state === "skip" ? "Not on this car" : state === "unset" ? "No mileage yet" : state === "due" ? "Due" : state === "soon" ? "Due soon" : "Ok";
                  const last = serviceDone[job.id];
                  return (
                    <li key={job.id} className="rounded-md bg-elevated p-3">
                      <button type="button" onClick={() => showCare(job.parts)} className="text-left text-sm font-medium text-fg">
                        {job.name}
                      </button>
                      <p className="text-sm text-muted">
                        {label}
                        {job.every > 0 ? ` · every ${job.every.toLocaleString()} miles` : ""}
                        {last != null ? ` · last at ${last.toLocaleString()}` : ""}
                      </p>
                      <p className="text-sm leading-relaxed text-fg">{job.note}</p>
                      {job.every > 0 ? (
                        <button
                          type="button"
                          onClick={() => {
                            if (!opened) {
                              setService(job.id, milesNow);
                              return;
                            }
                            patchCar((car) => ({
                              ...car,
                              service: { ...(car.service ?? {}), [job.id]: milesNow },
                              journal: [{ id: crypto.randomUUID(), miles: milesNow, text: `${job.name} marked done`, at: Date.now() }, ...(car.journal ?? [])],
                            }));
                          }}
                          className="mt-2 h-11 rounded-md border border-line px-3 text-sm text-fg"
                        >
                          Mark done at {milesNow.toLocaleString()}
                        </button>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : null}
          {tab === "parts" ? (
            <div className="flex flex-col gap-2">
              <label className="flex flex-col gap-1 text-sm text-fg">
                Find a part
                <input value={partQuery} onChange={(event) => setPartQuery(event.target.value)} className="h-11 rounded-md border border-line bg-bg px-3" />
              </label>
              <ul className="flex flex-col gap-1">
                {groups
                  .filter((item) => {
                    const query = partQuery.trim().toLowerCase();
                    return !query || item.name.toLowerCase().includes(query) || item.id.includes(query);
                  })
                  .map((item) => (
                    <li key={item.id}>
                      <button
                        type="button"
                        ref={(node) => {
                          rowRefs.current[item.id] = node;
                        }}
                        onClick={() => choosePart(item.id)}
                        onContextMenu={(event) => {
                          event.preventDefault();
                          setMenu({ x: event.clientX, y: event.clientY, id: item.id, name: item.name, system: item.system });
                        }}
                        className={`w-full rounded-md px-3 py-2 text-left text-sm ${selected === item.id ? "bg-accent font-medium text-accent-fg" : "bg-elevated text-fg"} ${item.parent ? "pl-6" : ""}`}
                      >
                        {item.name}
                      </button>
                    </li>
                  ))}
              </ul>
            </div>
          ) : null}
          {tab === "walk" ? (
            flow && step ? (
              <article className="flex flex-col gap-3">
                <h2 className="text-sm font-medium text-fg">
                  {flow.title} · step {stepIndex + 1} of {flow.steps.length}
                </h2>
                <p className="text-sm leading-relaxed text-muted">{flow.lead}</p>
                <h3 className="text-sm font-medium text-fg">{step.title}</h3>
                <p className="text-sm text-muted">{groups.find((item) => item.id === step.partId)?.name ?? step.partId}</p>
                <p className="text-sm leading-relaxed text-fg">{step.where}</p>
                <p className="text-sm leading-relaxed text-muted">{step.harness}</p>
                {step.wires.map((wire) => (
                  <p key={wire.role} className="text-sm text-fg">
                    {wire.role}: {wire.color}
                  </p>
                ))}
                <p className="text-sm leading-relaxed text-fg">{step.action}</p>
                <div className="flex flex-wrap gap-2">
                  <button type="button" onClick={() => setMarks({ ...marks, [step.id]: "pass" })} className="h-11 rounded-md bg-accent px-3 text-sm font-medium text-accent-fg">
                    This checks out
                  </button>
                  <button type="button" onClick={() => setMarks({ ...marks, [step.id]: "fail" })} className="h-11 rounded-md border border-line px-3 text-sm text-fg">
                    This failed
                  </button>
                </div>
                <p className="text-sm leading-relaxed text-muted">{marks[step.id] === "fail" ? step.fail : step.pass}</p>
                <label className="flex flex-col gap-1 text-sm text-fg">
                  What you measured
                  <textarea value={step ? (reading[step.id] ?? "") : ""} onChange={(event) => step && setReading((current) => ({ ...current, [step.id]: event.target.value }))} rows={3} className="rounded-md border border-line bg-bg p-2 text-sm" />
                </label>
                {opened && step && (reading[step.id] ?? "").trim() ? (
                  <button
                    type="button"
                    onClick={() => {
                      const text = (reading[step.id] ?? "").trim();
                      const result = marks[step.id] === "fail" ? "failed" : marks[step.id] === "pass" ? "checked out" : "noted";
                      patchCar((car) => ({
                        ...car,
                        journal: [{ id: crypto.randomUUID(), miles: car.miles, text: `${flow.title}, ${step.title} ${result}: ${text}`, at: Date.now() }, ...(car.journal ?? [])],
                      }));
                      setNotice("Saved on this car.");
                    }}
                    className="h-11 self-start rounded-md border border-line px-3 text-sm text-fg"
                  >
                    Save on this car
                  </button>
                ) : null}
                {found ? <p className="text-sm leading-relaxed text-fg">{found}</p> : null}
                <div className="flex gap-2">
                  <button type="button" disabled={stepIndex === 0} onClick={() => { const next = stepIndex - 1; setStepIndex(next); choosePart(flow.steps[next]!.partId); }} className="h-11 rounded-md border border-line px-3 text-sm text-fg disabled:opacity-40">
                    Back
                  </button>
                  <button type="button" disabled={stepIndex >= flow.steps.length - 1} onClick={() => { const next = stepIndex + 1; setStepIndex(next); choosePart(flow.steps[next]!.partId); }} className="h-11 rounded-md border border-line px-3 text-sm text-fg disabled:opacity-40">
                    Next step
                  </button>
                </div>
              </article>
            ) : (
              <p className="text-sm leading-relaxed text-muted">Pick a job under Shop, or right-click a part and choose Troubleshoot. What you measure can be saved on the garage car.</p>
            )
          ) : null}
          {tab === "build" ? (
            <div className="flex flex-col gap-3">
              {question ? (
                <section>
                  <h2 className="mb-2 text-sm font-medium text-fg">{question.prompt}</h2>
                  <ul className="flex flex-col gap-2">
                    {question.choices.map((choice) => (
                      <li key={choice.id}>
                        <button type="button" onClick={() => answer(question.id, choice.id)} className="w-full rounded-md bg-elevated px-3 py-3 text-left">
                          <span className="block text-sm text-fg">{choice.label}</span>
                          {choice.detail ? <span className="block text-sm text-muted">{choice.detail}</span> : null}
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : (
                <p className="text-sm text-muted">That is the car. Change a choice above if it is wrong.</p>
              )}
              <ul className="flex flex-col gap-1">
                {buildSheet(pack, answers).lines.map((line) => (
                  <li key={line.label} className="flex items-start justify-between gap-3 text-sm">
                    <span className="text-faint">{line.label}</span>
                    <span className="text-right text-fg">{line.value}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          </div>
        </div>
      </div>
      {hover && !menu && active.hoverNotes ? (
        <div className="pointer-events-none fixed z-40 w-64 rounded-md border border-line bg-elevated p-3" style={{ left: Math.min(hover.x + 16, window.innerWidth - 280), top: Math.min(hover.y + 16, window.innerHeight - 160) }}>
          <p className="text-sm font-medium text-fg">{partBlurb(hover.id, spec).name}</p>
          <p className="text-sm capitalize text-muted">{hover.system}</p>
          <p className="mt-1 text-sm leading-relaxed text-fg">{partBlurb(hover.id, spec).checks[0]}</p>
        </div>
      ) : null}
      {menu ? (
        <div className="fixed z-30 max-h-[70vh] w-64 overflow-auto rounded-md border border-line bg-elevated p-1" style={{ left: Math.min(menu.x, window.innerWidth - 272), top: Math.max(8, Math.min(menu.y, window.innerHeight - 320)) }} role="menu">
          <button type="button" role="menuitem" className="block h-11 w-full rounded-md px-3 text-left text-sm text-fg" onClick={() => troubleshoot(menu.id)}>
            Troubleshoot {menu.name}
          </button>
          <button
            type="button"
            role="menuitem"
            className="block h-11 w-full rounded-md px-3 text-left text-sm text-fg"
            onClick={() => {
              handle.current?.hide(menu.id);
              setMenu(null);
            }}
          >
            Hide {menu.name}
          </button>
          {editing ? (
            <>
              <button type="button" role="menuitem" className="block h-11 w-full rounded-md px-3 text-left text-sm text-fg" onClick={() => { askReplace(menu.id); setMenu(null); }}>
                Replace with a model
              </button>
              {partNames[menu.id] ? (
                <button type="button" role="menuitem" className="block h-11 w-full rounded-md px-3 text-left text-sm text-fg" onClick={() => {
                  void clearPartFile(menu.id);
                  handle.current?.clearPartModel(menu.id);
                  setPartNames((names) => {
                    const next = { ...names };
                    delete next[menu.id];
                    return next;
                  });
                  setMenu(null);
                }}>
                  Use the shop part
                </button>
              ) : null}
              <button type="button" role="menuitem" className="block h-11 w-full rounded-md px-3 text-left text-sm text-fg" onClick={() => { defaultHome(menu.id); setMenu(null); }}>
                Default place
              </button>
              <button type="button" role="menuitem" className="block h-11 w-full rounded-md px-3 text-left text-sm text-fg" onClick={() => { defaultHome(null); setMenu(null); }}>
                Default every place
              </button>
            </>
          ) : null}
          <button
            type="button"
            role="menuitem"
            className="block h-11 w-full rounded-md px-3 text-left text-sm text-fg"
            onClick={() => {
              handle.current?.clearShift(menu.id);
              const all = loadShifts();
              delete all[menu.id];
              saveShifts(all);
              setNotice(`${menu.name} is back on its default position. Pieces on it come with it.`);
              setMenu(null);
            }}
          >
            Default this part
          </button>
          <button
            type="button"
            role="menuitem"
            className="block h-11 w-full rounded-md px-3 text-left text-sm text-fg"
            onClick={() => {
              handle.current?.clearShifts();
              saveShifts({});
              setNotice("Every part is back on its default position.");
              setMenu(null);
            }}
          >
            Default all parts
          </button>
          <button
            type="button"
            role="menuitem"
            className="block h-11 w-full rounded-md px-3 text-left text-sm text-fg"
            onClick={() => {
              handle.current?.showHidden();
              setMenu(null);
            }}
          >
            Show hidden parts
          </button>
        </div>
      ) : null}
    </div>
  );
}
