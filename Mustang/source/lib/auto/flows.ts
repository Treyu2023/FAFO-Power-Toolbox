import { GROUPS, partBlurb } from "@/lib/auto/model";
import type { CarSpec } from "@/lib/auto/resolve";

export type Circuit = "fuel" | "all";
export type FlowWire = { role: string; color: string };
export type FlowStep = {
  id: string;
  partId: string;
  title: string;
  where: string;
  harness: string;
  wires: FlowWire[];
  action: string;
  pass: string;
  fail: string;
};

export type Flow = {
  id: string;
  title: string;
  lead: string;
  circuit: Circuit | "all";
  steps: FlowStep[];
};

const FUEL_PUMP_POWER: Flow = {
  id: "fuel-pump-power",
  title: "Fuel pump power",
  lead: "Cranks and will not fire, or you never hear the pump. This path is battery, the under-hood fuse, the CCRM relay, the inertia switch in the driver-side trunk, then the connector on the tank. This car has no fuel-pump driver module. Do not drop the tank until a step says the pump itself is dead.",
  circuit: "fuel",
  steps: [
    {
      id: "prime",
      partId: "fuel-pump",
      title: "Listen for the prime",
      where: "At the filler, cap off, or with an ear at the trunk floor.",
      harness: "Not yet. This step is only the sound.",
      wires: [],
      action:
        "Key to ON. Do not crank. A good circuit runs the pump for about one second, then stops. It runs again while a helper cranks, because the PCM only holds the relay closed once it sees the crank signal.",
      pass: "You heard it. Power is reaching the pump for the prime. If it still will not start, the miss is spark, pressure, or a pump that quits under load. Say so in the note before you buy parts.",
      fail: "Silence. Do not buy a pump. The next stop is the inertia switch, and it is free.",
    },
    {
      id: "inertia",
      partId: "inertia-switch",
      title: "Reset the inertia switch",
      where: "Driver side of the trunk, behind the liner, ahead of the left tail lamp. It is not in the passenger kick panel.",
      harness: "Fuel-pump harness in the trunk. Two wires on the switch. The sender wires are not on this switch.",
      wires: [
        {
          role: "Power in, from the CCRM",
          color: "Dark green / yellow",
        },
        {
          role: "Power out, toward the tank",
          color:
            "Read it on your connector and write it in the note. The feed into the switch is dark green/yellow. The wire leaving it is not the same in every book, so the color on the car wins.",
        },
      ],
      action:
        "Press the reset button until it stays down. Key ON again and listen. A bump, a curb, or a hard slam pops this and the car cranks forever.",
      pass: "The button was up, and now the pump primes. That was the whole job. If it pops again on a smooth road, replace the switch. Do not bypass it.",
      fail: "The button was already down and the pump is still silent. Leave the switch reset and move to the fuse.",
    },
    {
      id: "fuse",
      partId: "pdb",
      title: "Fuel-pump fuse",
      where: "Under-hood power distribution box, passenger side of the radiator support. The lid has the map. Use the lid, not a remembered slot.",
      harness: "Battery junction box. The fuse feeds the CCRM. It is not the dash fuse panel at the left knee.",
      wires: [],
      action:
        "Key off. Pull the fuel-pump fuse printed on the lid. Look at the element against the light. Reseat it, or replace it with the same amp rating that is printed.",
      pass: "It was open, and a new fuse of the same amp makes the pump prime. If the new one blows, find the short before you leave. A bigger fuse burns the harness.",
      fail: "The element is intact. Power is not dying in this fuse. Next is the CCRM.",
    },
    {
      id: "ccrm-out",
      partId: "ccrm",
      title: "Relay output",
      where: "CCRM, passenger side of the bay on the radiator support. Black module. The fuel-pump relay is inside it. You do not pry it open.",
      harness: "Engine harness at the CCRM connector.",
      wires: [
        {
          role: "Relay output, runs back to the inertia switch",
          color: "Dark green / yellow",
        },
        {
          role: "Battery feed into the fuel-pump relay",
          color: "Light blue / orange on the 99–04 CCRM. Confirm the stripe on your connector before you load it.",
        },
      ],
      action:
        "Backprobe the dark green/yellow. Black lead on battery negative. Key ON. You want battery voltage for about one second, then it falls away. Have a helper crank. It should come back while the engine is turning.",
      pass: "That pulse is there. The relay closed and the PCM commanded it. The open is downstream: the switch, the wire to the tank, the pump, or the ground.",
      fail: "It never goes hot, not even for the one-second prime. Stay at the CCRM. Do not drop the tank.",
    },
    {
      id: "relay",
      partId: "ccrm",
      title: "Feed and the click",
      where: "Same CCRM connector.",
      harness: "Engine harness. The PCM grounds the relay coil. That control wire’s color belongs to the EVTM. Do not guess a pin and ground it.",
      wires: [
        {
          role: "Battery feed",
          color: "Light blue / orange. Hot with the key off. It does not wait for the PCM.",
        },
      ],
      action:
        "Key off, then ON, and listen for a click at the CCRM. Meter the light blue/orange to battery negative. It should be battery voltage whether or not the relay clicks.",
      pass: "The feed is hot and you hear the click, but the dark green/yellow stayed dead on the last step. The contacts are open. The CCRM is the failed part, not the pump.",
      fail: "No click, or the light blue/orange is dead. Dead feed: back to the fuse and the wire into the CCRM. Feed is hot and there is no click: the PCM is not grounding the coil, or the coil is open. Still not a pump.",
    },
    {
      id: "both-sides",
      partId: "inertia-switch",
      title: "Both sides of the switch",
      where: "Inertia switch connector, driver side of the trunk.",
      harness: "Trunk harness. Unplug it only if you cannot backprobe. The pins are small.",
      wires: [
        { role: "In from the CCRM", color: "Dark green / yellow" },
        {
          role: "Out to the tank",
          color: "Whatever color you wrote down. Both wires should be hot during the prime if the switch is closed.",
        },
      ],
      action:
        "Helper turns the key to ON. During that one second, both wires at the switch should show battery voltage against battery negative. Miss the second and you will call a good switch bad. Do it twice.",
      pass: "Both sides go hot. Power is through the switch. The loss is between here and the pump, or it is the pump, or it is the ground.",
      fail: "Only the dark green/yellow goes hot. The switch is open even though the button looks down. Replace the switch. If neither side goes hot, you missed the prime or the CCRM output was never there. Recheck that step with the helper before you condemn the switch.",
    },
    {
      id: "hat",
      partId: "fuel-pump",
      title: "Voltage at the pump connector",
      where: "Top of the tank. Fold the rear seat, pull the trunk carpet, four bolts on the access cover. You can unplug the hat without dropping the tank.",
      harness: "Rear harness at the pump and sender connector. The pump uses two of the pins. The sender uses the others. Do not load-test the sender.",
      wires: [
        {
          role: "Pump power",
          color: "The same wire that was hot on the output side of the inertia switch. Follow that color. Do not stab a sender wire because it is easier to reach.",
        },
        {
          role: "Pump ground",
          color: "Black, to the body near the tank. Prove it ohms to battery negative. The sender has its own ground and it will lie to you.",
        },
      ],
      action:
        "During the prime, or while cranking, meter from the pump power pin to the pump ground pin. Write the number down, and write the battery voltage next to it.",
      pass: "Battery voltage, and within about half a volt of the battery. If the pump is silent with that, the last step is the ground drop. A good ground plus this reading is a dead pump.",
      fail: "Zero volts here, but both sides of the inertia switch were hot. The break is the wire between the trunk switch and this connector. A reading several volts under the battery is a drop in a connector, not a weak pump.",
    },
    {
      id: "ground",
      partId: "fuel-pump",
      title: "Ground drop",
      where: "Pump ground pin, and the ground eye on the body near the tank.",
      harness: "The black ground in the tank harness. Clean the eye if it is green. Do not add a new ground to a painted stud and call it done.",
      wires: [{ role: "Pump ground", color: "Black" }],
      action:
        "Key off. Ohms from the ground pin to battery negative. Then, during the prime, volts from that same pin to battery negative. A good ground is near 0 ohms and under about 0.2 V while the pump is commanded.",
      pass: "Ground is clean, and the last step had battery voltage at the pump, and it never ran. The pump is the failed part. Then you drop the tank. Replace the sock with it.",
      fail: "High ohms, or the pin rises off battery negative while the pump is commanded. Fix the ground before you buy a pump. A pump on a bad ground gets returned as defective.",
    },
  ],
};

const EVAP: Flow = {
  id: "evap",
  title: "Tank vapor valve",
  lead: "The valve that regulates evaporation is the EVAP purge valve, in the right front inner fender behind the splash shield. It is normally closed. The PCM duty-cycles it and intake vacuum pulls vapor out of the canister. It is not the fuel-pressure regulator. This 3.8 is returnless. Fuel pressure is set in the tank.",
  circuit: "all",
  steps: [
    {
      id: "purge",
      partId: "evap-purge",
      title: "Purge valve",
      where: "Right front inner fender, behind the splash shield. Right wheel and the shield come off to reach it.",
      harness: "Engine harness. Two-wire solenoid. One side is power, the other is the PCM driver.",
      wires: [
        {
          role: "Power and PCM driver",
          color: "Confirm both colors in the 2001 EVTM before you pierce either wire. The test that matters is duty cycle, not a guessed stripe.",
        },
      ],
      action:
        "Key on, engine running after it is warm. A scan tool should show the PCM commanding purge. Unplug the valve at idle. A valve stuck open changes the idle the moment you unplug it. A valve that never clicks and never gets commanded stores vapor until a hose or the cap burps an evap code.",
      pass: "It clicks when commanded, the idle changes when you unplug a valve that was open, and the hoses hold vacuum on the intake side. The valve is doing its job.",
      fail: "Stuck open is a vacuum leak. Never opens, with power and a command present, is a bad valve. No command is the PCM input side, not a reason to replace the canister yet.",
    },
    {
      id: "vent",
      partId: "evap-vent",
      title: "Vent solenoid",
      where: "On the canister, left rear quarter. Normally open so the canister can breathe. The PCM closes it only to seal the system for the leak test.",
      harness: "Rear harness at the canister. Separate connector from the purge valve up front.",
      wires: [
        {
          role: "Power and PCM driver",
          color: "Read them on the connector. Do not copy the purge-valve colors. It is a different circuit.",
        },
      ],
      action:
        "With the connector off, the vent path through the solenoid should be open. You can blow through it. Commanded closed, during a leak test, it should shut. A vent that is stuck closed pressure-locks the tank. A vent that will not close fails the leak test and sets an evap code with a good cap.",
      pass: "Open at rest, closes when commanded, hoses seated and not cracked.",
      fail: "Stuck shut: tank pressure and a hard-to-open cap. Stuck open during the test: the leak the PCM sees may be this solenoid, not a hole in the tank.",
    },
    {
      id: "tube",
      partId: "vapor-valve",
      title: "Vapor valve on the tank",
      where: "On top of the tank. Ford services the vapor control valve, the vapor vent valve, and the inline tank-pressure sensor as one tube assembly.",
      harness: "The pressure sensor has its own connector on that tube. The valves themselves are not a solenoid you can duty-cycle.",
      wires: [
        {
          role: "Tank pressure sensor",
          color: "Reference, signal, and return. Confirm the three colors in the EVTM. A wrong backprobe on the signal wire sets a false leak code.",
        },
      ],
      action:
        "Do not crack these hoses with the tank full and hot. Mark every hose. A liquid-filled line into the canister means this valve is letting fuel over, not just vapor. The sensor should move when you open the cap and the tank pressure equalizes.",
      pass: "Hoses are dry of liquid fuel, the sensor reads a change when the cap comes off, and the tube is not cracked at the tank nipple.",
      fail: "Liquid in the vapor hose, or a sensor that stays pegged with the cap off. The tube assembly is the service part. The purge valve up front will not fix that.",
    },
  ],
};

export function flowById(id: string | null): Flow | null {
  if (!id) return null;
  if (id === FUEL_PUMP_POWER.id) return FUEL_PUMP_POWER;
  if (id === EVAP.id) return EVAP;
  if (id.startsWith("part:")) return generic(id.slice(5), { pack: "mustang", body: "coupe", engine: "v6", trans: "manual", axle: "solid", scoop: false, paint: "#8f1d22" });
  return null;
}

export function flowFor(spec: CarSpec, partId: string): Flow {
  if (spec.pack !== "mustang") return generic(partId, spec);
  if (partId === "fuel-pump" || partId === "inertia-switch" || partId === "ccrm" || partId === "pdb") {
    return FUEL_PUMP_POWER;
  }
  if (partId === "evap-purge" || partId === "evap-vent" || partId === "vapor-valve" || partId === "tank-pressure" || partId === "evap-canister") {
    return EVAP;
  }
  return generic(partId, spec);
}

function generic(partId: string, spec: CarSpec): Flow {
  const info = partBlurb(partId, spec);
  const found = GROUPS.find((item) => item.id === partId);
  return {
    id: `part:${partId}`,
    title: info.name,
    lead: spec.pack === "common" ? "This is the common car. Do not use a Ford wire color or a Ford torque here." : "Confirm the wire color in the 2001 EVTM before you pierce anything.",
    circuit: found?.system === "fuel" ? "fuel" : "all",
    steps: info.checks.map((check, index) => ({
      id: `${partId}-${index}`,
      partId,
      title: `Check ${index + 1}`,
      where: info.name,
      harness: "Confirm the color on this car before you load a wire.",
      wires: [],
      action: check,
      pass: "This check is good. Go to the next one.",
      fail: "This check failed. Write down what you measured before you buy the part.",
    })),
  };
}

export function verdict(flow: Flow, marks: Record<string, "pass" | "fail">): string | null {
  const answered = flow.steps.filter((step) => marks[step.id]);
  if (!answered.length) return null;
  if (flow.id === "fuel-pump-power") return fuelVerdict(marks);
  const failed = flow.steps.find((step) => marks[step.id] === "fail");
  if (failed) return failed.fail;
  if (flow.steps.every((step) => marks[step.id] === "pass")) return "Every check passed. If the complaint is still there, it is upstream of this part. Ask Grok with the readings you wrote down.";
  return null;
}

function fuelVerdict(marks: Record<string, "pass" | "fail">): string | null {
  if (marks.inertia === "pass") return "The inertia switch was open. The pump should prime now. Leave the button down. If it pops again with no impact, replace the switch. Do not jumper it.";
  if (marks.fuse === "pass") return "The fuel-pump fuse was open. Replace it with the amp on the lid. If it blows again, find the short. The pump is not condemned.";
  if (marks.relay === "pass") return "The CCRM has power and it clicks, and the dark green/yellow output never went hot. Replace the CCRM. Do not drop the tank.";
  if (marks.relay === "fail" && marks["ccrm-out"] === "fail") {
    return "The relay is not closing, or the light blue/orange feed is dead. That is the fuse, the feed wire, the relay coil, or the PCM command. It is not the pump.";
  }
  if (marks["both-sides"] === "fail") return "Power is not getting through the inertia switch. Replace the switch if only the feed side goes hot. If neither side goes hot, go back to the CCRM output.";
  if (marks.hat === "fail" && marks["both-sides"] === "pass") {
    return "Power dies between the inertia switch and the tank connector. Repair that wire. The pump has not been proven bad.";
  }
  if (marks.ground === "fail") return "The pump ground is bad. Clean the eye near the tank and retest before you buy a pump.";
  if (marks.ground === "pass" && marks.hat === "pass") {
    return "Battery voltage at the pump, ground drop is clean, and it does not run. The pump is the failed part. Drop the tank and replace the sock with it.";
  }
  if (marks.prime === "pass" && !marks.hat) {
    return "The pump does prime. If the car still will not start, leave this circuit and check spark and rail pressure. A pump that only fails hot still needs a gauge, not a guess.";
  }
  return null;
}
