/**
 * TECH QUEST v2 — campaign, classes, gear, recruit, TBS combat
 */
(function (global) {
  'use strict';

  const D = () => global.TECHQUEST_DATA;
  const STORAGE = 'fafo.techquest.v2';

  function loadSave() {
    try { return JSON.parse(localStorage.getItem(STORAGE) || '{}') || {}; }
    catch { return {}; }
  }
  function saveSave(partial) {
    const next = { ...loadSave(), ...partial, updated: Date.now() };
    localStorage.setItem(STORAGE, JSON.stringify(next));
    return next;
  }
  function clone(o) { return JSON.parse(JSON.stringify(o)); }
  function uid() { return 'u' + Math.random().toString(36).slice(2, 9); }
  function dist(a, b) { return Math.abs(a.x - b.x) + Math.abs(a.y - b.y); }
  function roll(n) { return 1 + Math.floor(Math.random() * n); }
  function d20() { return roll(20); }

  function itemById(id) {
    return D().WEAPONS[id] || D().ARMOR[id] || null;
  }

  function canEquip(member, item) {
    if (!item) return false;
    const cls = D().CLASSES[member.classId];
    if (!cls) return false;
    if (cls.canEquip.includes('*')) return true;
    return cls.canEquip.includes(item.type);
  }

  function xpToLevel(lv) { return 40 + lv * 35; }

  function computeStats(member) {
    const cls = D().CLASSES[member.classId];
    const lv = member.level || 1;
    const g = cls.growth;
    const b = cls.base;
    const stats = {
      maxHp: b.maxHp + g.maxHp * (lv - 1),
      atk: b.atk + g.atk * (lv - 1),
      def: b.def + g.def * (lv - 1),
      move: b.move,
      range: b.range,
      spd: b.spd + g.spd * (lv - 1),
      mag: b.mag + g.mag * (lv - 1),
    };
    ['weapon', 'armor', 'offhand', 'boots', 'helm'].forEach((slot) => {
      const id = member.equip && member.equip[slot];
      const it = id && itemById(id);
      if (!it) return;
      stats.atk += it.atk || 0;
      stats.def += it.def || 0;
      stats.mag += it.mag || 0;
      stats.move += it.move || 0;
      stats.range += it.range || 0;
    });
    if (member.buffDef) stats.def += member.buffDef;
    return stats;
  }

  function makeMember(heroId, classId, opts) {
    opts = opts || {};
    const h = D().HEROES[heroId] || { id: heroId, name: opts.name || 'Recruit' };
    const c = D().CLASSES[classId];
    const member = {
      mid: uid(),
      heroId,
      classId,
      name: opts.name || h.name || c.name,
      title: h.title || c.role,
      emoji: opts.emoji || h.emoji || c.emoji,
      level: opts.level || 1,
      xp: 0,
      skills: (c.skills || []).slice(),
      equip: opts.equip || { weapon: 'rusty_wrench', armor: 'polo_basic', boots: 'steel_toes' },
      isPlayer: !!opts.isPlayer || !!h.isPlayer,
    };
    if (classId === 'lead_pos' || classId === 'smurf') {
      // lead starts with chance at hammer later; smurf likes water
      if (classId === 'smurf') member.equip.weapon = 'water_cannon';
    }
    if (classId === 'field_mage') member.equip.weapon = 'fiber_wand';
    if (classId === 'bard_mgr') member.equip.weapon = 'clipboard_plus';
    if (classId === 'paladin_const') member.equip.weapon = 'rebar_mace';
    if (classId === 'valkyrie') member.equip.weapon = 'javelin_pto';
    if (classId === 'pirate_merc') member.equip.weapon = 'cutlass_markup';
    if (classId === 'lead_pos') member.equip.weapon = 'warhammer_mr';
    const st = computeStats(member);
    member.hp = st.maxHp;
    return member;
  }

  function defaultCampaign(classId) {
    const player = makeMember('player', classId, { isPlayer: true, name: 'You' });
    return {
      classId,
      node: 0,
      gold: 80,
      inventory: ['aftermarket_bat', 'hivis'],
      roster: [player],
      recruited: ['player'],
      completed: [],
      battleCount: 0,
      shopBuff: null, // { discount, stockPenalty, battlesLeft }
      perDiemRounds: 0,
      skillsGlobal: [],
      spareDollar: true,
      champion: false,
      methenImmune: false,
    };
  }

  function migrateCampaign(raw) {
    if (!raw || !raw.roster) return null;
    return raw;
  }

  // ——— Battle unit from roster member ———
  function unitFromMember(member, x, y, campaign, battleIndex) {
    const st = computeStats(member);
    const cls = D().CLASSES[member.classId];
    let rollPenalty = 0;
    let onCall = false;
    if (cls.onCallEvery && campaign) {
      const n = (campaign.battleCount || 0) + 1;
      if (n % cls.onCallEvery === 0) {
        onCall = true;
        rollPenalty = cls.onCallRollPenalty || 2;
      }
    }
    let rollBonus = 0;
    if (campaign && campaign.perDiemRounds > 0) rollBonus += 2;

    const skills = member.skills.slice();
    (campaign.skillsGlobal || []).forEach((s) => {
      if (!skills.includes(s)) skills.push(s);
    });

    return {
      iid: uid(),
      mid: member.mid,
      templateId: member.classId,
      name: member.name,
      emoji: member.emoji,
      team: 'player',
      classId: member.classId,
      maxHp: st.maxHp,
      hp: Math.min(member.hp > 0 ? member.hp : st.maxHp, st.maxHp),
      atk: st.atk,
      def: st.def,
      mag: st.mag,
      move: Math.max(1, st.move),
      range: Math.max(1, st.range),
      spd: st.spd,
      skills,
      x, y,
      moved: false,
      acted: false,
      stun: 0, bind: 0, slow: 0, confuse: 0,
      skillCd: {},
      flags: {},
      airborne: false,
      coverFor: null,
      rollPenalty,
      rollBonus,
      onCall,
      whenItCounts: false,
      thickHull: false,
      buffDefTurns: 0,
      boss: false,
    };
  }

  function unitFromEnemy(eid, x, y) {
    const t = D().ENEMIES[eid];
    if (!t) throw new Error('enemy ' + eid);
    return {
      iid: uid(),
      templateId: eid,
      name: t.name,
      emoji: t.emoji,
      team: 'enemy',
      maxHp: t.maxHp,
      hp: t.maxHp,
      atk: t.atk,
      def: t.def,
      mag: t.mag || 0,
      move: t.move,
      range: t.range,
      spd: t.spd,
      skills: (t.skills || []).slice(),
      x, y,
      moved: false, acted: false,
      stun: 0, bind: 0, slow: 0, confuse: 0,
      skillCd: {},
      flags: {},
      airborne: false,
      boss: !!t.boss,
      ghettoOnly: !!t.ghettoOnly,
      rollPenalty: 0,
      rollBonus: 0,
    };
  }

  function walkable(grid, x, y) {
    if (y < 0 || x < 0 || y >= grid.length || x >= grid[0].length) return false;
    return grid[y][x] !== D().TILE.WALL;
  }

  function moveTiles(grid, unit, units) {
    if (unit.airborne) return [];
    const occupied = new Set(
      units.filter((u) => u.hp > 0 && u.iid !== unit.iid && !u.airborne).map((u) => u.x + ',' + u.y)
    );
    let max = unit.move - (unit.slow > 0 ? 2 : 0);
    if (unit.bind > 0) max = 0;
    if (max <= 0) return [{ x: unit.x, y: unit.y, cost: 0 }];
    const best = new Map([[unit.x + ',' + unit.y, 0]]);
    const q = [{ x: unit.x, y: unit.y, cost: 0 }];
    const dirs = [[1, 0], [-1, 0], [0, 1], [0, -1]];
    while (q.length) {
      const cur = q.shift();
      for (const [dx, dy] of dirs) {
        const nx = cur.x + dx, ny = cur.y + dy, key = nx + ',' + ny, nc = cur.cost + 1;
        if (nc > max || !walkable(grid, nx, ny) || occupied.has(key)) continue;
        if (best.has(key) && best.get(key) <= nc) continue;
        best.set(key, nc);
        q.push({ x: nx, y: ny, cost: nc });
      }
    }
    return [...best.entries()].map(([k, cost]) => {
      const [x, y] = k.split(',').map(Number);
      return { x, y, cost };
    });
  }

  function attackRoll(attacker) {
    let r = d20();
    r += attacker.rollBonus || 0;
    r -= attacker.rollPenalty || 0;
    return r;
  }

  function calcDamage(attacker, defender, mult, useMag) {
    const power = useMag ? (attacker.mag || attacker.atk) : attacker.atk;
    const base = Math.max(1, power - Math.floor(defender.def * 0.55));
    const r = attackRoll(attacker);
    // roll 1-5 weak, 15+ strong, crit 20
    let rollMult = 1;
    if (r <= 4) rollMult = 0.7;
    else if (r >= 18) rollMult = 1.35;
    if (r >= 20) rollMult = 1.6;
    if (attacker.whenItCounts) rollMult *= 1.6;
    const dmg = Math.max(1, Math.round(base * (mult || 1) * rollMult + (roll(3) - 2)));
    return { dmg, roll: r, crit: r >= 20 };
  }

  function pushLog(battle, msg) {
    battle.log.unshift({ t: Date.now(), msg });
    if (battle.log.length > 50) battle.log.length = 50;
  }

  function living(units, team) {
    return units.filter((u) => u.hp > 0 && !u.airborne && (!team || u.team === team));
  }
  function livingInclAir(units, team) {
    return units.filter((u) => u.hp > 0 && (!team || u.team === team));
  }

  function createBattle(node, campaign, deployMids) {
    const grid = clone(node.grid);
    const units = [];
    const spots = node.spawns.player;
    const members = campaign.roster.filter((m) => deployMids.includes(m.mid));
    members.forEach((m, i) => {
      const sp = spots[i] || spots[spots.length - 1];
      units.push(unitFromMember(m, sp[0], sp[1], campaign, campaign.battleCount));
    });
    node.spawns.enemies.forEach((e) => {
      units.push(unitFromEnemy(e.e, e.x, e.y));
    });
    return {
      node,
      grid,
      units,
      turn: 0,
      phase: 'player',
      selected: null,
      mode: 'select',
      log: [],
      lootBank: campaign.gold,
      goldDelta: 0,
      spareDollar: !!campaign.spareDollar,
      methenImmune: !!campaign.methenImmune || (campaign.skillsGlobal || []).includes('reach_ceiling'),
      perDiemRounds: campaign.perDiemRounds || 0,
      aggroScramble: false,
    };
  }

  function checkWin(battle) {
    const node = battle.node;
    const enemies = livingInclAir(battle.units, 'enemy');
    const players = livingInclAir(battle.units, 'player');
    if (!players.length) {
      battle.phase = 'lost';
      pushLog(battle, 'All techs down. Ticket reopened. Shame spiral loading…');
      return true;
    }
    if (node.win === 'defeat_all' && !enemies.length) {
      battle.phase = 'won';
      pushLog(battle, 'Site clear. Customer still mad. Ticket closed anyway.');
      return true;
    }
    if (node.win === 'defeat_boss') {
      const boss = battle.units.find((u) => u.templateId === node.boss && u.hp > 0);
      if (!boss) {
        battle.phase = 'won';
        pushLog(battle, 'Boss down. Somewhere, a KPI just blushed.');
        return true;
      }
    }
    return false;
  }

  function endUnitTurn(unit) {
    if (unit.stun > 0) unit.stun--;
    if (unit.bind > 0) unit.bind--;
    if (unit.slow > 0) unit.slow--;
    if (unit.confuse > 0) unit.confuse--;
    if (unit.buffDefTurns > 0) {
      unit.buffDefTurns--;
      if (unit.buffDefTurns <= 0) unit.def -= 4;
    }
    Object.keys(unit.skillCd).forEach((k) => {
      if (unit.skillCd[k] > 0) unit.skillCd[k]--;
    });
    unit.whenItCounts = false;
  }

  function tryMove(battle, unit, x, y) {
    if (battle.phase !== 'player' || unit.team !== 'player') return { ok: false };
    if (unit.acted || unit.moved || unit.stun > 0 || unit.airborne) return { ok: false };
    const tiles = moveTiles(battle.grid, unit, battle.units);
    if (!tiles.some((t) => t.x === x && t.y === y)) return { ok: false };
    unit.x = x; unit.y = y; unit.moved = true;
    battle.mode = 'act';
    pushLog(battle, `${unit.name} → (${x},${y})`);
    return { ok: true };
  }

  function applyAttack(battle, attacker, defender, opts) {
    opts = opts || {};
    if (!defender || defender.hp <= 0 || defender.airborne) return { dmg: 0 };
    if (attacker.templateId === 'methen' && defender.team === 'player' && battle.methenImmune) {
      pushLog(battle, 'Methen Kraken lunges… Reach for the Ceiling says no dollar, no drama.');
      return { dmg: 0, immune: true };
    }
    // cover
    if (defender.team === 'player') {
      const cover = battle.units.find(
        (u) => u.hp > 0 && u.coverFor === defender.iid && dist(u, defender) <= 1
      );
      if (cover) {
        pushLog(battle, `${cover.name} covers ${defender.name}!`);
        defender = cover;
      }
    }
    let target = defender;
    if (attacker.confuse > 0 && Math.random() < 0.5) {
      const adj = battle.units.filter((u) => u.hp > 0 && !u.airborne && u.iid !== attacker.iid && dist(attacker, u) === 1);
      if (adj.length) {
        target = adj[Math.floor(Math.random() * adj.length)];
        pushLog(battle, `${attacker.name} is confused and swings at ${target.name}!`);
      }
    }
    if (target.thickHull && (opts.stun || opts.bind)) {
      pushLog(battle, `${target.name}'s Thick Hull shrugs a status.`);
      opts = { ...opts, stun: 0, bind: 0 };
      target.thickHull = false;
    }
    const { dmg, roll: r, crit } = calcDamage(attacker, target, opts.mult, opts.useMag);
    target.hp = Math.max(0, target.hp - dmg);
    pushLog(
      battle,
      `${attacker.name} hits ${target.name} for ${dmg} (roll ${r}${crit ? ' CRIT' : ''}).` +
        (target.hp <= 0 ? ' KO!' : '')
    );
    if (opts.skill === 'master_reset' && target.hp > 0 && target.hp / target.maxHp <= 0.15) {
      target.hp = 0;
      pushLog(battle, `🔨 MASTER RESET bans ${target.name}.`);
    }
    if (opts.slow) target.slow = Math.max(target.slow, opts.slow);
    if (opts.stun) target.stun = Math.max(target.stun, opts.stun);
    if (opts.bind) target.bind = Math.max(target.bind, opts.bind);
    if (opts.confuse) target.confuse = Math.max(target.confuse, opts.confuse);
    if (opts.steal) {
      const g = 5 + roll(8);
      battle.goldDelta -= g;
      pushLog(battle, `Loot shifts by ${g}.`);
    }
    if (opts.selfDmg) {
      attacker.hp = Math.max(1, attacker.hp - opts.selfDmg);
      pushLog(battle, `${attacker.name} takes ${opts.selfDmg} glass-cannon feedback.`);
    }
    return { dmg, target, roll: r };
  }

  function useSkill(battle, unit, skillId, target, tile) {
    const sk = D().SKILLS[skillId];
    if (!sk) return { ok: false, reason: 'no-skill' };
    if (!unit.skills.includes(skillId) && skillId !== 'reach_ceiling') return { ok: false, reason: 'locked' };
    if ((unit.skillCd[skillId] || 0) > 0) return { ok: false, reason: 'cd' };
    if (unit.acted || unit.stun > 0) return { ok: false, reason: 'acted' };

    // Land from jump if using javelin
    if (unit.airborne && skillId !== 'javelin_pto') {
      return { ok: false, reason: 'airborne' };
    }

    if (skillId === 'valk_jump') {
      unit.airborne = true;
      unit.flags.wasX = unit.x;
      unit.flags.wasY = unit.y;
      unit.x = -1; unit.y = -1;
      pushLog(battle, `🪽 ${unit.name} jumps off the board! (untargetable)`);
      unit.skillCd[skillId] = sk.cd;
      unit.acted = true; unit.moved = true;
      return { ok: true };
    }

    if (skillId === 'javelin_pto') {
      if (!target || target.team === unit.team) return { ok: false, reason: 'target' };
      if (unit.airborne) {
        // land near target
        const dirs = [[0, 0], [1, 0], [-1, 0], [0, 1], [0, -1]];
        let landed = false;
        for (const [dx, dy] of dirs) {
          const nx = target.x + dx, ny = target.y + dy;
          if (!walkable(battle.grid, nx, ny)) continue;
          if (battle.units.some((u) => u.hp > 0 && !u.airborne && u.x === nx && u.y === ny)) continue;
          unit.x = nx; unit.y = ny; unit.airborne = false;
          landed = true;
          break;
        }
        if (!landed) {
          unit.x = unit.flags.wasX || 1;
          unit.y = unit.flags.wasY || 1;
          unit.airborne = false;
        }
        applyAttack(battle, unit, target, { mult: 1.8, skill: skillId });
        pushLog(battle, `Javelin of PTO rains from vacation-space!`);
      } else {
        if (dist(unit, target) > sk.range) return { ok: false, reason: 'range' };
        applyAttack(battle, unit, target, { mult: sk.mult || 1.4, skill: skillId });
      }
    } else if (skillId === 'shadowstep') {
      if (!tile) return { ok: false, reason: 'tile' };
      if (!walkable(battle.grid, tile.x, tile.y)) return { ok: false, reason: 'tile' };
      if (dist(unit, tile) > sk.range) return { ok: false, reason: 'range' };
      if (battle.units.some((u) => u.hp > 0 && !u.airborne && u.x === tile.x && u.y === tile.y)) {
        return { ok: false, reason: 'blocked' };
      }
      unit.x = tile.x; unit.y = tile.y;
      pushLog(battle, `👑 ${unit.name} shadowsteps to another site (${tile.x},${tile.y}). Nobody noticed.`);
    } else if (skillId === 'because_i_said_so') {
      battle.aggroScramble = true;
      pushLog(battle, '💅 Because I Said So — all aggressors re-roll targets next swing!');
    } else if (skillId === 'per_diem') {
      battle.perDiemRounds = 20;
      livingInclAir(battle.units, 'player').forEach((u) => { u.rollBonus = (u.rollBonus || 0) + 2; });
      pushLog(battle, '📋 Per Diem! Party +2 rolls & Well Rested for 20 rounds. Receipts: none.');
    } else if (skillId === 'reach_ceiling') {
      battle.methenImmune = true;
      living(battle.units, 'enemy').forEach((e) => {
        if (battle.node.ghetto || e.ghettoOnly || e.templateId === 'methen' || e.templateId === 'kid') {
          e.slow = Math.max(e.slow, 2);
        }
      });
      pushLog(battle, '🖐️ Reach for the Ceiling! Popcorn chaos. Methen tax revoked.');
    } else if (skillId === 'voluntold' || skillId === 'startup_bind' || skillId === 'gilbu_mouf' || skillId === 'hr_writeup') {
      if (!target || dist(unit, target) > sk.range) return { ok: false, reason: 'range' };
      if (sk.stun) target.stun = Math.max(target.stun, sk.stun);
      if (sk.bind) target.bind = Math.max(target.bind, sk.bind);
      if (sk.confuse) target.confuse = Math.max(target.confuse, sk.confuse);
      if (skillId === 'hr_writeup') applyAttack(battle, unit, target, { mult: 0.8 });
      pushLog(battle, `${sk.name} lands on ${target.name}.`);
    } else if (skillId === 'ban') {
      if (!target || target.team === unit.team || dist(unit, target) > 1) return { ok: false, reason: 'target' };
      if (target.hp / target.maxHp > 0.2) return { ok: false, reason: 'hp' };
      target.hp = 0;
      pushLog(battle, `🚫 BAN — ${target.name} is closed with prejudice.`);
    } else if (skillId === 'unbootstrap' || skillId === 'hardhat_blessing') {
      const t = target && dist(unit, target) <= 1 ? target : unit;
      if (t.team !== 'player') return { ok: false, reason: 'target' };
      t.stun = 0; t.bind = 0; t.slow = 0; t.confuse = 0;
      if (skillId === 'hardhat_blessing') t.hp = Math.min(t.maxHp, t.hp + 8);
      pushLog(battle, `✨ ${sk.name} restores ${t.name}.`);
    } else if (skillId === 'hydrate') {
      living(battle.units, 'player').forEach((a) => {
        if (dist(unit, a) <= 1) a.hp = Math.min(a.maxHp, a.hp + 10);
      });
      pushLog(battle, '💧 Crew hydrated. Electrolytes of war.');
    } else if (skillId === 'cover_ally') {
      if (!target || target.team !== 'player' || dist(unit, target) > 1) return { ok: false, reason: 'target' };
      unit.coverFor = target.iid;
      pushLog(battle, `${unit.name} covers ${target.name}.`);
    } else if (skillId === 'low_pay_grit') {
      unit.def += 4; unit.buffDefTurns = 3;
      pushLog(battle, '🧱 Low-Pay Grit — DEF up. Wallet unchanged.');
    } else if (skillId === 'when_it_counts') {
      if (unit.hp / unit.maxHp > 0.35) return { ok: false, reason: 'hp-gate' };
      unit.whenItCounts = true;
      pushLog(battle, '🪽 When It Counts — next hit is personal.');
    } else if (skillId === 'thick_hull') {
      unit.thickHull = true;
      unit.def += 2; unit.buffDefTurns = Math.max(unit.buffDefTurns, 2);
      pushLog(battle, '🏴‍☠️ Thick Hull engaged.');
    } else if (skillId === 'lie_cheat_steal') {
      if (target && target.team === 'enemy' && dist(unit, target) <= 1) {
        applyAttack(battle, unit, target, { mult: 0.9, steal: true });
      }
      battle.flags = battle.flags || {};
      battle.flags.shopScam = true;
      pushLog(battle, '📋 Lie·Cheat·Steal armed for the next shop (better prices, fewer goods).');
    } else if (skillId === 'config_storm' || skillId === 'rock_the_boat' || skillId === 'reboot_loop') {
      const foes = skillId === 'reboot_loop'
        ? living(battle.units, 'player')
        : living(battle.units, unit.team === 'player' ? 'enemy' : 'player');
      foes.forEach((f) => {
        if (dist(unit, f) <= (sk.range || 1)) {
          applyAttack(battle, unit, f, {
            mult: skillId === 'config_storm' ? 1.0 : 0.85,
            useMag: skillId === 'config_storm',
            confuse: skillId === 'rock_the_boat' && Math.random() < 0.3 ? 1 : 0,
          });
        }
      });
    } else if (skillId === 'tank_rush') {
      // simplified: hit nearest enemy in cardinal line within 3
      const dirs = [[1, 0], [-1, 0], [0, 1], [0, -1]];
      let hit = null, dest = null;
      for (const [dx, dy] of dirs) {
        for (let s = 1; s <= 3; s++) {
          const nx = unit.x + dx * s, ny = unit.y + dy * s;
          if (!walkable(battle.grid, nx, ny)) break;
          const u = battle.units.find((e) => e.hp > 0 && !e.airborne && e.x === nx && e.y === ny);
          if (u) { hit = u; dest = { x: unit.x + dx * (s - 1), y: unit.y + dy * (s - 1) }; break; }
        }
        if (hit) break;
      }
      if (!hit) return { ok: false, reason: 'no-line' };
      if (dest && walkable(battle.grid, dest.x, dest.y)) {
        if (!battle.units.some((u) => u.hp > 0 && u.x === dest.x && u.y === dest.y && u.iid !== unit.iid)) {
          unit.x = dest.x; unit.y = dest.y;
        }
      }
      applyAttack(battle, unit, hit, { mult: 1.2 });
    } else if (skillId === 'one_more_ting') {
      if (unit.hp / unit.maxHp > 0.1 || unit.flags.oneMoreTing) return { ok: false, reason: 'once' };
      unit.flags.oneMoreTing = true;
      pushLog(battle, '⚠️ ONE MORE TING!');
      applyAttack(battle, unit, target, { mult: 1.85, stun: 3 });
    } else if (skillId === 'dollar_demand') {
      if (battle.methenImmune) {
        pushLog(battle, '“Dollar?” — Ceiling power: denied.');
      } else if (battle.spareDollar) {
        battle.spareDollar = false;
        battle.goldDelta -= 1;
        pushLog(battle, 'You pay the dollar tax.');
      } else {
        applyAttack(battle, unit, target, { mult: 1.5 });
      }
    } else if (skillId === 'pin_decline') {
      if (!target || dist(unit, target) > sk.range) return { ok: false, reason: 'range' };
      target.acted = true;
      pushLog(battle, `💳 PIN Declined — ${target.name} loses the flourish.`);
    } else if (skillId === 'steal') {
      battle.goldDelta -= 1 + roll(3);
      if (target) target.hp = Math.max(0, target.hp - 2);
      pushLog(battle, '🧒 Sticky fingers!');
    } else if (skillId === 'dank_you' || skillId === 'flirt_dmg' || skillId === 'latch_on' ||
               skillId === 'hose_down' || skillId === 'remote_nuke' || skillId === 'glass_edge' ||
               skillId === 'master_reset' || skillId === 'toss_part' || skillId === 'plunder' ||
               skillId === 'slurpee_splash' || skillId === 'scope_creep' || skillId === 'unpaid_invoice') {
      if (!target || target.team === unit.team) return { ok: false, reason: 'target' };
      if (dist(unit, target) > (sk.range || unit.range)) return { ok: false, reason: 'range' };
      applyAttack(battle, unit, target, {
        mult: sk.mult || 1,
        useMag: sk.useMag,
        skill: skillId,
        slow: sk.slow,
        selfDmg: sk.selfDmg,
        steal: sk.steal || skillId === 'plunder' || skillId === 'unpaid_invoice',
      });
    } else {
      if (!target) return { ok: false, reason: 'target' };
      applyAttack(battle, unit, target, { mult: sk.mult || 1 });
    }

    unit.skillCd[skillId] = sk.cd || 0;
    unit.acted = true;
    unit.moved = true;
    checkWin(battle);
    return { ok: true };
  }

  function basicAttack(battle, unit, target) {
    if (unit.acted || unit.stun > 0 || unit.airborne) return { ok: false };
    if (!target || target.hp <= 0 || target.team === unit.team) return { ok: false };
    if (dist(unit, target) > unit.range) return { ok: false };
    // aggro scramble: enemy might hit random player
    if (unit.team === 'enemy' && battle.aggroScramble) {
      const pls = living(battle.units, 'player');
      if (pls.length) target = pls[Math.floor(Math.random() * pls.length)];
      pushLog(battle, `${unit.name} re-targets → ${target.name} (Because I Said So)`);
    }
    applyAttack(battle, unit, target, {});
    unit.acted = true; unit.moved = true;
    checkWin(battle);
    return { ok: true };
  }

  function waitUnit(battle, unit) {
    if (unit.airborne) {
      // forced land
      unit.x = unit.flags.wasX || 2;
      unit.y = unit.flags.wasY || 2;
      unit.airborne = false;
      pushLog(battle, `${unit.name} lands awkwardly.`);
    }
    unit.moved = true; unit.acted = true;
    pushLog(battle, `${unit.name} waits.`);
  }

  function enemyTurn(battle) {
    if (battle.phase !== 'enemy') return;
    const foes = living(battle.units, 'enemy').slice().sort((a, b) => b.spd - a.spd);
    const heroes = living(battle.units, 'player');
    foes.forEach((e) => {
      if (battle.phase !== 'enemy') return;
      if (e.stun > 0) { endUnitTurn(e); return; }
      if (e.templateId === 'quicke_mgr' && e.hp / e.maxHp <= 0.1 && !e.flags.oneMoreTing) {
        const t = heroes.slice().sort((a, b) => dist(e, a) - dist(e, b))[0];
        if (t && dist(e, t) <= 1) { useSkill(battle, e, 'one_more_ting', t); endUnitTurn(e); return; }
      }
      let target = heroes.slice().sort((a, b) => dist(e, a) - dist(e, b))[0];
      if (battle.aggroScramble && heroes.length) {
        target = heroes[Math.floor(Math.random() * heroes.length)];
      }
      if (!target) return;
      if (e.bind <= 0) {
        const tiles = moveTiles(battle.grid, e, battle.units);
        let best = { x: e.x, y: e.y, score: dist(e, target) };
        tiles.forEach((t) => {
          const score = Math.abs(t.x - target.x) + Math.abs(t.y - target.y);
          if (score < best.score) best = { x: t.x, y: t.y, score };
        });
        e.x = best.x; e.y = best.y;
      }
      const inR = dist(e, target) <= Math.max(e.range, 1);
      if (e.templateId === 'methen' && inR) useSkill(battle, e, Math.random() < 0.5 ? 'dollar_demand' : 'latch_on', target);
      else if (e.templateId === 'quicke_mgr' && inR) {
        if ((e.skillCd.dank_you || 0) <= 0) useSkill(battle, e, 'dank_you', target);
        else basicAttack(battle, e, target);
      } else if (e.templateId === 'gilbest' && inR) {
        if ((e.skillCd.startup_bind || 0) <= 0) useSkill(battle, e, 'startup_bind', target);
        else if ((e.skillCd.gilbu_mouf || 0) <= 0) useSkill(battle, e, 'gilbu_mouf', target);
        else basicAttack(battle, e, target);
      } else if (e.templateId === 'trixie' && inR) useSkill(battle, e, 'flirt_dmg', target);
      else if (e.templateId === 'kid' && inR) useSkill(battle, e, 'steal', target);
      else if (e.templateId === 'veryfony') {
        if (dist(e, target) <= 2 && (e.skillCd.pin_decline || 0) <= 0) useSkill(battle, e, 'pin_decline', target);
        else if ((e.skillCd.reboot_loop || 0) <= 0) useSkill(battle, e, 'reboot_loop', target);
        else if (dist(e, target) <= e.range) basicAttack(battle, e, target);
      } else if (e.templateId === 'regional' && inR) {
        if ((e.skillCd.hr_writeup || 0) <= 0) useSkill(battle, e, 'hr_writeup', target);
        else basicAttack(battle, e, target);
      } else if (e.templateId === 'consultant' && dist(e, target) <= 2) {
        useSkill(battle, e, 'scope_creep', target);
      } else if (e.skills.includes('slurpee_splash') && dist(e, target) <= 2) useSkill(battle, e, 'slurpee_splash', target);
      else if (dist(e, target) <= e.range) basicAttack(battle, e, target);
      else pushLog(battle, `${e.name} repositions.`);
      e.moved = true; e.acted = true;
      endUnitTurn(e);
    });
    battle.aggroScramble = false;
    if (battle.perDiemRounds > 0) battle.perDiemRounds--;
    if (!checkWin(battle)) {
      battle.phase = 'player';
      battle.turn++;
      livingInclAir(battle.units, 'player').forEach((u) => {
        if (u.stun > 0) { u.moved = true; u.acted = true; }
        else { u.moved = false; u.acted = false; }
        u.coverFor = null;
      });
      battle.selected = null;
      battle.mode = 'select';
      pushLog(battle, `— Round ${battle.turn + 1} · Your crew —`);
    }
  }

  function endPlayerTurn(battle) {
    livingInclAir(battle.units, 'player').forEach((u) => {
      if (!u.acted) waitUnit(battle, u);
      endUnitTurn(u);
    });
    if (checkWin(battle)) return;
    battle.phase = 'enemy';
    battle.selected = null;
    pushLog(battle, '— Enemy phase —');
    enemyTurn(battle);
  }

  function grantXpGold(campaign, node, battle) {
    const xp = node.xp || 0;
    const gold = (node.gold || 0) + Math.max(0, battle.goldDelta || 0);
    campaign.gold = Math.max(0, (campaign.gold || 0) + gold);
    campaign.roster.forEach((m) => {
      // only deployed gain full xp — approximate: all roster half, deployed full via mid match
      m.xp = (m.xp || 0) + Math.floor(xp * 0.5);
      while (m.level < D().LEVEL_CAP && m.xp >= xpToLevel(m.level)) {
        m.xp -= xpToLevel(m.level);
        m.level++;
        const st = computeStats(m);
        m.hp = st.maxHp;
      }
    });
    // heal roster slightly
    campaign.roster.forEach((m) => {
      const st = computeStats(m);
      m.hp = Math.min(st.maxHp, Math.max(m.hp, Math.floor(st.maxHp * 0.5)));
    });
    // sync HP from battle survivors
    if (battle && battle.units) {
      battle.units.filter((u) => u.team === 'player').forEach((u) => {
        const m = campaign.roster.find((r) => r.mid === u.mid);
        if (m) {
          m.hp = u.hp > 0 ? u.hp : 1;
          m.xp = (m.xp || 0) + Math.floor(xp * 0.5);
          while (m.level < D().LEVEL_CAP && m.xp >= xpToLevel(m.level)) {
            m.xp -= xpToLevel(m.level);
            m.level++;
          }
          const st = computeStats(m);
          if (u.hp > 0) m.hp = Math.min(st.maxHp, u.hp + Math.floor(st.maxHp * 0.2));
          else m.hp = Math.floor(st.maxHp * 0.4);
        }
      });
    }
    return { xp, gold };
  }

  function applyVictory(campaign, battle) {
    const node = battle.node;
    campaign.battleCount = (campaign.battleCount || 0) + 1;
    if (battle.methenImmune) {
      campaign.methenImmune = true;
      if (!campaign.skillsGlobal.includes('reach_ceiling')) campaign.skillsGlobal.push('reach_ceiling');
    }
    campaign.perDiemRounds = battle.perDiemRounds || 0;
    campaign.spareDollar = battle.spareDollar;
    if (battle.flags && battle.flags.shopScam) {
      campaign.shopBuff = { discount: 0.25, stockPenalty: 2, shopsLeft: 1 };
    }
    const reward = grantXpGold(campaign, node, battle);
    if (!campaign.completed.includes(node.id)) campaign.completed.push(node.id);
    if (node.grantSkill && !campaign.skillsGlobal.includes(node.grantSkill)) {
      campaign.skillsGlobal.push(node.grantSkill);
    }
    if (node.final) {
      campaign.champion = true;
      try {
        localStorage.setItem('fafo.techquest.champion', '1');
        localStorage.setItem('fafo.mythos.techquestClear', JSON.stringify({ at: Date.now() }));
      } catch (_) { /* ignore */ }
    }
    campaign.node = (campaign.node || 0) + 1;
    saveSave({ campaign });
    return { campaign, reward };
  }

  function recruit(campaign, heroId) {
    if (campaign.recruited.includes(heroId)) return { ok: false, reason: 'have' };
    const h = D().HEROES[heroId];
    if (!h || !h.classId) return { ok: false, reason: 'bad' };
    const m = makeMember(heroId, h.classId, { level: Math.max(1, Math.floor((campaign.roster[0]?.level || 1) * 0.9)) });
    campaign.roster.push(m);
    campaign.recruited.push(heroId);
    campaign.node = (campaign.node || 0) + 1;
    saveSave({ campaign });
    return { ok: true, member: m };
  }

  function shopStock(campaign, node) {
    let stock = (node.stock || []).slice();
    let discount = 0;
    campaign.roster.forEach((m) => {
      const c = D().CLASSES[m.classId];
      if (c.shopDiscount) discount = Math.max(discount, c.shopDiscount);
    });
    if (campaign.shopBuff) {
      discount = Math.max(discount, campaign.shopBuff.discount || 0);
      const pen = campaign.shopBuff.stockPenalty || 0;
      for (let i = 0; i < pen && stock.length > 2; i++) {
        stock.splice(Math.floor(Math.random() * stock.length), 1);
      }
    }
    // bard stock penalty
    campaign.roster.forEach((m) => {
      const c = D().CLASSES[m.classId];
      if (c.shopStockPenalty) {
        for (let i = 0; i < c.shopStockPenalty && stock.length > 2; i++) {
          stock.splice(roll(stock.length) - 1, 1);
        }
      }
    });
    return { stock: [...new Set(stock)], discount };
  }

  function buyItem(campaign, itemId, discount) {
    const it = itemById(itemId);
    if (!it) return { ok: false };
    const price = Math.max(1, Math.floor(it.price * (1 - (discount || 0))));
    if (campaign.gold < price) return { ok: false, reason: 'gold' };
    campaign.gold -= price;
    campaign.inventory.push(itemId);
    saveSave({ campaign });
    return { ok: true, price };
  }

  function equipItem(campaign, mid, itemId) {
    const m = campaign.roster.find((r) => r.mid === mid);
    const it = itemById(itemId);
    if (!m || !it) return { ok: false };
    if (!canEquip(m, it)) return { ok: false, reason: 'class' };
    const invIdx = campaign.inventory.indexOf(itemId);
    // allow equip from inventory
    const slot = it.slot || 'weapon';
    const prev = m.equip[slot];
    if (invIdx >= 0) campaign.inventory.splice(invIdx, 1);
    else {
      // maybe already only on someone — simplify: must be in inventory
      return { ok: false, reason: 'inv' };
    }
    if (prev) campaign.inventory.push(prev);
    m.equip[slot] = itemId;
    const st = computeStats(m);
    m.hp = Math.min(st.maxHp, m.hp || st.maxHp);
    saveSave({ campaign });
    return { ok: true };
  }

  function advanceNode(campaign) {
    campaign.node = (campaign.node || 0) + 1;
    if (campaign.shopBuff && campaign.shopBuff.shopsLeft != null) {
      // consumed after leaving shop via explicit call
    }
    saveSave({ campaign });
  }

  function consumeShopBuff(campaign) {
    if (campaign.shopBuff) {
      campaign.shopBuff.shopsLeft = (campaign.shopBuff.shopsLeft || 1) - 1;
      if (campaign.shopBuff.shopsLeft <= 0) campaign.shopBuff = null;
    }
    campaign.node = (campaign.node || 0) + 1;
    saveSave({ campaign });
  }

  global.TECHQUEST = {
    STORAGE, loadSave, saveSave, defaultCampaign, migrateCampaign,
    makeMember, computeStats, canEquip, itemById, xpToLevel,
    createBattle, moveTiles, tryMove, basicAttack, useSkill, waitUnit,
    endPlayerTurn, enemyTurn, checkWin, applyVictory, living, livingInclAir,
    dist, pushLog, recruit, shopStock, buyItem, equipItem, advanceNode, consumeShopBuff,
    grantXpGold,
  };
})(typeof window !== 'undefined' ? window : globalThis);
