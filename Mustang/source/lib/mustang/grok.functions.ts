import { createServerFn } from "@tanstack/react-start";
import { partView } from "./parts";
import { VEHICLE } from "./types";

type Ask = { partId: string; symptom: string; trans: "t5" | "4r70w" };

const cache = new Map<string, string>();

function readAsk(input: unknown): Ask {
  if (!input || typeof input !== "object") throw new Error("Missing part");
  const raw = input as Record<string, unknown>;
  const partId = typeof raw.partId === "string" ? raw.partId.slice(0, 64) : "";
  const symptom = typeof raw.symptom === "string" ? raw.symptom.slice(0, 400) : "";
  const trans = raw.trans === "4r70w" ? "4r70w" : "t5";
  if (!partId) throw new Error("Missing part");
  return { partId, symptom, trans };
}

export const askMustang = createServerFn({ method: "POST" })
  .validator(readAsk)
  .handler(async ({ data }) => {
    const part = partView(data.partId, data.trans);
    if (part.name === "Unknown") return { ok: false as const, error: "That part is not on this car." };

    const key = `${data.trans}|${data.partId}|${data.symptom.trim().toLowerCase()}`;
    const hit = cache.get(key);
    if (hit) return { ok: true as const, text: hit, cached: true as const };

    const apiKey = process.env.XAI_API_KEY;
    if (!apiKey) return { ok: false as const, error: "Grok is not available in this bay right now." };

    const transLine =
      data.trans === "4r70w"
        ? "This one is marked as the optional 4R70W automatic."
        : "This one is marked as the standard T-5 five-speed.";

    const body = {
      model: "grok-4.5",
      temperature: 0.2,
      max_tokens: 420,
      messages: [
        {
          role: "system",
          content:
            "You are the shop voice in FAFO Toolbox for one car: a 2001 Ford Mustang coupe, base, 3.8L OHV Essex V6 (VIN engine code 4), EDIS waste-spark, returnless SEFI, front disc/rear drum, 7.5-inch axle. " +
            transLine +
            " The reader turns wrenches. Be direct. Lead with the first check. Name the mistake that causes a comeback. " +
            "Use the owner-manual facts in the notes. Do not invent torque values, pin numbers, or part numbers. If a number is not in the notes, say to confirm it in the Ford shop manual or on the VECI decal. " +
            "On this 2001 3.8 the fuel pump is fed by the CCRM relay, not a fuel-pump driver module. Dark green/yellow runs from the CCRM to the inertia switch in the driver-side trunk. Do not invent the color of the wire leaving that switch. The EVAP purge valve is in the right front inner fender and meters vapor. It is not the fuel-pressure regulator. " +
            "Short paragraphs. No greetings, no markdown headings.",
        },
        {
          role: "user",
          content: JSON.stringify({
            vehicle: VEHICLE,
            transmission: data.trans,
            symptom: data.symptom || "General inspection of this part",
            part: {
              name: part.name,
              system: part.system,
              circuit: part.circuit ?? null,
              notes: part.blurb,
              specs: part.specs,
              fasteners: part.fasteners,
              checks: part.checks,
            },
          }),
        },
      ],
    };

    const send = () =>
      fetch("https://api.x.ai/v1/chat/completions", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${apiKey}`,
        },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(25000),
      });

    let res = await send();
    if (res.status === 429 || res.status >= 500) res = await send();
    if (!res.ok) return { ok: false as const, error: `Grok could not answer (${res.status}).` };

    const json = (await res.json()) as { choices?: { message?: { content?: string } }[] };
    const text = json.choices?.[0]?.message?.content?.trim() ?? "";
    if (!text) return { ok: false as const, error: "Grok returned an empty note." };
    cache.set(key, text);
    return { ok: true as const, text, cached: false as const };
  });
