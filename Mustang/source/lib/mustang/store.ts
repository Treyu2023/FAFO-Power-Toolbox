import { create } from "zustand";
import { traceOf } from "./diagram";
import { flowById, flowForPart } from "./flows";
import { commitStage, live } from "./live";
import { PARTS } from "./parts";
import type { Circuit, Mode, System, Trans } from "./types";

const WALK_KEY = "mustang.walkthrough.v1";

type Walk = { flowId: string | null; step: number; marks: Record<string, Mark>; reading: string };

function loadWalk(): Partial<Walk> {
  try {
    const o = JSON.parse(localStorage.getItem(WALK_KEY) || "null");
    const flow = o && o.v === 1 ? flowById(o.flowId) : undefined;
    if (!flow) return {};
    const marks: Record<string, Mark> = {};
    if (o.marks && typeof o.marks === "object") {
      for (const [id, mark] of Object.entries(o.marks)) {
        if (mark === "pass" || mark === "fail") marks[id] = mark;
      }
    }
    const step = Math.min(flow.steps.length - 1, Math.max(0, Math.floor(Number(o.step) || 0)));
    return { flowId: flow.id, step, marks, reading: String(o.reading ?? "").slice(0, 400) };
  } catch {
    return {};
  }
}

function saveWalk(s: Walk) {
  try {
    localStorage.setItem(WALK_KEY, JSON.stringify({ v: 1, flowId: s.flowId, step: s.step, marks: s.marks, reading: s.reading }));
  } catch {
    /* quota or private mode */
  }
}

type Mark = "pass" | "fail";

type State = {
  selected: string | null;
  hover: string | null;
  trace: string[];
  mode: Mode;
  trans: Trans;
  paintHex: string;
  paintAlpha: number;
  paintGrad: boolean;
  paintTo: string;
  bgHex: string;
  bgAlpha: number;
  bgGrad: boolean;
  bgTo: string;
  zoomDrives: boolean;
  system: System | "all";
  section: number | null;
  circuit: Circuit | "all";
  query: string;
  focusTick: number;
  hidden: Record<string, true>;
  menu: { x: number; y: number; id: string | null } | null;
  dock: "sheet" | "walk";
  railOpen: boolean;
  railW: number;
  carShare: number;
  flowId: string | null;
  step: number;
  marks: Record<string, Mark>;
  reading: string;
  pin: string | null;
  select: (id: string | null, frame?: boolean) => void;
  setHover: (id: string | null) => void;
  setMode: (mode: Mode) => void;
  setTrans: (trans: Trans) => void;
  setPaintHex: (hex: string) => void;
  setPaintAlpha: (alpha: number) => void;
  setPaintGrad: (on: boolean) => void;
  setPaintTo: (hex: string) => void;
  setBgHex: (hex: string) => void;
  setBgAlpha: (alpha: number) => void;
  setBgGrad: (on: boolean) => void;
  setBgTo: (hex: string) => void;
  setZoomDrives: (on: boolean) => void;
  setSystem: (system: System | "all") => void;
  setSection: (section: number | null) => void;
  setCircuit: (circuit: Circuit | "all") => void;
  setQuery: (query: string) => void;
  setStage: (stage: number) => void;
  restoreLook: () => void;
  hide: (id: string) => void;
  showHidden: () => void;
  openMenu: (id: string | null, x: number, y: number) => void;
  closeMenu: () => void;
  showOnCar: () => void;
  showOnSheet: () => void;
  setDock: (dock: "sheet" | "walk") => void;
  setRailOpen: (open: boolean) => void;
  setPin: (pin: string | null) => void;
  setRailW: (width: number) => void;
  setCarShare: (share: number) => void;
  startFlow: (id: string, isolate?: boolean) => void;
  setStep: (step: number) => void;
  markStep: (stepId: string, mark: Mark) => void;
  setReading: (reading: string) => void;
  clearWalk: () => void;
};

function framePart(id: string) {
  const part = PARTS[id];
  const stage = Math.max(live.targetStage, part?.stage ?? 0);
  live.targetStage = stage;
  live.focusId = id;
  live.focusing = true;
  live.dolly = null;
}

export const useMustang = create<State>((set, get) => ({
  selected: null,
  hover: null,
  trace: [],
  mode: "both",
  trans: "t5",
  paintHex: "#8f1d22",
  paintAlpha: 1,
  paintGrad: false,
  paintTo: "#1a1a1e",
  bgHex: "#141413",
  bgAlpha: 1,
  bgGrad: false,
  bgTo: "#3a2a28",
  zoomDrives: true,
  system: "all",
  section: null,
  circuit: "all",
  query: "",
  focusTick: 0,
  hidden: {},
  menu: null,
  dock: "walk",
  railOpen: false,
  pin: null,
  railW: 340,
  carShare: 0.72,
  flowId: null,
  step: 0,
  marks: {},
  reading: "",
  ...loadWalk(),
  select: (id, frame = false) => {
    const mode = get().mode;
    const nextMode = id && frame && mode === "sheet" ? "both" : id && !frame && mode === "car" ? "both" : mode;
    set({
      selected: id,
      trace: traceOf(id),
      mode: nextMode,
      query: id ? "" : get().query,
    });
    if (id && frame) {
      framePart(id);
      set({ focusTick: get().focusTick + 1 });
    }
  },
  setHover: (id) => set({ hover: id }),
  setMode: (mode) => set({ mode }),
  setTrans: (trans) => {
    const selected = get().selected;
    let next = selected;
    if (trans === "4r70w" && (selected === "clutch" || selected === "flywheel")) next = "torque-converter";
    if (trans === "t5" && selected === "torque-converter") next = "clutch";
    set({ trans, selected: next, trace: traceOf(next) });
  },
  setPaintHex: (paintHex) => set({ paintHex }),
  setPaintAlpha: (paintAlpha) => set({ paintAlpha: Math.min(1, Math.max(0, paintAlpha)) }),
  setPaintGrad: (paintGrad) => set({ paintGrad }),
  setPaintTo: (paintTo) => set({ paintTo }),
  setBgHex: (bgHex) => set({ bgHex }),
  setBgAlpha: (bgAlpha) => set({ bgAlpha: Math.min(1, Math.max(0, bgAlpha)) }),
  setBgGrad: (bgGrad) => set({ bgGrad }),
  setBgTo: (bgTo) => set({ bgTo }),
  setZoomDrives: (zoomDrives) => set({ zoomDrives }),
  setSystem: (system) => set({ system }),
  setSection: (section) => set({ section }),
  setCircuit: (circuit) => set({ circuit }),
  setQuery: (query) => set({ query }),
  setStage: (stage) => {
    commitStage(stage);
    live.focusing = false;
    live.focusId = null;
    live.recenter = true;
    live.dolly = null;
  },
  restoreLook: () => {
    live.focusing = false;
    live.focusId = null;
    live.dolly = null;
    set({
      selected: null,
      hover: null,
      trace: [],
      system: "all",
      section: null,
      circuit: "all",
      pin: null,
    });
  },
  hide: (id) => set({ hidden: { ...get().hidden, [id]: true }, menu: null }),
  showHidden: () => set({ hidden: {}, menu: null }),
  openMenu: (id, x, y) => set({ menu: { id, x, y } }),
  closeMenu: () => set({ menu: null }),
  showOnCar: () => {
    const id = get().selected;
    if (get().mode === "sheet") set({ mode: "both" });
    if (!id) return;
    framePart(id);
    set({ focusTick: get().focusTick + 1 });
  },
  showOnSheet: () => {
    if (get().mode === "car") set({ mode: "both" });
    set({ dock: "sheet" });
  },
  setDock: (dock) => set({ dock, mode: get().mode === "car" ? "both" : get().mode }),
  setRailOpen: (railOpen) => set({ railOpen }),
  setPin: (pin) => set({ pin }),
  setRailW: (railW) => set({ railW: Math.min(520, Math.max(260, railW)) }),
  setCarShare: (carShare) => set({ carShare: Math.min(0.86, Math.max(0.42, carShare)) }),
  startFlow: (id, isolate = true) => {
    const flow = flowById(id) ?? flowForPart(id);
    const partId = flow.steps[0]?.partId ?? null;
    set({
      flowId: flow.id,
      step: 0,
      marks: {},
      reading: "",
      dock: "walk",
      mode: get().mode === "car" ? "both" : get().mode,
      circuit: isolate ? flow.circuit : get().circuit,
      selected: isolate ? partId : get().selected,
      trace: isolate ? traceOf(partId) : get().trace,
    });
    saveWalk(get());
  },
  setStep: (step) => {
    const flow = flowById(get().flowId);
    if (!flow) return;
    const next = Math.min(flow.steps.length - 1, Math.max(0, step));
    const partId = flow.steps[next]?.partId ?? null;
    set({ step: next, selected: partId, trace: traceOf(partId) });
    saveWalk(get());
    if (partId) framePart(partId);
  },
  markStep: (stepId, mark) => {
    const flow = flowById(get().flowId);
    const marks = { ...get().marks, [stepId]: mark };
    set({ marks });
    saveWalk(get());
    if (!flow) return;
    const index = flow.steps.findIndex((step) => step.id === stepId);
    if (mark === "pass" && index >= 0 && index < flow.steps.length - 1) {
      const partId = flow.steps[index + 1].partId;
      set({ step: index + 1, selected: partId, trace: traceOf(partId) });
      saveWalk(get());
      framePart(partId);
    }
  },
  setReading: (reading) => {
    set({ reading });
    saveWalk(get());
  },
  clearWalk: () => {
    set({ flowId: null, step: 0, marks: {}, reading: "" });
    try {
      localStorage.removeItem(WALK_KEY);
    } catch {
      /* private mode */
    }
  },
}));
