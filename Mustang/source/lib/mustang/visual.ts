import { PARTS } from "./parts";
import type { Circuit, System } from "./types";

export type Role = "normal" | "neon" | "parent" | "ghost" | "hide";

export function chainOf(id: string): string[] {
  const out: string[] = [];
  let cur: string | undefined = id;
  const seen = new Set<string>();
  while (cur && PARTS[cur] && !seen.has(cur)) {
    seen.add(cur);
    out.push(cur);
    cur = PARTS[cur].parent;
  }
  return out;
}

export function sectionActive(system: System | "all", section: number | null, circuit: Circuit | "all", selected: string | null) {
  if (system !== "all" || section != null) return true;
  return circuit !== "all" && !selected;
}

export function visualRole(
  id: string,
  selected: string | null,
  system: System | "all",
  circuit: Circuit | "all",
  section: number | null,
): Role {
  if (id === "floor") return "hide";
  const isolate = !!selected && system === "all" && section == null;
  if (isolate) {
    if (id === selected) return "neon";
    if (chainOf(selected).includes(id)) return "parent";
    return "hide";
  }
  if (system !== "all" || section != null || circuit !== "all") {
    const part = PARTS[id];
    if (!part) return "ghost";
    if (system !== "all" && part.system !== system) return "ghost";
    if (section != null && part.stage !== section) return "ghost";
    if (circuit !== "all" && part.circuit && part.circuit !== circuit) return "ghost";
    if (circuit !== "all" && !part.circuit && system === "all" && section == null) return "ghost";
    return "neon";
  }
  return "normal";
}
