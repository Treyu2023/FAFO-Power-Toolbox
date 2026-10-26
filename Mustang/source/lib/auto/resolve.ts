export type PackId = "mustang" | "common";

export type Answers = Record<string, string>;

export type Choice = { id: string; label: string; detail: string };

export type Question = { id: string; prompt: string; choices: Choice[] };

export type CarSpec = {
  pack: PackId;
  body: "coupe" | "convertible";
  engine: "i4" | "v6" | "v8-2v" | "v8-4v";
  trans: "manual" | "auto";
  axle: "solid" | "irs";
  scoop: boolean;
  paint: string;
};

export type SheetLine = { label: string; value: string };

export type Sheet = {
  title: string;
  lines: SheetLine[];
  check: string | null;
  done: boolean;
};

const PAINT: Record<string, string> = {
  red: "#8f1d22",
  black: "#16161a",
  silver: "#c5c8ce",
  white: "#e4e0d8",
  yellow: "#c6ad22",
  blue: "#1e3f73",
  green: "#1c3a2a",
};

function paintChoices(ids: string[]): Choice[] {
  const labels: Record<string, string> = {
    red: "Laser Red",
    black: "Black",
    silver: "Silver",
    white: "Oxford White",
    yellow: "Zinc Yellow",
    blue: "True Blue",
    green: "Dark Highland Green",
  };
  return ids.map((id) => ({ id, label: labels[id] ?? id, detail: "" }));
}

export function chosenPath(pack: PackId, answers: Answers): { id: string; prompt: string; label: string }[] {
  const path: { id: string; prompt: string; label: string }[] = [];
  const partial: Answers = {};
  for (;;) {
    const question = nextQuestion(pack, partial);
    if (!question || !answers[question.id]) break;
    const choice = question.choices.find((item) => item.id === answers[question.id]);
    path.push({ id: question.id, prompt: question.prompt, label: choice?.label ?? answers[question.id]! });
    partial[question.id] = answers[question.id]!;
  }
  return path;
}

export function nextQuestion(pack: PackId, answers: Answers): Question | null {
  if (pack === "common") return commonQuestion(answers);
  return mustangQuestion(answers);
}

function mustangQuestion(answers: Answers): Question | null {
  if (!answers.body) {
    return {
      id: "body",
      prompt: "Body",
      choices: [
        { id: "coupe", label: "Coupe", detail: "Fixed roof" },
        { id: "convertible", label: "Convertible", detail: "No coupe roof" },
      ],
    };
  }
  if (!answers.line) {
    const choices: Choice[] = [
      { id: "v6", label: "V6", detail: "3.8L OHV" },
      { id: "gt", label: "GT", detail: "4.6L 2-valve" },
      { id: "cobra", label: "Cobra", detail: "4.6L 32-valve" },
    ];
    if (answers.body === "coupe") choices.splice(2, 0, { id: "bullitt", label: "Bullitt", detail: "Coupe only" });
    return { id: "line", prompt: "Model", choices };
  }
  if (!answers.trim && (answers.line === "v6" || answers.line === "gt")) {
    const choices: Choice[] = [
      { id: "deluxe", label: "Deluxe", detail: "Mid equipment" },
      { id: "premium", label: "Premium", detail: "Top equipment" },
    ];
    if (answers.line === "v6" && answers.body === "coupe") {
      choices.unshift({ id: "standard", label: "Standard", detail: "Base coupe only" });
    }
    return { id: "trim", prompt: "Trim", choices };
  }
  if (!answers.paint) {
    let ids = ["red", "black", "silver", "white", "yellow", "blue"];
    if (answers.line === "bullitt") ids = ["green", "black", "blue"];
    if (answers.line === "cobra") ids = ["red", "black", "yellow", "blue"];
    return { id: "paint", prompt: "Paint", choices: paintChoices(ids) };
  }
  if (!answers.trans) {
    if (answers.line === "bullitt" || answers.line === "cobra") {
      return {
        id: "trans",
        prompt: "Transmission",
        choices: [{ id: "manual", label: "TR-3650 5-speed", detail: "No automatic on this model" }],
      };
    }
    if (answers.line === "v6") {
      return {
        id: "trans",
        prompt: "Transmission",
        choices: [
          { id: "manual", label: "T-5 5-speed", detail: "V6 manual" },
          { id: "auto", label: "4R70W automatic", detail: "Four-speed" },
        ],
      };
    }
    return {
      id: "trans",
      prompt: "Transmission",
      choices: [
        { id: "manual", label: "TR-3650 5-speed", detail: "Early 2001 cars may have a T-45" },
        { id: "auto", label: "4R70W automatic", detail: "Four-speed" },
      ],
    };
  }
  if (!answers.abs && answers.line !== "cobra") {
    return {
      id: "abs",
      prompt: "Brakes",
      choices: [
        { id: "no", label: answers.line === "v6" ? "Disc / drum" : "Four-wheel disc", detail: "No ABS" },
        { id: "yes", label: answers.line === "v6" ? "Disc / drum with ABS" : "Four-wheel disc with ABS", detail: "ABS was optional" },
      ],
    };
  }
  return null;
}

function commonQuestion(answers: Answers): Question | null {
  if (!answers.body) {
    return {
      id: "body",
      prompt: "Body",
      choices: [
        { id: "coupe", label: "Coupe", detail: "Fixed roof" },
        { id: "convertible", label: "Convertible", detail: "Folding top" },
      ],
    };
  }
  if (!answers.engine) {
    return {
      id: "engine",
      prompt: "Engine",
      choices: [
        { id: "i4", label: "Inline-4", detail: "Common small gas engine" },
        { id: "v6", label: "V6", detail: "Common six" },
        { id: "v8", label: "V8", detail: "Common eight" },
      ],
    };
  }
  if (!answers.fuel) {
    return {
      id: "fuel",
      prompt: "Fuel system",
      choices: [
        { id: "return", label: "Return", detail: "Regulator on the rail" },
        { id: "returnless", label: "Returnless", detail: "Pressure set in the tank" },
      ],
    };
  }
  if (!answers.ignition) {
    return {
      id: "ignition",
      prompt: "Ignition",
      choices: [
        { id: "distributor", label: "Distributor", detail: "One coil, cap, and wires" },
        { id: "cop", label: "Coil on plug", detail: "A coil at each plug" },
      ],
    };
  }
  if (!answers.trans) {
    return {
      id: "trans",
      prompt: "Transmission",
      choices: [
        { id: "manual", label: "Manual", detail: "Clutch and a shifter" },
        { id: "auto", label: "Automatic", detail: "No clutch pedal" },
      ],
    };
  }
  if (!answers.rear) {
    return {
      id: "rear",
      prompt: "Rear brakes",
      choices: [
        { id: "drum", label: "Drums", detail: "Common on plain cars" },
        { id: "disc", label: "Discs", detail: "Common on later cars" },
      ],
    };
  }
  if (!answers.throttle) {
    return {
      id: "throttle",
      prompt: "Throttle",
      choices: [
        { id: "cable", label: "Cable", detail: "A cable from the pedal" },
        { id: "electronic", label: "Electronic", detail: "A sensor and a motor" },
      ],
    };
  }
  return null;
}

export function carSpec(pack: PackId, answers: Answers): CarSpec {
  if (pack === "common") {
    const engine = answers.engine === "v8" ? "v8-2v" : answers.engine === "v6" ? "v6" : "i4";
    return {
      pack,
      body: answers.body === "convertible" ? "convertible" : "coupe",
      engine,
      trans: answers.trans === "auto" ? "auto" : "manual",
      axle: "solid",
      scoop: false,
      paint: "#6e726c",
    };
  }
  const line = answers.line ?? "v6";
  const engine = line === "cobra" ? "v8-4v" : line === "v6" ? "v6" : "v8-2v";
  return {
    pack,
    body: answers.body === "convertible" ? "convertible" : "coupe",
    engine,
    trans: answers.trans === "auto" ? "auto" : "manual",
    axle: line === "cobra" ? "irs" : "solid",
    scoop: line === "gt" || line === "bullitt" || line === "cobra",
    paint: PAINT[answers.paint ?? ""] ?? "#8f1d22",
  };
}

export function buildSheet(pack: PackId, answers: Answers): Sheet {
  const done = nextQuestion(pack, answers) == null;
  if (pack === "common") return commonSheet(answers, done);
  return mustangSheet(answers, done);
}

function mustangSheet(answers: Answers, done: boolean): Sheet {
  const line = answers.line ?? "";
  const engine =
    line === "cobra"
      ? "4.6L DOHC 32-valve, 320 hp, 317 lb-ft"
      : line === "bullitt"
        ? "4.6L SOHC, 265 hp, 305 lb-ft"
        : line === "gt"
          ? "4.6L SOHC 2-valve, 260 hp, 302 lb-ft"
          : line === "v6"
            ? "3.8L OHV V6, 193 hp, 225 lb-ft"
            : "Not chosen";
  const axle =
    line === "cobra" ? "8.8-inch independent rear" : line === "v6" ? "7.5-inch solid axle" : line ? "8.8-inch solid axle" : "Not chosen";
  const brakes =
    line === "cobra"
      ? "Four-wheel disc"
      : line === "v6"
        ? answers.abs === "yes"
          ? "Front disc, rear drum, with ABS"
          : answers.abs === "no"
            ? "Front disc, rear drum"
            : "Not chosen"
        : line
          ? answers.abs === "yes"
            ? "Four-wheel disc with ABS"
            : answers.abs === "no"
              ? "Four-wheel disc"
              : "Not chosen"
          : "Not chosen";
  const trans =
    answers.trans === "auto"
      ? "4R70W automatic"
      : answers.trans === "manual" && line === "v6"
        ? "T-5 5-speed"
        : answers.trans === "manual" && line === "gt"
          ? "TR-3650 5-speed. Early 2001 cars may have a T-45."
          : answers.trans === "manual"
            ? "TR-3650 5-speed"
            : "Not chosen";
  return {
    title: "2001 Mustang",
    done,
    check: done
      ? "This is the build sheet for the picture. It is not a wiring diagram. Confirm the door sticker before you order a part that changes with the axle or the brakes."
      : null,
    lines: [
      { label: "Body", value: answers.body === "convertible" ? "Convertible" : answers.body === "coupe" ? "Coupe" : "Not chosen" },
      { label: "Model", value: line === "v6" ? "V6" : line === "gt" ? "GT" : line === "bullitt" ? "Bullitt coupe" : line === "cobra" ? "SVT Cobra" : "Not chosen" },
      { label: "Trim", value: answers.trim ? answers.trim[0]!.toUpperCase() + answers.trim.slice(1) : line === "bullitt" || line === "cobra" ? "The model is the trim" : "Not chosen" },
      { label: "Engine", value: engine },
      { label: "Transmission", value: trans },
      { label: "Rear", value: axle },
      { label: "Brakes", value: brakes },
    ],
  };
}

function commonSheet(answers: Answers, done: boolean): Sheet {
  const fuel = answers.fuel === "return" ? "Return, regulator on the rail" : answers.fuel === "returnless" ? "Returnless, pressure set in the tank" : "Not chosen";
  const ignition = answers.ignition === "distributor" ? "Distributor and plug wires" : answers.ignition === "cop" ? "Coil on each plug" : "Not chosen";
  let check: string | null = null;
  if (done) {
    const fuelLine =
      answers.fuel === "return"
        ? "A return-style car can hold pressure at the rail with the pump off. Do not call the pump dead until you measure that pressure and the regulator."
        : "A returnless car sets pressure in the tank. There is no rail regulator to replace.";
    const sparkLine =
      answers.ignition === "distributor"
        ? "One dead cylinder is often the wire, the cap, or that plug."
        : "One dead cylinder is often that coil or that plug, not the whole engine.";
    check = `${fuelLine} ${sparkLine} This is a common gas car, not the Mustang. Do not use a Ford pin or a Ford torque here.`;
  }
  return {
    title: "Common coupe",
    done,
    check,
    lines: [
      { label: "Body", value: answers.body === "convertible" ? "Convertible" : answers.body === "coupe" ? "Coupe" : "Not chosen" },
      { label: "Engine", value: answers.engine === "i4" ? "Inline-4" : answers.engine === "v6" ? "V6" : answers.engine === "v8" ? "V8" : "Not chosen" },
      { label: "Fuel", value: fuel },
      { label: "Ignition", value: ignition },
      { label: "Transmission", value: answers.trans === "auto" ? "Automatic" : answers.trans === "manual" ? "Manual" : "Not chosen" },
      { label: "Rear brakes", value: answers.rear === "drum" ? "Drums" : answers.rear === "disc" ? "Discs" : "Not chosen" },
      { label: "Throttle", value: answers.throttle === "cable" ? "Cable" : answers.throttle === "electronic" ? "Electronic" : "Not chosen" },
    ],
  };
}
