import { OrbitControls, RoundedBox } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { HARNESS } from "@/lib/mustang/harness";
import { explodeOf, live, openAmount, settleStage } from "@/lib/mustang/live";
import { PARTS } from "@/lib/mustang/parts";
import { coupeGeometry, focusPoint, PRIMS, type Prim } from "@/lib/mustang/geometry";
import { useMustang } from "@/lib/mustang/store";
import { CIRCUIT_COLOR, type Circuit } from "@/lib/mustang/types";
import { sectionActive, visualRole, type Role } from "@/lib/mustang/visual";

const NO_RAYCAST = () => null;

function DashedEdges({ geometry, color }: { geometry: THREE.BufferGeometry; color: string }) {
  const ref = useRef<THREE.LineSegments>(null);
  useLayoutEffect(() => {
    const line = ref.current;
    if (!line) return;
    geometry.computeBoundingSphere();
    const radius = geometry.boundingSphere?.radius ?? 0.2;
    const dash = Math.min(0.055, Math.max(0.007, radius * 0.16));
    const mat = line.material as THREE.LineDashedMaterial;
    mat.color.set(color);
    mat.dashSize = dash;
    mat.gapSize = dash * 0.62;
    line.computeLineDistances();
  }, [geometry, color]);
  return (
    <lineSegments ref={ref} geometry={geometry} raycast={NO_RAYCAST} frustumCulled={false} renderOrder={2}>
      <lineDashedMaterial color={color} depthTest depthWrite={false} toneMapped={false} transparent={false} opacity={1} />
    </lineSegments>
  );
}

function edgesFrom(source: THREE.BufferGeometry) {
  const edges = new THREE.EdgesGeometry(source, 28);
  source.dispose();
  return edges;
}

function PartOutline({ prim, color }: { prim: Prim; color: string }) {
  const geom = useMemo(() => {
    if (prim.shape === "box") {
      const [w, h, d] = prim.args;
      return edgesFrom(new THREE.BoxGeometry(w, h, d));
    }
    if (prim.shape === "cyl") {
      const [rt, rb, h, seg] = prim.args;
      return edgesFrom(new THREE.CylinderGeometry(rt, rb ?? rt, h, Math.min(seg ?? 12, 12)));
    }
    if (prim.shape === "sph") return edgesFrom(new THREE.SphereGeometry(prim.args[0], 10, 8));
    return edgesFrom(new THREE.TorusGeometry(prim.args[0], prim.args[1], 8, 14));
  }, [prim]);
  useEffect(() => () => geom.dispose(), [geom]);
  return <DashedEdges geometry={geom} color={color} />;
}

function BoxOutline({
  size,
  position,
  rotation,
  color,
}: {
  size: [number, number, number];
  position: [number, number, number];
  rotation?: [number, number, number];
  color: string;
}) {
  const geom = useMemo(() => edgesFrom(new THREE.BoxGeometry(size[0], size[1], size[2])), [size[0], size[1], size[2]]);
  useEffect(() => () => geom.dispose(), [geom]);
  return (
    <group position={position} rotation={rotation}>
      <DashedEdges geometry={geom} color={color} />
    </group>
  );
}

function DashedRun({ points, color }: { points: [number, number, number][]; color: string }) {
  const geom = useMemo(() => {
    const v = points.map((p) => new THREE.Vector3(p[0], p[1], p[2]));
    const curve =
      v.length >= 3
        ? new THREE.CatmullRomCurve3(v)
        : new THREE.CatmullRomCurve3([v[0]!, v[0]!.clone().lerp(v[1] ?? v[0]!, 0.5), v[1] ?? v[0]!]);
    return new THREE.BufferGeometry().setFromPoints(curve.getPoints(56));
  }, [points]);
  const ref = useRef<THREE.Line>(null);
  useLayoutEffect(() => {
    const line = ref.current;
    if (!line) return;
    const mat = line.material as THREE.LineDashedMaterial;
    mat.dashSize = 0.05;
    mat.gapSize = 0.032;
    line.computeLineDistances();
  }, [geom]);
  useEffect(() => () => geom.dispose(), [geom]);
  return (
    <line ref={ref} geometry={geom} raycast={NO_RAYCAST} frustumCulled={false} renderOrder={2}>
      <lineDashedMaterial color={color} depthTest depthWrite={false} toneMapped={false} transparent={false} opacity={1} />
    </line>
  );
}

const gradCache = new Map<string, THREE.CanvasTexture>();
function gradTexture(from: string, to: string) {
  const key = `${from}|${to}`;
  const hit = gradCache.get(key);
  if (hit) return hit;
  const canvas = document.createElement("canvas");
  canvas.width = 8;
  canvas.height = 128;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  const g = ctx.createLinearGradient(0, 0, 0, 128);
  g.addColorStop(0, from);
  g.addColorStop(1, to);
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 8, 128);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  gradCache.set(key, tex);
  return tex;
}

function anchorOf(id: string): [number, number, number] {
  const run = HARNESS.find((item) => item.id === id);
  const pts = run?.runs[0];
  if (pts && pts.length) return pts[Math.floor(pts.length / 2)]!;
  return focusPoint(id);
}

function Rig() {
  const camera = useThree((s) => s.camera);
  const controls = useThree((s) => s.controls) as unknown as {
    target: THREE.Vector3;
    addEventListener: (type: string, cb: () => void) => void;
    removeEventListener: (type: string, cb: () => void) => void;
  } | null;
  const focusTick = useMustang((s) => s.focusTick);
  const look = useRef(new THREE.Vector3(0, 0.62, 0));
  const wantDist = useRef<number | null>(null);

  useEffect(() => {
    if (!controls) return;
    const stop = () => {
      live.focusing = false;
      live.focusId = null;
      wantDist.current = null;
      live.recenter = false;
      live.dolly = null;
    };
    controls.addEventListener("start", stop);
    return () => controls.removeEventListener("start", stop);
  }, [controls]);

  useEffect(() => {
    if (!live.focusId) return;
    const part = PARTS[live.focusId];
    const stage = Math.max(live.stage, part?.stage ?? live.targetStage);
    live.targetStage = stage;
    wantDist.current = Math.min(6.4, Math.max(0.62, 7.4 - stage * 1.2));
    live.focusing = true;
  }, [focusTick]);

  useFrame((_, dt) => {
    const step = 1 - Math.exp(-4.2 * Math.min(dt, 0.05));
    settleStage(dt);
    if (!controls) return;

    if (live.dolly != null) {
      const offset = camera.position.clone().sub(controls.target);
      const dist = offset.length() || 1;
      const next = dist + (live.dolly - dist) * step;
      offset.setLength(next);
      camera.position.copy(controls.target).add(offset);
      if (Math.abs(next - live.dolly) < 0.04) live.dolly = null;
    }

    if (live.focusing && live.focusId) {
      live.recenter = false;
      const base = anchorOf(live.focusId);
      const ex = explodeOf(live.focusId, live.stage);
      look.current.set(base[0] + ex[0], base[1] + ex[1], base[2] + ex[2]);
      controls.target.lerp(look.current, step);
      if (wantDist.current != null) {
        const offset = camera.position.clone().sub(controls.target);
        const dist = Math.max(offset.length(), 0.001);
        const next = dist + (wantDist.current - dist) * step;
        offset.setLength(next);
        camera.position.copy(controls.target).add(offset);
        if (Math.abs(next - wantDist.current) < 0.06 && Math.abs(live.stage - live.targetStage) < 0.06) {
          live.focusing = false;
          wantDist.current = null;
        }
      }
    } else if (live.recenter) {
      look.current.set(0, 0.62, 0.05);
      controls.target.lerp(look.current, step);
      if (look.current.distanceTo(controls.target) < 0.04) live.recenter = false;
    }
  });

  return null;
}

let pointerX = 0;
let pointerY = 0;

const TUCKED = new Set([
  "hood",
  "fender-fl",
  "fender-fr",
  "door-l",
  "door-r",
  "quarter-l",
  "quarter-r",
  "roof",
  "trunk",
  "bumper-f",
  "bumper-r",
  "rocker-l",
  "rocker-r",
  "windshield",
  "rear-glass",
  "glass-door-l",
  "glass-door-r",
]);

function Shell() {
  const paintHex = useMustang((s) => s.paintHex);
  const paintTo = useMustang((s) => s.paintTo);
  const paintGrad = useMustang((s) => s.paintGrad);
  const paintAlpha = useMustang((s) => s.paintAlpha);
  const select = useMustang((s) => s.select);
  const setHover = useMustang((s) => s.setHover);
  const openMenu = useMustang((s) => s.openMenu);
  const selected = useMustang((s) => s.selected);
  const system = useMustang((s) => s.system);
  const section = useMustang((s) => s.section);
  const circuit = useMustang((s) => s.circuit);
  const hidden = useMustang((s) => !!s.hidden.unibody);
  const body = useRef<THREE.MeshStandardMaterial>(null);
  const glass = useRef<THREE.MeshStandardMaterial>(null);
  const flashAt = useRef(-10);
  const wasHot = useRef(false);
  const geo = useMemo(() => coupeGeometry(), []);
  const shellEdges = useMemo(() => new THREE.EdgesGeometry(geo, 28), [geo]);
  useEffect(() => () => shellEdges.dispose(), [shellEdges]);
  const map = useMemo(() => (paintGrad ? gradTexture(paintHex, paintTo) : null), [paintGrad, paintHex, paintTo]);
  const ghosting = sectionActive(system, section, circuit, selected) || (!!selected && system === "all" && section == null);

  useFrame((state) => {
    const hot = selected === "unibody";
    if (hot && !wasHot.current) flashAt.current = state.clock.elapsedTime;
    wasHot.current = hot;
    const age = state.clock.elapsedTime - flashAt.current;
    if (body.current) {
      if (ghosting && !hot) {
        body.current.color.set("#f4f4f2");
        body.current.emissive.set("#000000");
        body.current.emissiveIntensity = 0;
        body.current.map = null;
        body.current.opacity = 0.12;
        body.current.transparent = true;
        body.current.depthWrite = false;
      } else if (hot) {
        const red = age < 0.34;
        body.current.color.set(red ? "#ff2d2d" : "#39ff6a");
        body.current.emissive.set(red ? "#ff2d2d" : "#39ff6a");
        body.current.emissiveIntensity = 0.8;
        body.current.map = null;
        body.current.opacity = 0.92;
        body.current.transparent = true;
        body.current.depthWrite = false;
      } else {
        body.current.color.set(map ? "#ffffff" : paintHex);
        body.current.map = map;
        body.current.emissive.set("#000000");
        body.current.emissiveIntensity = 0;
        body.current.opacity = paintAlpha;
        body.current.transparent = paintAlpha < 0.98;
        body.current.depthWrite = paintAlpha > 0.85;
      }
    }
    if (glass.current) {
      glass.current.opacity = 0.45 * paintAlpha;
    }
  });

  if (hidden) return null;

  const pass = ghosting && selected !== "unibody";
  if (pass) {
    return (
      <group>
        <DashedEdges geometry={shellEdges} color="#f7f7f5" />
        <BoxOutline size={[1.2, 0.58, 0.02]} position={[0, 1.02, -0.22]} rotation={[0.5, 0, 0]} color="#f7f7f5" />
        <BoxOutline size={[1.12, 0.42, 0.02]} position={[0, 1.04, 0.9]} rotation={[-0.55, 0, 0]} color="#f7f7f5" />
        <BoxOutline size={[0.02, 0.28, 0.7]} position={[-0.84, 0.95, 0.15]} color="#f7f7f5" />
        <BoxOutline size={[0.02, 0.28, 0.7]} position={[0.84, 0.95, 0.15]} color="#f7f7f5" />
      </group>
    );
  }
  return (
    <group>
      <mesh
        geometry={geo}
        castShadow
        receiveShadow
        onClick={(e) => {
          e.stopPropagation();
          select("unibody", false);
        }}
        onContextMenu={(e) => {
          e.stopPropagation();
          e.nativeEvent.preventDefault();
          openMenu("unibody", e.nativeEvent.clientX, e.nativeEvent.clientY);
          live.menuFromPart = true;
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          setHover("unibody");
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => {
          setHover(null);
          document.body.style.cursor = "";
        }}
      >
        <meshStandardMaterial ref={body} color={paintHex} map={map} metalness={0.55} roughness={0.38} side={THREE.DoubleSide} transparent opacity={paintAlpha} />
      </mesh>
      <mesh position={[0, 1.02, -0.22]} rotation={[0.5, 0, 0]} raycast={NO_RAYCAST}>
        <boxGeometry args={[1.2, 0.58, 0.02]} />
        <meshStandardMaterial ref={glass} color="#1c2830" metalness={0.4} roughness={0.08} transparent opacity={0.45} depthWrite={false} />
      </mesh>
      <mesh position={[0, 1.04, 0.9]} rotation={[-0.55, 0, 0]} raycast={NO_RAYCAST}>
        <boxGeometry args={[1.12, 0.42, 0.02]} />
        <meshStandardMaterial color="#1c2830" metalness={0.4} roughness={0.08} transparent opacity={0.4} depthWrite={false} />
      </mesh>
      <mesh position={[-0.84, 0.95, 0.15]} raycast={NO_RAYCAST}>
        <boxGeometry args={[0.02, 0.28, 0.7]} />
        <meshStandardMaterial color="#1a242c" metalness={0.3} roughness={0.12} transparent opacity={0.55} depthWrite={false} />
      </mesh>
      <mesh position={[0.84, 0.95, 0.15]} raycast={NO_RAYCAST}>
        <boxGeometry args={[0.02, 0.28, 0.7]} />
        <meshStandardMaterial color="#1a242c" metalness={0.3} roughness={0.12} transparent opacity={0.55} depthWrite={false} />
      </mesh>
    </group>
  );
}

function RoleMaterial({
  role,
  hot,
  color,
  map,
  metal,
  rough,
  opacity,
  emissive,
  emissiveIntensity,
  xray,
}: {
  role: Role;
  hot: boolean;
  color: string;
  map: THREE.Texture | null;
  metal: number;
  rough: number;
  opacity: number;
  emissive: string;
  emissiveIntensity: number;
  xray?: boolean;
}) {
  const ref = useRef<THREE.MeshStandardMaterial>(null);
  const flashAt = useRef(-10);
  const wasHot = useRef(false);
  useFrame((state) => {
    const mat = ref.current;
    if (!mat) return;
    const neon = role === "neon" || !!xray;
    if (hot && neon && !wasHot.current) flashAt.current = state.clock.elapsedTime;
    wasHot.current = hot && neon;
    const age = state.clock.elapsedTime - flashAt.current;
    if (neon) {
      const red = hot && !xray && age < 0.34;
      mat.color.set(red ? "#ff2d2d" : "#39ff6a");
      mat.emissive.set(red ? "#ff2d2d" : "#39ff6a");
      mat.emissiveIntensity = xray ? 0.7 : 1;
      mat.map = null;
      mat.opacity = xray ? 0.55 : 1;
      mat.transparent = Boolean(xray);
      mat.depthWrite = !xray;
      mat.depthTest = !xray;
    } else if (role === "parent") {
      mat.color.set("#f7f7f4");
      mat.emissive.set("#c5d0c4");
      mat.emissiveIntensity = 0.12;
      mat.map = null;
      mat.opacity = 0.24;
      mat.transparent = true;
      mat.depthWrite = false;
      mat.depthTest = true;
    } else if (role === "ghost") {
      mat.color.set("#f4f4f2");
      mat.emissive.set("#000000");
      mat.emissiveIntensity = 0;
      mat.map = null;
      mat.opacity = 0.075;
      mat.transparent = true;
      mat.depthWrite = false;
      mat.depthTest = true;
    } else {
      mat.color.set(map ? "#ffffff" : color);
      mat.map = map;
      mat.emissive.set(emissive);
      mat.emissiveIntensity = emissiveIntensity;
      mat.opacity = opacity;
      mat.transparent = opacity < 0.98;
      mat.depthWrite = opacity > 0.85;
      mat.depthTest = true;
    }
  });
  return <meshStandardMaterial ref={ref} color={color} metalness={metal} roughness={rough} />;
}

function PartMeshes({ id, prims }: { id: string; prims: Prim[] }) {
  const ref = useRef<THREE.Group>(null);
  const paintHex = useMustang((s) => s.paintHex);
  const paintTo = useMustang((s) => s.paintTo);
  const paintGrad = useMustang((s) => s.paintGrad);
  const paintAlpha = useMustang((s) => s.paintAlpha);
  const selected = useMustang((s) => s.selected);
  const trace = useMustang((s) => s.trace);
  const system = useMustang((s) => s.system);
  const section = useMustang((s) => s.section);
  const circuit = useMustang((s) => s.circuit);
  const trans = useMustang((s) => s.trans);
  const select = useMustang((s) => s.select);
  const setHover = useMustang((s) => s.setHover);
  const openMenu = useMustang((s) => s.openMenu);
  const hidden = useMustang((s) => !!s.hidden[id]);
  const part = PARTS[id];
  const role = visualRole(id, selected, system, circuit, section);
  const isolate = !!selected && system === "all" && section == null;

  useFrame(() => {
    if (!ref.current) return;
    const [x, y, z] = explodeOf(id, live.stage);
    ref.current.position.set(x, y, z);
    const opened = !TUCKED.has(id) || openAmount(live.stage, part?.stage ?? 1) > 0.001;
    ref.current.visible = !hidden && role !== "hide" && (role !== "normal" || opened);
  });

  const visible = prims.some((p) => !p.only || p.only === trans);
  if (!visible || hidden || role === "hide") return null;

  const hot = selected === id;
  const warm = !hot && trace.includes(id);
  const pass = role === "ghost";
  const paintMap = paintGrad ? gradTexture(paintHex, paintTo) : null;

  const draw = (p: Prim, i: number, xray: boolean) => {
    if (p.only && p.only !== trans) return null;
    const baseOpacity = Math.min(1, (p.opacity ?? 1) * (p.paint ? paintAlpha : 1));
    const color = p.paint ? paintHex : p.color;
    const emissive = warm ? "#d9dce2" : (p.emissive ?? "#000000");
    const emissiveIntensity = warm ? 0.32 : (p.emissiveIntensity ?? 0);
    const rough = p.rough ?? 0.55;
    const metal = p.metal ?? 0.45;
    if ((role === "ghost" || role === "parent") && !xray) {
      return (
        <group key={i} position={p.pos} rotation={p.rot}>
          <PartOutline prim={p} color={role === "parent" ? "#d5e0d4" : "#f7f7f5"} />
        </group>
      );
    }
    const onOver = (e: { stopPropagation: () => void }) => {
      if (pass || xray) return;
      e.stopPropagation();
      setHover(id);
      document.body.style.cursor = "pointer";
    };
    const shared = {
      castShadow: !xray && Boolean(p.shadow) && role === "normal",
      receiveShadow: !xray && role === "normal",
      raycast: pass || xray ? NO_RAYCAST : undefined,
      renderOrder: xray ? 3 : role === "ghost" ? 0 : 1,
      onPointerOver: onOver,
      onPointerOut: (e: { stopPropagation: () => void }) => {
        e.stopPropagation();
        setHover(null);
        document.body.style.cursor = "";
      },
      onPointerDown: (e: { stopPropagation: () => void; nativeEvent: { clientX: number; clientY: number } }) => {
        if (pass || xray) return;
        e.stopPropagation();
        pointerX = e.nativeEvent.clientX;
        pointerY = e.nativeEvent.clientY;
      },
      onClick: (e: { stopPropagation: () => void; nativeEvent: { clientX: number; clientY: number } }) => {
        if (pass || xray) return;
        e.stopPropagation();
        const dx = e.nativeEvent.clientX - pointerX;
        const dy = e.nativeEvent.clientY - pointerY;
        if (dx * dx + dy * dy > 25) return;
        select(id, false);
      },
      onContextMenu: (e: { stopPropagation: () => void; nativeEvent: MouseEvent }) => {
        if (pass || xray) return;
        e.stopPropagation();
        e.nativeEvent.preventDefault();
        openMenu(id, e.nativeEvent.clientX, e.nativeEvent.clientY);
        live.menuFromPart = true;
      },
    };
    const mat = (
      <RoleMaterial
        role={xray ? "neon" : role}
        hot={hot}
        xray={xray}
        color={color}
        map={p.paint ? paintMap : null}
        metal={metal}
        rough={rough}
        opacity={baseOpacity}
        emissive={emissive}
        emissiveIntensity={emissiveIntensity}
      />
    );
    if (p.shape === "box") {
      const [w, h, d] = p.args;
      const r = Math.min(p.radius ?? 0, w / 2 - 0.001, h / 2 - 0.001, d / 2 - 0.001);
      if (r > 0.008) {
        return (
          <RoundedBox key={i} args={[w, h, d]} radius={r} smoothness={2} position={p.pos} rotation={p.rot} {...shared}>
            {mat}
          </RoundedBox>
        );
      }
      return (
        <mesh key={i} position={p.pos} rotation={p.rot} {...shared}>
          <boxGeometry args={[w, h, d]} />
          {mat}
        </mesh>
      );
    }
    if (p.shape === "cyl") {
      const [rt, rb, h, seg] = p.args;
      return (
        <mesh key={i} position={p.pos} rotation={p.rot} {...shared}>
          <cylinderGeometry args={[rt, rb ?? rt, h, seg ?? 20]} />
          {mat}
        </mesh>
      );
    }
    if (p.shape === "sph") {
      return (
        <mesh key={i} position={p.pos} rotation={p.rot} {...shared}>
          <sphereGeometry args={[p.args[0], p.args[1] ?? 16, p.args[2] ?? 12]} />
          {mat}
        </mesh>
      );
    }
    return (
      <mesh key={i} position={p.pos} rotation={p.rot} {...shared}>
        <torusGeometry args={[p.args[0], p.args[1], p.args[2] ?? 8, p.args[3] ?? 18]} />
        {mat}
      </mesh>
    );
  };

  return (
    <>
      <group ref={ref}>{prims.map((p, i) => draw(p, i, false))}</group>
      {isolate && hot ? <group>{prims.map((p, i) => draw(p, i, true))}</group> : null}
    </>
  );
}

function WireRun({
  id,
  circuit,
  points,
  radius,
}: {
  id: string;
  circuit: Circuit;
  points: [number, number, number][];
  radius: number;
}) {
  const ref = useRef<THREE.Group>(null);
  const selected = useMustang((s) => s.selected);
  const trace = useMustang((s) => s.trace);
  const circuitFilter = useMustang((s) => s.circuit);
  const system = useMustang((s) => s.system);
  const section = useMustang((s) => s.section);
  const select = useMustang((s) => s.select);
  const setHover = useMustang((s) => s.setHover);
  const openMenu = useMustang((s) => s.openMenu);
  const hidden = useMustang((s) => !!s.hidden[id]);
  const role: Role = PARTS[id]
    ? visualRole(id, selected, system, circuitFilter, section)
    : (() => {
        const isolate = !!selected && system === "all" && section == null;
        if (isolate) return id === selected || trace.includes(id) ? "neon" : "hide";
        if (sectionActive(system, section, circuitFilter, selected)) {
          if (circuitFilter !== "all" && circuitFilter !== circuit) return "ghost";
          if (system !== "all" && system !== "electrical" && system !== "fuel") return "ghost";
          return "neon";
        }
        return "normal";
      })();
  const geom = useMemo(() => {
    const v = points.map((p) => new THREE.Vector3(p[0], p[1], p[2]));
    const curve =
      v.length >= 3
        ? new THREE.CatmullRomCurve3(v)
        : new THREE.CatmullRomCurve3([v[0]!, v[0]!.clone().lerp(v[1]!, 0.5), v[1]!]);
    return new THREE.TubeGeometry(curve, 40, radius, 6, false);
  }, [points, radius]);

  useFrame(() => {
    if (!ref.current) return;
    const [x, y, z] = explodeOf(id, live.stage);
    ref.current.position.set(x, y, z);
    ref.current.visible = !hidden && role !== "hide";
  });

  if (hidden || role === "hide") return null;

  const hot = selected === id;
  const pass = role === "ghost" || role === "parent";
  if (pass) {
    return (
      <group ref={ref}>
        <DashedRun points={points} color={role === "parent" ? "#d5e0d4" : "#f7f7f5"} />
      </group>
    );
  }
  return (
    <group ref={ref}>
      <mesh
        geometry={geom}
        raycast={pass ? NO_RAYCAST : undefined}
        onPointerOver={(e) => {
          if (pass) return;
          e.stopPropagation();
          setHover(id);
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={(e) => {
          e.stopPropagation();
          setHover(null);
          document.body.style.cursor = "";
        }}
        onPointerDown={(e) => {
          if (pass) return;
          e.stopPropagation();
          pointerX = e.nativeEvent.clientX;
          pointerY = e.nativeEvent.clientY;
        }}
        onClick={(e) => {
          if (pass) return;
          e.stopPropagation();
          const dx = e.nativeEvent.clientX - pointerX;
          const dy = e.nativeEvent.clientY - pointerY;
          if (dx * dx + dy * dy > 25) return;
          select(id, false);
        }}
        onContextMenu={(e) => {
          if (pass) return;
          e.stopPropagation();
          e.nativeEvent.preventDefault();
          openMenu(id, e.nativeEvent.clientX, e.nativeEvent.clientY);
          live.menuFromPart = true;
        }}
      >
        <RoleMaterial
          role={role}
          hot={hot}
          color={CIRCUIT_COLOR[circuit]}
          map={null}
          metal={0.2}
          rough={0.45}
          opacity={1}
          emissive={CIRCUIT_COLOR[circuit]}
          emissiveIntensity={0.18}
        />
      </mesh>
    </group>
  );
}

function Leaders() {
  const lines = useMemo(() => {
    const ids = [...new Set(PRIMS.map((p) => p.id))];
    return ids.map((id) => {
      const geo = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(),
        new THREE.Vector3(0, 0.001, 0),
      ]);
      const mat = new THREE.LineDashedMaterial({
        color: 0xf4f4f5,
        dashSize: 0.05,
        gapSize: 0.038,
        transparent: true,
        opacity: 0.9,
      });
      const line = new THREE.Line(geo, mat);
      line.computeLineDistances();
      line.raycast = NO_RAYCAST;
      line.userData.partId = id;
      line.frustumCulled = false;
      line.visible = false;
      return line;
    });
  }, []);
  const ref = useRef<THREE.Group>(null);

  useEffect(() => {
    const group = ref.current;
    if (!group) return;
    for (const line of lines) group.add(line);
    return () => {
      for (const line of lines) group.remove(line);
    };
  }, [lines]);

  useFrame(() => {
    const state = useMustang.getState();
    for (const line of lines) {
      const id = line.userData.partId as string;
      const role = visualRole(id, state.selected, state.system, state.circuit, state.section);
      const part = PARTS[id];
      const ex = explodeOf(id, live.stage);
      const home = focusPoint(id);
      const parentId = part?.parent;
      const parent = parentId ? PARTS[parentId] : undefined;
      const parentHome = parent ? focusPoint(parentId as string) : home;
      const pex = parent ? explodeOf(parentId as string, live.stage) : [0, 0, 0];
      const x0 = parent ? parentHome[0] + pex[0] : home[0];
      const y0 = parent ? parentHome[1] + pex[1] : home[1];
      const z0 = parent ? parentHome[2] + pex[2] : home[2];
      const x1 = home[0] + ex[0];
      const y1 = home[1] + ex[1];
      const z1 = home[2] + ex[2];
      const dist = Math.hypot(x1 - x0, y1 - y0, z1 - z0);
      const show = dist > 0.04 && !state.hidden[id] && role !== "hide" && role !== "ghost";
      line.visible = show;
      if (!show) continue;
      const mat = line.material as THREE.LineDashedMaterial;
      mat.color.set(role === "neon" ? "#39ff6a" : "#f4f4f5");
      const pos = line.geometry.getAttribute("position") as THREE.BufferAttribute;
      pos.setXYZ(0, x0, y0, z0);
      pos.setXYZ(1, x1, y1, z1);
      pos.needsUpdate = true;
      line.computeLineDistances();
    }
  });

  return <group ref={ref} />;
}

function PointerTools() {
  const gl = useThree((s) => s.gl);
  useEffect(() => {
    const el = gl.domElement;
    const onWheel = (e: WheelEvent) => {
      if (!e.shiftKey) return;
      e.preventDefault();
      e.stopImmediatePropagation();
      const step = Math.max(-0.28, Math.min(0.28, -e.deltaY / 320));
      live.targetStage = Math.max(0, Math.min(5, live.targetStage + step));
      live.focusing = false;
      live.focusId = null;
      live.dolly = null;
    };
    const blockMenu = (e: Event) => {
      live.menuFromPart = false;
      e.preventDefault();
    };
    const onMenu = (e: MouseEvent) => {
      if (live.menuFromPart) return;
      const state = useMustang.getState();
      if (!Object.keys(state.hidden).length) {
        state.closeMenu();
        return;
      }
      state.openMenu(null, e.clientX, e.clientY);
    };
    el.addEventListener("wheel", onWheel, { capture: true, passive: false });
    el.addEventListener("contextmenu", blockMenu, true);
    el.addEventListener("contextmenu", onMenu);
    return () => {
      el.removeEventListener("wheel", onWheel, true);
      el.removeEventListener("contextmenu", blockMenu, true);
      el.removeEventListener("contextmenu", onMenu);
    };
  }, [gl]);
  return null;
}

function Car() {
  const groups = useMemo(() => {
    const map = new Map<string, Prim[]>();
    for (const prim of PRIMS) {
      const list = map.get(prim.id);
      if (list) list.push(prim);
      else map.set(prim.id, [prim]);
    }
    return [...map.entries()].filter(([id]) => id !== "floor");
  }, []);

  return (
    <group>
      {groups.map(([id, list]) => (
        <PartMeshes key={id} id={id} prims={list} />
      ))}
      {HARNESS.map((harness) =>
        harness.runs.map((run, i) => (
          <WireRun key={`${harness.id}-${i}`} id={harness.id} circuit={harness.circuit} points={run} radius={harness.radius} />
        )),
      )}
    </group>
  );
}

function Bay() {
  return (
    <>
      <hemisphereLight args={["#d7dbe2", "#2a2722", 0.55]} />
      <ambientLight intensity={0.28} />
      <directionalLight
        position={[6, 9, 5]}
        intensity={1.55}
        castShadow
        shadow-mapSize-width={1024}
        shadow-mapSize-height={1024}
        shadow-camera-far={30}
        shadow-camera-left={-8}
        shadow-camera-right={8}
        shadow-camera-top={8}
        shadow-camera-bottom={-8}
      />
      <directionalLight position={[-5, 4, -3]} intensity={0.35} color="#c9d2dc" />
      <Car />
      <Shell />
      <Leaders />
      <PointerTools />
      <Rig />
      <OrbitControls
        makeDefault
        enableDamping
        dampingFactor={0.08}
        minDistance={0.28}
        maxDistance={14}
        maxPolarAngle={Math.PI * 0.995}
        target={[0, 0.62, 0.05]}
      />
    </>
  );
}

export function MustangScene() {
  return (
    <Canvas
      className="bay-canvas"
      dpr={[1, 1.75]}
      shadows
      camera={{ position: [5.5, 1.65, 6.55], fov: 36, near: 0.02, far: 50 }}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      onPointerMissed={() => useMustang.getState().select(null)}
      onCreated={({ gl, scene }) => {
        gl.toneMapping = THREE.ACESFilmicToneMapping;
        gl.toneMappingExposure = 1.05;
        gl.setClearColor(0x000000, 0);
        scene.background = null;
      }}
    >
      <Bay />
    </Canvas>
  );
}
