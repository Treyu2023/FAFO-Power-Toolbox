/**
 * Veeder-Root TLS phone-assist trees (TLS-250/300/350 keypad + TLS-400/450/PLUS touch).
 * Procedures aligned with Veeder-Root operator docs (veeder.com) and field TLS-3XX guides:
 *  - MODE / FUNCTION / STEP (3xx)
 *  - Menu > Diagnostics > PLLD > Manual Test > Start 3.0 (450PLUS)
 *  - Gross 3.0 gph line test to re-enable after PLLD / gross line shutdown
 */
window.PHONE_ASSIST_TLS = {
  id: 'tls',
  label: 'Veeder TLS',
  skin: 'tls',
  root: 'tls_pick',
  jumps: [
    { id: 't3_line_why', label: '3xx · Line test (re-enable site)' },
    { id: 't3_clear', label: '3xx · Clear / silence alarm' },
    { id: 't3_inv', label: '3xx · Inventory' },
    { id: 't4_line', label: '450 · Manual 3.0 line test' },
    { id: 't4_results', label: '450 · Watch 3.0 results in Diagnostics' },
    { id: 't4_confirm_enable', label: '450 · Confirm line re-enabled' },
    { id: 't4_favorites', label: '450 · Favorites (simplify next call)' },
    { id: 't4_clear', label: '450 · Clear alarm' },
    { id: 't4_inv', label: '450 · Tank overview' },
  ],
  nodes: {
    tls_pick: {
      title: 'Veeder-Root TLS — pick the console',
      hint: 'TLS-250/300/350 = MODE·FUNCTION·STEP keys. TLS-400/450/450PLUS = color touchscreen. Docs: veeder.com',
      say: 'Look at the tank gauge on the wall. Does it have buttons labeled MODE and FUNCTION, or a color touchscreen like a small computer?',
      tech: 'Family split:\n• TLS-250/300/350 (3xx) — keypad, MODE/FUNCTION/STEP/PRINT/ALARM-TEST\n• TLS-400/450/450PLUS/TLS4 — touch, Menu > Diagnostics > PLLD\nBiggest phone win: after GROSS LINE FAIL / PLLD SHUTDOWN, a passed manual 3.0 gph line test often re-enables product without a truck roll — when the line is actually OK.',
      items: [
        { n: '3xx', label: 'TLS-250 / 300 / 350 (MODE · FUNCTION · STEP)', go: 't3_home', say: 'Grey or light console with MODE, FUNCTION, STEP keys. Do not press anything yet.' },
        { n: '4xx', label: 'TLS-400 / 450 / 450PLUS (touchscreen)', go: 't4_home', say: 'Color touchscreen. Do not tap anything yet.' },
        { n: '?', label: 'Not sure — identify', go: 'tls_identify', say: 'Look for a sticker: TLS-350, TLS-300, TLS-450PLUS. Or tell me if you see MODE printed on a key.' },
      ],
    },
    tls_identify: {
      title: 'Identify model',
      hint: 'Bezel / door labels',
      say: 'Read any model number on the front or door. If none: do you see MODE and FUNCTION on physical buttons?',
      tech: '250 rare legacy but same 3xx key model. 450PLUS/TLS4i/TLS4c = touch path.',
      items: [
        { n: '→', label: 'MODE / FUNCTION keys', go: 't3_home', say: 'Using the 350-style button walkthrough.' },
        { n: '→', label: 'Color touchscreen', go: 't4_home', say: 'Using the 450PLUS touch walkthrough.' },
      ],
    },

    /* ─── TLS-3XX ─── */
    t3_home: {
      title: 'TLS-3xx (250 / 300 / 350)',
      hint: 'Keys: MODE · FUNCTION · STEP · TANK/SENSOR · PRINT · ENTER · CHANGE · ALARM/TEST',
      say: 'You are at the tank gauge button pad. We only press keys I name. What do we need: pumps dead after a line alarm, silence beeping, or read tank levels?',
      tech: 'Veeder TLS-3XX Operator / Quick Help (veeder.com):\nMODE cycles Operating / Setup / Diag…\nFUNCTION next function in mode\nSTEP next page\nALARM/TEST silence/ack\nPhone re-enable: manual 3.0 gph PLLD/WPLLD line test after gross line fail.',
      items: [
        { n: '1', label: '★ Line test — re-enable after line fail', go: 't3_line_why', say: 'We will run a short line leak test so the gauge can turn that product back on if the line is good.' },
        { n: '2', label: 'Silence / clear alarm beeping', go: 't3_clear', say: 'First we quiet the alarm so you can hear me.' },
        { n: '3', label: 'Read tank inventory', go: 't3_inv', say: 'Levels only — no programming.' },
        { n: '4', label: 'Print line / leak history', go: 't3_print_hist', say: 'We will print if the printer has paper.' },
        { n: '5', label: 'In-tank leak test (not line)', go: 't3_tank_test', say: 'Only if I asked for a tank test — different from a line test.' },
        { n: '⌨', label: 'Button cheat-sheet', go: 't3_keys', say: 'I will name the buttons before we start.' },
      ],
    },
    t3_keys: {
      title: '3xx keys',
      hint: 'Physical pad',
      say: 'Find MODE, FUNCTION, STEP, PRINT, and ALARM or ALARM/TEST. Finger near them — do not press until I say which one.',
      tech: 'Also ENTER, CHANGE, TANK/SENSOR. Never send store staff into SETUP MODE for programming.',
      items: [
        { n: '→', label: 'Ready — 3xx menu', go: 't3_home', say: 'Good.' },
      ],
    },
    t3_line_why: {
      title: 'Why run a line test?',
      hint: 'Gross line fail / PLLD shutdown holds product off until pass or repair',
      say: 'The tank gauge turned off a fuel line because a line-leak check failed or an alarm is holding it off. If the pipe is actually fine, a 3.0 gallon-per-hour line test can clear that and restore pumps — without waiting for a truck.',
      tech: 'Messages: GROSS LINE FAIL, GRS LINE TEST FAIL, PLLD SHUTDOWN ALARM, WPLLD SHUTDOWN, LINE LEAK SHUTDOWN.\nAuto gross test also runs after dispense when all handles off (Veeder PLLD notes).\nRepeated 3.0 fails → leak, PLLD/WPLLD hardware, check valve, pressure switch — dispatch.\nAll handles must be off during test.',
      items: [
        { n: '1', label: 'Safety prep first', go: 't3_line_prep', say: 'Before keys: no one fueling. All nozzles hung up.' },
        { n: '2', label: 'Prep done — start keys', go: 't3_line_op', say: 'All nozzles up. Hands only on the gauge.' },
      ],
    },
    t3_line_prep: {
      title: 'Prep forecourt',
      hint: 'No handle signals',
      say: 'Check the islands: every nozzle in its holster. Tell customers that grade may pause a few minutes. Say ready when every handle is down.',
      tech: 'Handle signal active 16h = HANDLE ALARM. Delivery in progress can block tests.',
      items: [
        { n: '✓', label: 'All handles down', go: 't3_line_op', say: 'Perfect.' },
      ],
    },
    t3_line_op: {
      title: '3xx · Operating Mode → start PLLD test',
      hint: 'Preferred: Operating Mode start PLLD / line leak test',
      say: 'Press MODE slowly several times until you are NOT in SETUP and NOT stuck only on DIAG — prefer normal tank readings or OPERATING MODE. Tell me the top line of the display.',
      tech: 'Operator path: Operating mode → Start PLLD Test → select line (STEP) → select 3.0 → continue/ENTER.\nIf missing: DIAG MODE path next.',
      items: [
        { n: '1', label: 'Normal / OPERATING screen', go: 't3_line_func', say: 'Press FUNCTION repeatedly until you see LINE LEAK, PLLD, START TEST, or PRESSURE LINE. Read both lines of the display to me.' },
        { n: '2', label: 'Only DIAG MODE', go: 't3_line_diag', say: 'OK — we use Diagnostic mode.' },
        { n: '3', label: 'SETUP MODE', go: 't3_leave_setup', say: 'Stop. Leave Setup — we are not programming.' },
      ],
    },
    t3_leave_setup: {
      title: 'Leave Setup',
      hint: 'No phone programming',
      say: 'Press MODE until SETUP is gone. We only want Operating or Diag.',
      tech: 'Setup = probe/line programming — on-site certified tech.',
      items: [
        { n: '→', label: 'Left Setup', go: 't3_line_op', say: 'Tell me the top line now.' },
      ],
    },
    t3_line_func: {
      title: '3xx · Start line / PLLD test screen',
      hint: 'FUNCTION to start test · STEP line · 3.0 · ENTER',
      say: 'When you see start line leak or PLLD test, use STEP to pick the product line that will not pump. Choose 3.0 if it asks 3.0 / 0.2 / 0.1. Press ENTER only when I say start.',
      tech: '3.0 gph = gross (re-enable). 0.2 = periodic. 0.1 = annual — avoid annual on casual phone calls.',
      items: [
        { n: '1', label: 'Starting 3.0 now', go: 't3_line_run', say: 'Press ENTER to start. No one fuel that product. Stay on the phone.' },
        { n: '2', label: 'Cannot find start — use DIAG', go: 't3_line_diag', say: 'We will use DIAG MODE.' },
      ],
    },
    t3_line_diag: {
      title: '3xx · DIAG → PRESSURE LINE LEAK',
      hint: 'MODE→DIAG · FUNCTION→PRESSURE LINE LEAK · STEP→3.0',
      say: 'Press MODE until it says DIAG MODE and PRESS FUNCTION TO CONTINUE. Then press FUNCTION many times until PRESSURE LINE LEAK. Read that out.',
      tech: 'Veeder gross/periodic troubleshooting:\n1 MODE → DIAG MODE\n2 FUNCTION → PRESSURE LINE LEAK / PRESSURE LINE LEAK DIAG\n3 STEP → 3.0 DIAG or start 3.0\n4 PRINT for last pass/fail\nAlso WPLLD LINE LEAK in same DIAG list when wireless PLLD installed.',
      items: [
        { n: '1', label: 'PRESSURE LINE LEAK showing', go: 't3_line_diag2', say: 'Press STEP until 3.0 or Start. Tell me each new line if unsure.' },
        { n: '2', label: 'WPLLD LINE LEAK showing', go: 't3_line_diag2', say: 'Same — STEP to 3.0 or manual start.' },
        { n: '3', label: 'Only LINE LEAK DIAG DATA', go: 't3_line_diag_data', say: 'That is history. One more FUNCTION or use Operating start path.' },
      ],
    },
    t3_line_diag2: {
      title: '3xx · Select line & start 3.0',
      hint: 'STEP/TANK · start 3.0 gph',
      say: 'STEP or TANK/SENSOR until the failed grade is selected. Start the 3.0 test with ENTER. Wait with me — minutes, not seconds. No authorize on that product.',
      tech: 'STP may run to pressurize. Pass often clears shutdown. Fail → do not spam retests.',
      items: [
        { n: '✓', label: 'Finished — PASS', go: 't3_line_pass', say: 'Read every word of the result.' },
        { n: '✗', label: 'Finished — FAIL', go: 't3_line_fail', say: 'Read the fail message. Do not restart yet.' },
        { n: '…', label: 'Still running', go: 't3_line_run', say: 'Stay put. Tell me if it beeps.' },
      ],
    },
    t3_line_diag_data: {
      title: '3xx · Diag data / PRINT history',
      hint: 'PRINT last pass/fail',
      say: 'Press PRINT for a paper history if needed, or FUNCTION until Start test appears.',
      tech: 'DIAG → PRESSURE LINE LEAK DIAG → STEP 3.0 DIAG → PRINT.',
      items: [
        { n: '→', label: 'Start a test', go: 't3_line_op', say: 'Back to starting a test.' },
        { n: '⌂', label: '3xx home', go: 't3_home', say: 'MODE toward normal tanks when done.' },
      ],
    },
    t3_line_run: {
      title: '3xx · Test running',
      hint: 'Handles off',
      say: 'Leave every nozzle hung up. When the screen changes, read the top two lines word for word.',
      tech: 'LLD PRESSURE WARN/ALARM = pressure switch never opened — hardware, not more phone tests.',
      items: [
        { n: '✓', label: 'PASS', go: 't3_line_pass', say: 'Result pass.' },
        { n: '✗', label: 'FAIL', go: 't3_line_fail', say: 'Result fail.' },
      ],
    },
    t3_line_pass: {
      title: '3xx · PASS — check pumps',
      hint: 'Ack alarm · authorize grade',
      say: 'Press ALARM/TEST once or twice if still beeping. Then try one quiet pump on that grade. Does it pump?',
      tech: 'If still down: other disable alarm, FUEL OUT, DIM, etc.',
      items: [
        { n: '✓', label: 'Pumps work — done', go: 't3_home', say: 'You fixed it without a service call. Thank you.' },
        { n: '✗', label: 'Still no pump', go: 't3_still_down', say: 'Stop testing. Alarm list next.' },
      ],
    },
    t3_line_fail: {
      title: '3xx · FAIL — stop',
      hint: 'Dispatch path',
      say: 'Do not keep running tests. Leave nozzles down. Read any GROSS, PER, or PRESSURE words. A tech needs to look at the line or detector.',
      tech: 'Gross fail with possible real leak — shear, fitting, PLLD. Print if possible.',
      items: [
        { n: '1', label: 'Try PRINT for tech', go: 't3_print_hist', say: 'PRINT if the screen allows — keep the paper.' },
        { n: '⌂', label: '3xx home', go: 't3_home', say: 'MODE back to normal readings.' },
      ],
    },
    t3_still_down: {
      title: 'Still down after PASS',
      hint: 'Other alarms',
      say: 'ALARM/TEST to silence. MODE to normal. Read any remaining alarm text slowly.',
      tech: 'FUEL OUT, SENSOR OUT, COMM, LOW PRESSURE may still block.',
      items: [
        { n: '→', label: 'Work alarms', go: 't3_clear', say: 'Alarm steps next.' },
      ],
    },
    t3_clear: {
      title: '3xx · ALARM/TEST silence',
      hint: 'Acknowledge beeper',
      say: 'Press ALARM or ALARM/TEST once. If it still beeps, press again. Read the alarm name if still visible.',
      tech: 'Ack ≠ clear shutdown. Line disable needs pass or root cause cleared.',
      items: [
        { n: '1', label: 'Need line test', go: 't3_line_why', say: 'Line test next.' },
        { n: '⌂', label: '3xx home', go: 't3_home', say: 'Alarm quiet.' },
      ],
    },
    t3_inv: {
      title: '3xx · Inventory',
      hint: 'Operating · STEP / TANK',
      say: 'MODE to normal tank screen. STEP or TANK/SENSOR each tank. Read name, volume or inches, water if shown.',
      tech: 'Quick phone inventory.',
      items: [
        { n: '⌂', label: '3xx home', go: 't3_home', say: 'Done.' },
      ],
    },
    t3_print_hist: {
      title: '3xx · Print history',
      hint: 'DIAG · Pressure Line Leak · PRINT',
      say: 'MODE to DIAG MODE, FUNCTION to PRESSURE LINE LEAK or LINE LEAK DIAG, STEP to history or 3.0 diag, then PRINT. Printer paper loaded and door closed.',
      tech: 'Also leak history / 0.20 / 0.10 report prints in DIAG.',
      items: [
        { n: '⌂', label: '3xx home', go: 't3_home', say: 'Keep the printout.' },
      ],
    },
    t3_tank_test: {
      title: '3xx · In-tank test (not line)',
      hint: 'IN-TANK LEAK / CSLD',
      say: 'Only if I asked for a tank leak test. Quiet period required — no pumping that product.',
      tech: 'Different menus from PRESSURE LINE LEAK.',
      items: [
        { n: '⌂', label: '3xx home', go: 't3_home', say: 'Cancel if unsure.' },
      ],
    },

    /* ─── TLS-4xx / 450 ─── */
    t4_home: {
      title: 'TLS-400 / 450 / 450PLUS',
      hint: 'Touch: Home · Menu · Favorites · Alarm bar · Actions',
      say: 'Color touchscreen. Gentle finger taps. Do you see Home, Menu, Favorites, or tank boxes?',
      tech: 'veeder.com TLS-450PLUS operator tips:\n• Favorites = one-tap later (set after first successful path)\n• Line test: Menu > Diagnostics > PLLD > Manual Test > Actions > Start 3.0\n• Results: Menu > Diagnostics > PLLD > 3.0 gph Tests (last pass/fail per line)\n• Re-enable check: ack Alarm ×2, confirm line not in shutdown, try quiet pump\n• Alarm bar twice to ack',
      items: [
        { n: '1', label: '★ Full path: 3.0 test → results → confirm re-enabled', go: 't4_line', say: 'We will start a 3.0 line test, then look at Diagnostics results, then confirm the line is back on.' },
        { n: '1b', label: 'Already ran test — go to results only', go: 't4_results', say: 'We will open Diagnostics and watch the 3.0 results for that line.' },
        { n: '1c', label: 'Open from Favorites (if already set up)', go: 't4_fav_use', say: 'Look for Favorites on the home screen — we may jump straight to the line-test screens.' },
        { n: '2', label: 'Silence alarm banner', go: 't4_clear', say: 'Quiet the red or orange alarm first.' },
        { n: '3', label: 'Tank overview / levels', go: 't4_inv', say: 'Look at levels only.' },
        { n: '4', label: 'Reports / alarm history', go: 't4_reports', say: 'Reports only — no Setup changes.' },
        { n: '5', label: 'Set Favorites for next time', go: 't4_favorites', say: 'We will bookmark the screens so the next call is easier.' },
        { n: '6', label: 'Static tank test (SLD)', go: 't4_sld', say: 'Only if I asked for a tank test.' },
      ],
    },
    t4_fav_use: {
      title: '450 · Use Favorites (shortcut)',
      hint: 'Home → Favorites → saved PLLD / Manual Test / 3.0 Tests',
      say: 'On the Home screen, tap Favorites (or the star / heart style icon if that is how it is labeled). Look for names like PLLD, Manual Test, or 3.0 Tests. Tap the one I name.',
      tech: 'Favorites are per-user on 450PLUS — simplify phone assist after first successful walkthrough. If empty, set them at end of this call (t4_favorites).',
      items: [
        { n: '1', label: 'Open Manual Test from Favorites', go: 't4_line3', say: 'You should be on Manual Test — we can start 3.0 from Actions.' },
        { n: '2', label: 'Open 3.0 gph Tests (results) from Favorites', go: 't4_results_view', say: 'You should see recent pass and fail history for each line.' },
        { n: '3', label: 'No Favorites set yet', go: 't4_line', say: 'No problem — we will use Menu this time, then save Favorites at the end.' },
      ],
    },
    t4_line: {
      title: '450 · Step 1 · Menu → Diagnostics → PLLD',
      hint: 'Manual Test · Actions · Start 3.0  (or open via Favorites)',
      say: 'Every nozzle hung up first. Then either: tap Favorites if you already saved Manual Test — or tap Menu. Tell me which you used.',
      tech: 'Path: Menu > Diagnostics > PLLD > PLLD Manual Test\nActions > Start 3.0 Test\nAfter test finishes → must open Menu > Diagnostics > PLLD > 3.0 gph Tests to confirm result history and line status — do not stop at “it said pass” alone.',
      items: [
        { n: '1', label: 'Menu open', go: 't4_line2', say: 'Tap Diagnostics. Scroll if needed and read names if you cannot find it.' },
        { n: '1b', label: 'Opened Manual Test from Favorites', go: 't4_line3', say: 'Perfect — find Actions for Start 3.0.' },
        { n: '2', label: 'Handles still up', go: 't4_prep', say: 'Hang all nozzles first.' },
      ],
    },
    t4_prep: {
      title: '450 · Hang nozzles',
      hint: 'No handle signal',
      say: 'Holster every nozzle. Say ready when the forecourt is quiet.',
      tech: 'Same as 3xx.',
      items: [
        { n: '✓', label: 'Ready', go: 't4_line', say: 'Back to Menu or Favorites.' },
      ],
    },
    t4_line2: {
      title: '450 · Diagnostics → PLLD → Manual Test',
      hint: 'PLLD · Manual Test',
      say: 'In Diagnostics tap PLLD or Line Leak. Then Manual Test if shown. Stay in Diagnostics after the test — we will read results next.',
      tech: 'DPLLD / WPLLD naming varies by installed option.',
      items: [
        { n: '1', label: 'Manual Test screen open', go: 't4_line3', say: 'Find Actions on the screen.' },
        { n: '2', label: 'See 0.2 or Mid-Range only', go: 't4_line3', say: 'We want Start 3.0 / Gross — not 0.2 unless I say.' },
      ],
    },
    t4_line3: {
      title: '450 · Step 2 · Actions → Start 3.0',
      hint: 'Pick line · Start 3.0 Test · then go to results',
      say: 'Tap Actions, then Start 3.0 Test. Pick the grade that will not pump if asked. Confirm. Wait — do not fuel. When it finishes, do not leave yet — say “done” and we will open the results screen in Diagnostics.',
      tech: 'After completion: Menu > Diagnostics > PLLD > 3.0 gph Tests shows five most recent passes and fails per line (Veeder gross line failure support article).',
      items: [
        { n: '…', label: 'Still running', go: 't4_line_wait', say: 'Stay on this screen with me.' },
        { n: '→', label: 'Test finished (Pass or Fail showing)', go: 't4_results', say: 'Do not hang up. We will open Diagnostics results for that line.' },
      ],
    },
    t4_line_wait: {
      title: '450 · Test running',
      hint: 'No dispense · then results',
      say: 'Leave the screen alone. When status changes to finished, say “done” — next we open results, not the pump yet.',
      tech: 'Several minutes typical.',
      items: [
        { n: '→', label: 'Finished — open results', go: 't4_results', say: 'Opening Diagnostics results next.' },
      ],
    },
    t4_results: {
      title: '450 · Step 3 · Watch results in Diagnostics',
      hint: 'Menu > Diagnostics > PLLD > 3.0 gph Tests',
      say: 'Tap Menu, then Diagnostics, then PLLD again. Now open 3.0 gph Tests or 3.0 Tests — not Manual Test this time. This screen shows recent passes and fails for each line.',
      tech: 'Veeder: Menu > Diagnostics > PLLD > 3.0 gph Tests\nShows five most recent passes and five most recent fails per line.\nAlso useful: Mid-Range Tests, 0.2 GPH TESTS for periodic fails.\nConfirm the line you tested shows a new PASS with today’s time.',
      items: [
        { n: '1', label: 'I am on 3.0 gph Tests screen', go: 't4_results_view', say: 'Find the product line we tested — regular, plus, diesel — and read the newest result.' },
        { n: '1b', label: 'Opened 3.0 Tests from Favorites', go: 't4_results_view', say: 'Same — read the newest result for that line.' },
        { n: '2', label: 'Cannot find 3.0 gph Tests', go: 't4_results_find', say: 'Stay in Diagnostics → PLLD. Read me every item name on that list.' },
      ],
    },
    t4_results_find: {
      title: '450 · Find 3.0 gph Tests under PLLD',
      hint: 'Manual Test vs 3.0 gph Tests vs Mid-Range vs 0.2',
      say: 'Under PLLD you may see Manual Test, 3.0 gph Tests, Mid-Range Tests, and 0.2 GPH Tests. We want 3.0 gph Tests for the result history. Tap that.',
      tech: 'Manual Test = run test. 3.0 gph Tests = history/results. Do not confuse them on the phone.',
      items: [
        { n: '→', label: 'Found 3.0 gph Tests', go: 't4_results_view', say: 'Open it and find our line.' },
      ],
    },
    t4_results_view: {
      title: '450 · Read the result for that line',
      hint: 'Newest PASS/FAIL · timestamp · line label',
      say: 'Scroll to the line we tested. Read the newest entry: does it say PASS or FAIL, and does the time look like just now? Read any other red or fail rows above it too.',
      tech: 'Confirm new PASS logged. If still FAIL at top, line not re-enabled by this attempt. Historic fails can remain below a new pass — that is OK if newest is PASS.',
      items: [
        { n: '✓', label: 'Newest result is PASS', go: 't4_confirm_enable', say: 'Good — next we confirm the line is actually allowed to pump again.' },
        { n: '✗', label: 'Newest result is FAIL', go: 't4_line_fail', say: 'Stop retesting. We will note the fail for dispatch.' },
        { n: '?', label: 'Not sure which row is newest', go: 't4_results_view', say: 'Look at the date and time column — the top or most recent time. Read the first two rows slowly.' },
      ],
    },
    t4_confirm_enable: {
      title: '450 · Step 4 · Confirm line re-enabled',
      hint: 'Ack alarms · no PLLD shutdown · try quiet pump',
      say: 'Three quick checks. First: tap the Alarm bar at the top twice if anything is still red or beeping. Second: look at Home or the line/pump status — tell me if you still see Shutdown, Disabled, or PLLD shutdown for that grade. Third: at a quiet pump, try that grade only. Does it authorize and pump?',
      tech: 'Re-enable confirmation checklist:\n1) Alarm status bar ×2 (ack)\n2) No active PLLD SHUTDOWN / gross line fail on that line\n3) Physical authorize on a nozzle\nIf PASS in 3.0 Tests but still shutdown → other alarm or programming; do not loop tests.\nAfter success: set Favorites so next call skips hunting menus.',
      items: [
        { n: '✓', label: 'Pumps work — line re-enabled', go: 't4_success_fav', say: 'Excellent. Before we hang up, we will save Favorites so this is faster next time.' },
        { n: '✗', label: 'Still shutdown / will not pump', go: 't4_still_down', say: 'Stop. Read any remaining alarm text on Home or the alarm list.' },
        { n: '!', label: 'PASS on screen but alarm still shows shutdown', go: 't4_still_down', say: 'Read the exact alarm words — do not start another test yet.' },
      ],
    },
    t4_still_down: {
      title: '450 · Still not enabled',
      hint: 'Other alarms · do not spam 3.0',
      say: 'Open the Alarm list or banner and read every active alarm name. Do not run another line test until I say. We may need a technician if something else is holding the line off.',
      tech: 'FUEL OUT, sensor, comm, low pressure, handle, or secondary disable. Capture 3.0 Tests screenshot + alarm list.',
      items: [
        { n: '1', label: 'Review alarm banner again', go: 't4_clear', say: 'Alarm steps.' },
        { n: '⌂', label: '450 home', go: 't4_home', say: 'Home — stay available for dispatch questions.' },
      ],
    },
    t4_success_fav: {
      title: '450 · Success — save Favorites now',
      hint: 'Bookmark Manual Test + 3.0 gph Tests for next phone call',
      say: 'Pumps are working. Please stay one more minute so we bookmark two screens for next time — it will take about thirty seconds.',
      tech: 'Favorites make phone assist reliable for non-techs. Save both run path and results path.',
      items: [
        { n: '1', label: 'Set up Favorites', go: 't4_favorites', say: 'We will add Manual Test and 3.0 gph Tests to Favorites.' },
        { n: '2', label: 'Skip Favorites — done', go: 't4_home', say: 'OK — you are done. Thank you.' },
      ],
    },
    t4_favorites: {
      title: '450 · Favorites (simplify next call)',
      hint: 'Add PLLD Manual Test + 3.0 gph Tests (+ optional Home diagnostics)',
      say: 'We will save shortcuts. First open Menu → Diagnostics → PLLD → Manual Test so that screen is showing. Tell me when Manual Test is on the screen.',
      tech: 'TLS-450PLUS: customize with Favorites for common screens (Veeder product/operator tips).\nRecommend favorites:\n1) Diagnostics > PLLD > Manual Test\n2) Diagnostics > PLLD > 3.0 gph Tests\nOptional: Alarm history, Tank overview\nExact “Add to Favorites” control varies by software — often star icon, Favorites button, or Actions → Add to Favorites while screen is open. If store cannot find it, describe icons at top of screen.',
      items: [
        { n: '1', label: 'Manual Test is on screen', go: 't4_fav_add1', say: 'Look for a star, heart, or Favorites control — or Actions → Add to Favorites. Tap to save this screen. Tell me when it says saved or the star fills in.' },
        { n: '2', label: 'How do I open Favorites later?', go: 't4_fav_use', say: 'From Home, Favorites lists what we save — we will practice after adding.' },
      ],
    },
    t4_fav_add1: {
      title: '450 · Favorite #1 saved · add results',
      hint: 'Next: 3.0 gph Tests screen → Add to Favorites',
      say: 'Good. Now go to Menu → Diagnostics → PLLD → 3.0 gph Tests so the results history is on the screen. Save that one to Favorites the same way.',
      tech: 'Two favorites cover the full re-enable phone path: run test + verify results.',
      items: [
        { n: '1', label: '3.0 gph Tests favorited', go: 't4_fav_done', say: 'Perfect. From now on: Home → Favorites → pick Manual Test or 3.0 Tests when I ask.' },
        { n: '2', label: 'Cannot find Add to Favorites', go: 't4_fav_help', say: 'Describe the icons at the top of the screen — star, pin, folder, or Favorites word.' },
      ],
    },
    t4_fav_help: {
      title: '450 · Find Add to Favorites',
      hint: 'Star / Actions / long-press — software dependent',
      say: 'Try: tap Actions and look for Add to Favorites or Bookmark. Or tap a star icon on the top bar. Or open Home → Favorites → edit/add. Tell me what words you see.',
      tech: 'If Favorites cannot be set remotely, document path on SITE-INFO and retry on next visit. Do not spend 20 minutes on UI hunting during outage.',
      items: [
        { n: '✓', label: 'Got it — saved both', go: 't4_fav_done', say: 'Great.' },
        { n: '⌂', label: 'Skip — finish call', go: 't4_home', say: 'We will set Favorites on the next on-site visit.' },
      ],
    },
    t4_fav_done: {
      title: '450 · Favorites ready',
      hint: 'Next call: Home → Favorites',
      say: 'You are set. Next time a line shuts down: open Favorites, Manual Test, run 3.0, then Favorites again to 3.0 gph Tests to confirm PASS, then try a pump. Thank you — you saved a trip.',
      tech: 'Note in SITE-INFO: Favorites configured for PLLD Manual Test + 3.0 gph Tests.',
      items: [
        { n: '⌂', label: '450 home', go: 't4_home', say: 'You can go back to Home.' },
      ],
    },
    t4_line_fail: {
      title: '450 · FAIL on results',
      hint: 'No retest loop · capture Diagnostics result',
      say: 'Stop testing. On the 3.0 gph Tests screen, leave that FAIL showing if you can, or take a photo. Nozzles down. We will send a technician — do not keep starting tests.',
      tech: 'Dispatch with line #, newest FAIL from Diagnostics > PLLD > 3.0 gph Tests, alarm list.',
      items: [
        { n: '1', label: 'Still on results — read FAIL line again', go: 't4_results_view', say: 'Read the fail row one more time for my notes.' },
        { n: '⌂', label: '450 home', go: 't4_home', say: 'Home — stay available for dispatch.' },
      ],
    },
    t4_clear: {
      title: '450 · Ack alarm',
      hint: 'Alarm bar ×2',
      say: 'Tap the alarm banner twice to stop the beep. Read the alarm name if still visible.',
      tech: 'Ack ≠ fix line disable. Still confirm via Diagnostics 3.0 results + pump test.',
      items: [
        { n: '1', label: 'Need full line re-enable path', go: 't4_line', say: '3.0 test, then results, then confirm pumps.' },
        { n: '2', label: 'Go confirm line status only', go: 't4_confirm_enable', say: 'We already have a PASS — confirm pumps.' },
        { n: '⌂', label: '450 home', go: 't4_home', say: 'Quiet.' },
      ],
    },
    t4_inv: {
      title: '450 · Tank overview',
      hint: 'Home / tank tiles',
      say: 'Tap Home if lost. Tap each tank; read volume, product, water.',
      tech: 'Tank Detail per operator tips.',
      items: [
        { n: '⌂', label: '450 home', go: 't4_home', say: 'Done.' },
      ],
    },
    t4_reports: {
      title: '450 · Reports',
      hint: 'Menu → Reports',
      say: 'Menu, then Reports or Environmental reports. Do not change setup or dates unless I ask.',
      tech: 'Compliance / combined tank test report. Line history better under Diagnostics > PLLD > 3.0 gph Tests.',
      items: [
        { n: '1', label: 'Need line test results instead', go: 't4_results', say: 'Diagnostics PLLD 3.0 Tests is better for line pass/fail.' },
        { n: '⌂', label: '450 home', go: 't4_home', say: 'Home.' },
      ],
    },
    t4_sld: {
      title: '450 · SLD tank test',
      hint: 'Not line test',
      say: 'Only for tank static test. Menu path for SLD / in-tank test. Stop if that product is pumping.',
      tech: 'veeder.com Starting an SLD Test tip. Separate from PLLD line re-enable.',
      items: [
        { n: '⌂', label: '450 home', go: 't4_home', say: 'Cancel if unsure.' },
      ],
    },
  },
};
