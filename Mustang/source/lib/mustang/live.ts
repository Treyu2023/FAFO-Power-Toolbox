import { PARTS } from "./parts";
import type { PartInfo } from "./types";

/** Mutable rig state. The canvas reads this every frame; React does not. */
export const live = {
  stage: 0,
  targetStage: 0,
  dolly: null as number | null,
  focusing: false,
  focusId: null as string | null,
  recenter: false,
  menuFromPart: false,
};

export const CAM_FAR = 8.55;
export const CAM_NEAR = 2.45;

export function clamp(n: number, a: number, b: number) {
  return Math.max(a, Math.min(b, n));
}

export function stageFromDist(d: number) {
  return clamp(((CAM_FAR - d) / (CAM_FAR - CAM_NEAR)) * 5, 0, 5);
}

export function distForStage(s: number) {
  return CAM_FAR - (clamp(s, 0, 5) / 5) * (CAM_FAR - CAM_NEAR);
}

export function openAmount(stage: number, partStage: number) {
  if (partStage <= 0) return 0;
  return clamp(stage - (partStage - 1), 0, 1);
}

/** Ease the rig, then land on the target. Closed is exactly 0, so panels cannot sit 5% open. */
export function settleStage(dt: number) {
  if (live.targetStage <= 0.001) {
    live.targetStage = 0;
    live.stage = 0;
    return;
  }
  const step = 1 - Math.exp(-4.2 * Math.min(Math.max(dt, 0), 0.05));
  const diff = live.targetStage - live.stage;
  if (Math.abs(diff) <= 0.05) live.stage = live.targetStage;
  else live.stage += diff * step;
}

/** Slider and stage chips set an exact opening. The closed end is fully assembled. */
export function commitStage(stage: number) {
  const next = Math.round(clamp(stage, 0, 5) * 100) / 100;
  if (next <= 0) {
    live.targetStage = 0;
    live.stage = 0;
    return;
  }
  live.targetStage = next;
  live.stage = next;
}

export function explodeOf(id: string, stage: number): [number, number, number] {
  let x = 0;
  let y = 0;
  let z = 0;
  let cur: string | undefined = id;
  const seen = new Set<string>();
  while (cur && !seen.has(cur)) {
    seen.add(cur);
    const part: PartInfo | undefined = PARTS[cur];
    if (!part) break;
    const a = openAmount(stage, part.stage) * 2.25;
    x += part.ex[0] * a;
    y += part.ex[1] * a;
    z += part.ex[2] * a;
    cur = part.parent;
  }
  return [x, y, z];
}
