export type VinRead = {
  vin: string;
  ok: boolean;
  year: string | null;
  plant: string | null;
  body: "coupe" | "convertible" | null;
  line: "v6" | "gt" | "cobra" | null;
  engine: string | null;
  lines: { label: string; value: string }[];
  warning: string | null;
};

const WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2];

function vinValue(char: string) {
  if (char >= "0" && char <= "9") return Number(char);
  const map: Record<string, number> = { A: 1, B: 2, C: 3, D: 4, E: 5, F: 6, G: 7, H: 8, J: 1, K: 2, L: 3, M: 4, N: 5, P: 7, R: 9, S: 2, T: 3, U: 4, V: 5, W: 6, X: 7, Y: 8, Z: 9 };
  return map[char] ?? -1;
}

export function checkDigit(vin: string) {
  let sum = 0;
  for (let i = 0; i < 17; i++) {
    const value = vinValue(vin[i] ?? "");
    if (value < 0) return false;
    sum += value * WEIGHTS[i]!;
  }
  const mod = sum % 11;
  const expected = mod === 10 ? "X" : String(mod);
  return vin[8] === expected;
}

const BODY: Record<string, { body: "coupe" | "convertible"; line: "v6" | "gt" | "cobra"; label: string }> = {
  P40: { body: "coupe", line: "v6", label: "Coupe" },
  P42: { body: "coupe", line: "gt", label: "GT coupe" },
  P44: { body: "convertible", line: "v6", label: "Convertible" },
  P45: { body: "convertible", line: "gt", label: "GT convertible" },
  P46: { body: "convertible", line: "cobra", label: "Cobra convertible" },
  P47: { body: "coupe", line: "cobra", label: "Cobra coupe" },
};

const ENGINE: Record<string, string> = {
  "4": "3.8L OHV V6",
  X: "4.6L SOHC V8",
  V: "4.6L DOHC V8",
};

export function readVin(raw: string): VinRead {
  const vin = raw.toUpperCase().replace(/[^A-Z0-9]/g, "");
  const lines: { label: string; value: string }[] = [];
  if (vin.length !== 17) {
    return { vin, ok: false, year: null, plant: null, body: null, line: null, engine: null, lines, warning: "A VIN is 17 characters. It is on the dash, seen through the windshield, and on the door sticker." };
  }
  const check = checkDigit(vin);
  const series = vin.slice(4, 7);
  const body = BODY[series] ?? null;
  const engineCode = vin[7] ?? "";
  const yearCode = vin[9] ?? "";
  const plant = vin[10] === "F" ? "Dearborn" : vin[10] ? `Plant ${vin[10]}` : null;
  const year = yearCode === "1" ? "2001" : yearCode ? `Year code ${yearCode}, not 2001` : null;
  lines.push({ label: "Maker", value: vin.startsWith("1FA") ? "Ford, USA, passenger car" : `${vin.slice(0, 3)} is not the 1FA Mustang mark` });
  lines.push({ label: "Restraint", value: vin[3] === "F" ? "Belts and the second-generation airbags" : `Code ${vin[3]}. The 2001 book uses F.` });
  lines.push({ label: "Body", value: body?.label ?? `${series} is not a 2001 Mustang body code in this book` });
  lines.push({ label: "Engine", value: ENGINE[engineCode] ?? `Code ${engineCode} is not 4, X, or V` });
  lines.push({ label: "Check digit", value: check ? "Matches" : "Does not match. Read it again before you trust the rest." });
  lines.push({ label: "Year", value: year ?? "Missing" });
  lines.push({ label: "Plant", value: plant ?? "Missing" });
  lines.push({ label: "Serial", value: vin.slice(11) });
  const warning = !check
    ? "The check digit failed. Do not set the build from this."
    : yearCode !== "1"
      ? "This decoder is the 2001 Mustang table. A different year code needs its own book."
      : !body
        ? "The body code is not one this book lists for 2001."
        : null;
  return {
    vin,
    ok: check && yearCode === "1" && !!body && !!ENGINE[engineCode],
    year,
    plant,
    body: body?.body ?? null,
    line: body?.line ?? null,
    engine: ENGINE[engineCode] ?? null,
    lines,
    warning,
  };
}

export type ShopCode = {
  code: string;
  title: string;
  means: string;
  first: string;
  parts: string[];
  flow: string | null;
};

export const CODES: ShopCode[] = [
  { code: "P1000", title: "Monitors not complete", means: "The car has not finished its self-tests since the battery or the codes were cleared.", first: "Do not buy a part. Drive it through a complete warm cycle and read the codes again.", parts: [], flow: null },
  { code: "P0102", title: "MAF signal low", means: "The air-meter signal is lower than the air the engine is using.", first: "Check the connector and the filter before the meter. A loose boot after the meter is unmetered air and often sets a lean code instead.", parts: ["air-element", "maf"], flow: null },
  { code: "P0103", title: "MAF signal high", means: "The meter is reporting more air than the engine can be using.", first: "Look for oil in the meter and a short to power on the signal wire. Clean is not a calibration.", parts: ["maf"], flow: null },
  { code: "P0117", title: "Coolant temp low voltage", means: "The coolant sensor is reading very hot, or the signal is shorted.", first: "Compare the gauge, the hose temperatures, and the sensor reading before you replace it. A cold engine that claims to be hot is the sensor or the wire.", parts: ["ect"], flow: null },
  { code: "P0118", title: "Coolant temp high voltage", means: "The sensor is unplugged, open, or reading very cold.", first: "Seat the connector. An open sensor keeps the fans and the fuel off their normal map.", parts: ["ect"], flow: null },
  { code: "P0171", title: "Lean, bank 1", means: "Bank 1 is getting more air than the meter and the fuel account for.", first: "If P0174 is set too, look for a vacuum leak, the PCV, or low fuel pressure. One bank alone is that side.", parts: ["hose-booster", "hose-pcv", "intake"], flow: null },
  { code: "P0174", title: "Lean, bank 2", means: "Bank 2 is lean.", first: "Both lean codes together are a shared leak or a weak pump. One code is that bank.", parts: ["hose-pcv-fresh", "intake"], flow: null },
  { code: "P0230", title: "Fuel-pump primary", means: "The computer did not see the pump relay circuit behave.", first: "This is the relay and the fuse, not a reason to drop the tank. Walk the pump power path.", parts: ["pdb", "ccrm", "fuel-pump"], flow: "fuel-pump-power" },
  { code: "P0300", title: "Random misfire", means: "More than one cylinder is missing, or the computer cannot pin it.", first: "Fuel pressure, the coil pack, and a vacuum leak come before six new plugs. A single cylinder code is more useful.", parts: ["coil-pack", "fuel-rail"], flow: null },
  { code: "P0301", title: "Misfire, cylinder 1", means: "Cylinder 1. On the 3.8 that is the front plug on the passenger bank.", first: "Swap that plug wire with cylinder 2. If the miss moves, the wire is bad. If it stays, the plug or the injector stays.", parts: ["plug-1", "wire-1"], flow: null },
  { code: "P0302", title: "Misfire, cylinder 2", means: "Cylinder 2. Passenger bank, middle.", first: "Same wire-swap test, against cylinder 1.", parts: ["plug-2", "wire-2"], flow: null },
  { code: "P0303", title: "Misfire, cylinder 3", means: "Cylinder 3. Passenger bank, rear.", first: "Same wire-swap test.", parts: ["plug-3", "wire-3"], flow: null },
  { code: "P0304", title: "Misfire, cylinder 4", means: "Cylinder 4. Driver bank, front.", first: "Same wire-swap test.", parts: ["plug-4", "wire-4"], flow: null },
  { code: "P0305", title: "Misfire, cylinder 5", means: "Cylinder 5. Driver bank, middle.", first: "Same wire-swap test.", parts: ["plug-5", "wire-5"], flow: null },
  { code: "P0306", title: "Misfire, cylinder 6", means: "Cylinder 6. Driver bank, rear.", first: "Same wire-swap test.", parts: ["plug-6", "wire-6"], flow: null },
  { code: "P0320", title: "Crank signal", means: "The computer is not seeing a usable crank signal.", first: "The sensor is on the front cover. Check the connector and the gap before the sensor. No crank signal means no spark and no injector pulse.", parts: ["ckp"], flow: null },
  { code: "P0351", title: "Ignition coil primary", means: "The coil primary circuit failed its test.", first: "On the 3.8 this is the coil pack, not six coil-on-plug coils. Check the connector and the power feed before the pack.", parts: ["coil-pack"], flow: null },
  { code: "P0401", title: "EGR flow too low", means: "The computer commanded EGR and did not see the flow.", first: "The solenoid fails more often than the valve. Then the red control hose, then the DPFE hoses. HI and REF swapped sets a DPFE code, not a fixed valve.", parts: ["evr", "egr", "hose-egr-control", "dpfe"], flow: null },
  { code: "P0420", title: "Catalyst efficiency", means: "The downstream oxygen sensor says the catalyst is not cleaning up.", first: "Fix any misfire or lean code first. A misfire will ruin a new catalyst. Then compare the two oxygen sensors.", parts: ["o2-up", "o2-down", "cat"], flow: null },
  { code: "P0442", title: "EVAP small leak", means: "The vapor system cannot hold a small amount of pressure or vacuum.", first: "Cap, the hose at the purge valve behind the passenger liner, and cracked vapor lines at the tank. Walk the vapor path before a smoke machine guess.", parts: ["evap-purge", "fuel-cap", "evap-canister"], flow: "evap" },
  { code: "P0443", title: "Purge valve circuit", means: "The electrical test of the purge valve failed.", first: "This is the valve circuit, not a gas cap. Connector first.", parts: ["evap-purge"], flow: "evap" },
  { code: "P0455", title: "EVAP large leak", means: "The system is wide open.", first: "The cap is the usual one. After that, a hose off the purge valve or a broken line at the tank.", parts: ["fuel-cap", "evap-purge"], flow: "evap" },
  { code: "P0460", title: "Fuel level sensor", means: "The gauge sender does not match what the computer expects.", first: "The sender is on the pump hat. A gauge problem is not a pump problem until the hat is tested.", parts: ["fuel-pump"], flow: null },
  { code: "P1131", title: "Upstream oxygen, bank 1, not switching", means: "Ford test. The bank 1 sensor ahead of the catalyst is stuck.", first: "Look for an exhaust leak before the sensor, then the sensor. Do not replace the downstream sensor for this code.", parts: ["o2-up"], flow: null },
  { code: "P1151", title: "Upstream oxygen, bank 2, not switching", means: "The same test on bank 2.", first: "Same as P1131, the other bank.", parts: ["o2-up"], flow: null },
  { code: "P1400", title: "DPFE low", means: "The EGR pressure sensor reads too low.", first: "The hoses at the sensor, then the sensor. HI is the larger hose, toward the exhaust.", parts: ["dpfe", "hose-dpfe-hi", "hose-dpfe-ref"], flow: null },
  { code: "P1401", title: "DPFE high", means: "The EGR pressure sensor reads too high.", first: "Hoses reversed is a common cause. REF is the smaller hose, closer to the intake.", parts: ["dpfe", "hose-dpfe-ref", "hose-dpfe-hi"], flow: null },
  { code: "P1506", title: "Idle higher than commanded", means: "The engine is idling faster than the air control asked for.", first: "A vacuum leak and a stuck-open idle valve do this. The booster hose is the large one.", parts: ["hose-booster", "iac"], flow: null },
  { code: "P1507", title: "Idle lower than commanded", means: "The idle cannot come up.", first: "A dirty idle passage or a valve that is not opening. Clean the passage before a new valve.", parts: ["iac"], flow: null },
];

export function findCode(raw: string) {
  const code = raw.toUpperCase().replace(/[^A-Z0-9]/g, "");
  if (!code) return [];
  return CODES.filter((item) => item.code.includes(code) || item.title.toUpperCase().includes(code));
}

export type BookRow = { label: string; value: string };

export function bookRows(engine: string): BookRow[] {
  const v6 = engine === "v6";
  const v8 = engine === "v8-2v" || engine === "v8-4v";
  if (!v6 && !v8) {
    return [
      { label: "This car", value: "The part numbers and quart figures below are the 2001 Mustang book. They do not apply to the common car." },
      { label: "Plugs", value: "Number them from the front. Do not copy the Mustang gap." },
    ];
  }
  const rows: BookRow[] = [
    { label: "Fuel", value: "87 octane. Tank is 15.7 gallons." },
    { label: "Oil", value: "5W-20, 5.0 quarts with the filter. The 2001 book lists this for the 3.8 and the 4.6 SOHC." },
    { label: "Coolant", value: v6 ? "11.8 quarts. Green or yellow Motorcraft. Do not add orange extended-life." : engine === "v8-4v" ? "The 14.1 quart line in the 2001 book is the 4.6 SOHC. A Cobra is not that row. Green or yellow still applies. Not orange." : "14.1 quarts on the 4.6 SOHC table. Green or yellow. Not orange." },
    { label: "Plugs", value: "The gap is on the emissions decal under the hood, not in this list. A plug that comes out goes back in the same hole." },
    { label: "Firing order", value: v6 ? "1-4-2-5-3-6. Passenger bank is 1, 2, 3 from the front." : "1-3-7-2-6-5-4-8 on the 4.6. Do not use the V6 order on a GT." },
    { label: "Power steering", value: "MERCON, filled to the mark." },
    { label: "Manual transmission", value: v6 ? "5.6 pints of MERCON. The fill plug is the level." : "Fill to the plug. Do not use a quart guess from a different transmission." },
    { label: "Battery", value: "BXT-59." },
  ];
  if (v6) {
    rows.push(
      { label: "Air filter", value: "FA-1611" },
      { label: "Fuel filter", value: "FG-986" },
      { label: "Oil filter", value: "FL-400S" },
      { label: "PCV", value: "EV-152" },
      { label: "Plugs, part", value: "AWSF-42EE. Match the suffix on the decal." },
    );
  } else if (engine === "v8-2v") {
    rows.push(
      { label: "Air filter", value: "FA-1634" },
      { label: "Fuel filter", value: "FG-986B" },
      { label: "Oil filter", value: "FL-820S" },
      { label: "PCV", value: "EV-98" },
      { label: "Plugs, part", value: "AWSF-32P. Match the suffix on the decal." },
    );
  }
  return rows;
}

export const SYMPTOMS: { title: string; first: string; parts: string[]; flow: string | null }[] = [
  { title: "Cranks, no start", first: "Listen for the one-second prime before you buy a pump.", parts: ["fuel-pump", "inertia-switch"], flow: "fuel-pump-power" },
  { title: "No pump prime", first: "Inertia switch, then the fuse on the lid, then the CCRM. The tank is last.", parts: ["inertia-switch", "pdb", "ccrm"], flow: "fuel-pump-power" },
  { title: "Starts, then dies", first: "If it fires and dies as soon as you release the key, the run circuit or the inertia switch is open.", parts: ["inertia-switch", "ccrm"], flow: "fuel-pump-power" },
  { title: "Miss on one cylinder", first: "Read the cylinder number. Swap that wire with the next plug. The miss moves with a bad wire.", parts: ["coil-pack", "plug-1"], flow: null },
  { title: "Lean on both banks", first: "A shared vacuum leak or low fuel pressure. One bank is not both banks.", parts: ["hose-booster", "hose-pcv", "fuel-rail"], flow: null },
  { title: "Gas cap or EVAP light", first: "Cap first, then the purge hose behind the passenger front liner.", parts: ["fuel-cap", "evap-purge"], flow: "evap" },
  { title: "Runs hot", first: "Do not open the cap hot. Fans, the thermostat, and the coolant level. Orange coolant does not belong in this car.", parts: ["rad-cap", "coolant-tank", "thermostat"], flow: null },
];
