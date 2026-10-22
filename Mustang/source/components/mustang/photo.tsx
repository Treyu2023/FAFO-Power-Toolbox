import { useState } from "react";
import { PARTS } from "@/lib/mustang/parts";

// Committed context shots only (see Mustang/CREDITS.md). Never a picture of this car's connector.
const BAY = "img/mustang-9904-engine-context.jpg";
const ESSEX = "img/essex-38-context.jpg";

export function contextPhoto(partId: string): string | null {
  if (partId === "pdb" || partId === "ccrm") return BAY;
  return PARTS[partId]?.system === "engine" ? ESSEX : null;
}

const LOCAL_KEY = "mustang.localPhotos.v1";
export function localPhotosOn(): boolean {
  try {
    return localStorage.getItem(LOCAL_KEY) === "1";
  } catch {
    return false;
  }
}
export function setLocalPhotos(on: boolean) {
  try {
    if (on) localStorage.setItem(LOCAL_KEY, "1");
    else localStorage.removeItem(LOCAL_KEY);
  } catch {
    /* storage blocked: stays off */
  }
}

export function PartPhoto({ id, partId, alt, local = false }: { id: string; partId: string; alt: string; local?: boolean }) {
  const ctx = contextPhoto(partId);
  const mine = local ? [`local/photos/${id.replace(/:/g, "__")}.jpg`, `local/photos/${partId}.jpg`] : [];
  const list = [...mine, ...(ctx ? [ctx] : [])];
  return <PhotoChain key={`${id}|${local}`} list={list} ctx={ctx} alt={alt} />;
}

function PhotoChain({ list, ctx, alt }: { list: string[]; ctx: string | null; alt: string }) {
  const [i, setI] = useState(0);
  if (i >= list.length) {
    return (
      <figure className="conn-photo">
        <ConnectorSvg />
        <figcaption className="fine">Illustration only, not your car&rsquo;s connector. Add your own photo in Mustang/local/photos/ and turn on &ldquo;Use my local photos&rdquo; under Advanced.</figcaption>
      </figure>
    );
  }
  const src = list[i];
  return (
    <figure className="conn-photo">
      <img src={src} alt={alt} loading="lazy" decoding="async" referrerPolicy="no-referrer" onError={() => setI(i + 1)} />
      <figcaption className="fine">
        {src === ctx && ctx === BAY ? "Representative: 1999 SVT Cobra V8 bay, not the 3.8 V6" : src === ctx ? "Context only, not your car\u2019s connector. Credits in Mustang/CREDITS.md." : "Your photo, from Mustang/local/photos/."}
      </figcaption>
    </figure>
  );
}

export function ConnectorSvg() {
  return (
    <svg className="conn-svg" viewBox="0 0 320 120" role="img" aria-label="Generic connector illustration">
      <rect x="60" y="20" width="200" height="80" rx="10" fill="var(--color-surface-2)" stroke="var(--color-line)" />
      <rect x="140" y="8" width="40" height="14" rx="3" fill="var(--color-surface-2)" stroke="var(--color-line)" />
      {[0, 1, 2, 3].map((k) => (
        <rect key={k} x={84 + k * 42} y="48" width="26" height="26" rx="4" fill="none" stroke="var(--color-muted)" />
      ))}
    </svg>
  );
}
