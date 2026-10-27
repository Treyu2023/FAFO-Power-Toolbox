import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { commonGeometry, coupeGeometry, type Prim } from "@/lib/auto/geometry";
import { runsFor, type ServiceRun } from "@/lib/auto/hoses";
import { groupIdOf, groupsFor, primsFor, type GroupInfo } from "@/lib/auto/model";
import type { CarSpec } from "@/lib/auto/resolve";
import { DEFAULT_LOOK, STAGE_NAMES, type Look, type SavedView, type Shift, type SystemId } from "@/lib/auto/scene-types";

type Node = {
  info: GroupInfo;
  group: THREE.Group;
  meshes: THREE.Mesh[];
  edges: THREE.LineSegments[];
  rest: THREE.Vector3;
  centroid: THREE.Vector3;
  shift: THREE.Vector3;
  shiftFrom: number;
  home: THREE.Vector3;
  boost: number;
  hidden: boolean;
  line: THREE.Line;
};

type Grad = { a: THREE.Color; b: THREE.Color; on: { value: number }; dir: { value: number }; rest: THREE.Vector3 };

export type MenuHit = { x: number; y: number; id: string; name: string; system: string };

export type CarEvents = {
  onSelect: (id: string | null) => void;
  onMenu: (menu: MenuHit | null) => void;
  onStage: (stage: number) => void;
  onHover: (hit: MenuHit | null) => void;
  onPaint: (id: string) => void;
  onDemo: (on: boolean) => void;
  onShift: (id: string, shift: Shift) => void;
  onHome: (id: string, home: { x: number; y: number; z: number }) => void;
  onDistance: (distance: number) => void;
};

export type CarHandle = {
  setSpec: (spec: CarSpec) => void;
  setLook: (look: Look) => void;
  setStage: (stage: number) => void;
  setFocus: (focus: SystemId) => void;
  setIsolate: (ids: string[] | null, color?: string, to?: string | null) => void;
  select: (id: string | null) => void;
  framePart: (id: string, frame: { mode: "still" | "orbit"; distance: number; orbit: number; transit: number } | null) => void;
  dollyTo: (distance: number) => void;
  orbitBy: (dx: number, dy: number) => void;
  hide: (id: string) => void;
  showHidden: () => void;
  restoreTextures: () => void;
  shiftOf: (id: string) => Shift | null;
  applyShifts: (shifts: Record<string, Shift>) => void;
  getSnapshot: () => SavedView;
  applyView: (view: SavedView) => void;
  setDemo: (on: boolean) => void;
  setIdleDemo: (on: boolean) => void;
  setIdleSeconds: (seconds: number) => void;
  clearShifts: () => void;
  clearShift: (id: string) => void;
  setEditing: (on: boolean) => void;
  applyHomes: (homes: Record<string, { x: number; y: number; z: number }>) => void;
  clearHome: (id: string) => void;
  clearHomes: () => void;
  replacePart: (id: string, data: ArrayBuffer, name: string) => Promise<void>;
  clearPartModel: (id: string) => void;
  loadScan: (data: ArrayBuffer, name: string) => Promise<void>;
  setScanMode: (mode: "off" | "shell" | "both") => void;
  setScanUpright: (on: boolean) => void;
  clearScan: () => void;
  dispose: () => void;
};

const _a = new THREE.Vector3();
const _b = new THREE.Vector3();

function smooth(t: number, start: number) {
  if (start <= 0) return t > 0 ? 1 : 0;
  if (t <= start - 1) return 0;
  if (t >= start) return 1;
  const u = t - (start - 1);
  return u * u * (3 - 2 * u);
}

function makeGeom(prim: Prim) {
  if (prim.shape === "box") {
    const [w, h, d] = prim.args;
    const room = Math.min(w, h, d) / 2 - 0.001;
    const radius = Math.min(prim.radius ?? 0, Math.max(room, 0));
    if (radius > 0.004) return new RoundedBoxGeometry(w, h, d, 2, radius);
    return new THREE.BoxGeometry(w, h, d);
  }
  if (prim.shape === "cyl") return new THREE.CylinderGeometry(prim.args[0], prim.args[1] ?? prim.args[0], prim.args[2], Math.min(prim.args[3] ?? 16, 28));
  if (prim.shape === "sph") return new THREE.SphereGeometry(prim.args[0], prim.args[1] ?? 14, prim.args[2] ?? 10);
  return new THREE.TorusGeometry(prim.args[0], prim.args[1], prim.args[2] ?? 8, prim.args[3] ?? 14);
}

function numberBadge(text: string, color: string) {
  const mark = document.createElement("canvas");
  mark.width = 64;
  mark.height = 64;
  const ctx = mark.getContext("2d");
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ depthTest: false }));
  if (ctx) {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(32, 32, 28, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#14130f";
    ctx.font = "700 36px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, 32, 36);
    sprite.material.map = new THREE.CanvasTexture(mark);
    sprite.material.needsUpdate = true;
  }
  sprite.scale.set(0.08, 0.08, 1);
  sprite.raycast = () => null;
  return sprite;
}

export function mountCar(host: HTMLElement, events: CarEvents): CarHandle {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(host.clientWidth || 1, host.clientHeight || 1, false);
  renderer.domElement.style.width = "100%";
  renderer.domElement.style.height = "100%";
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.domElement.style.touchAction = "none";
  host.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  pmrem.dispose();
  const camera = new THREE.PerspectiveCamera(32, 1, 0.04, 80);
  camera.position.set(6.4, 2.15, -6.6);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 0.62, 0);
  controls.enableDamping = true;
  controls.enableZoom = false;
  controls.enablePan = true;
  controls.screenSpacePanning = true;
  controls.minDistance = 0.16;
  controls.maxDistance = 42;
  controls.mouseButtons.LEFT = THREE.MOUSE.ROTATE;
  controls.mouseButtons.RIGHT = THREE.MOUSE.PAN;
  controls.update();

  scene.add(new THREE.HemisphereLight("#f7f4ee", "#2a2926", 0.85));
  const sun = new THREE.DirectionalLight("#fff6e8", 1.35);
  sun.position.set(5, 8, 4);
  scene.add(sun);
  const root = new THREE.Group();
  scene.add(root);
  const room = new THREE.Group();
  scene.add(room);

  const nodes = new Map<string, Node>();
  const holders = new Map<string, THREE.Group>();
  let bodyHidden = false;
  let stage = 0;
  let stageVel = 0;
  let targetStage = 0;
  let focus: SystemId = "all";
  let isolate: Set<string> | null = null;
  let isolateColor = "#f4f4f2";
  let isolateTo: string | null = null;
  const fingers = new Map<number, { x: number; y: number }>();
  let pinch: number | null = null;
  let penSpin = false;
  const gaze = new THREE.Vector3();
  let framing: { id: string; mode: "still" | "orbit"; distance: number; orbit: number; transit: number } | null = null;
  let frameAngle = 0.9;
  let framePhi = 1.15;
  let selected: string | null = null;
  let look: Look | null = null;
  let disposed = false;
  let hoverId: string | null = null;
  let builtPlace: Look["place"] | null = null;
  let demo = false;
  let demoT = 0;
  let idle = 0;
  let idleLimit = 180;
  const scanHolder = new THREE.Group();
  scanHolder.name = "scan";
  const scanRest = new THREE.Vector3();
  let scanMode: "off" | "shell" | "both" = "off";
  let scanUpright = false;
  let spec: CarSpec = {
    pack: "mustang",
    body: "coupe",
    engine: "v6",
    trans: "manual",
    axle: "solid",
    scoop: false,
    paint: "#8f1d22",
  };

  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  const plane = new THREE.Plane();
  const hit = new THREE.Vector3();
  const lastHit = new THREE.Vector3();
  const desired = new THREE.Vector3();
  const desiredTarget = new THREE.Vector3();
  let dragging: Node | null = null;
  let left: { x: number; y: number; node: Node | null } | null = null;
  let right: { x: number; y: number; moved: boolean } | null = null;

  const backdropCanvas = document.createElement("canvas");
  backdropCanvas.width = 512;
  backdropCanvas.height = 512;
  const backdropTex = new THREE.CanvasTexture(backdropCanvas);
  backdropTex.colorSpace = THREE.SRGBColorSpace;

  function clearNodes() {
    for (const holder of holders.values()) holder.removeFromParent();
    scanHolder.removeFromParent();
    for (const node of nodes.values()) {
      node.group.traverse((child) => {
        const mesh = child as THREE.Mesh;
        if (!mesh.userData.shared) mesh.geometry?.dispose();
        const material = mesh.material;
        if (Array.isArray(material)) material.forEach((item) => item.dispose());
        else material?.dispose();
      });
      node.line.geometry.dispose();
      (node.line.material as THREE.Material).dispose();
      scene.remove(node.line);
    }
    root.clear();
    nodes.clear();
  }

  function attachGradient(mat: THREE.MeshStandardMaterial): Grad {
    const existing = mat.userData.grad as Grad | undefined;
    if (existing) return existing;
    const grad: Grad = {
      a: new THREE.Color("#ffffff"),
      b: new THREE.Color("#000000"),
      on: { value: 0 },
      dir: { value: 0 },
      rest: new THREE.Vector3(),
    };
    mat.customProgramCacheKey = () => "fafo-paint";
    mat.onBeforeCompile = (shader) => {
      shader.uniforms.uPaintA = { value: grad.a };
      shader.uniforms.uPaintB = { value: grad.b };
      shader.uniforms.uGradOn = grad.on;
      shader.uniforms.uGradDir = grad.dir;
      shader.uniforms.uRest = { value: grad.rest };
      shader.vertexShader = shader.vertexShader
        .replace("#include <common>", "#include <common>\nuniform vec3 uRest;\nvarying vec3 vGrad;")
        .replace("#include <begin_vertex>", "#include <begin_vertex>\nvGrad = uRest + mat3(modelMatrix) * position;");
      shader.fragmentShader = shader.fragmentShader
        .replace("#include <common>", "#include <common>\nvarying vec3 vGrad;\nuniform vec3 uPaintA;\nuniform vec3 uPaintB;\nuniform float uGradOn;\nuniform float uGradDir;")
        .replace(
          "#include <color_fragment>",
          `#include <color_fragment>
           if (uGradOn > 0.5) {
             float g = uGradDir > 0.5 ? clamp((vGrad.y - 0.2) / 1.25, 0.0, 1.0) : clamp((vGrad.z + 2.2) / 4.3, 0.0, 1.0);
             diffuseColor.rgb = mix(uPaintA, uPaintB, g);
           }`,
        );
    };
    mat.userData.grad = grad;
    mat.needsUpdate = true;
    return grad;
  }

  function finishValues() {
    if (!look) return { metal: 0.45, rough: 0.42 };
    if (look.finish === "metal") return { metal: 0.82, rough: 0.22 };
    if (look.finish === "satin") return { metal: 0.2, rough: 0.62 };
    return { metal: 0.5, rough: 0.32 };
  }

  function armClicks() {
    for (const node of nodes.values()) {
      const ghost = ghostOf(node);
      const solid = !node.hidden && !ghost;
      for (const mesh of node.meshes) {
        const mat = mesh.material as THREE.MeshStandardMaterial;
        const clear = solid && !mesh.userData.swapped && mat.opacity > 0.04;
        mesh.raycast = clear ? THREE.Mesh.prototype.raycast : () => null;
      }
      const holder = holders.get(node.info.id);
      holder?.traverse((child) => {
        const mesh = child as THREE.Mesh;
        if (mesh.isMesh) mesh.raycast = solid ? THREE.Mesh.prototype.raycast : () => null;
      });
    }
  }

  function ghostOf(node: Node) {
    if (node.hidden) return false;
    if (isolate) return !isolate.has(node.info.id);
    if (focus === "all") return false;
    return node.info.system !== focus;
  }

  function keptOf(node: Node) {
    if (ghostOf(node) || node.hidden) return false;
    return isolate !== null || focus !== "all";
  }

  function applyLook() {
    const paint = look?.paint ?? spec.paint;
    const finish = finishValues();
    for (const node of nodes.values()) {
      const ghost = ghostOf(node);
      const hot = selected === node.info.id;
      const hovered = hoverId === node.info.id && !hot;
      const kept = keptOf(node);
      const style = look?.ghost ?? "wire";
      const custom = look?.partPaints?.[node.info.id];
      node.group.visible = !node.hidden;
      for (const mesh of node.meshes) {
        if (mesh.userData.swapped) {
          mesh.visible = false;
          mesh.raycast = () => null;
          continue;
        }
        const mat = mesh.material as THREE.MeshStandardMaterial;
        const base = (mesh.userData.base as string) || "#888888";
        const opaque = (mesh.userData.opacity ?? 1) > 0.9;
        const paintable = custom ? opaque : mesh.userData.paint === true || (node.info.system === "body" && opaque);
        const gradientOn = !ghost && (custom ? custom.gradient : paintable && !!look?.gradient);
        const from = custom?.color ?? (paintable ? paint : base);
        const to = custom?.to ?? look?.paintTo ?? from;
        if (ghost && (style === "translucent" || style === "both")) {
          mat.color.set(hot ? "#39ff6a" : "#f4f4f2");
          mat.map = null;
          mat.opacity = hot || hovered ? 0.45 : 0.12;
          mat.transparent = true;
          mat.depthWrite = false;
          mat.emissive.set(hot ? "#39ff6a" : hovered ? "#f4f4f2" : "#000000");
          mat.emissiveIntensity = hot || hovered ? 0.55 : 0;
        } else if (ghost) {
          mat.color.set(hot ? "#39ff6a" : "#f4f4f2");
          mat.opacity = hot || hovered ? 0.5 : 0;
          mat.transparent = true;
          mat.depthWrite = false;
          mat.emissive.set(hot ? "#39ff6a" : hovered ? "#f4f4f2" : "#000000");
          mat.emissiveIntensity = hot || hovered ? 0.6 : 0;
        } else if (paintable || custom) {
          mat.color.set(gradientOn ? "#ffffff" : from);
          mat.map = null;
          mat.opacity = mesh.userData.opacity ?? 1;
          mat.transparent = mat.opacity < 0.98;
          mat.depthWrite = mat.opacity > 0.85;
          if (node.info.system === "body" || mesh.userData.paint === true || node.info.id === "unibody") {
            mat.metalness = finish.metal;
            mat.roughness = finish.rough;
          }
          const grad = attachGradient(mat);
          grad.on.value = gradientOn ? 1 : 0;
          grad.dir.value = look?.direction === "height" ? 1 : 0;
          grad.a.set(from);
          grad.b.set(to);
          grad.rest.copy((mesh.userData.rest as THREE.Vector3 | undefined) ?? _a.set(0, 0, 0));
          mat.emissive.set(hot ? "#39ff6a" : hovered ? "#f4f4f2" : kept ? isolateColor : "#000000");
          mat.emissiveIntensity = hot ? 0.35 : hovered ? 0.5 : kept ? 0.22 : 0;
        } else {
          mat.color.set(base);
          mat.map = null;
          mat.opacity = mesh.userData.opacity ?? 1;
          mat.transparent = mat.opacity < 0.98;
          mat.depthWrite = true;
          const grad = mat.userData.grad as Grad | undefined;
          if (grad) grad.on.value = 0;
          mat.emissive.set(hot ? "#39ff6a" : hovered ? "#f4f4f2" : kept ? isolateColor : (mesh.userData.emissive as string) || "#000000");
          mat.emissiveIntensity = hot ? 0.45 : hovered ? 0.5 : kept ? 0.28 : (mesh.userData.emissiveIntensity as number) || 0;
        }
        if (kept && isolateTo && !ghost) {
          mat.color.set("#ffffff");
          mat.opacity = 1;
          mat.transparent = false;
          mat.depthWrite = true;
          const grad = attachGradient(mat);
          grad.on.value = 1;
          grad.dir.value = 1;
          grad.a.set(isolateColor);
          grad.b.set(isolateTo);
          grad.rest.copy((mesh.userData.rest as THREE.Vector3 | undefined) ?? _a.set(0, 0, 0));
          mat.emissive.set("#000000");
          mat.emissiveIntensity = 0;
          mesh.visible = true;
        }
        mesh.visible = !(ghost && (look?.ghost ?? "wire") === "wire");
        mesh.raycast = ghost || node.hidden || mesh.userData.swapped ? () => null : THREE.Mesh.prototype.raycast;
      }
      for (const edge of node.edges) edge.visible = ghost && !node.hidden && style !== "translucent" && !node.meshes.some((mesh) => mesh.userData.swapped);
    }
    scanHolder.visible = !bodyHidden && scanMode !== "off" && scanHolder.children.length > 0;
    scanHolder.traverse((child) => {
      const mesh = child as THREE.Mesh;
      if (!mesh.isMesh) return;
      const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      for (const mat of mats) {
        const saved = mat.userData.scanSaved as { transparent: boolean; opacity: number; depthWrite: boolean } | undefined;
        if (!saved) continue;
        if (scanMode === "both") {
          mat.transparent = true;
          mat.opacity = 0.42;
          mat.depthWrite = false;
        } else {
          mat.transparent = saved.transparent;
          mat.opacity = saved.opacity;
          mat.depthWrite = saved.depthWrite;
        }
      }
    });
  }

  function lead() {
    return scanMode === "shell" && scanHolder.children.length > 0 ? 1 : 0;
  }

  function maxStage() {
    return 4 + lead();
  }

  function unit(t: number) {
    const u = Math.min(1, Math.max(0, t));
    return u * u * (3 - 2 * u);
  }

  const shopSkin = new Set(["hood", "fender-fl", "fender-fr", "door-l", "door-r", "quarter-l", "quarter-r", "roof", "trunk", "bumper-f", "bumper-r", "mirror-l", "mirror-r", "rocker-l", "rocker-r", "interior"]);

  function localAt(node: Node, t: number, out: THREE.Vector3, live = false) {
    const start = node.info.stage + lead();
    const amt = live ? Math.max(smooth(t, start), node.boost) : smooth(t, start);
    const extra = live ? Math.max(smooth(t, 4 + lead()), node.boost > 0.85 ? 1 : 0) : smooth(t, 4 + lead());
    out.copy(node.rest);
    out.add(node.home);
    out.x += node.info.explode[0] * amt + node.info.extra[0] * extra;
    out.y += node.info.explode[1] * amt + node.info.extra[1] * extra;
    out.z += node.info.explode[2] * amt + node.info.extra[2] * extra;
    if (t >= node.shiftFrom) out.add(node.shift);
    return out;
  }

  function worldAt(node: Node, t: number, out: THREE.Vector3) {
    out.set(0, 0, 0);
    const chain: Node[] = [];
    let current: Node | undefined = node;
    while (current) {
      chain.push(current);
      current = current.info.parent ? nodes.get(current.info.parent) : undefined;
    }
    for (let i = chain.length - 1; i >= 0; i--) out.add(localAt(chain[i]!, t, _a, true));
    return out;
  }

  function placeScan(t: number) {
    if (!scanHolder.children.length || bodyHidden) return;
    scanHolder.position.copy(scanRest);
    if (!lead()) return;
    const lift = unit(Math.min(t, 1) / 0.5);
    const back = unit(Math.max(0, Math.min(t, 1) - 0.5) / 0.5);
    scanHolder.position.y += 1.85 * lift;
    scanHolder.position.z += 5.6 * back;
    const covered = lift < 0.45;
    for (const node of nodes.values()) {
      if (node.hidden) continue;
      const skin = node.info.id === "unibody" || shopSkin.has(node.info.id);
      if (!skin) continue;
      const keep = node.info.id === selected || node.info.id === hoverId || node === dragging || node.shift.lengthSq() > 0.0004 || node.home.lengthSq() > 0.0004;
      if (node.info.id === "unibody") {
        for (const mesh of node.meshes) mesh.visible = mesh.userData.swapped ? false : !covered || keep;
        continue;
      }
      node.group.visible = !covered || keep;
    }
  }

  function place(t: number) {
    for (const node of nodes.values()) node.group.position.copy(localAt(node, t, _b, true));
    placeScan(t);
    if (t < 0.08 && ![...nodes.values()].some((node) => node.boost > 0.05)) {
      for (const node of nodes.values()) node.line.visible = false;
      return;
    }
    const origin = nodes.get("unibody") ? worldAt(nodes.get("unibody")!, 0, new THREE.Vector3()) : new THREE.Vector3(0, 0.4, 0);
    for (const node of nodes.values()) {
      if (node.hidden || node.info.id === "unibody") {
        node.line.visible = false;
        continue;
      }
      const pts: THREE.Vector3[] = [origin.clone()];
      for (let mark = 0; mark <= 4; mark++) if (mark <= t + 0.02) pts.push(worldAt(node, mark, new THREE.Vector3()));
      pts.push(worldAt(node, t, new THREE.Vector3()));
      const positions = new Float32Array(pts.length * 3);
      pts.forEach((point, index) => {
        positions[index * 3] = point.x;
        positions[index * 3 + 1] = point.y;
        positions[index * 3 + 2] = point.z;
      });
      node.line.geometry.dispose();
      node.line.geometry = new THREE.BufferGeometry();
      node.line.geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
      node.line.computeLineDistances();
      node.line.visible = true;
    }
  }

  function rebuild(next: CarSpec) {
    const homes = new Map<string, THREE.Vector3>();
    const shifts = new Map<string, { shift: THREE.Vector3; from: number; hidden: boolean }>();
    const boosts = new Map<string, number>();
    for (const [id, node] of nodes) {
      shifts.set(id, { shift: node.shift.clone(), from: node.shiftFrom, hidden: node.hidden });
      homes.set(id, node.home.clone());
      boosts.set(id, node.boost);
    }
    clearNodes();
    spec = next;
    const groups = groupsFor(next);
    const prims = primsFor(next);
    const runs = new Map<string, ServiceRun>(runsFor(next).map((run) => [run.id, run]));
    const buckets = new Map<string, Prim[]>();
    for (const prim of prims) {
      const id = groupIdOf(prim.id);
      const bucket = buckets.get(id) ?? [];
      bucket.push(prim);
      buckets.set(id, bucket);
    }
    const centroids = new Map<string, THREE.Vector3>();
    for (const info of groups) {
      const bucket = buckets.get(info.id) ?? [];
      const run = runs.get(info.id);
      const centroid = new THREE.Vector3();
      if (bucket.length) {
        for (const prim of bucket) centroid.add(new THREE.Vector3(prim.pos[0], prim.pos[1], prim.pos[2]));
        centroid.multiplyScalar(1 / bucket.length);
      } else if (run) {
        for (const point of run.points) centroid.add(new THREE.Vector3(point[0], point[1], point[2]));
        centroid.multiplyScalar(1 / run.points.length);
      }
      centroids.set(info.id, centroid);
    }
    for (const info of groups) {
      const group = new THREE.Group();
      group.name = info.id;
      const meshes: THREE.Mesh[] = [];
      const edges: THREE.LineSegments[] = [];
      const centroid = centroids.get(info.id) ?? new THREE.Vector3();
      if (info.id === "unibody") {
        const shell = new THREE.Mesh(
          next.pack === "mustang" ? coupeGeometry() : commonGeometry(),
          new THREE.MeshStandardMaterial({ color: next.paint, metalness: 0.5, roughness: 0.35, side: THREE.DoubleSide }),
        );
        shell.position.copy(centroid).multiplyScalar(-1);
        shell.userData.shared = true;
        shell.userData.paint = true;
        shell.userData.base = next.paint;
        shell.userData.opacity = 1;
        shell.userData.rest = new THREE.Vector3();
        group.add(shell);
        meshes.push(shell);
      }
      for (const prim of buckets.get(info.id) ?? []) {
        const mesh = new THREE.Mesh(
          makeGeom(prim),
          new THREE.MeshStandardMaterial({
            color: prim.color,
            metalness: prim.metal ?? 0.4,
            roughness: prim.rough ?? 0.5,
            emissive: new THREE.Color(prim.emissive ?? "#000000"),
            emissiveIntensity: prim.emissiveIntensity ?? 0,
            transparent: (prim.opacity ?? 1) < 0.98,
            opacity: prim.opacity ?? 1,
          }),
        );
        mesh.position.set(prim.pos[0] - centroid.x, prim.pos[1] - centroid.y, prim.pos[2] - centroid.z);
        if (prim.rot) mesh.rotation.set(prim.rot[0], prim.rot[1], prim.rot[2]);
        mesh.userData.paint = !!prim.paint;
        mesh.userData.base = prim.color;
        mesh.userData.opacity = prim.opacity ?? 1;
        mesh.userData.emissive = prim.emissive ?? "#000000";
        mesh.userData.emissiveIntensity = prim.emissiveIntensity ?? 0;
        mesh.userData.rest = new THREE.Vector3(prim.pos[0], prim.pos[1], prim.pos[2]);
        group.add(mesh);
        meshes.push(mesh);
        const edge = new THREE.LineSegments(new THREE.EdgesGeometry(mesh.geometry, 28), new THREE.LineDashedMaterial({ color: "#f7f7f5", dashSize: 0.04, gapSize: 0.025 }));
        edge.position.copy(mesh.position);
        edge.rotation.copy(mesh.rotation);
        edge.visible = false;
        edge.computeLineDistances();
        edge.raycast = () => null;
        group.add(edge);
        edges.push(edge);
      }
      const run = runs.get(info.id);
      if (run && run.points.length > 1) {
        const local = run.points.map((point) => new THREE.Vector3(point[0] - centroid.x, point[1] - centroid.y, point[2] - centroid.z));
        const tube = new THREE.Mesh(
          new THREE.TubeGeometry(new THREE.CatmullRomCurve3(local), 18, run.kind === "wire" ? 0.007 : 0.013, 5, false),
          new THREE.MeshStandardMaterial({ color: run.color, roughness: 0.45, metalness: 0.05 }),
        );
        tube.userData.base = run.color;
        tube.userData.opacity = 1;
        tube.userData.rest = centroid.clone();
        group.add(tube);
        meshes.push(tube);
        if (run.number) {
          const atPlug = numberBadge(String(run.number), run.color);
          atPlug.position.copy(local[local.length - 1]!).add(new THREE.Vector3(0, 0.06, 0));
          group.add(atPlug);
          const atCoil = numberBadge(String(run.number), run.color);
          atCoil.position.copy(local[0]!).add(new THREE.Vector3(0, 0.05, 0));
          atCoil.scale.multiplyScalar(0.75);
          group.add(atCoil);
        }
      }
      const plugNo = /^plug-(\d)$/.exec(info.id);
      if (plugNo) {
        const mark = document.createElement("canvas");
        mark.width = 64;
        mark.height = 64;
        const ctx = mark.getContext("2d");
        if (ctx) {
          ctx.fillStyle = "#f4f4f2";
          ctx.beginPath();
          ctx.arc(32, 32, 28, 0, Math.PI * 2);
          ctx.fill();
          ctx.fillStyle = "#1a1a1c";
          ctx.font = "700 36px sans-serif";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(plugNo[1] ?? "", 32, 36);
          const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(mark), depthTest: false }));
          sprite.scale.set(0.09, 0.09, 1);
          sprite.position.set(0, 0.08, 0);
          sprite.raycast = () => null;
          group.add(sprite);
        }
      }
      const parentCentroid = info.parent ? centroids.get(info.parent) ?? new THREE.Vector3() : new THREE.Vector3();
      const line = new THREE.Line(new THREE.BufferGeometry(), new THREE.LineDashedMaterial({ color: "#c8c4ba", dashSize: 0.06, gapSize: 0.04 }));
      line.frustumCulled = false;
      line.visible = false;
      line.raycast = () => null;
      scene.add(line);
      const kept = shifts.get(info.id);
      nodes.set(info.id, {
        info,
        group,
        meshes,
        edges,
        rest: centroid.clone().sub(parentCentroid),
        centroid,
        shift: kept?.shift ?? new THREE.Vector3(),
        shiftFrom: kept?.from ?? 0,
        home: homes.get(info.id)?.clone() ?? new THREE.Vector3(),
        boost: boosts.get(info.id) ?? 0,
        hidden: kept?.hidden ?? false,
        line,
      });
    }
    for (const node of nodes.values()) {
      const parent = node.info.parent ? nodes.get(node.info.parent)?.group : root;
      parent?.add(node.group);
    }
    for (const [id, holder] of holders) {
      const node = nodes.get(id);
      if (!node) continue;
      for (const mesh of node.meshes) mesh.userData.swapped = true;
      node.group.add(holder);
    }
    root.add(scanHolder);
    applyLook();
    place(stage);
  }

  function fitScan() {
    root.add(scanHolder);
    scanHolder.position.set(0, 0, 0);
    scanHolder.rotation.set(0, 0, 0);
    scanHolder.scale.set(1, 1, 1);
    scanHolder.updateMatrixWorld(true);
    const raw = new THREE.Box3().setFromObject(scanHolder).getSize(new THREE.Vector3());
    const rotX = (raw.y <= raw.x && raw.y <= raw.z ? 0 : -Math.PI / 2) + (scanUpright ? -Math.PI / 2 : 0);
    scanHolder.rotation.x = rotX;
    scanHolder.updateMatrixWorld(true);
    const turned = new THREE.Box3().setFromObject(scanHolder).getSize(new THREE.Vector3());
    scanHolder.rotation.y = (turned.x > turned.z ? Math.PI / 2 : 0) + Math.PI;
    scanHolder.updateMatrixWorld(true);
    const before = new THREE.Box3().setFromObject(scanHolder).getSize(new THREE.Vector3());
    scanHolder.scale.setScalar(4.35 / Math.max(before.x, before.z, 0.001));
    scanHolder.updateMatrixWorld(true);
    const fitted = new THREE.Box3().setFromObject(scanHolder);
    const center = fitted.getCenter(new THREE.Vector3());
    scanHolder.position.x -= center.x;
    scanHolder.position.z -= center.z;
    scanHolder.position.y -= fitted.min.y;
    scanRest.copy(scanHolder.position);
  }

  function disposeScanContents() {
    scanHolder.traverse((child) => {
      const mesh = child as THREE.Mesh;
      if (!mesh.isMesh) return;
      mesh.geometry?.dispose();
      const material = mesh.material;
      if (Array.isArray(material)) material.forEach((item) => item.dispose());
      else material?.dispose();
    });
    scanHolder.clear();
  }

  function markSwapped(node: Node) {
    for (const mesh of node.meshes) {
      mesh.userData.swapped = true;
      mesh.visible = false;
      mesh.raycast = () => null;
    }
    for (const edge of node.edges) edge.visible = false;
  }

  function fitHolder(holder: THREE.Object3D, worldBox: THREE.Box3, parent: THREE.Object3D) {
    holder.position.set(0, 0, 0);
    holder.rotation.set(0, 0, 0);
    holder.scale.set(1, 1, 1);
    holder.updateMatrixWorld(true);
    const raw = new THREE.Box3().setFromObject(holder);
    const size = raw.getSize(new THREE.Vector3());
    const want = worldBox.getSize(new THREE.Vector3());
    const maxIn = Math.max(size.x, size.y, size.z, 0.0001);
    const maxOut = Math.max(want.x, want.y, want.z, 0.05);
    holder.scale.setScalar(maxOut / maxIn);
    holder.updateMatrixWorld(true);
    const fitted = new THREE.Box3().setFromObject(holder);
    parent.updateMatrixWorld(true);
    const localFrom = parent.worldToLocal(fitted.getCenter(new THREE.Vector3()));
    const localTo = parent.worldToLocal(worldBox.getCenter(new THREE.Vector3()));
    holder.position.add(localTo.sub(localFrom));
  }

  function shopBox(node: Node) {
    const box = new THREE.Box3();
    node.group.updateWorldMatrix(true, true);
    for (const mesh of node.meshes) {
      if (!mesh.geometry) continue;
      if (!mesh.geometry.boundingBox) mesh.geometry.computeBoundingBox();
      const local = mesh.geometry.boundingBox;
      if (!local || local.isEmpty()) continue;
      box.union(local.clone().applyMatrix4(mesh.matrixWorld));
    }
    if (!box.isEmpty()) return box;
    const center = new THREE.Vector3();
    node.group.getWorldPosition(center);
    return new THREE.Box3(center.clone().addScalar(-0.08), center.clone().addScalar(0.08));
  }

  async function parseModel(data: ArrayBuffer, name: string) {
    const ext = name.split(".").pop()?.toLowerCase() ?? "";
    if (ext === "stl") {
      const geo = new STLLoader().parse(data);
      return new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: "#8a8680", metalness: 0.55, roughness: 0.4, side: THREE.DoubleSide }));
    }
    if (ext === "obj") return new OBJLoader().parse(new TextDecoder().decode(data));
    if (ext === "glb" || ext === "gltf") {
      const gltf = await new GLTFLoader().parseAsync(data, "");
      return gltf.scene;
    }
    throw new Error("Use a .glb, .gltf, .stl, or .obj file.");
  }

  function disposeHolder(holder: THREE.Object3D) {
    holder.traverse((child) => {
      const mesh = child as THREE.Mesh;
      if (!mesh.isMesh) return;
      mesh.geometry?.dispose();
      const material = mesh.material;
      if (Array.isArray(material)) material.forEach((item) => item.dispose());
      else material?.dispose();
    });
  }

  async function replacePart(id: string, data: ArrayBuffer, name: string) {
    const node = nodes.get(id);
    if (!node) return;
    const box = shopBox(node);
    const previous = holders.get(id);
    if (previous) {
      previous.removeFromParent();
      disposeHolder(previous);
    }
    const holder = new THREE.Group();
    holder.name = `${id}-model`;
    holder.userData.replacementHolder = true;
    holder.add(await parseModel(data, name));
    node.group.add(holder);
    fitHolder(holder, box, node.group);
    holders.set(id, holder);
    markSwapped(node);
    applyLook();
  }

  function clearPartModel(id: string) {
    const holder = holders.get(id);
    if (holder) {
      holder.removeFromParent();
      disposeHolder(holder);
      holders.delete(id);
    }
    const node = nodes.get(id);
    if (!node) return;
    for (const mesh of node.meshes) {
      mesh.userData.swapped = false;
      mesh.visible = true;
      mesh.raycast = THREE.Mesh.prototype.raycast;
    }
    applyLook();
  }

  async function loadScan(data: ArrayBuffer, name: string) {
    const ext = name.split(".").pop()?.toLowerCase() ?? "";
    disposeScanContents();
    if (ext === "stl") {
      const geo = new STLLoader().parse(data);
      scanHolder.add(new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: spec.paint, metalness: 0.45, roughness: 0.42, side: THREE.DoubleSide })));
    } else if (ext === "obj") {
      scanHolder.add(new OBJLoader().parse(new TextDecoder().decode(data)));
    } else if (ext === "glb" || ext === "gltf") {
      const gltf = await new GLTFLoader().parseAsync(data, "");
      scanHolder.add(gltf.scene);
    } else {
      throw new Error("Use a .glb, .gltf, .stl, or .obj file.");
    }
    scanHolder.traverse((child) => {
      const mesh = child as THREE.Mesh;
      if (!mesh.isMesh) return;
      mesh.raycast = () => null;
      const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      for (const mat of mats) {
        if (!mat) continue;
        mat.side = THREE.DoubleSide;
        if (!mat.userData.scanSaved) {
          mat.userData.scanSaved = { transparent: mat.transparent, opacity: mat.opacity, depthWrite: mat.depthWrite };
        }
      }
    });
    if (scanMode === "off") scanMode = "shell";
    fitScan();
    applyLook();
  }

  function roomBox(w: number, h: number, d: number, x: number, y: number, z: number, color: string, role: string, extra?: Partial<THREE.MeshStandardMaterialParameters>) {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), new THREE.MeshStandardMaterial({ color, roughness: 0.85, metalness: 0.05, ...extra }));
    mesh.position.set(x, y, z);
    mesh.userData.role = role;
    mesh.raycast = () => null;
    room.add(mesh);
  }

  function rebuildRoom(place: Look["place"]) {
    for (const child of [...room.children]) {
      room.remove(child);
      const mesh = child as THREE.Mesh;
      mesh.geometry?.dispose();
      (mesh.material as THREE.Material)?.dispose();
    }
    if (place === "color") return;
    const show = place === "showroom";
    roomBox(20, 0.08, 20, 0, -0.06, 0.4, show ? "#1c1c1e" : "#4a4a4c", "floor", show ? { roughness: 0.16, metalness: 0.55 } : { roughness: 0.92 });
    roomBox(16, 4.6, 0.18, 0, 2.2, 6.2, "#2a2a2c", "wall");
    roomBox(0.18, 4.6, 14, -7.2, 2.2, 0.2, "#2a2a2c", "wall");
    roomBox(0.18, 4.6, 14, 7.2, 2.2, 0.2, "#2a2a2c", "wall");
    roomBox(16, 0.16, 14, 0, 4.5, 0.2, "#2a2a2c", "ceiling");
    if (show) {
      roomBox(0.28, 4.2, 0.28, -3.4, 2.1, 3.2, "#d9d6d0", "wall");
      roomBox(0.28, 4.2, 0.28, 3.4, 2.1, 3.2, "#d9d6d0", "wall");
      roomBox(1.4, 0.06, 1.4, -2.2, 4.2, -1.2, "#fff6e4", "lamp", { emissive: "#fff1d2", emissiveIntensity: 1.2, roughness: 0.4 });
      roomBox(1.4, 0.06, 1.4, 2.2, 4.2, -1.2, "#fff6e4", "lamp", { emissive: "#fff1d2", emissiveIntensity: 1.2, roughness: 0.4 });
    } else {
      roomBox(2.2, 0.9, 0.6, 4.6, 0.5, 2.4, "#6a4a32", "bench", { roughness: 0.7 });
      roomBox(6, 0.08, 0.35, -2, 4.15, 1.2, "#e7f2ef", "lamp", { emissive: "#d7efe8", emissiveIntensity: 0.8 });
      roomBox(6, 0.08, 0.35, 2, 4.15, -1.4, "#e7f2ef", "lamp", { emissive: "#d7efe8", emissiveIntensity: 0.8 });
    }
  }

  function applyEnvironment() {
    const current = look ?? DEFAULT_LOOK;
    if (builtPlace !== current.place) {
      builtPlace = current.place;
      rebuildRoom(current.place);
    }
    for (const child of room.children) {
      const mesh = child as THREE.Mesh;
      const mat = mesh.material as THREE.MeshStandardMaterial;
      const role = mesh.userData.role as string;
      if (role === "wall" || role === "ceiling") mat.color.set(role === "ceiling" && current.backgroundGradient ? current.backgroundTo : current.background);
    }
    if (current.place !== "color") scene.background = new THREE.Color(current.place === "garage" ? "#141618" : "#c8c4bc");
    else if (current.backgroundGradient) {
      const ctx = backdropCanvas.getContext("2d");
      if (ctx) {
        const g = current.bayDirection === "height" ? ctx.createLinearGradient(0, 0, 0, 512) : ctx.createLinearGradient(0, 0, 512, 0);
        g.addColorStop(0, current.background);
        g.addColorStop(1, current.backgroundTo);
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, 512, 512);
        backdropTex.needsUpdate = true;
      }
      scene.background = backdropTex;
    } else scene.background = new THREE.Color(current.background);
    renderer.domElement.style.cursor = editing ? "grab" : current.paintMode === "part" ? "crosshair" : "";
    applyLook();
  }

  function pick(event: PointerEvent) {
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObjects([root], true);
    for (const item of hits) {
      let current: THREE.Object3D | null = item.object;
      while (current) {
        const found = [...nodes.values()].find((node) => node.group === current);
        if (found && !found.hidden) return found;
        current = current.parent;
      }
    }
    return null;
  }

  function stopDemo() {
    if (!demo) return;
    demo = false;
    camera.up.set(0, 1, 0);
    controls.enabled = true;
    events.onDemo(false);
  }

  function startDemo() {
    if (demo) return;
    framing = null;
    for (const node of nodes.values()) node.boost = 0;
    rollReel();
    demo = true;
    demoT = 0;
    controls.enabled = false;
    events.onHover(null);
    events.onMenu(null);
    events.onDemo(true);
  }

  function select(id: string | null) {
    selected = id;
    const node = id ? nodes.get(id) : undefined;
    if (node && targetStage < node.info.stage + lead()) targetStage = node.info.stage + lead();
    events.onSelect(id);
    applyLook();
  }

  function onPointerDown(event: PointerEvent) {
    idle = 0;
    stopDemo();
    fingers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (fingers.size >= 2) {
      pinch = fingerSpan();
      controls.enabled = false;
      left = null;
      dragging = null;
      return;
    }
    if (event.pointerType === "pen" && (event.button === 5 || event.button === 2)) {
      penSpin = true;
      controls.enabled = false;
      return;
    }
    if (event.button === 2) {
      right = { x: event.clientX, y: event.clientY, moved: false };
      return;
    }
    if (event.button !== 0) return;
    framing = null;
    const node = pick(event);
    left = { x: event.clientX, y: event.clientY, node };
    if (node) {
      controls.enabled = false;
      event.stopPropagation();
    }
  }

  function fingerSpan() {
    const pts = [...fingers.values()];
    if (pts.length < 2) return 0;
    return Math.hypot(pts[0]!.x - pts[1]!.x, pts[0]!.y - pts[1]!.y);
  }

  function orbitBy(dx: number, dy: number) {
    if (framing) {
      frameAngle -= dx * 0.01;
      framePhi = Math.min(Math.PI - 0.08, Math.max(0.08, framePhi + dy * 0.01));
      return;
    }
    const offset = camera.position.clone().sub(controls.target);
    const spherical = new THREE.Spherical().setFromVector3(offset);
    spherical.theta -= dx * 0.01;
    spherical.phi = Math.min(Math.PI - 0.05, Math.max(0.05, spherical.phi + dy * 0.01));
    offset.setFromSpherical(spherical);
    camera.position.copy(controls.target).add(offset);
    controls.update();
  }

  function applyDistance(next: number) {
    const dist = Math.min(42, Math.max(0.16, next));
    if (framing) framing.distance = dist;
    const offset = camera.position.clone().sub(controls.target);
    offset.setLength(dist || 0.16);
    camera.position.copy(controls.target).add(offset);
    controls.update();
    events.onDistance(camera.position.distanceTo(controls.target));
  }

  function onPointerMove(event: PointerEvent) {
    if (fingers.has(event.pointerId)) fingers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (fingers.size >= 2 && pinch) {
      const next = fingerSpan();
      if (pinch > 12 && next > 12) applyDistance(camera.position.distanceTo(controls.target) * (pinch / next));
      pinch = next;
      return;
    }
    if (penSpin) {
      orbitBy(event.movementX, event.movementY);
      return;
    }
    if (demo && demoT > 1.2 && Math.hypot(event.movementX, event.movementY) > 6) {
      idle = 0;
      stopDemo();
    } else if (!demo && (Math.abs(event.movementX) > 0 || Math.abs(event.movementY) > 0)) idle = 0;
    if (right && Math.hypot(event.clientX - right.x, event.clientY - right.y) > 5) right.moved = true;
    const rect = renderer.domElement.getBoundingClientRect();
    const inside = event.clientX >= rect.left && event.clientX <= rect.right && event.clientY >= rect.top && event.clientY <= rect.bottom;
    if (!dragging && !left && inside) {
      const node = pick(event);
      const id = node?.info.id ?? null;
      if (id !== hoverId) {
        hoverId = id;
        applyLook();
        events.onHover(node ? { x: event.clientX, y: event.clientY, id: node.info.id, name: node.info.name, system: node.info.system } : null);
      }
    }
    if (!inside && hoverId) {
      hoverId = null;
      applyLook();
      events.onHover(null);
    }
    if (!left?.node) return;
    if (!dragging && Math.hypot(event.clientX - left.x, event.clientY - left.y) > 5) {
      dragging = left.node;
      dragging.shiftFrom = Math.max(0, Math.floor(stage));
      const world = worldAt(dragging, stage, new THREE.Vector3());
      plane.setFromNormalAndCoplanarPoint(camera.getWorldDirection(_a).clone(), world);
      lastHit.copy(world);
    }
    if (!dragging) return;
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    if (!raycaster.ray.intersectPlane(plane, hit)) return;
    const delta = hit.clone().sub(lastHit);
    if (editing) dragging.home.add(delta);
    else dragging.shift.add(delta);
    lastHit.copy(hit);
  }

  function onPointerUp(event: PointerEvent) {
    fingers.delete(event.pointerId);
    if (fingers.size < 2) pinch = null;
    if (penSpin) {
      penSpin = false;
      if (!demo) controls.enabled = true;
      return;
    }
    if (event.button === 2 && right && !right.moved && event.pointerType !== "pen") {
      const node = pick(event);
      events.onMenu({ x: event.clientX, y: event.clientY, id: node?.info.id ?? "", name: node?.info.name ?? "Bay", system: node?.info.system ?? "all" });
    }
    if (event.button === 0 && left && !dragging && Math.hypot(event.clientX - left.x, event.clientY - left.y) <= 5) select(left.node?.info.id ?? null);
    if (dragging && editing) events.onHome(dragging.info.id, { x: dragging.home.x, y: dragging.home.y, z: dragging.home.z });
    else if (dragging && dragging.shift.lengthSq() > 0.0001) {
      events.onShift(dragging.info.id, { x: dragging.shift.x, y: dragging.shift.y, z: dragging.shift.z, from: dragging.shiftFrom });
    }
    dragging = null;
    left = null;
    right = null;
    if (!demo) controls.enabled = true;
  }

  function onWheel(event: WheelEvent) {
    idle = 0;
    stopDemo();
    event.preventDefault();
    if (event.altKey) {
      targetStage = Math.min(maxStage(), Math.max(0, targetStage + (event.deltaY > 0 ? 0.55 : -0.55)));
      return;
    }
    if ((event.ctrlKey || event.metaKey) && selected) {
      const delta = event.deltaY > 0 ? 0.16 : -0.16;
      const ids = new Set<string>();
      const walk = (id: string) => {
        if (ids.has(id)) return;
        ids.add(id);
        for (const node of nodes.values()) if (node.info.parent === id) walk(node.info.id);
      };
      walk(selected);
      for (const id of ids) {
        const node = nodes.get(id);
        if (node) node.boost = Math.max(0, Math.min(1, node.boost + delta));
      }
      return;
    }
    const offset = camera.position.clone().sub(controls.target);
    const next = Math.min(42, Math.max(0.16, offset.length() * (event.deltaY > 0 ? 1.08 : 0.92)));
    applyDistance(next);
  }

  function onKey() {
    idle = 0;
    stopDemo();
  }

  function onActivity() {
    idle = 0;
    stopDemo();
  }

  renderer.domElement.addEventListener("pointerdown", onPointerDown, true);
  window.addEventListener("pointermove", onPointerMove);
  window.addEventListener("pointerup", onPointerUp);
  window.addEventListener("pointerdown", onActivity);
  window.addEventListener("keydown", onKey);
  renderer.domElement.addEventListener("wheel", onWheel, { passive: false });
  renderer.domElement.addEventListener("contextmenu", (event) => event.preventDefault());

  function resize() {
    const width = Math.max(1, host.clientWidth);
    const height = Math.max(1, host.clientHeight);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height, false);
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";
  }
  const observer = new ResizeObserver(resize);
  observer.observe(host);
  resize();
  rebuild(spec);

  type Shot = { hold: number; speed: number; dist: number; height: number; orbit: number; tilt: number; stage: number; part: string | null; follow: number; roll: number };
  let reel: Shot[] = [];
  let shotI = 0;
  let shotT = 0;
  let allowIdle = true;
  const beats: { stage: number; part: string | null }[] = [
    { stage: 0, part: null },
    { stage: 1, part: "hood" },
    { stage: 1, part: "bumper-f" },
    { stage: 2, part: "engine" },
    { stage: 2, part: "wheel-fl" },
    { stage: 3, part: "intake" },
    { stage: 3, part: "trans" },
    { stage: 4, part: "fuel-pump" },
    { stage: 4, part: "brake-fl" },
    { stage: 4, part: "fuel-tank" },
  ];

  function rollReel() {
    reel = beats.map((beat) => {
      const wide = beat.stage < 2;
      return {
        hold: 3.4 + Math.random() * 3.2,
        speed: 0.55 + Math.random() * 0.85,
        dist: wide ? 6 + Math.random() * 3 : 1.8 + Math.random() * 1.7,
        height: 0.3 + Math.random() * (wide ? 1.7 : 1),
        orbit: (Math.random() < 0.5 ? 1 : -1) * (0.22 + Math.random() * 0.5),
        tilt: (Math.random() - 0.5) * 0.5,
        stage: beat.stage,
        part: beat.part,
        follow: 0.03 + Math.random() * 0.045,
        roll: (Math.random() - 0.5) * 0.2,
      };
    });
    shotI = 0;
    shotT = 0;
  }

  function tourTarget(t: number) {
    const shot = reel[shotI];
    const node = shot?.part ? nodes.get(shot.part) : undefined;
    if (!node) return desiredTarget.set(Math.sin(demoT * 0.2) * 0.3, 0.7, 0.05);
    return worldAt(node, t, desiredTarget);
  }

  let reported = -1;
  function frame() {
    if (disposed) return;
    const dt = 0.016;
    if (demo) {
      if (!reel.length) rollReel();
      const shot = reel[shotI]!;
      demoT += dt * shot.speed;
      shotT += dt * shot.speed;
      if (shotT > shot.hold) {
        shotI += 1;
        shotT = 0;
        if (shotI >= reel.length) rollReel();
      }
      const currentShot = reel[shotI]!;
      stage += (currentShot.stage + lead() - stage) * Math.min(1, dt * 1.2);
      targetStage = currentShot.stage + lead();
      const focusPoint = tourTarget(stage);
      const angle = demoT * currentShot.orbit + shotI;
      desired.set(focusPoint.x + Math.sin(angle) * currentShot.dist, focusPoint.y + currentShot.height + Math.sin(shotT * 0.6) * currentShot.tilt, focusPoint.z + Math.cos(angle) * currentShot.dist);
      camera.position.lerp(desired, currentShot.follow);
      controls.target.lerp(focusPoint, currentShot.follow);
      camera.up.set(Math.sin(currentShot.roll), Math.cos(currentShot.roll), 0).normalize();
      camera.lookAt(controls.target);
    } else {
      idle += dt;
      if (idle > idleLimit && allowIdle && !editing) startDemo();
      const pull = (targetStage - stage) * 22 * dt;
      stageVel = (stageVel + pull) * Math.exp(-7 * dt);
      stage += stageVel * dt;
      if (Math.abs(targetStage - stage) < 0.001 && Math.abs(stageVel) < 0.001) stage = targetStage;
      if (framing) {
        const node = nodes.get(framing.id);
        if (node) {
          const focusPoint = worldAt(node, stage, gaze);
          if (framing.mode === "orbit") frameAngle += dt * framing.orbit;
          const dist = framing.distance;
          const horiz = Math.sin(framePhi) * dist;
          desired.set(focusPoint.x + Math.sin(frameAngle) * horiz, focusPoint.y + Math.cos(framePhi) * dist, focusPoint.z + Math.cos(frameAngle) * horiz);
          const k = Math.min(1, 1 - Math.exp(-dt * framing.transit));
          camera.position.lerp(desired, k);
          controls.target.lerp(focusPoint, k);
        }
      }
      controls.update();
    }
    const az = demo ? demoT * 0.45 : ((look?.light ?? 40) * Math.PI) / 180;
    sun.position.set(Math.sin(az) * 8, 5.2, Math.cos(az) * 8);
    place(stage);
    armClicks();
    const nameIndex = Math.round(Math.max(0, Math.min(maxStage(), stage)));
    if (nameIndex !== reported) {
      reported = nameIndex;
      events.onStage(nameIndex);
    }
    renderer.render(scene, camera);
    requestAnimationFrame(frame);
  }
  frame();
  startDemo();

  return {
    setSpec(next) {
      rebuild(next);
    },
    setLook(next) {
      look = next;
      applyEnvironment();
    },
    setStage(next) {
      targetStage = Math.max(0, Math.min(maxStage(), next));
    },
    setFocus(next) {
      focus = next;
      isolate = null;
      applyLook();
    },
    setIsolate(ids, color, to) {
      isolate = ids && ids.length ? new Set(ids) : null;
      if (color) isolateColor = color;
      isolateTo = to || null;
      if (isolate) focus = "all";
      applyLook();
    },
    framePart(id, frame) {
      if (!frame) {
        framing = null;
        return;
      }
      stopDemo();
      framing = { id, ...frame };
    },
    dollyTo(distance) {
      stopDemo();
      applyDistance(distance);
    },
    orbitBy,
    select,
    hide(id) {
      const node = nodes.get(id);
      if (node) node.hidden = true;
      if (id === "unibody") bodyHidden = true;
      applyLook();
    },
    showHidden() {
      bodyHidden = false;
      for (const node of nodes.values()) node.hidden = false;
      applyLook();
    },
    restoreTextures() {
      focus = "all";
      isolate = null;
      applyLook();
    },
    shiftOf(id) {
      const node = nodes.get(id);
      if (!node) return null;
      return { x: node.shift.x, y: node.shift.y, z: node.shift.z, from: node.shiftFrom };
    },
    applyShifts(shifts) {
      for (const node of nodes.values()) {
        const saved = shifts[node.info.id];
        if (!saved) continue;
        node.shift.set(saved.x, saved.y, saved.z);
        node.shiftFrom = saved.from;
      }
    },
    getSnapshot() {
      const shifts: Record<string, Shift> = {};
      const hidden: string[] = [];
      for (const node of nodes.values()) {
        if (node.shift.lengthSq() > 0.0001) shifts[node.info.id] = { x: node.shift.x, y: node.shift.y, z: node.shift.z, from: node.shiftFrom };
        if (node.hidden) hidden.push(node.info.id);
      }
      return {
        stage: targetStage,
        camera: [camera.position.x, camera.position.y, camera.position.z],
        target: [controls.target.x, controls.target.y, controls.target.z],
        shifts,
        focus,
        hidden,
        look: look ?? { ...DEFAULT_LOOK, paint: spec.paint },
      };
    },
    applyView(view) {
      stopDemo();
      targetStage = view.stage;
      stage = view.stage;
      stageVel = 0;
      camera.position.set(view.camera[0], view.camera[1], view.camera[2]);
      controls.target.set(view.target[0], view.target[1], view.target[2]);
      focus = view.focus;
      isolate = null;
      look = { ...DEFAULT_LOOK, ...view.look, partPaints: view.look.partPaints ?? {} };
      for (const node of nodes.values()) {
        const saved = view.shifts[node.info.id];
        node.shift.set(saved?.x ?? 0, saved?.y ?? 0, saved?.z ?? 0);
        node.shiftFrom = saved?.from ?? 0;
        node.hidden = view.hidden.includes(node.info.id);
      }
      applyEnvironment();
      events.onStage(Math.round(view.stage));
    },
    setDemo(on) {
      if (on) startDemo();
      else stopDemo();
    },
    setIdleDemo(on) {
      allowIdle = on;
      if (!on) stopDemo();
    },
    setIdleSeconds(seconds) {
      idleLimit = Math.max(15, seconds);
    },
    clearShifts() {
      for (const node of nodes.values()) {
        node.shift.set(0, 0, 0);
        node.shiftFrom = 0;
      }
    },
    clearShift(id) {
      const node = nodes.get(id);
      if (!node) return;
      node.shift.set(0, 0, 0);
      node.shiftFrom = 0;
    },
    setEditing(on) {
      editing = on;
      if (on) stopDemo();
      renderer.domElement.style.cursor = on ? "grab" : "";
    },
    applyHomes(homes) {
      for (const node of nodes.values()) {
        const saved = homes[node.info.id];
        node.home.set(saved?.x ?? 0, saved?.y ?? 0, saved?.z ?? 0);
      }
    },
    clearHome(id) {
      const node = nodes.get(id);
      if (!node) return;
      node.home.set(0, 0, 0);
    },
    clearHomes() {
      for (const node of nodes.values()) node.home.set(0, 0, 0);
    },
    replacePart,
    clearPartModel,
    loadScan,
    setScanMode(mode) {
      scanMode = mode;
      const cap = maxStage();
      if (targetStage > cap) targetStage = cap;
      if (stage > cap) stage = cap;
      applyLook();
    },
    setScanUpright(on) {
      scanUpright = on;
      if (scanHolder.children.length) fitScan();
      applyLook();
    },
    clearScan() {
      disposeScanContents();
      scanMode = "off";
      applyLook();
    },
    dispose() {
      disposed = true;
      disposeScanContents();
      for (const holder of holders.values()) disposeHolder(holder);
      holders.clear();
      observer.disconnect();
      renderer.domElement.removeEventListener("pointerdown", onPointerDown, true);
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
      window.removeEventListener("pointerdown", onActivity);
      window.removeEventListener("keydown", onKey);
      controls.dispose();
      clearNodes();
      backdropTex.dispose();
      scene.environment?.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    },
  };
}

export { STAGE_NAMES };
