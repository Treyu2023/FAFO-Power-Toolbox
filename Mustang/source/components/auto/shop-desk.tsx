import { useMemo, useState } from "react";
import { bookRows, CODES, findCode, readVin, SYMPTOMS, type ShopCode } from "@/lib/auto/shop-ref";
import { careState } from "@/lib/auto/care";

export function ShopDesk({
  engine,
  miles,
  jobs,
  savedVin,
  onApplyVin,
  onRememberVin,
  onShow,
  onWalk,
}: {
  engine: string;
  miles: number;
  jobs: { id: string; name: string; every: number; note: string; last?: number }[];
  savedVin: string;
  onApplyVin: (body: "coupe" | "convertible", line: "v6" | "gt" | "cobra") => void;
  onRememberVin: (vin: string) => void;
  onShow: (ids: string[]) => void;
  onWalk: (flowId: string, partId: string) => void;
}) {
  const [section, setSection] = useState<"job" | "code" | "vin" | "book" | "miles">("job");
  const [query, setQuery] = useState("");
  const [picked, setPicked] = useState<ShopCode | null>(null);
  const [vin, setVin] = useState(savedVin);
  const decoded = useMemo(() => readVin(vin), [vin]);
  const matches = query.trim() ? findCode(query) : CODES;
  const rows = bookRows(engine);

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm leading-relaxed text-muted">A code is a failed test, not a parts order. The book figures are the 2001 Mustang owner's table. A common car does not use these part numbers.</p>
      <div className="flex flex-wrap gap-2">
        {(
          [
            ["job", "What is it doing"],
            ["code", "Codes"],
            ["vin", "VIN"],
            ["book", "Book"],
            ["miles", "Schedule"],
          ] as const
        ).map(([id, label]) => (
          <button key={id} type="button" onClick={() => setSection(id)} className={`h-11 rounded-md px-3 text-sm ${section === id ? "bg-accent font-medium text-accent-fg" : "border border-line text-fg"}`}>
            {label}
          </button>
        ))}
      </div>
      {section === "job" ? (
        <ul className="flex flex-col gap-2">
          {SYMPTOMS.map((item) => (
            <li key={item.title} className="rounded-md bg-elevated p-3">
              <button type="button" onClick={() => onShow(item.parts)} className="text-left text-sm font-medium text-fg">
                {item.title}
              </button>
              <p className="text-sm leading-relaxed text-fg">{item.first}</p>
              {item.flow ? (
                <button type="button" onClick={() => onWalk(item.flow!, item.parts[0] ?? "")} className="mt-2 h-11 rounded-md border border-line px-3 text-sm text-fg">
                  Walk this
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
      {section === "code" ? (
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm text-fg">
            Code
            <input value={query} onChange={(event) => { setQuery(event.target.value); setPicked(null); }} placeholder="P0301" className="h-11 rounded-md border border-line bg-bg px-3" />
          </label>
          <ul className="flex flex-col gap-2">
            {(picked ? [picked] : matches).slice(0, query.trim() || picked ? 12 : 8).map((item) => (
              <li key={item.code} className="rounded-md bg-elevated p-3">
                <button type="button" onClick={() => setPicked(picked?.code === item.code ? null : item)} className="text-left text-sm font-medium text-fg">
                  {item.code} · {item.title}
                </button>
                {picked?.code === item.code || query.trim() ? (
                  <>
                    <p className="text-sm leading-relaxed text-fg">{item.means}</p>
                    <p className="text-sm leading-relaxed text-muted">{item.first}</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {item.parts.length ? (
                        <button type="button" onClick={() => onShow(item.parts)} className="h-11 rounded-md border border-line px-3 text-sm text-fg">
                          Show on the car
                        </button>
                      ) : null}
                      {item.flow ? (
                        <button type="button" onClick={() => onWalk(item.flow!, item.parts[0] ?? "")} className="h-11 rounded-md bg-accent px-3 text-sm font-medium text-accent-fg">
                          Walk this
                        </button>
                      ) : null}
                    </div>
                  </>
                ) : null}
              </li>
            ))}
          </ul>
          {!query.trim() && !picked ? <p className="text-sm text-muted">Type a code to narrow this list. Open one to see the first check.</p> : null}
          {query.trim() && matches.length === 0 ? <p className="text-sm text-muted">That code is not in this list. Write down the freeze frame before you clear it.</p> : null}
        </div>
      ) : null}
      {section === "vin" ? (
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm text-fg">
            VIN
            <input value={vin} onChange={(event) => setVin(event.target.value.toUpperCase())} spellCheck={false} className="h-11 rounded-md border border-line bg-bg px-3 font-mono" />
          </label>
          {vin.replace(/[^A-Za-z0-9]/g, "").length > 0 ? (
            <ul className="flex flex-col gap-1">
              {decoded.lines.map((line) => (
                <li key={line.label} className="text-sm text-fg">
                  <span className="text-muted">{line.label}. </span>
                  {line.value}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted">Seventeen characters. Position 8 is the engine. Positions 5 through 7 are the body. Position 10 is the year, and 1 means 2001.</p>
          )}
          {decoded.warning ? <p className="text-sm text-fg">{decoded.warning}</p> : null}
          {decoded.ok && decoded.body && decoded.line ? (
            <button
              type="button"
              onClick={() => {
                onRememberVin(decoded.vin);
                onApplyVin(decoded.body!, decoded.line!);
              }}
              className="h-11 self-start rounded-md bg-accent px-3 text-sm font-medium text-accent-fg"
            >
              Use this build
            </button>
          ) : null}
        </div>
      ) : null}
      {section === "book" ? (
        <ul className="flex flex-col gap-2">
          {rows.map((row) => (
            <li key={row.label} className="text-sm text-fg">
              <span className="font-medium">{row.label}. </span>
              {row.value}
            </li>
          ))}
        </ul>
      ) : null}
      {section === "miles" ? (
        <div className="flex flex-col gap-2">
          <p className="text-sm text-muted">{miles > 0 ? `Using ${miles.toLocaleString()} miles on this car.` : "No miles yet. Set them under Care. They stay on this garage car."}</p>
          <ul className="flex flex-col gap-2">
            {jobs.map((item) => {
              const state = careState(miles, item.last, item.every);
              const left = item.last == null || item.every <= 0 ? null : item.every - (miles - item.last);
              const label = state === "skip" ? "Not on this car" : state === "unset" ? "Not recorded" : state === "due" ? "Due" : state === "soon" ? "Due soon" : "Ok";
              return (
                <li key={item.id} className="rounded-md bg-elevated p-3">
                  <p className="text-sm font-medium text-fg">
                    {item.name} <span className="font-normal text-muted">· {label}</span>
                  </p>
                  <p className="text-sm leading-relaxed text-fg">{item.note}</p>
                  {left != null && left > 0 ? <p className="text-sm text-muted">{left.toLocaleString()} miles until the next one.</p> : null}
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
