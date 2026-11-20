"""Extra QA checks: exhaustive placement rules, turn guards, AI legality,
hit/miss/sunk bookkeeping, full win and loss games, restart, phones, console errors.
Run with the game served at http://localhost:8080/ (see README)."""
import glob, os, time
from playwright.sync_api import sync_playwright

CHROME = os.environ.get('CHROME_PATH') or (sorted(glob.glob('/opt/.devin/chrome/chrome/linux-*/chrome-linux64/chrome')) or [None])[-1]
URL = os.environ.get('GAME_URL', 'http://localhost:8080/')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'screenshots') + '/'
os.makedirs(OUT, exist_ok=True)
fails, errors = [], []


def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond:
        fails.append(msg)


def watch(page):
    page.on('pageerror', lambda e: errors.append(f'{page.url}: {e}'))
    page.on('console', lambda m: errors.append(f'{page.url}: {m.text}') if m.type == 'error' else None)
    return page


def wait_for(page, js, timeout=15):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if page.evaluate(js):
            return True
        time.sleep(0.05)
    return False


PLAYER_TURN = "(()=>{const s=window.__battleship.state;return s.phase!=='battle'||(s.turn==='player'&&!s.busy)})()"


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME, headless=True) if CHROME else p.chromium.launch(headless=True)

    # ---------- 1. Placement: every ship, both directions, every square ----------
    pg = watch(b.new_page(viewport={'width': 1024, 'height': 768}))
    pg.goto(URL)
    res = pg.evaluate('''() => {
      const B = window.__battleship, S = B.state, F = B.FLEET, N = B.SIZE;
      const cell = (r, c) => document.querySelector(`#player-board .cell[data-r="${r}"][data-c="${c}"]`);
      const out = { boundaryBad: [], tried: 0 };
      F.forEach((def, i) => ['h', 'v'].forEach(dir => {
        for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) {
          document.getElementById('clear-btn').click();
          document.querySelector(`#ship-list .ship-btn[data-index="${i}"]`).click();
          document.querySelector(`#dir-seg button[data-dir="${dir}"]`).click();
          cell(r, c).click(); out.tried++;
          const ships = S.player.ships;
          const ok = ships.length === 1 && ships[0].name === def.name && ships[0].dir === dir &&
            ships[0].cells.length === def.size &&
            ships[0].cells.every(([a, b]) => a >= 0 && a < N && b >= 0 && b < N) &&
            ships[0].cells.some(([a, b]) => a === r && b === c) &&
            ships[0].cells.every(([a, b], k) => dir === 'h' ? (a === r && b === ships[0].cells[0][1] + k) : (b === c && a === ships[0].cells[0][0] + k));
          if (!ok) out.boundaryBad.push([def.name, dir, r, c, JSON.stringify(ships.map(s => s.cells))]);
        }
      }));
      return out;
    }''')
    check(res['tried'] == 1000 and not res['boundaryBad'],
          f"Each ship placed at all 100 squares in both directions stays on the board and covers the tapped square ({res['tried']} placements, problems: {res['boundaryBad'][:3]})")

    res = pg.evaluate('''() => {
      const B = window.__battleship, S = B.state, F = B.FLEET, N = B.SIZE;
      const cell = (r, c) => document.querySelector(`#player-board .cell[data-r="${r}"][data-c="${c}"]`);
      const out = { overlapAccepted: 0, validRejected: 0, overlapTried: 0, validTried: 0, rounds: 0 };
      for (let round = 0; round < 6; round++) {
        document.getElementById('random-btn').click();
        const idx = round % F.length, def = F[idx];
        document.querySelector(`#ship-list .ship-btn[data-index="${idx}"]`).click();      // pick that ship up
        const others = JSON.stringify(S.player.ships.map(s => s.cells));
        const occupied = new Set(S.player.ships.flatMap(s => s.cells.map(([r, c]) => r * N + c)));
        for (const dir of ['h', 'v']) for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) {
          if (occupied.has(r * N + c)) continue;              // tapping a ship picks it up (by design)
          document.querySelector(`#dir-seg button[data-dir="${dir}"]`).click();
          let rr = r, cc = c;
          if (dir === 'h') cc = Math.min(c, N - def.size); else rr = Math.min(r, N - def.size);
          const want = Array.from({ length: def.size }, (_, k) => dir === 'h' ? [rr, cc + k] : [rr + k, cc]);
          const overlaps = want.some(([a, b]) => occupied.has(a * N + b));
          cell(r, c).click();
          const placed = S.player.ships.length === 5;
          if (overlaps) { out.overlapTried++; if (placed) out.overlapAccepted++; }
          else { out.validTried++; if (!placed) out.validRejected++; }
          if (JSON.stringify(S.player.ships.filter(s => s.name !== def.name).map(s => s.cells)) !== others) out.overlapAccepted += 1000;
          if (placed) document.querySelector(`#ship-list .ship-btn[data-index="${idx}"]`).click();
        }
        out.rounds++;
      }
      return out;
    }''')
    check(res['overlapTried'] > 50 and res['overlapAccepted'] == 0,
          f"Overlapping placements always rejected and other ships untouched ({res['overlapTried']} tried)")
    check(res['validRejected'] == 0, f"Every non-overlapping placement accepted ({res['validTried']} tried)")

    res = pg.evaluate('''() => {
      const B = window.__battleship; const out = {};
      const s = B.newSide(); B.placeFleetRandomly(s);
      const before = JSON.stringify(s);
      out.oob = [[-1,0],[0,-1],[10,0],[0,10],[10,10],[-5,99]].map(([r,c]) => B.fireAt(s, r, c));
      out.unchanged = JSON.stringify(s) === before;
      document.getElementById('clear-btn').click();
      for (const el of document.querySelectorAll('#player-board .corner, #player-board .cols span, #player-board .rows span, #player-board .cells')) el.click();
      out.labelClicksPlaced = B.state.player.ships.length;
      document.getElementById('start-btn').click();
      out.startBlocked = B.state.phase;
      return out;
    }''')
    check(all(x is None for x in res['oob']) and res['unchanged'], 'Shots outside the 10x10 grid are rejected and change nothing')
    check(res['labelClicksPlaced'] == 0, 'Clicking row/column labels or grid gaps places nothing')
    check(res['startBlocked'] == 'setup', 'Start battle does nothing with an empty board')

    # ---------- 2. Computer opponent: every shot legal and new ----------
    res = pg.evaluate('''() => {
      const B = window.__battleship, out = {};
      for (const skill of ['beginner', 'intermediate', 'advanced']) {
        let illegal = 0, repeats = 0, games = 400, longest = 0;
        for (let g = 0; g < games; g++) {
          const side = B.newSide(); B.placeFleetRandomly(side);
          let n = 0;
          while (!B.allSunk(side) && n <= 100) {
            const t = B.computerChooseShot(side, skill);
            if (!Array.isArray(t) || !Number.isInteger(t[0]) || !Number.isInteger(t[1]) || t[0] < 0 || t[0] > 9 || t[1] < 0 || t[1] > 9) { illegal++; break; }
            if (side.shots[t[0]][t[1]]) { repeats++; break; }
            B.fireAt(side, t[0], t[1]); n++;
          }
          if (!B.allSunk(side)) illegal++;
          longest = Math.max(longest, n);
        }
        out[skill] = { illegal, repeats, longest };
      }
      // Full board: no squares left -> no shot offered
      const full = B.newSide(); full.shots = full.shots.map(row => row.map(() => 'miss'));
      out.fullBoard = B.computerChooseShot(full, 'advanced');
      return out;
    }''')
    for k in ('beginner', 'intermediate', 'advanced'):
        r = res[k]
        check(r['illegal'] == 0 and r['repeats'] == 0 and r['longest'] <= 100,
              f"{k}: 400 games, every computer shot on the board and never repeated, always finishes ({r})")
    check(res['fullBoard'] is None, 'Computer offers no shot when every square has been fired at')
    pg.close()

    # ---------- 3. Full games in the browser (reduced motion keeps them fast) ----------
    ctx = b.new_context(viewport={'width': 1024, 'height': 768}, reduced_motion='reduce')
    g = watch(ctx.new_page())
    g.goto(URL)
    g.click('#random-btn')
    g.click('#skill-seg button[data-skill="advanced"]')
    g.click('#start-btn')
    ecell = lambda r, c: g.locator(f'#enemy-board .cell[data-r="{r}"][data-c="{c}"]')
    S = g.evaluate

    # Turn guards
    g.evaluate('window.__clicked = 0')
    water = S('''(() => { const s = window.__battleship.state.enemy, out = [];
      for (let r = 0; r < 10; r++) for (let c = 0; c < 10; c++) if (!s.ships.some(x => x.cells.some(([a,b]) => a===r && b===c))) out.push([r,c]);
      return out; })()''')
    ecell(*water[0]).dblclick()
    ecell(*water[1]).click()
    check(S('window.__battleship.state.stats.playerShots') <= 1, 'Double-click and a quick second click fire only one missile')
    wait_for(g, "window.__battleship.state.turn==='computer'")
    ecell(*water[2]).click()
    check(S('window.__battleship.state.enemy.shots[%d][%d]' % tuple(water[2])) is None, 'Clicking enemy waters during the computer turn does nothing')
    wait_for(g, PLAYER_TURN)
    check(S('window.__battleship.state.stats') == {'playerShots': 1, 'playerHits': 0, 'computerShots': 1, 'computerHits': S('window.__battleship.state.stats.computerHits')},
          'One shot each after the first round')
    g.locator(f'#player-board .cell[data-r="0"][data-c="0"]').click()
    check(S('window.__battleship.state.player.shots[0][0]') in (None, 'hit', 'miss') and S('window.__battleship.state.turn') == 'player'
          and S('window.__battleship.state.stats.playerShots') == 1, 'Clicking your own board during battle does nothing')
    ecell(*water[0]).click()
    time.sleep(0.8)
    check(S('window.__battleship.state.turn') == 'player' and S('window.__battleship.state.stats.computerShots') == 1,
          'Re-clicking a square you already fired at keeps your turn and does not trigger the computer')
    ecell(*water[0]).focus(); g.keyboard.press('Enter'); time.sleep(0.5)
    check(S('window.__battleship.state.stats.playerShots') == 1, 'Pressing Enter on an already-fired square is ignored')

    # Win: fire at every enemy ship square, checking hit/sunk bookkeeping each shot
    ships = S('window.__battleship.state.enemy.ships.map(s => ({name: s.name, cells: s.cells}))')
    bad, early_end = [], False
    sunk_so_far = 0
    for si, ship in enumerate(ships):
        for ci, (r, c) in enumerate(ship['cells']):
            if S('window.__battleship.state.phase') == 'over':
                early_end = True
            ecell(r, c).click()
            wait_for(g, f"window.__battleship.state.enemy.shots[{r}][{c}] !== null")
            last = ci == len(ship['cells']) - 1
            want = 'sunk' if last else 'hit'
            got = S(f'window.__battleship.state.lastShot.enemy')
            text = g.inner_text('#last-action')
            if last:
                sunk_so_far += 1
                wait_for(g, f"document.querySelectorAll('#enemy-fleet .chip.sunk').length === {sunk_so_far} || window.__battleship.state.phase === 'over'")
                if f"sank the enemy {ship['name']}" not in text: bad.append(('sunk text', ship['name'], text))
                cells_sunk = all('sunk' in ecell(a, b2).get_attribute('class') for a, b2 in ship['cells'])
                if not cells_sunk: bad.append(('sunk cells', ship['name']))
            else:
                if 'Hit' not in text: bad.append(('hit text', ship['name'], text))
                if 'hit' not in ecell(r, c).get_attribute('class'): bad.append(('hit class', ship['name'], r, c))
            if got != [r, c]: bad.append(('lastShot', got, [r, c]))
            if not (si == len(ships) - 1 and last):
                if not wait_for(g, PLAYER_TURN, 20): bad.append(('turn stuck', r, c))
    check(not bad, f'Every hit and every sinking reported correctly on the board, fleet list and message bar ({bad[:3]})')
    check(not early_end, 'Game did not end before the last enemy ship was sunk')
    wait_for(g, "!document.getElementById('modal').classList.contains('hidden')", 5)
    st = S('window.__battleship.state')
    check(st['phase'] == 'over' and g.inner_text('#modal-title').lower() == 'victory!', 'Victory declared after exactly 17 hits')
    check(st['stats']['playerShots'] == 18 and st['stats']['playerHits'] == 17, f"Victory stats correct ({st['stats']})")
    check(st['stats']['playerShots'] == st['stats']['computerShots'] + 1, 'Computer does not fire after you win')
    stats_text = g.inner_text('#modal-stats')
    check('18' in stats_text and '17' in stats_text and '94%' in stats_text and '5/5' in stats_text, f'Victory screen shows shots, hits, accuracy and ships sunk')
    played = S('window.__battleship.state.player.shots.flat().filter(Boolean).length')
    check(played == st['stats']['computerShots'], f'Computer shot count matches marks on your board ({played})')
    g.screenshot(path=OUT + 'qa_victory.png')

    # Restart resets everything
    g.click('#play-again-btn')
    st = S('''(() => { const s = window.__battleship.state; return {
      phase: s.phase, turn: s.turn, busy: s.busy, aim: s.aim, sinking: s.sinking, selected: s.selected,
      pships: s.player.ships.length, eships: s.enemy.ships.length,
      shots: s.player.shots.flat().concat(s.enemy.shots.flat()).filter(Boolean).length,
      stats: s.stats, last: s.lastShot, skill: s.skill,
      marks: document.querySelectorAll('.board:not(#demo-board) .cell.hit, .board:not(#demo-board) .cell.miss, .board:not(#demo-board) .cell.sunk').length,
      shipEls: document.querySelectorAll('#player-board .ship-el:not(.ghost), #enemy-board .ship-el').length,
      chips: [...document.querySelectorAll('#player-fleet .chip, #enemy-fleet .chip')].filter(c => c.offsetParent).length,
      modal: document.getElementById('modal').classList.contains('hidden'),
      setup: !document.getElementById('setup-panel').classList.contains('hidden'),
      start: document.getElementById('start-btn').disabled,
      lastAction: document.getElementById('last-action').textContent,
      tag: document.getElementById('turn-tag').textContent }; })()''')
    ok = (st['phase'] == 'setup' and st['turn'] == 'player' and not st['busy'] and st['aim'] is None and st['sinking'] is None
          and st['pships'] == 0 and st['eships'] == 0 and st['shots'] == 0 and st['marks'] == 0 and st['shipEls'] == 0 and st['chips'] == 0
          and st['stats'] == {'playerShots': 0, 'playerHits': 0, 'computerShots': 0, 'computerHits': 0}
          and st['last'] == {'player': None, 'enemy': None} and st['modal'] and st['setup'] and st['start']
          and st['lastAction'] == '' and st['tag'] == 'Setup' and st['selected'] == 0)
    check(ok, f'Play again fully resets boards, ships, shots, stats, messages and buttons ({st})')
    check(st['skill'] == 'advanced', 'Chosen difficulty is kept for the next game')
    g.click('#random-btn'); g.click('#start-btn')
    ships2 = S('window.__battleship.state.enemy.ships.map(s => ({name: s.name, cells: s.cells}))')
    check(ships2 != ships, 'New game hides a newly arranged enemy fleet')

    # Abandon during the computer's turn: its missile must not land on the new game
    ecell(*[x for x in water if x not in [w for w in []]][5]).click()
    wait_for(g, "window.__battleship.state.turn==='computer'")
    g.click('#new-game-btn'); g.click('#confirm-yes')
    time.sleep(1.5)
    st = S('({phase: window.__battleship.state.phase, shots: window.__battleship.state.player.shots.flat().filter(Boolean).length, cs: window.__battleship.state.stats.computerShots})')
    check(st == {'phase': 'setup', 'shots': 0, 'cs': 0}, f'Abandoning during the computer turn leaves no stray shot on the new game ({st})')

    # Loss: keep firing at water until the computer wins
    g.click('#random-btn'); g.click('#start-btn')
    water = S('''(() => { const s = window.__battleship.state.enemy, out = [];
      for (let r = 0; r < 10; r++) for (let c = 0; c < 10; c++) if (!s.ships.some(x => x.cells.some(([a,b]) => a===r && b===c))) out.push([r,c]);
      return out; })()''')
    i = 0
    while S('window.__battleship.state.phase') == 'battle' and i < len(water):
        if wait_for(g, PLAYER_TURN, 20) and S('window.__battleship.state.phase') == 'battle':
            ecell(*water[i]).click(); i += 1
            wait_for(g, "(()=>{const s=window.__battleship.state;return s.phase!=='battle'||s.turn==='computer'})()", 10)
    wait_for(g, "!document.getElementById('modal').classList.contains('hidden')", 5)
    st = S('window.__battleship.state')
    check(st['phase'] == 'over' and g.inner_text('#modal-title').lower() == 'defeat', f'Defeat declared when all your ships are sunk (after {i} of your shots)')
    check(st['stats']['playerShots'] == st['stats']['computerShots'], 'Turns alternated evenly up to the defeat')
    check(all(sum(1 for (r, c) in s['cells'] if st['player']['shots'][r][c] == 'hit') == s['size'] for s in st['player']['ships']),
          'Every one of your ships was fully hit when the defeat was declared')
    check(st['stats']['computerHits'] == 17, f"Computer needed exactly 17 hits ({st['stats']['computerHits']})")
    before = S('window.__battleship.state.stats.playerShots')
    g.click('#view-board-btn')
    ecell(*water[i]).click(); time.sleep(0.5)
    check(S('window.__battleship.state.stats.playerShots') == before, 'Firing after the defeat is ignored')
    g.screenshot(path=OUT + 'qa_defeat_board.png')
    ctx.close()

    # ---------- 4. Phones and tablets ----------
    sizes = [(360, 640), (375, 667), (390, 844), (412, 915), (414, 896), (640, 360), (844, 390), (768, 1024), (1024, 768)]
    for w, h in sizes:
        c = b.new_context(viewport={'width': w, 'height': h}, has_touch=True, is_mobile=True, device_scale_factor=2, reduced_motion='reduce')
        m = watch(c.new_page())
        m.goto(URL)
        m.wait_for_timeout(300)
        sw = m.evaluate('document.documentElement.scrollWidth')
        cell_px = m.evaluate("document.querySelector('#player-board .cell').getBoundingClientRect().width")
        btns_ok = m.evaluate('''[...document.querySelectorAll('#start-btn, #random-btn, #clear-btn, #new-game-btn, #demo-btn, #sound-btn')].every(b => { const r = b.getBoundingClientRect(); return r.width > 0 && r.left >= 0 && r.right <= innerWidth; })''')
        m.locator('#player-board .cell[data-r="4"][data-c="4"]').tap()
        placed = m.evaluate('window.__battleship.state.player.ships.length')
        m.screenshot(path=OUT + f'qa_phone_{w}x{h}_setup.png')
        m.click('#random-btn'); m.click('#start-btn')
        m.wait_for_timeout(300)
        ecr = m.evaluate("(() => { const r = document.querySelector('#enemy-board .field').getBoundingClientRect(); return [r.left, r.right, r.width]; })()")
        target = m.locator('#enemy-board .cell[data-r="0"][data-c="0"]')
        try:
            target.scroll_into_view_if_needed(timeout=3000); target.tap(timeout=3000)
        except Exception:
            pass
        wait_for(m, "window.__battleship.state.enemy.shots[0][0] !== null", 5)
        fired = m.evaluate('window.__battleship.state.enemy.shots[0][0]')
        sw2 = m.evaluate('document.documentElement.scrollWidth')
        m.screenshot(path=OUT + f'qa_phone_{w}x{h}_battle.png')
        check(sw <= w and sw2 <= w, f'{w}x{h}: no sideways scrolling in setup or battle ({sw}, {sw2})')
        check(btns_ok, f'{w}x{h}: header and setup buttons fully on screen')
        check(placed == 1, f'{w}x{h}: tapping places a ship')
        check(fired is not None, f'{w}x{h}: tapping enemy waters fires')
        check(ecr[2] >= 200 and ecr[0] >= 0 and ecr[1] <= w, f'{w}x{h}: battle board is {ecr[2]:.0f} px wide (at least 200) and fully on screen horizontally; setup squares {cell_px:.0f} px')
        c.close()

    # ---------- 5. Animation demo: closing mid-flight and reopening ----------
    d = watch(b.new_page(viewport={'width': 1024, 'height': 768}))
    d.goto(URL)
    for _ in range(12):
        d.click('#demo-btn'); d.click('#demo-reset')
        d.click('[data-demo="sink"]'); d.wait_for_timeout(100)
        d.click('#demo-close'); d.click('#demo-btn')
        d.click('[data-demo="sink"]'); d.wait_for_timeout(3400)
        d.click('#demo-close')
    sunk = d.evaluate('window.__battleship.demo.side.ships.filter(s => s.hits >= s.size).length')
    check(not any('demo' in e or 'result' in e for e in errors), 'BUG-6: closing and reopening the demo mid-missile causes no error')
    check(not d.evaluate('window.__battleship.demo.busy'), 'BUG-6: demo buttons usable again afterwards')
    d.close()

    # ---------- 7. Version label ----------
    for (w, h) in [(1280, 800), (1024, 768), (390, 844)]:
        v = watch(b.new_page(viewport={'width': w, 'height': h}))
        v.goto(URL)
        info = v.evaluate('''() => { const m = document.querySelector('meta[name="app-version"]').content, el = document.getElementById("app-version");
          const r = el.getBoundingClientRect(), hdr = document.querySelector("header").getBoundingClientRect();
          return { meta: m, label: el.textContent, shown: r.width > 0, inHeader: r.bottom <= hdr.bottom + 1 && r.right <= innerWidth }; }''')
        check(info['label'] == 'v' + info['meta'], f"{w}x{h}: version label {info['label']} matches index.html version {info['meta']}")
        check(not info['shown'] or info['inHeader'], f'{w}x{h}: version label stays inside the header ({info})')
        v.close()

    # ---------- 6. Animation demo: closing during the sinking animation ----------
    d = watch(b.new_page(viewport={'width': 1280, 'height': 800}))
    d.goto(URL)
    d.evaluate('''() => { window.__shakes = 0; const m = document.getElementById("main");
      new MutationObserver(() => { if (/shake/.test(m.className)) window.__shakes++; }).observe(m, { attributes: true, attributeFilter: ["class"] }); }''')
    d.click('#demo-btn'); d.click('#demo-reset')
    d.click('[data-demo="sink"]')
    d.wait_for_function('window.__battleship.demo.sinking !== null', timeout=8000)
    d.wait_for_timeout(150)
    mid = d.evaluate('''() => { const D = window.__battleship.demo, s = D.sinking;
      return { name: s.name, sunk: s.hits >= s.size, busy: D.busy }; }''')
    d.click('#demo-close')
    closed = d.evaluate('({ sinking: window.__battleship.demo.sinking, parts: window.__battleship.fx.stats().find(s => s.board === "demo-board").parts, shaking: /shake/.test(document.getElementById("main").className) })')
    d.evaluate('window.__shakes = 0')
    d.click('#random-btn'); d.click('#start-btn')
    d.wait_for_timeout(2000)
    game = d.evaluate('''() => { const S = window.__battleship.state;
      return { shakes: window.__shakes, phase: S.phase, enemyShots: S.enemy.shots.flat().filter(Boolean).length,
        playerShots: S.player.shots.flat().filter(Boolean).length }; }''')
    d.click('#demo-btn')
    reopen = d.evaluate(f'''[...document.querySelectorAll("#demo-board .ship-el")].map(e => e.className)''')
    banner = d.evaluate('document.querySelector("#demo-board .banner").classList.contains("show")')
    d.click('[data-demo="hit"]'); d.wait_for_function('!window.__battleship.demo.busy', timeout=8000)
    later_cls = d.evaluate('[...document.querySelectorAll("#demo-board .ship-el")].map(e => e.className)')
    d.click('#demo-close')
    check(mid['sunk'] and mid['busy'], f"BUG-8: demo closed while the {mid['name']} was mid-sinking")
    check(closed['sinking'] is None and closed['parts'] == 0, f'BUG-8: closing clears the sinking ship and demo effects ({closed})')
    check(not closed['shaking'], 'BUG-8: the shake started by the demo sink stops when the demo closes')
    check(game['shakes'] == 0, f"BUG-8: no leftover demo explosions shake the real game ({game['shakes']} shakes)")
    check(game['phase'] == 'battle' and game['enemyShots'] == 0 and game['playerShots'] == 0, f'BUG-8: new game starts clean ({game})')
    check(not banner, 'BUG-8: demo sink banner does not replay on reopen')
    check(sum('sinking' in c for c in reopen + later_cls) == 0 and sum('sunk' in c for c in reopen) == 1 and sum('sunk' in c for c in later_cls) == 1,
          f'BUG-8: after reopening, the sunk ship shows as sunk, not stuck sinking ({reopen} / {later_cls})')
    d.close()

    check(not errors, f'No JavaScript errors or console errors anywhere ({errors[:5]})')
    b.close()

print('\nFAILURES:', fails if fails else 'none')
raise SystemExit(1 if fails else 0)
