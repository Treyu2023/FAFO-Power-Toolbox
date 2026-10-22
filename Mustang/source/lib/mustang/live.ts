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
