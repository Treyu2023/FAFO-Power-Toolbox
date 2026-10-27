import { useEffect, useState, type ComponentType, type PointerEvent as ReactPointerEvent } from "react";
import { WiringSheet } from "./diagram";
import { Inspector } from "./inspector";
import { Walkthrough } from "./walk";
import { PARTS, searchParts } from "@/lib/mustang/parts";
import { flowForPart } from "@/lib/mustang/flows";
import { live } from "@/lib/mustang/live";
import { useMustang } from "@/lib/mustang/store";
import { PAINTS, STAGES, SYSTEM_LABEL, type Mode, type System } from "@/lib/mustang/types";

const SYSTEMS: (System | "all")[] = [
  "all",
  "body",
  "engine",
  "electrical",
  "fuel",
  "brake",
  "suspension",
  "driveline",
  "cooling",
  "interior",
];

function useStage() {
  const [stage, setStage] = useState(0);
  useEffect(() => {
    let frame = 0;
    let last = -1;
    const loop = () => {
      frame = requestAnimationFrame(loop);
      const next = live.targetStage;
      if (next !== last) {
        last = next;
        setStage(next);
      }
    };
    frame = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(frame);
  }, []);
  return stage;
}

export function MustangApp() {
  const mode = useMustang((s) => s.mode);
  const setMode = useMustang((s) => s.setMode);
  const trans = useMustang((s) => s.trans);
  const setTrans = useMustang((s) => s.setTrans);
  const paintHex = useMustang((s) => s.paintHex);
  const paintAlpha = useMustang((s) => s.paintAlpha);
  const paintGrad = useMustang((s) => s.paintGrad);
  const paintTo = useMustang((s) => s.paintTo);
  const setPaintHex = useMustang((s) => s.setPaintHex);
  const setPaintAlpha = useMustang((s) => s.setPaintAlpha);
  const setPaintGrad = useMustang((s) => s.setPaintGrad);
  const setPaintTo = useMustang((s) => s.setPaintTo);
  const bgHex = useMustang((s) => s.bgHex);
  const bgAlpha = useMustang((s) => s.bgAlpha);
  const bgGrad = useMustang((s) => s.bgGrad);
  const bgTo = useMustang((s) => s.bgTo);
  const setBgHex = useMustang((s) => s.setBgHex);
  const setBgAlpha = useMustang((s) => s.setBgAlpha);
  const setBgGrad = useMustang((s) => s.setBgGrad);
  const setBgTo = useMustang((s) => s.setBgTo);
  const section = useMustang((s) => s.section);
  const circuit = useMustang((s) => s.circuit);
  const setSection = useMustang((s) => s.setSection);
  const restoreLook = useMustang((s) => s.restoreLook);
  const zoomDrives = useMustang((s) => s.zoomDrives);
  const setZoomDrives = useMustang((s) => s.setZoomDrives);
  const system = useMustang((s) => s.system);
  const setSystem = useMustang((s) => s.setSystem);
  const query = useMustang((s) => s.query);
  const setQuery = useMustang((s) => s.setQuery);
  const select = useMustang((s) => s.select);
  const setStage = useMustang((s) => s.setStage);
  const hover = useMustang((s) => s.hover);
  const selected = useMustang((s) => s.selected);
  const menu = useMustang((s) => s.menu);
  const hidden = useMustang((s) => s.hidden);
  const hide = useMustang((s) => s.hide);
  const showHidden = useMustang((s) => s.showHidden);
  const closeMenu = useMustang((s) => s.closeMenu);
  const dock = useMustang((s) => s.dock);
  const setDock = useMustang((s) => s.setDock);
  const railOpen = useMustang((s) => s.railOpen);
  const setRailOpen = useMustang((s) => s.setRailOpen);
  const railW = useMustang((s) => s.railW);
  const setRailW = useMustang((s) => s.setRailW);
  const carShare = useMustang((s) => s.carShare);
  const setCarShare = useMustang((s) => s.setCarShare);
  const startFlow = useMustang((s) => s.startFlow);
  const stage = useStage();
  const [drag, setDrag] = useState<number | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem("fafo-mustang-prefs");
      if (raw) {
        const saved = JSON.parse(raw) as {
          paint?: string;
          paintHex?: string;
          paintAlpha?: number;
          paintGrad?: boolean;
          paintTo?: string;
          bgHex?: string;
          bgAlpha?: number;
          bgGrad?: boolean;
          bgTo?: string;
          trans?: string;
          zoom?: boolean;
        };
        const legacy: Record<string, string> = { red: "#8f1d22", black: "#1a1a1e", silver: "#c5c8ce", white: "#e4e0d8" };
        if (saved.paintHex) setPaintHex(saved.paintHex);
        else if (saved.paint && legacy[saved.paint]) setPaintHex(legacy[saved.paint]);
        if (typeof saved.paintAlpha === "number") setPaintAlpha(saved.paintAlpha);
        if (typeof saved.paintGrad === "boolean") setPaintGrad(saved.paintGrad);
        if (saved.paintTo) setPaintTo(saved.paintTo);
        if (saved.bgHex) setBgHex(saved.bgHex);
        if (typeof saved.bgAlpha === "number") setBgAlpha(saved.bgAlpha);
        if (typeof saved.bgGrad === "boolean") setBgGrad(saved.bgGrad);
        if (saved.bgTo) setBgTo(saved.bgTo);
        if (saved.trans === "t5" || saved.trans === "4r70w") setTrans(saved.trans);
        if (typeof saved.zoom === "boolean") setZoomDrives(saved.zoom);
      }
    } catch {
      /* ignore */
    }
    setReady(true);
    if (!useMustang.getState().flowId) startFlow("fuel-pump-power", false);
  }, [setPaintHex, setPaintAlpha, setPaintGrad, setPaintTo, setBgHex, setBgAlpha, setBgGrad, setBgTo, setTrans, setZoomDrives, startFlow]);

  useEffect(() => {
    if (!ready) return;
    try {
      localStorage.setItem(
        "fafo-mustang-prefs",
        JSON.stringify({ paintHex, paintAlpha, paintGrad, paintTo, bgHex, bgAlpha, bgGrad, bgTo, trans, zoom: zoomDrives }),
      );
    } catch {
      /* ignore */
    }
  }, [paintHex, paintAlpha, paintGrad, paintTo, bgHex, bgAlpha, bgGrad, bgTo, trans, zoomDrives, ready]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.key >= "0" && e.key <= "5") {
        const next = Number(e.key);
        setStage(next);
        if (next === 0) restoreLook();
        else setSection(next);
      }
      if (e.key === "Escape") restoreLook();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [restoreLook, setSection, setStage]);

  useEffect(() => {
    const close = (e: PointerEvent) => {
      if (e.button === 2) return;
      const target = e.target as HTMLElement | null;
      if (target?.closest(".ctx")) return;
      closeMenu();
    };
    window.addEventListener("pointerdown", close);
    return () => window.removeEventListener("pointerdown", close);
  }, [closeMenu]);

  const hiddenCount = Object.keys(hidden).length;
  const menuPart = menu?.id ? PARTS[menu.id] : null;
  const results = searchParts(query);
  const stageIndex = Math.round(stage);
  const stageName = STAGES[stageIndex]?.name ?? "Whole";
  const hoverName = hover ? (PARTS[hover]?.name ?? null) : null;

  return (
    <div className="shell">
      <div className="stripe" />
      <header className="top">
        <div className="brand">
          <p className="eyebrow">FAFO Toolbox</p>
          <h1 className="brand-name">Mustang</h1>
          <p className="brand-sub">2001 coupe · 3.8 base</p>
        </div>
        <div className="search">
          <label className="field">
            <span className="sr">Find a part</span>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search plugs, inertia switch, 1/2-20…"
              aria-label="Find a part"
            />
          </label>
          {query && results.length > 0 ? (
            <ul className="results">
              {results.map((part) => (
                <li key={part.id}>
                  <button type="button" onClick={() => select(part.id, true)}>
                    <span>{part.name}</span>
                    <span className="result-meta">{SYSTEM_LABEL[part.system]}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
          {query && results.length === 0 ? <p className="results empty-results">Nothing on this car by that name.</p> : null}
        </div>
        <div className="gear-toggle" role="group" aria-label="Transmission">
          <button type="button" className={trans === "t5" ? "chip chip-on" : "chip"} onClick={() => setTrans("t5")}>
            5-speed
          </button>
          <button type="button" className={trans === "4r70w" ? "chip chip-on" : "chip"} onClick={() => setTrans("4r70w")}>
            Automatic
          </button>
        </div>
      </header>
      <div className="toolbar">
        <div className="stage-read">
          <span className="stage-kicker">Stage {stageIndex}</span>
          <strong>{stageName}</strong>
        </div>
        <label className="stage-slider">
          <span className="sr">Explosion stage</span>
          <input
            type="range"
            min={0}
            max={5}
            step={0.01}
            value={drag ?? stage}
            aria-valuetext={stageName}
            onPointerDown={() => setDrag(stage)}
            onPointerUp={() => setDrag(null)}
            onPointerCancel={() => setDrag(null)}
            onChange={(e) => {
              const value = Number(e.target.value);
              setDrag(value);
              setStage(value);
            }}
          />
        </label>
        <div className="chip-row stages">
          {STAGES.map((item) => (
            <button
              key={item.id}
              type="button"
              className={stageIndex === item.id ? "chip chip-on" : "chip"}
              onClick={() => {
                setStage(item.id);
                if (item.id === 0) restoreLook();
                else setSection(item.id);
              }}
            >
              {item.name}
            </button>
          ))}
        </div>
        <p className="control-note">Wheel zooms. Shift+wheel opens the car.</p>
        <button
          type="button"
          className={system !== "all" || section != null || circuit !== "all" || selected ? "chip chip-on" : "chip"}
          title="Show paint and colors on every part. Leaves the explode slider where it is."
          onClick={restoreLook}
        >
          All textures
        </button>
        {hiddenCount > 0 ? (
          <button type="button" className="chip" onClick={showHidden}>
            Show hidden ({hiddenCount})
          </button>
        ) : null}
        <div className="chip-row" role="group" aria-label="View">
          {(
            [
              ["car", "Car"],
              ["both", "Both"],
              ["sheet", "Sheet"],
            ] as [Mode, string][]
          ).map(([id, label]) => (
            <button key={id} type="button" className={mode === id ? "chip chip-on" : "chip"} onClick={() => setMode(id)}>
              {label}
            </button>
          ))}
        </div>
        <ColorPop
          label="Paint"
          hex={paintHex}
          alpha={paintAlpha}
          grad={paintGrad}
          gradHex={paintTo}
          onHex={setPaintHex}
          onAlpha={setPaintAlpha}
          onGrad={setPaintGrad}
          onGradHex={setPaintTo}
          presets={PAINTS.map((item) => ({ name: item.name, hex: item.hex }))}
        />
        <ColorPop
          label="Bay"
          hex={bgHex}
          alpha={bgAlpha}
          grad={bgGrad}
          gradHex={bgTo}
          onHex={setBgHex}
          onAlpha={setBgAlpha}
          onGrad={setBgGrad}
          onGradHex={setBgTo}
        />
      </div>
      <div className="filter-row">
        {SYSTEMS.map((id) => (
          <button key={id} type="button" className={system === id ? "chip chip-on" : "chip"} onClick={() => setSystem(id)}>
            {id === "all" ? "All systems" : SYSTEM_LABEL[id]}
          </button>
        ))}
      </div>
      <div
        className="workspace"
        style={{ ["--car" as string]: String(mode === "car" ? 1 : mode === "sheet" ? 0.38 : carShare), ["--rail" as string]: railOpen ? `${railW}px` : "48px" }}
      >
        <div className={`stage mode-${mode}`}>
          <div className="pane-car" style={{ background: bayBackground({ bgHex, bgAlpha, bgGrad, bgTo }) }}>
            <CarPane />
            <p className="bay-hint">
              {hoverName ??
                (selected
                  ? "Wheel zooms. Shift+wheel opens the car. Right-click a part to hide it or troubleshoot it."
                  : "Drag to orbit. Wheel zooms. Shift+wheel opens the car. Right-click a part to hide it.")}
            </p>
          </div>
          {mode !== "car" ? (
            <>
              <div
                className="split split-y"
                role="separator"
                aria-orientation="vertical"
                aria-label="Resize the car"
                onPointerDown={(e) =>
                  dragSplit(e, (dx, width) => setCarShare(useMustang.getState().carShare + dx / width))
                }
              />
              <section className="dock" aria-label="Diagram and reference">
                <div className="dock-tabs" role="tablist">
                  <button type="button" className={dock === "sheet" ? "chip chip-on" : "chip"} onClick={() => setDock("sheet")}>
                    Sheet
                  </button>
                  <button type="button" className={dock === "walk" ? "chip chip-on" : "chip"} onClick={() => setDock("walk")}>
                    Walkthrough
                  </button>
                </div>
                <div className="dock-body">{dock === "sheet" ? <WiringSheet /> : <Walkthrough />}</div>
              </section>
            </>
          ) : null}
        </div>
        <div
          className="split split-rail"
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize details"
          onPointerDown={(e) => {
            if (!railOpen) return;
            dragSplit(e, (dx) => setRailW(useMustang.getState().railW - dx));
          }}
        />
        <aside className={railOpen ? "rail rail-open" : "rail rail-shut"}>
          <button type="button" className="rail-toggle" aria-expanded={railOpen} onClick={() => setRailOpen(!railOpen)}>
            {railOpen ? "Hide" : "Details"}
          </button>
          {railOpen ? (
            <>
              <Inspector />
              <VinField />
            </>
          ) : (
            <p className="rail-peek">{selected ? (PARTS[selected]?.name ?? "Part") : "Fuel pump power"}</p>
          )}
        </aside>
      </div>
      {menu ? (
        <div className="ctx" style={{ left: menu.x, top: menu.y }} role="menu">
          {menu.id ? (
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                startFlow(menu.id === "fuel-pump" || menu.id === "inertia-switch" || menu.id === "ccrm" || menu.id === "pdb" ? "fuel-pump-power" : flowForPart(menu.id as string).id);
                closeMenu();
              }}
            >
              Troubleshoot {menuPart?.name ?? "this"}
            </button>
          ) : null}
          {menu.id ? (
            <button type="button" role="menuitem" onClick={() => hide(menu.id as string)}>
              Hide {menuPart?.name ?? "this part"}
            </button>
          ) : null}
          {menu.id !== "unibody" && !hidden.unibody ? (
            <button type="button" role="menuitem" onClick={() => hide("unibody")}>
              Hide body shell
            </button>
          ) : null}
          {hiddenCount > 0 ? (
            <button type="button" role="menuitem" onClick={showHidden}>
              Show hidden parts
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

const VIN_KEY = "mustang.vin.v1";

function VinField() {
  const [vin, setVin] = useState(() => {
    try {
      return localStorage.getItem(VIN_KEY) ?? "";
    } catch {
      return "";
    }
  });
  useEffect(() => {
    (window as { FafoChrome?: { initFold?: () => void } }).FafoChrome?.initFold?.();
  }, []);
  const save = (next: string) => {
    setVin(next);
    try {
      if (next) localStorage.setItem(VIN_KEY, next);
      else localStorage.removeItem(VIN_KEY);
    } catch {
      /* quota or private mode */
    }
  };
  return (
    <details className="fafo-fold" data-fafo-fold="vehicle" data-collapsed-default>
      <summary>Vehicle</summary>
      <label className="field">
        <span>VIN (stays on this device)</span>
        <input maxLength={17} autoComplete="off" spellCheck={false} value={vin} onChange={(e) => save(e.target.value.toUpperCase())} />
      </label>
      {vin ? (
        <button type="button" className="btn" onClick={() => window.confirm("Clear the VIN from this device?") && save("")}>
          Clear
        </button>
      ) : null}
    </details>
  );
}

function dragSplit(event: ReactPointerEvent<HTMLDivElement>, onDelta: (dx: number, width: number) => void) {
  const handle = event.currentTarget as HTMLElement;
  const bounds = handle.parentElement?.getBoundingClientRect();
  const width = bounds?.width || 1;
  handle.setPointerCapture(event.pointerId);
  let last = event.clientX;
  const move = (ev: PointerEvent) => {
    onDelta(ev.clientX - last, width);
    last = ev.clientX;
  };
  const up = () => {
    handle.removeEventListener("pointermove", move);
    handle.removeEventListener("pointerup", up);
  };
  handle.addEventListener("pointermove", move);
  handle.addEventListener("pointerup", up);
}

function CarPane() {
  const [Scene, setScene] = useState<ComponentType | null>(null);
  useEffect(() => {
    let live = true;
    import("./scene").then((mod) => {
      if (live) setScene(() => mod.MustangScene);
    });
    return () => {
      live = false;
    };
  }, []);
  if (!Scene) return <div className="bay-fallback">Opening the bay…</div>;
  return <Scene />;
}

function bayBackground(look: { bgHex: string; bgAlpha: number; bgGrad: boolean; bgTo: string }) {
  const a = cssHex(look.bgHex, look.bgAlpha);
  if (!look.bgGrad) return a;
  return `linear-gradient(180deg, ${a}, ${cssHex(look.bgTo, look.bgAlpha)})`;
}

function cssHex(hex: string, alpha: number) {
  const h = hex.replace("#", "");
  const n = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  const r = parseInt(n.slice(0, 2), 16);
  const g = parseInt(n.slice(2, 4), 16);
  const b = parseInt(n.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function ColorPop({
  label,
  hex,
  alpha,
  grad,
  gradHex,
  onHex,
  onAlpha,
  onGrad,
  onGradHex,
  presets,
}: {
  label: string;
  hex: string;
  alpha: number;
  grad: boolean;
  gradHex: string;
  onHex: (hex: string) => void;
  onAlpha: (alpha: number) => void;
  onGrad: (on: boolean) => void;
  onGradHex: (hex: string) => void;
  presets?: { name: string; hex: string }[];
}) {
  const [open, setOpen] = useState(false);
  const chip = grad ? `linear-gradient(90deg, ${hex}, ${gradHex})` : hex;
  return (
    <div className="color-pop">
      <button type="button" className="chip color-launch" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        <span className="color-dot" style={{ background: chip, opacity: Math.max(0.15, alpha) }} />
        {label}
      </button>
      {open ? (
        <div className="color-card" role="dialog" aria-label={`${label} color`}>
          <label className="field">
            <span>Color</span>
            <input type="color" value={hex} onChange={(e) => onHex(e.target.value)} />
          </label>
          <label className="field">
            <span>Transparency {Math.round((1 - alpha) * 100)}%</span>
            <input type="range" min={0} max={100} value={Math.round((1 - alpha) * 100)} onChange={(e) => onAlpha(1 - Number(e.target.value) / 100)} />
          </label>
          <label className="check-line">
            <input type="checkbox" checked={grad} onChange={(e) => onGrad(e.target.checked)} />
            Gradient
          </label>
          {grad ? (
            <label className="field">
              <span>Second color</span>
              <input type="color" value={gradHex} onChange={(e) => onGradHex(e.target.value)} />
            </label>
          ) : null}
          {presets ? (
            <div className="swatches">
              {presets.map((item) => (
                <button key={item.hex} type="button" className="swatch" style={{ background: item.hex }} aria-label={item.name} onClick={() => onHex(item.hex)} />
              ))}
            </div>
          ) : null}
          <button type="button" className="btn" onClick={() => setOpen(false)}>
            Done
          </button>
        </div>
      ) : null}
    </div>
  );
}
