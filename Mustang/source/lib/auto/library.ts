const KEY = "fafo.auto.library.v1";

export type LibraryFit = "any" | "wheel" | "brake" | "filter" | "body";

export type LibraryPiece = {
  id: string;
  label: string;
  pieces: string[];
  fits: LibraryFit;
};

export type LibraryModel = {
  file: string;
  title: string;
  credit: string;
  pieces: LibraryPiece[];
};

export type LibraryAssignment = { file: string; pieces: string[]; label: string };

export const WHEEL_IDS = ["wheel-fl", "wheel-fr", "wheel-rl", "wheel-rr"] as const;
export const BRAKE_IDS = ["brake-fl", "brake-fr", "brake-rl", "brake-rr"] as const;

export const LIBRARY: LibraryModel[] = [
  {
    file: "oil-filter.glb",
    title: "Oil filter",
    credit: "nodelet, CC-BY-NC-4.0",
    pieces: [{ id: "filter", label: "Filter", pieces: [], fits: "filter" }],
  },
  {
    file: "spoon-sw388.glb",
    title: "Spoon SW388",
    credit: "Martin Trafas, CC-BY-4.0",
    pieces: [
      { id: "high", label: "Wheel and tire", pieces: ["HighPolySpoon", "HighPolyTire"], fits: "wheel" },
      { id: "low", label: "Wheel, low detail", pieces: ["LowPolySpoon"], fits: "wheel" },
      { id: "tire", label: "Spare tire", pieces: ["HighPolyTire.001"], fits: "wheel" },
      { id: "stand", label: "Display stand", pieces: ["Stand"], fits: "any" },
    ],
  },
  {
    file: "rays-57dr.glb",
    title: "RAYS Gram Lights 57DR",
    credit: "ilvskf, CC-BY-4.0",
    pieces: [
      {
        id: "wheel",
        label: "Wheel",
        pieces: ["DISK.001_1", "Sticker_Black.001_3", "Sticker_RED_5", "NAT.001_7", "valve_cap.001_9"],
        fits: "wheel",
      },
      { id: "cap", label: "Valve cap", pieces: ["valve_cap.001_9"], fits: "any" },
    ],
  },
  {
    file: "brake-assembly.glb",
    title: "Brake assembly",
    credit: "Nieve5677, CC-BY-4.0",
    pieces: [
      { id: "all", label: "Disc, caliper, and hardware", pieces: [], fits: "brake" },
      { id: "disc", label: "Disc", pieces: ["0-_BrakeAssembly_Disc"], fits: "brake" },
      { id: "caliper", label: "Caliper", pieces: ["2-_BrakeAssembly_Cali"], fits: "brake" },
      { id: "hardware", label: "Hardware", pieces: ["3-_"], fits: "brake" },
    ],
  },
  {
    file: "kralz-wheel.glb",
    title: "Kralz wheel",
    credit: "Dave Love, CC-BY-4.0",
    pieces: [
      { id: "all", label: "Whole model", pieces: [], fits: "any" },
      { id: "wheel", label: "Wheel", pieces: ["wheel_1"], fits: "wheel" },
      { id: "carbon", label: "Carbon", pieces: ["carbon.001_2"], fits: "any" },
      { id: "base", label: "Base", pieces: ["base_0"], fits: "any" },
    ],
  },
  {
    file: "lotus-emira-gt4.glb",
    title: "2022 Lotus Emira GT4",
    credit: "Kaleemullah, CC-BY-4.0",
    pieces: [
      { id: "car", label: "Whole car", pieces: [], fits: "body" },
      { id: "paint", label: "Paint", pieces: ["CarPaint"], fits: "body" },
      { id: "glass", label: "Glass", pieces: ["GLASS"], fits: "body" },
      { id: "tires", label: "Tires", pieces: ["Tires"], fits: "wheel" },
      { id: "rims", label: "Rims", pieces: ["Rims1"], fits: "wheel" },
      { id: "rotors", label: "Rotors", pieces: ["Rotors"], fits: "brake" },
      { id: "lugs", label: "Lug nuts", pieces: ["Lugnuts"], fits: "wheel" },
      { id: "lights", label: "Lights", pieces: ["LGT"], fits: "body" },
      { id: "fan", label: "Fan", pieces: ["Fan"], fits: "any" },
      { id: "grille", label: "Grille", pieces: ["Grid"], fits: "body" },
      { id: "carbon", label: "Carbon", pieces: ["CARBON"], fits: "body" },
      { id: "decals", label: "Decals", pieces: ["Decals"], fits: "body" },
      { id: "metal", label: "Metal", pieces: ["CommonMetal"], fits: "any" },
    ],
  },
];

export function loadLibrary(): Record<string, LibraryAssignment> {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, LibraryAssignment>;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

export function writeLibrary(id: string, assignment: LibraryAssignment) {
  const all = loadLibrary();
  all[id] = assignment;
  localStorage.setItem(KEY, JSON.stringify(all));
  return all;
}

export async function fetchLibraryFile(file: string) {
  const urls = [
    new URL(`models/library/${file}`, document.baseURI).href,
    new URL(`Mustang/models/library/${file}`, document.baseURI).href,
    `/models/library/${file}`,
    `/Mustang/models/library/${file}`,
  ];
  let last = "That model file was not next to the page.";
  for (const url of urls) {
    try {
      const response = await fetch(url);
      if (response.ok) return await response.arrayBuffer();
      last = `${response.status}`;
    } catch (error) {
      last = error instanceof Error ? error.message : last;
    }
  }
  throw new Error(last);
}

export function clearLibrary(id: string) {
  const all = loadLibrary();
  delete all[id];
  localStorage.setItem(KEY, JSON.stringify(all));
  return all;
}
