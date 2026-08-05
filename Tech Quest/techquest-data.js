/**
 * TECH QUEST — Big Bold Beautiful edition
 * FFT × Shining Force × Mobile Legends energy for C-store / fuel techs.
 * Parody only — not affiliated with real brands.
 */
(function (global) {
  'use strict';

  const TILE = {
    FLOOR: 0, WALL: 1, PUMP: 2, COUNTER: 3, TRASH: 4, HOOD: 5, TRAILER: 6, SERVER: 7, WATER: 8, SHOP: 9,
  };
  const TILE_STYLE = {
    0: '#1a2430', 1: '#0a0e14', 2: '#2a3540', 3: '#3a3020', 4: '#252018',
    5: '#2a1a28', 6: '#3a2818', 7: '#142030', 8: '#0a3040', 9: '#2a2838',
  };

  /** Player classes — pick one as YOUR hero; more join as recruits */
  const CLASSES = {
    smurf: {
      id: 'smurf',
      name: 'Smurf Operator',
      role: 'Warrior',
      emoji: '💧',
      color: '#3b82f6',
      blurb: 'Water-truck guy. Blue uniform energy. Hoses problems until OSHA looks over.',
      base: { maxHp: 52, atk: 12, def: 7, move: 4, range: 1, spd: 7, mag: 2 },
      growth: { maxHp: 6, atk: 2, def: 2, spd: 1, mag: 0 },
      skills: ['hose_down', 'tank_rush', 'hydrate'],
      canEquip: ['melee', 'water', 'shield', 'armor', 'boots'],
      flavor: '“I brought 3,000 gallons of solution. Not answers — solution.”',
    },
    field_mage: {
      id: 'field_mage',
      name: 'Field Technician',
      role: 'Mage · Glass Cannon',
      emoji: '⚡',
      color: '#a78bfa',
      blurb: 'Deletes firmware with a stare. −2 to all rolls when On-Call (1 of every 4 battles).',
      base: { maxHp: 34, atk: 8, def: 3, move: 4, range: 2, spd: 9, mag: 14 },
      growth: { maxHp: 3, atk: 1, def: 1, spd: 2, mag: 3 },
      skills: ['remote_nuke', 'config_storm', 'glass_edge'],
      canEquip: ['magic', 'tool', 'robe', 'boots'],
      onCallEvery: 4,
      onCallRollPenalty: 2,
      flavor: '“I’m not yelling. This is my ticket voice.”',
    },
    bard_mgr: {
      id: 'bard_mgr',
      name: 'Service Manager',
      role: 'Bard',
      emoji: '📋',
      color: '#fbbf24',
      blurb: 'Lie · Cheat · Steal pricing. Shops love you / stock hates you. Voluntold. Per Diem buffs.',
      base: { maxHp: 40, atk: 7, def: 4, move: 4, range: 2, spd: 8, mag: 8 },
      growth: { maxHp: 4, atk: 1, def: 1, spd: 1, mag: 2 },
      skills: ['voluntold', 'per_diem', 'lie_cheat_steal'],
      canEquip: ['clipboard', 'melee', 'polo', 'boots'],
      shopDiscount: 0.22,
      shopStockPenalty: 2,
      flavor: '“That’s not a lie. That’s a revised ETA.”',
    },
    paladin_const: {
      id: 'paladin_const',
      name: 'Construction',
      role: 'Paladin · Low-Pay Soldiers',
      emoji: '🧱',
      color: '#f97316',
      blurb: 'Hardhat faith. Absorbs damage for the party. Paid in exposure and concrete dust.',
      base: { maxHp: 60, atk: 10, def: 10, move: 3, range: 1, spd: 5, mag: 4 },
      growth: { maxHp: 7, atk: 2, def: 3, spd: 0, mag: 1 },
      skills: ['cover_ally', 'low_pay_grit', 'hardhat_blessing'],
      canEquip: ['melee', 'shield', 'armor', 'boots', 'hardhat'],
      flavor: '“We don’t get hazard pay. We get hazards.”',
    },
    valkyrie: {
      id: 'valkyrie',
      name: 'Projects & Startups',
      role: 'Valkyrie',
      emoji: '🪽',
      color: '#ec4899',
      blurb: 'Jump off the board one turn, then rain the Javelin of PTO. Good when it counts.',
      base: { maxHp: 42, atk: 11, def: 5, move: 5, range: 1, spd: 10, mag: 6 },
      growth: { maxHp: 4, atk: 2, def: 1, spd: 2, mag: 1 },
      skills: ['valk_jump', 'javelin_pto', 'when_it_counts'],
      canEquip: ['javelin', 'melee', 'armor', 'boots'],
      flavor: '“I’m not ghosting the site. I’m in the air.”',
    },
    pirate_merc: {
      id: 'pirate_merc',
      name: 'Pirate Mercenary',
      role: 'Merc · Boat-Rocker',
      emoji: '🏴‍☠️',
      color: '#ef4444',
      blurb: 'Toughest hull on the lot. Known to rock the boat, the invoice, and HR.',
      base: { maxHp: 58, atk: 13, def: 8, move: 4, range: 1, spd: 6, mag: 3 },
      growth: { maxHp: 6, atk: 3, def: 2, spd: 1, mag: 0 },
      skills: ['rock_the_boat', 'plunder', 'thick_hull'],
      canEquip: ['melee', 'gun', 'armor', 'boots', 'hat'],
      flavor: '“Arrr ye got a PO for that attitude?”',
    },
    lead_pos: {
      id: 'lead_pos',
      name: 'Lead / POS Technician',
      role: 'Hybrid Ace',
      emoji: '👑',
      color: '#00f3ff',
      blurb: 'Any weapon/armor. Shadowstep sites. “Because I Said So” scrambles aggro.',
      base: { maxHp: 46, atk: 11, def: 6, move: 4, range: 1, spd: 9, mag: 7 },
      growth: { maxHp: 5, atk: 2, def: 2, spd: 2, mag: 2 },
      skills: ['shadowstep', 'because_i_said_so', 'master_reset', 'ban', 'unbootstrap'],
      canEquip: ['*'],
      flavor: '“I was never here. The ticket says otherwise.”',
    },
  };

  /** Named heroes / recruits (class templates + personality) */
  const HEROES = {
    player: { id: 'player', name: 'You', title: 'ANY Key Legend-in-Training', isPlayer: true },
    harold: {
      id: 'harold', name: 'Hydration Harold', title: 'Smurf of the South Loop',
      classId: 'smurf', emoji: '💧',
      blurb: 'Owns three hoses and zero weekends. Recruits after the flooded Quick E lot.',
    },
    fiona: {
      id: 'fiona', name: 'Fiber Fiona', title: 'Glass Cannon Supreme',
      classId: 'field_mage', emoji: '🔮',
      blurb: 'Splices souls and single-mode. On-call curse is personal.',
    },
    vicki: {
      id: 'vicki', name: 'Vicki Voluntold', title: 'Bard of the Schedule',
      classId: 'bard_mgr', emoji: '📋',
      blurb: 'Can reassign your life with a calendar invite.',
    },
    hank: {
      id: 'hank', name: 'Hardhat Hank', title: 'Low-Pay Paladin',
      classId: 'paladin_const', emoji: '🧱',
      blurb: 'Shields the weak. Invoices the strong. Paid in dust.',
    },
    penelope: {
      id: 'penelope', name: 'PTO Penelope', title: 'Valkyrie of Vacation',
      classId: 'valkyrie', emoji: '🪽',
      blurb: 'Jumps out of meetings. Lands as a javelin of approved leave.',
    },
    markup: {
      id: 'markup', name: 'Captain Markup', title: 'Pirate of the Parts Counter',
      classId: 'pirate_merc', emoji: '🏴‍☠️',
      blurb: 'Sails the seven seas of markup percentages.',
    },
    sam: {
      id: 'sam', name: 'Shadowstep Sam', title: 'Lead Who Was Never There',
      classId: 'lead_pos', emoji: '👑',
      blurb: 'Appears at Site B before Site A knows he left.',
    },
    pete: {
      id: 'pete', name: 'Parts-Runner Pete', title: 'Van Bard (unofficial)',
      classId: 'bard_mgr', emoji: '🚐',
      blurb: 'Wrong part, right attitude, legendary GPS arguments.',
    },
    carl: {
      id: 'carl', name: 'Cable Carl', title: 'Field Mage (copper edition)',
      classId: 'field_mage', emoji: '🔌',
      blurb: 'Still mad about Cat5e in a Cat6 world.',
    },
    rebecca: {
      id: 'rebecca', name: 'Receipt Rebecca', title: 'Bard of Chargebacks',
      classId: 'bard_mgr', emoji: '🧾',
      blurb: 'Her clipboard has ended marriages and warranties.',
    },
    terry: {
      id: 'terry', name: 'Tank-Top Terry', title: 'Construction Paladin (summer build)',
      classId: 'paladin_const', emoji: '🦺',
      blurb: 'Hi-vis is a lifestyle. Sunscreen is a myth.',
    },
    otto: {
      id: 'otto', name: 'Overtime Otto', title: 'Pirate of the Double-Time Seas',
      classId: 'pirate_merc', emoji: '⏱️',
      blurb: 'Clocks in emotionally at 4:59 PM.',
    },
    brenda: {
      id: 'brenda', name: 'Because-I-Said-So Brenda', title: 'Lead POS Matriarch',
      classId: 'lead_pos', emoji: '💅',
      blurb: 'Aggro is a social construct. She invented the construct.',
    },
  };

  const WEAPONS = {
    rusty_wrench: { id: 'rusty_wrench', name: 'Rusty Wrench', type: 'melee', slot: 'weapon', atk: 3, price: 0, price: 40, rarity: 'common', desc: 'Still sticky with last week’s DEF fluid.' },
    warhammer_mr: { id: 'warhammer_mr', name: 'Warhammer of MASTER RESET', type: 'melee', slot: 'weapon', atk: 12, range: 0, mag: 2, price: 0, rarity: 'legendary', desc: 'Bans problems. Unbootstraps fate. Warranty void if filmed.', unique: true },
    water_cannon: { id: 'water_cannon', name: 'Smurf Cannon Mk.II', type: 'water', slot: 'weapon', atk: 8, range: 2, price: 180, rarity: 'rare', desc: '3,000 PSI of “I told you to shut the valve.”' },
    fiber_wand: { id: 'fiber_wand', name: 'Fusion Splicer Wand', type: 'magic', slot: 'weapon', atk: 2, mag: 10, range: 2, price: 220, rarity: 'rare', desc: 'Arc-fused spite.' },
    clipboard_plus: { id: 'clipboard_plus', name: 'Clipboard of Absolute Authority', type: 'clipboard', slot: 'weapon', atk: 5, mag: 4, range: 1, price: 150, rarity: 'uncommon', desc: 'Signatures fear it.' },
    rebar_mace: { id: 'rebar_mace', name: 'Rebar of Low Pay', type: 'melee', slot: 'weapon', atk: 9, price: 0, price: 120, rarity: 'uncommon', desc: 'Forged in a porta-john epiphany.' },
    javelin_pto: { id: 'javelin_pto', name: 'Javelin of PTO', type: 'javelin', slot: 'weapon', atk: 10, range: 2, price: 260, rarity: 'epic', desc: 'Approved leave, weaponized.' },
    cutlass_markup: { id: 'cutlass_markup', name: 'Cutlass of 300% Markup', type: 'melee', slot: 'weapon', atk: 11, price: 0, price: 240, rarity: 'epic', desc: 'Cuts deeper than the invoice.' },
    pinpad_staff: { id: 'pinpad_staff', name: 'Staff of Declined Auth', type: 'magic', slot: 'weapon', atk: 4, mag: 9, range: 2, price: 200, rarity: 'rare', desc: 'Beep. No. Beep. No.' },
    aftermarket_bat: { id: 'aftermarket_bat', name: 'Aftermarket “OEM” Bat', type: 'melee', slot: 'weapon', atk: 7, price: 0, price: 90, rarity: 'common', desc: 'Definitely not OEM. Definitely works.' },
    nozzle_lance: { id: 'nozzle_lance', name: 'Nozzle Lance', type: 'melee', slot: 'weapon', atk: 8, range: 1, price: 110, rarity: 'uncommon', desc: 'Smells like premium.' },
    receipt_blade: { id: 'receipt_blade', name: 'Thermal Receipt Blade', type: 'melee', slot: 'weapon', atk: 6, mag: 3, range: 1, price: 100, rarity: 'uncommon', desc: 'Fades in sunlight. Like your will to live.' },
  };

  const ARMOR = {
    polo_basic: { id: 'polo_basic', name: 'Company Polo (M, stained)', type: 'polo', slot: 'armor', def: 2, price: 30, rarity: 'common', desc: 'Logo cracked. Soul cracked.' },
    hivis: { id: 'hivis', name: 'Hi-Vis of False Safety', type: 'armor', slot: 'armor', def: 5, price: 80, rarity: 'common', desc: 'Visible to everyone except management.' },
    steel_toes: { id: 'steel_toes', name: 'Steel Toes of Regret', type: 'boots', slot: 'boots', def: 3, move: 0, price: 70, rarity: 'common', desc: 'Toes survive. Pride does not.' },
    kevlar_apron: { id: 'kevlar_apron', name: 'Kevlar Apron (Parts Counter)', type: 'armor', slot: 'armor', def: 8, price: 200, rarity: 'rare', desc: 'Stops shrapnel and customer opinions.' },
    hardhat_gold: { id: 'hardhat_gold', name: 'Gilded Hardhat', type: 'hardhat', slot: 'helm', def: 4, price: 160, rarity: 'rare', desc: 'Looks expensive. Isn’t.' },
    robe_fiber: { id: 'robe_fiber', name: 'Robe of Single-Mode', type: 'robe', slot: 'armor', def: 3, mag: 5, price: 180, rarity: 'rare', desc: 'Bend radius: your patience.' },
    pirate_coat: { id: 'pirate_coat', name: 'Oilskin of Markup', type: 'armor', slot: 'armor', def: 7, atk: 1, price: 210, rarity: 'epic', desc: 'Smells like diesel and audacity.' },
    lead_jacket: { id: 'lead_jacket', name: 'Lead Tech Jacket (Any Gear OK)', type: 'armor', slot: 'armor', def: 6, atk: 1, mag: 1, price: 300, rarity: 'epic', desc: 'Pockets for every adapter that doesn’t fit.' },
    shield_barrel: { id: 'shield_barrel', name: 'Barrel Shield', type: 'shield', slot: 'offhand', def: 6, price: 140, rarity: 'uncommon', desc: 'Former fuel barrel. Current bad idea.' },
    sneakers_shadow: { id: 'sneakers_shadow', name: 'Shadowstep Sneakers', type: 'boots', slot: 'boots', def: 2, move: 1, price: 250, rarity: 'epic', desc: 'Left foot on Site A. Right foot already invoiced.' },
  };

  const SKILLS = {
    // Class kits
    hose_down: { id: 'hose_down', name: 'Hose Down', desc: 'Water blast range 2. Slows target 1 turn.', cd: 1, range: 2, kind: 'attack', mult: 1.15, slow: 1 },
    tank_rush: { id: 'tank_rush', name: 'Tank Rush', desc: 'Charge 1–3 tiles in a line, hit first enemy.', cd: 3, range: 3, kind: 'special' },
    hydrate: { id: 'hydrate', name: 'Hydrate the Crew', desc: 'Heal adjacent allies small HP.', cd: 3, range: 1, kind: 'support' },
    remote_nuke: { id: 'remote_nuke', name: 'Remote Config Nuke', desc: 'Magic strike range 2. Glass cannon special.', cd: 1, range: 2, kind: 'attack', mult: 1.35, useMag: true },
    config_storm: { id: 'config_storm', name: 'Config Storm', desc: 'Hit all enemies in range 2 for mag damage.', cd: 4, range: 2, kind: 'aoe' },
    glass_edge: { id: 'glass_edge', name: 'Glass Edge', desc: '+50% damage this hit; take 4 self damage.', cd: 2, range: 2, kind: 'attack', mult: 1.5, selfDmg: 4, useMag: true },
    voluntold: { id: 'voluntold', name: 'Voluntold', desc: 'Stun enemy 1 turn. “Congrats, you volunteered.”', cd: 3, range: 2, kind: 'special', stun: 1 },
    per_diem: { id: 'per_diem', name: 'Per Diem', desc: 'Party +2 rolls & Well Rested for 20 rounds.', cd: 6, range: 0, kind: 'aura' },
    lie_cheat_steal: { id: 'lie_cheat_steal', name: 'Lie · Cheat · Steal', desc: 'Next shop: better prices, fewer goods. Battle: steal 5–12 loot.', cd: 4, range: 1, kind: 'special' },
    cover_ally: { id: 'cover_ally', name: 'Cover Ally', desc: 'Redirect next hit on adjacent ally to you (1 turn).', cd: 3, range: 1, kind: 'support' },
    low_pay_grit: { id: 'low_pay_grit', name: 'Low-Pay Grit', desc: 'Gain +4 DEF for 3 turns. Flavor text is unpaid.', cd: 4, range: 0, kind: 'self' },
    hardhat_blessing: { id: 'hardhat_blessing', name: 'Hardhat Blessing', desc: 'Small heal + cleanse bind on ally.', cd: 3, range: 1, kind: 'support' },
    valk_jump: { id: 'valk_jump', name: 'Valkyrie Jump', desc: 'Leave the board 1 turn (untargetable). Next action must be Javelin or land.', cd: 4, range: 0, kind: 'self' },
    javelin_pto: { id: 'javelin_pto', name: 'Javelin of PTO', desc: 'If airborne or normal: devastating strike range 2 (×1.8 if jump).', cd: 2, range: 2, kind: 'attack', mult: 1.4 },
    when_it_counts: { id: 'when_it_counts', name: 'When It Counts', desc: 'If HP < 35%, next attack +60%.', cd: 5, range: 0, kind: 'self' },
    rock_the_boat: { id: 'rock_the_boat', name: 'Rock the Boat', desc: 'AoE shake: adjacent enemies take damage + 30% confuse.', cd: 3, range: 1, kind: 'aoe' },
    plunder: { id: 'plunder', name: 'Plunder', desc: 'Attack + steal loot.', cd: 2, range: 1, kind: 'attack', mult: 1.1, steal: true },
    thick_hull: { id: 'thick_hull', name: 'Thick Hull', desc: 'Ignore next stun/bind. +2 DEF 2 turns.', cd: 4, range: 0, kind: 'self' },
    shadowstep: { id: 'shadowstep', name: 'Shadowstep', desc: 'Teleport to any empty tile in 5 range. “Another site.”', cd: 4, range: 5, kind: 'move' },
    because_i_said_so: { id: 'because_i_said_so', name: 'Because I Said So', desc: 'All aggressive enemies re-roll random targets (lose aggro).', cd: 5, range: 0, kind: 'aura' },
    master_reset: { id: 'master_reset', name: 'Warhammer · MASTER RESET', desc: 'Melee smash ×1.3. ≤15% HP → BAN.', cd: 0, range: 1, kind: 'attack', mult: 1.3 },
    ban: { id: 'ban', name: 'BAN', desc: 'Erase enemy under 20% HP.', cd: 3, range: 1, kind: 'special' },
    unbootstrap: { id: 'unbootstrap', name: 'Unbootstrap', desc: 'Clear stun/bind/slow/confuse on self or ally.', cd: 2, range: 1, kind: 'support' },
    toss_part: { id: 'toss_part', name: 'Toss OEM Part', desc: 'Ranged part (rng 3).', cd: 1, range: 3, kind: 'attack', mult: 1.1 },
    reach_ceiling: { id: 'reach_ceiling', name: 'Reach for the Ceiling', desc: 'Slow ghetto foes 2; Methen immunity.', cd: 4, range: 0, kind: 'aura' },
    // Enemy
    dank_you: { id: 'dank_you', name: 'Dank You, Cumah-gen', desc: 'Manager smile-damage.', cd: 2, range: 1, kind: 'attack', mult: 1.2 },
    one_more_ting: { id: 'one_more_ting', name: 'One More Ting', desc: '<10% once: stun 3 + heavy.', cd: 99, range: 1, kind: 'ultimate', once: true },
    dollar_demand: { id: 'dollar_demand', name: 'You Got a Dollar?', desc: 'Tax or smash.', cd: 2, range: 1, kind: 'special' },
    latch_on: { id: 'latch_on', name: 'Latch On', desc: 'Slow + hit.', cd: 2, range: 1, kind: 'attack', mult: 0.9, slow: 1 },
    flirt_dmg: { id: 'flirt_dmg', name: 'Rode-Hard Charm', desc: 'Emotional damage.', cd: 1, range: 1, kind: 'attack' },
    steal: { id: 'steal', name: 'Sticky Fingers', desc: 'Steal loot.', cd: 0, range: 1, kind: 'special' },
    startup_bind: { id: 'startup_bind', name: 'Startup Bind', desc: 'Immobilize 2.', cd: 3, range: 1, kind: 'special', bind: 2 },
    gilbu_mouf: { id: 'gilbu_mouf', name: 'Gilbu in the Mouf', desc: 'Confuse 2.', cd: 3, range: 1, kind: 'special', confuse: 2 },
    pin_decline: { id: 'pin_decline', name: 'PIN Declined', desc: 'Force acted.', cd: 2, range: 2, kind: 'special' },
    reboot_loop: { id: 'reboot_loop', name: 'Reboot Loop', desc: 'Adjacent players damaged.', cd: 3, range: 1, kind: 'aoe' },
    slurpee_splash: { id: 'slurpee_splash', name: 'Slurpee Splash', desc: 'Sticky range 2.', cd: 1, range: 2, kind: 'attack', mult: 0.95 },
    hr_writeup: { id: 'hr_writeup', name: 'HR Write-Up', desc: 'Stun 1 + shame damage.', cd: 3, range: 2, kind: 'special', stun: 1 },
    scope_creep: { id: 'scope_creep', name: 'Scope Creep', desc: 'Slow party vibes — slow 1 on hit.', cd: 2, range: 2, kind: 'attack', slow: 1 },
    unpaid_invoice: { id: 'unpaid_invoice', name: 'Unpaid Invoice', desc: 'Drain loot on hit.', cd: 2, range: 1, kind: 'attack', steal: true },
  };

  /** Enemy templates */
  const ENEMIES = {
    cust: { name: 'Hangry Customer', emoji: '😤', maxHp: 16, atk: 5, def: 1, move: 3, range: 1, spd: 6, skills: [], blurb: 'Three minutes is an eternity.' },
    clerk: { name: 'Night Clerk', emoji: '🧋', maxHp: 18, atk: 4, def: 2, move: 3, range: 2, spd: 5, skills: ['slurpee_splash'] },
    pump_gremlin: { name: 'Pump Gremlin', emoji: '👾', maxHp: 22, atk: 6, def: 2, move: 3, range: 1, spd: 7, skills: [] },
    kid: { name: "Trixie's Kid", emoji: '🧒', maxHp: 12, atk: 2, def: 0, move: 4, range: 1, spd: 11, skills: ['steal'] },
    hr_drone: { name: 'HR Drone', emoji: '📎', maxHp: 28, atk: 6, def: 3, move: 3, range: 2, spd: 6, skills: ['hr_writeup'], blurb: 'Here about your tone.' },
    scope_imp: { name: 'Scope Creep Imp', emoji: '📈', maxHp: 24, atk: 7, def: 2, move: 4, range: 2, spd: 8, skills: ['scope_creep'] },
    invoice_wraith: { name: 'Invoice Wraith', emoji: '💸', maxHp: 30, atk: 8, def: 3, move: 3, range: 1, spd: 7, skills: ['unpaid_invoice'] },
    quicke_mgr: { name: 'Manager of Quick E', emoji: '🕴️', maxHp: 95, atk: 10, def: 4, move: 3, range: 1, spd: 7, skills: ['dank_you', 'one_more_ting'], boss: true, blurb: 'Dank you… cumah-gen.' },
    methen: { name: 'The Methen Kraken', emoji: '🦑', maxHp: 75, atk: 11, def: 2, move: 4, range: 1, spd: 9, skills: ['dollar_demand', 'latch_on'], boss: true, ghettoOnly: true },
    trixie: { name: 'Trixie', emoji: '💄', maxHp: 58, atk: 9, def: 2, move: 3, range: 1, spd: 6, skills: ['flirt_dmg'], boss: true },
    gilbest: { name: 'The Gilbest', emoji: '⛽', maxHp: 90, atk: 11, def: 5, move: 3, range: 1, spd: 6, skills: ['startup_bind', 'gilbu_mouf'], boss: true },
    veryfony: { name: 'Veryfony Sentinel', emoji: '💳', maxHp: 110, atk: 12, def: 6, move: 2, range: 2, spd: 5, skills: ['pin_decline', 'reboot_loop'], boss: true },
    regional: { name: 'Regional of Holding', emoji: '📞', maxHp: 100, atk: 12, def: 5, move: 3, range: 2, spd: 6, skills: ['hr_writeup', 'scope_creep', 'voluntold'], boss: true, blurb: 'Holding music is a weapon.' },
    consultant: { name: 'Outside Consultant', emoji: '🤵', maxHp: 80, atk: 9, def: 4, move: 4, range: 2, spd: 8, skills: ['lie_cheat_steal', 'scope_creep'], boss: true, blurb: 'Charges $400/hr to rename your folders.' },
  };

  function rect(w, h, fill, extras) {
    const g = [];
    for (let y = 0; y < h; y++) {
      const row = [];
      for (let x = 0; x < w; x++) {
        let t = fill;
        if (x === 0 || y === 0 || x === w - 1 || y === h - 1) t = TILE.WALL;
        row.push(t);
      }
      g.push(row);
    }
    (extras || []).forEach(([x, y, t]) => { if (g[y]) g[y][x] = t; });
    return g;
  }

  /**
   * Campaign nodes: battle | shop | recruit | story
   * Deploy party of up to partyCap from roster.
   */
  const CAMPAIGN = [
    {
      id: 'c0', type: 'battle', chapter: 'Prologue · Clock In',
      name: 'Ticket #000 — Lot Diplomacy',
      mapHint: 'Sircle K · Lot B',
      story: [
        'The ANY Key dispatch tablet pings before coffee finishes existing.',
        'You chose your class for a reason. The Warhammer of MASTER RESET rattles in the van like a prophecy with OSHA paperwork.',
        'Clear the hangry pilgrims. This is still a warm-up ticket — but the industry is watching.',
      ],
      grid: rect(10, 8, TILE.FLOOR, [[3, 2, TILE.PUMP], [4, 2, TILE.PUMP], [5, 2, TILE.PUMP], [7, 5, TILE.TRASH]]),
      spawns: { player: [[2, 4], [2, 5], [1, 4]], enemies: [{ e: 'cust', x: 6, y: 3 }, { e: 'cust', x: 7, y: 4 }, { e: 'cust', x: 5, y: 5 }] },
      win: 'defeat_all', xp: 40, gold: 25, partyCap: 2,
    },
    {
      id: 'c1', type: 'shop', chapter: 'Hub · Parts Counter',
      name: 'Pete’s Almost-OEM Emporium',
      story: ['A fluorescent hum. A man named almost-Pete sells “OEM-adjacent” destiny.', 'Service Managers get Lie·Cheat·Steal pricing — but the shelf looks lonely.'],
      stock: ['aftermarket_bat', 'hivis', 'steel_toes', 'water_cannon', 'fiber_wand', 'clipboard_plus', 'shield_barrel'],
    },
    {
      id: 'c2', type: 'battle', chapter: 'Act I · Quick E',
      name: 'Ticket #401 — Manager of Quick E',
      mapHint: 'Quick E Mart · Back-office energy',
      story: [
        '“Dank you… cumah-gen,” says the Manager of Quick E, as if that were a password to heaven.',
        'Field note: below 10% HP he may cast One More Ting — stun three rounds, heavy unfairness, low tech rating, high chaos.',
        'If a Smurf is in the party, the parking lot mysteriously glistens.',
      ],
      grid: rect(11, 9, TILE.FLOOR, [[2, 2, TILE.COUNTER], [3, 2, TILE.COUNTER], [8, 3, TILE.PUMP], [8, 4, TILE.PUMP]]),
      spawns: {
        player: [[2, 5], [2, 6], [1, 5], [3, 6]],
        enemies: [{ e: 'clerk', x: 6, y: 3 }, { e: 'clerk', x: 7, y: 5 }, { e: 'quicke_mgr', x: 8, y: 4 }],
      },
      win: 'defeat_boss', boss: 'quicke_mgr', xp: 80, gold: 50, partyCap: 3,
      recruitAfter: 'harold',
    },
    {
      id: 'c3', type: 'recruit', chapter: 'Recruit',
      name: 'Hydration Harold joins',
      recruitId: 'harold',
      story: ['Harold steps out of a water truck like a blue-collar Neptune.', '“You look dry,” he says, and it is unclear if he means spiritually.'],
    },
    {
      id: 'c4', type: 'battle', chapter: 'Act I · Scope',
      name: 'Ticket #Scope — Imps in the Walk-In',
      mapHint: 'Cooler · Warmer tempers',
      story: ['Scope Creep Imps multiply whenever someone says “while you’re here…”', 'HR Drone arrives about your tone in the group chat.'],
      grid: rect(11, 9, TILE.FLOOR, [[4, 4, TILE.COUNTER], [5, 4, TILE.COUNTER], [6, 3, TILE.TRASH]]),
      spawns: {
        player: [[2, 4], [2, 5], [1, 5], [3, 4]],
        enemies: [{ e: 'scope_imp', x: 7, y: 3 }, { e: 'scope_imp', x: 8, y: 5 }, { e: 'hr_drone', x: 6, y: 6 }, { e: 'cust', x: 5, y: 2 }],
      },
      win: 'defeat_all', xp: 70, gold: 40, partyCap: 4,
    },
    {
      id: 'c5', type: 'shop', chapter: 'Hub · Regional Office Parking',
      name: 'Trunk Sale of the Damned',
      story: ['Someone’s hatchback is a store. Captain Markup would be proud.'],
      stock: ['rebar_mace', 'hardhat_gold', 'kevlar_apron', 'pinpad_staff', 'nozzle_lance', 'receipt_blade', 'sneakers_shadow'],
    },
    {
      id: 'c6', type: 'battle', chapter: 'Act II · Ghetto Site',
      name: 'Ticket #911 — Dollar Question',
      mapHint: 'Night · Popcorn ceilings',
      story: [
        'The Methen Kraken uncoils from behind a broken ice freezer — Gollum’s cousin if Gollum were a half-sized squid on a three-day binge.',
        'He only attacks ghetto sites. He will ask for a dollar. He is not taking no for an answer.',
        'Unlock Reach for the Ceiling: drag your hand across popcorn texture and watch pursuers lose the plot.',
      ],
      grid: rect(11, 9, TILE.HOOD, [[3, 3, TILE.TRASH], [5, 2, TILE.PUMP], [8, 4, TILE.WALL], [8, 5, TILE.WALL]]),
      spawns: {
        player: [[2, 4], [1, 5], [2, 6], [3, 5]],
        enemies: [{ e: 'cust', x: 5, y: 5 }, { e: 'pump_gremlin', x: 6, y: 3 }, { e: 'methen', x: 8, y: 4 }],
      },
      win: 'defeat_boss', boss: 'methen', xp: 90, gold: 45, partyCap: 4, ghetto: true,
      grantSkill: 'reach_ceiling', recruitAfter: 'fiona',
    },
    {
      id: 'c7', type: 'recruit', chapter: 'Recruit',
      name: 'Fiber Fiona accepts the ticket',
      recruitId: 'fiona',
      story: ['Fiona appears mid-splice, glass-cannon eyes glowing.', '“I’m on-call every fourth apocalypse,” she says. “Today might count.”'],
    },
    {
      id: 'c8', type: 'battle', chapter: 'Act III · Trailer Court',
      name: 'Ticket #13 — Prom Queen Economics',
      mapHint: 'Lot 13',
      story: [
        'Trixie: trailer-park prom queen, forty-ish, rode hard and hung up wet, accepting applications for daddy-of-the-babies.',
        'Census: thirteen kids. Business model: she damages; they steal your van blind.',
      ],
      grid: rect(12, 9, TILE.FLOOR, [[3, 2, TILE.TRAILER], [4, 2, TILE.TRAILER], [8, 6, TILE.TRAILER]]),
      spawns: {
        player: [[2, 5], [2, 6], [1, 4], [3, 6]],
        enemies: [
          { e: 'trixie', x: 8, y: 4 }, { e: 'kid', x: 6, y: 3 }, { e: 'kid', x: 7, y: 5 },
          { e: 'kid', x: 9, y: 3 }, { e: 'kid', x: 5, y: 6 },
        ],
      },
      win: 'defeat_boss', boss: 'trixie', xp: 85, gold: 35, partyCap: 4, recruitAfter: 'vicki',
    },
    {
      id: 'c9', type: 'recruit', chapter: 'Recruit',
      name: 'Vicki Voluntold reassigns reality',
      recruitId: 'vicki',
      story: ['A calendar invite appears in midair.', 'Vicki: “You’re free Friday.” You were not free Friday. You are now a bard.'],
    },
    {
      id: 'c10', type: 'battle', chapter: 'Act III · Construction',
      name: 'Ticket #CON — Low-Pay Crusade',
      mapHint: 'New build · Old pain',
      story: ['Invoice Wraiths haunt the unfinished canopy.', 'Hardhat Hank radio-crackles: “I’ll tank. You swing. We all get paid late.”'],
      grid: rect(12, 9, TILE.FLOOR, [[4, 3, TILE.WALL], [5, 3, TILE.WALL], [6, 5, TILE.TRASH], [8, 2, TILE.PUMP]]),
      spawns: {
        player: [[2, 4], [2, 5], [1, 5], [3, 4], [2, 6]],
        enemies: [
          { e: 'invoice_wraith', x: 8, y: 4 }, { e: 'invoice_wraith', x: 7, y: 6 },
          { e: 'scope_imp', x: 6, y: 3 }, { e: 'hr_drone', x: 9, y: 5 },
        ],
      },
      win: 'defeat_all', xp: 95, gold: 55, partyCap: 5, recruitAfter: 'hank',
    },
    {
      id: 'c11', type: 'recruit', chapter: 'Recruit',
      name: 'Hardhat Hank takes a shift',
      recruitId: 'hank',
      story: ['Hank plants a shield made of barrel lids.', '“Low pay,” he nods, “high purpose.”'],
    },
    {
      id: 'c12', type: 'shop', chapter: 'Hub · Pirate Parts',
      name: 'Captain Markup’s Floating Invoice',
      story: ['A flatbed barge of stolen-looking inventory. Pirates of the percentage.'],
      stock: ['cutlass_markup', 'pirate_coat', 'javelin_pto', 'lead_jacket', 'robe_fiber', 'warhammer_mr'],
    },
    {
      id: 'c13', type: 'battle', chapter: 'Act IV · The Gilbest',
      name: 'Ticket #CRIND — Purdy Teefisis',
      mapHint: 'Brand-new dispenser · Ancient startup',
      story: [
        'The Gilbest smiles like a voided warranty.',
        'Startup Bind freezes techs in boot loops. Gilbu in the mouf confuses the righteous.',
        'Unbootstrap was invented for this man.',
      ],
      grid: rect(11, 9, TILE.FLOOR, [[3, 2, TILE.PUMP], [4, 2, TILE.PUMP], [5, 2, TILE.PUMP], [3, 6, TILE.PUMP]]),
      spawns: {
        player: [[1, 4], [1, 5], [2, 4], [2, 6], [1, 6]],
        enemies: [{ e: 'pump_gremlin', x: 5, y: 3 }, { e: 'pump_gremlin', x: 5, y: 5 }, { e: 'gilbest', x: 8, y: 4 }],
      },
      win: 'defeat_boss', boss: 'gilbest', xp: 110, gold: 70, partyCap: 5, recruitAfter: 'penelope',
    },
    {
      id: 'c14', type: 'recruit', chapter: 'Recruit',
      name: 'PTO Penelope descends',
      recruitId: 'penelope',
      story: ['She jumps. The board loses her. Heaven gains a javelin.', '“Projects and startups,” she says. “We’re good when it counts.”'],
    },
    {
      id: 'c15', type: 'battle', chapter: 'Act IV · Consultants',
      name: 'Ticket #$400/hr — Outside Help',
      mapHint: 'Conference room that used to be a storage closet',
      story: ['Outside Consultant arrives to “optimize your culture.”', 'Captain Markup smells blood in the water of the budget.'],
      grid: rect(12, 9, TILE.SERVER, [[4, 4, TILE.COUNTER], [5, 4, TILE.COUNTER], [8, 2, TILE.WALL]]),
      spawns: {
        player: [[2, 4], [2, 5], [1, 5], [3, 4], [2, 6]],
        enemies: [
          { e: 'consultant', x: 9, y: 4 }, { e: 'hr_drone', x: 7, y: 3 },
          { e: 'scope_imp', x: 7, y: 6 }, { e: 'invoice_wraith', x: 8, y: 5 },
        ],
      },
      win: 'defeat_boss', boss: 'consultant', xp: 100, gold: 80, partyCap: 5, recruitAfter: 'markup',
    },
    {
      id: 'c16', type: 'recruit', chapter: 'Recruit',
      name: 'Captain Markup boards the van',
      recruitId: 'markup',
      story: ['“Yer inventory be light,” he grins. “Lucky for ye, I do bulk.”'],
    },
    {
      id: 'c17', type: 'battle', chapter: 'Act V · Holding',
      name: 'Ticket #Hold — Regional of Holding',
      mapHint: 'Phone tree final boss energy',
      story: [
        'Regional of Holding weaponizes hold music.',
        'Brenda’s voice echoes: Because I Said So — if a Lead is present, aggro becomes performance art.',
      ],
      grid: rect(12, 10, TILE.SERVER, [[3, 3, TILE.WALL], [4, 3, TILE.WALL], [7, 6, TILE.COUNTER]]),
      spawns: {
        player: [[2, 5], [2, 6], [1, 4], [3, 5], [1, 6]],
        enemies: [
          { e: 'regional', x: 9, y: 5 }, { e: 'hr_drone', x: 7, y: 3 },
          { e: 'hr_drone', x: 7, y: 7 }, { e: 'scope_imp', x: 6, y: 5 },
        ],
      },
      win: 'defeat_boss', boss: 'regional', xp: 120, gold: 90, partyCap: 5, recruitAfter: 'sam',
    },
    {
      id: 'c18', type: 'recruit', chapter: 'Recruit',
      name: 'Shadowstep Sam was already here',
      recruitId: 'sam',
      story: ['You turn around. Sam is holding the keys you thought you lost.', '“Lead techs,” he shrugs. “Any gear. Any site. No witnesses.”'],
    },
    {
      id: 'c19', type: 'shop', chapter: 'Hub · Final Prep',
      name: 'Black Market of Broken Seals',
      story: ['Last chance to buy dignity and steel toes.'],
      stock: ['warhammer_mr', 'javelin_pto', 'lead_jacket', 'cutlass_markup', 'sneakers_shadow', 'kevlar_apron', 'fiber_wand'],
    },
    {
      id: 'c20', type: 'battle', chapter: 'Finale · Veryfony',
      name: 'Ticket #ROOT — PIN Pad Olympus',
      mapHint: 'Server closet · 95°F · Hope is a firmware file',
      story: [
        'Veryfony awaits — not affiliated with anyone’s lawyers, deeply affiliated with your weekend.',
        'The full party of the ANY Key stands: Smurfs, mages, bards, paladins, valkyries, pirates, leads.',
        'Ban the minions. Unbootstrap the world. Swing like overtime is already approved.',
      ],
      grid: rect(12, 10, TILE.SERVER, [[4, 3, TILE.WALL], [5, 3, TILE.WALL], [4, 6, TILE.WALL], [5, 6, TILE.WALL]]),
      spawns: {
        player: [[2, 4], [2, 5], [2, 6], [1, 5], [3, 5]],
        enemies: [
          { e: 'pump_gremlin', x: 6, y: 4 }, { e: 'pump_gremlin', x: 6, y: 5 },
          { e: 'clerk', x: 8, y: 3 }, { e: 'veryfony', x: 9, y: 5 }, { e: 'invoice_wraith', x: 8, y: 7 },
        ],
      },
      win: 'defeat_boss', boss: 'veryfony', xp: 200, gold: 150, partyCap: 5, final: true,
    },
    {
      id: 'c21', type: 'ending', chapter: 'Epilogue',
      name: 'Champion of the ANY Key',
      story: [
        'Veryfony falls. Hold music dies mid-loop.',
        'You are Champion of the ANY Key — van permanent, legend temporary, overtime eternal.',
        'The Hidden Treasure Room opens wider. Progress Map chamber still has the day-path toys for the serious vault.',
        'Clock out. Or don’t. The next ticket is already printing.',
      ],
    },
  ];

  const LORE = {
    hammer: {
      title: 'Warhammer of MASTER RESET',
      body:
        'Forged from a retired rubber mallet, three dead lithium cells, and the tears of a tech who typed the wrong IP for six hours.\n\n' +
        'Powers: BAN · Unbootstrap · general problem-smashing.\n' +
        'Pairs beautifully with Lead / POS Technicians (any gear).\n\n' +
        'Warranty: void if you admit you used it on camera.',
    },
    treasure: {
      title: 'Hidden Treasure Room',
      body:
        'Open anytime from the title menu — before or after the blood, sweat, and per diem.\n\n' +
        'Vault notes, champion seals, and a door back to Progress Map Chamber.\n' +
        'Adventure laughs live HERE so public map pages stay professional.',
    },
  };

  const RARITY_COLOR = {
    common: '#9ca3af', uncommon: '#34d399', rare: '#60a5fa', epic: '#c084fc', legendary: '#fbbf24',
  };

  global.TECHQUEST_DATA = {
    TILE, TILE_STYLE, CLASSES, HEROES, WEAPONS, ARMOR, SKILLS, ENEMIES, CAMPAIGN, LORE, RARITY_COLOR,
    VERSION: '2.0.0',
    TITLE: 'TECH QUEST',
    SUBTITLE: 'Warhammer of MASTER RESET · ANY Key Chronicles',
    PARTY_MAX: 5,
    LEVEL_CAP: 20,
  };
})(typeof window !== 'undefined' ? window : globalThis);
