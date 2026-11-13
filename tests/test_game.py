import glob, os, sys, time
from playwright.sync_api import sync_playwright
CHROME = os.environ.get('CHROME_PATH') or (sorted(glob.glob('/opt/.devin/chrome/chrome/linux-*/chrome-linux64/chrome')) or [None])[-1]
os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'screenshots'), exist_ok=True)
URL = 'http://localhost:8080/'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'screenshots') + '/'
fails = []
def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME, headless=True) if CHROME else p.chromium.launch(headless=True)

    # ---------- 1. Rules + AI simulation ----------
    pg = b.new_page()
    errors = []
    pg.on('pageerror', lambda e: errors.append(str(e)))
    pg.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
    pg.goto(URL)
    res = pg.evaluate('''() => {
      const B = window.__battleship; const out = {};
      for (const skill of ['beginner','intermediate','advanced']) {
        let total = 0, maxS = 0, bad = 0, n = 300;
        for (let g = 0; g < n; g++) {
          const side = B.newSide(); B.placeFleetRandomly(side);
          // fleet validity
          const seen = new Set(); let cnt = 0;
          for (const s of side.ships) for (const [r,c] of s.cells) { if (r<0||r>9||c<0||c>9) bad++; seen.add(r*10+c); cnt++; }
          if (seen.size !== 17 || cnt !== 17 || side.ships.length !== 5) bad++;
          let shots = 0;
          while (!B.allSunk(side)) {
            const t = B.computerChooseShot(side, skill);
            const r = B.fireAt(side, t[0], t[1]);
            if (!r) { bad++; break; }
            shots++; if (shots > 100) { bad++; break; }
          }
          total += shots; maxS = Math.max(maxS, shots);
        }
        out[skill] = { avg: total/n, max: maxS, bad };
      }
      const s = B.newSide(); B.placeFleetRandomly(s);
      const [r,c] = s.ships[0].cells[0];
      out.repeat = B.fireAt(s, r, c) !== null && B.fireAt(s, r, c) === null;
      return out;
    }''')
    print(res)
    for k in ('beginner', 'intermediate', 'advanced'):
        check(res[k]['bad'] == 0, f'{k} AI: valid fleets, never repeats a shot, always finishes ({res[k]})')
    check(res['advanced']['avg'] < res['intermediate']['avg'] < res['beginner']['avg'], 'Each difficulty level is stronger than the one below it')
    check(res['repeat'], 'Firing the same square twice is rejected')

    # ---------- 2. Placement UI ----------
    pg.set_viewport_size({'width': 1024, 'height': 768})
    pg.goto(URL)
    S = lambda js: pg.evaluate(js)
    cell = lambda board, r, c: pg.locator(f'#{board}-board .cell[data-r="{r}"][data-c="{c}"]')
    check(pg.locator('#start-btn').is_disabled(), 'Start disabled before ships placed')
    check(not pg.locator('#enemy-card').is_visible(), 'Enemy board hidden during setup')
    pg.screenshot(path=OUT + 'setup_empty.png')
    # Carrier selected by default; place horizontally at row 0 col 8 -> nudged to col 5
    cell('player', 0, 8).click()
    ships = S('window.__battleship.state.player.ships.map(s=>[s.name,s.cells])')
    check(ships == [['Carrier', [[0,5],[0,6],[0,7],[0,8],[0,9]]]], f'Carrier placed & nudged onto board: {ships}')
    check(S('window.__battleship.state.selected') == 1, 'Next ship (Battleship) auto-selected')
    # Overlap: battleship vertical at (0,6) would overlap carrier -> taps on carrier pick it up instead; test overlap on empty square
    pg.click('#dir-seg button[data-dir="v"]')
    cell('player', 1, 6).click()  # vertical from row1 col6 - no overlap, valid
    check(len(S('window.__battleship.state.player.ships')) == 2, 'Battleship placed vertically')
    # Cruiser horizontal at (2,4) overlaps battleship at (2,6) -> rejected
    pg.click('#dir-seg button[data-dir="h"]')
    cell('player', 2, 4).click()
    check(len(S('window.__battleship.state.player.ships')) == 2, 'Overlapping placement rejected')
    # Mouse hover preview
    cell('player', 2, 4).hover()
    check(pg.locator('#player-board .preview-bad').count() == 3, 'Invalid preview shown in red on hover')
    cell('player', 8, 0).hover()
    check(pg.locator('#player-board .preview-ok').count() == 3, 'Valid preview shown in green on hover')
    pg.screenshot(path=OUT + 'setup_preview.png')
    # R key rotates
    pg.keyboard.press('r')
    check(S('window.__battleship.state.dir') == 'v', 'R key rotates ship')
    pg.keyboard.press('r')
    # Pick up carrier by tapping it
    cell('player', 0, 7).click()
    st = S('({n: window.__battleship.state.player.ships.length, sel: window.__battleship.state.selected})')
    check(st == {'n': 1, 'sel': 0}, f'Tapping a placed ship picks it up: {st}')
    cell('player', 9, 0).click()  # re-place carrier at bottom row
    for (r, c) in [(4, 0), (6, 0), (8, 8)]:
        cell('player', r, c).click()
    n = S('window.__battleship.state.player.ships.length')
    check(n == 5, f'All five ships placed ({n})')
    check(not pg.locator('#start-btn').is_disabled(), 'Start enabled when fleet complete')
    check([x.strip().lower() for x in pg.locator('#skill-seg button').all_inner_texts()] == ['beginner', 'intermediate', 'advanced'], 'Three difficulty levels offered')
    check(S('window.__battleship.state.skill') == 'intermediate', 'Intermediate is the default difficulty')
    for lvl in ['beginner', 'advanced', 'intermediate']:
        pg.click(f'#skill-seg button[data-skill="{lvl}"]')
        check(S('window.__battleship.state.skill') == lvl and 'on' in pg.get_attribute(f'#skill-seg button[data-skill="{lvl}"]', 'class'), f'Can choose {lvl}')
    pg.click('#clear-btn')
    check(S('window.__battleship.state.player.ships.length') == 0 and pg.locator('#start-btn').is_disabled(), 'Clear board works')
    pg.click('#random-btn')
    check(S('window.__battleship.state.player.ships.length') == 5, 'Random placement places all ships')
    pg.screenshot(path=OUT + 'setup_ready.png')

    # ---------- 3. Battle: win ----------
    pg.click('#start-btn')
    check(pg.locator('#enemy-card').is_visible() and not pg.locator('#setup-panel').is_visible(), 'Battle screen shown')
    check('Your turn' in pg.inner_text('#status-text'), 'Status says it is your turn')
    check(pg.locator('#enemy-board .ship-el').count() == 0, 'Enemy ships are hidden')
    enemy = S('window.__battleship.state.enemy.ships.map(s=>s.cells)')
    targets = [c for s in enemy for c in s]
    # Fire one miss first to watch the turn swap
    occupied = {(r, c) for r, c in targets}
    miss = next((r, c) for r in range(10) for c in range(10) if (r, c) not in occupied)
    cell('enemy', *miss).click()
    pg.wait_for_timeout(120)
    st = S('window.__battleship.fx.stats()')
    check(any(l['missiles'] for l in st), f'Missile is in flight after firing {st}')
    check('locked' in cell('enemy', *miss).get_attribute('class'), 'Target square is locked while the missile flies')
    cell('enemy', *targets[0]).click()
    check(S('window.__battleship.state.enemy.shots[%d][%d]' % tuple(targets[0])) is None, 'Cannot fire a second missile while one is in flight')
    pg.wait_for_function('document.querySelector(\'#enemy-board .cell[data-r="%d"][data-c="%d"]\').classList.contains("miss")' % miss, timeout=5000)
    check(True, 'Miss shown on enemy board after impact')
    st = {l['board']: l for l in S('window.__battleship.fx.stats()')}
    check(st['enemy-board']['parts'] > 30, f"Splash particles spawned on miss ({st['enemy-board']['parts']})")
    pg.wait_for_function('document.querySelector("#status-text").textContent.includes("Computer")', timeout=5000)
    check(True, 'Turn passes to computer')
    cell('enemy', *targets[0]).click()
    check(S('window.__battleship.state.enemy.shots[%d][%d]' % tuple(targets[0])) is None, 'Cannot fire during computer turn')
    pg.wait_for_function('(window.__battleship.state.turn === "player" && !window.__battleship.state.busy)', timeout=15000)
    check(S('window.__battleship.state.stats.computerShots') == 1, 'Computer fired exactly once')
    # clicking an already-shot square does nothing
    cell('enemy', *miss).click()
    check(S('window.__battleship.state.turn') == 'player', 'Re-firing at a used square is ignored (still your turn)')
    for i, (r, c) in enumerate(targets):
        pg.wait_for_function('(window.__battleship.state.turn === "player" && !window.__battleship.state.busy) || window.__battleship.state.phase === "over"', timeout=15000)
        if S('window.__battleship.state.phase') == 'over': break
        cell('enemy', r, c).click()
        if i == 0:
            pg.wait_for_function('document.querySelector(\'#enemy-board .cell[data-r="%d"][data-c="%d"]\').classList.contains("hit")' % (r, c), timeout=5000)
            pg.wait_for_timeout(80)
            st = {l['board']: l for l in S('window.__battleship.fx.stats()')}
            check(st['enemy-board']['parts'] > 40, f"Explosion particles spawned on hit ({st['enemy-board']['parts']})")
            check(S('document.getElementById("main").classList.contains("shake-s")'), 'Screen shakes on hit')
            pg.screenshot(path=OUT + 'hit_explosion.png')
        if i == len(enemy[0]) - 1:
            pg.wait_for_function('document.querySelector("#enemy-board .ship-el.sinking")', timeout=5000)
            check(True, 'Sinking animation starts when the last section is hit')
            check(pg.locator('#enemy-board .banner.show').count() == 1, 'Destroyed banner shown')
            check('sank the enemy' in pg.inner_text('#last-action'), 'Sinking is announced')
            pg.wait_for_timeout(700)
            pg.screenshot(path=OUT + 'sinking.png')
        pg.wait_for_function('(window.__battleship.state.turn === "player" && !window.__battleship.state.busy) || window.__battleship.state.phase === "over"', timeout=15000)
        if i == 1:
            cls = cell('enemy', *targets[0]).get_attribute('class')
            check('hit' in cls or 'sunk' in cls, 'Hit shown on enemy board')
            pg.screenshot(path=OUT + 'battle_landscape.png')
        if i == len(enemy[0]) - 1:
            check(cell('enemy', *targets[0]).get_attribute('class').find('sunk') >= 0, 'Sunk ship shown on enemy board')
            check(pg.locator('#enemy-board .ship-el.sunk').count() == 1, 'Sunk enemy ship stays visible as a wreck')
            check(pg.locator('#enemy-fleet .chip.sunk').count() == 1, 'Sunk ship crossed off enemy fleet list')
    pg.wait_for_selector('#modal:not(.hidden)')
    check(pg.inner_text('#modal-title').lower() == 'victory!', 'Winner announced: player')
    check('You win' in pg.inner_text('#status-text'), 'Status shows you win')
    pg.screenshot(path=OUT + 'win_modal.png')
    pg.click('#view-board-btn')
    cell('enemy', 9, 9).click()
    check(S('window.__battleship.state.stats.playerShots') == 18, 'No firing after the game is over')
    pg.click('#new-game-btn')
    check(S('window.__battleship.state.phase') == 'setup' and pg.locator('#setup-panel').is_visible(), 'New game returns to setup')

    # ---------- 4. Battle: lose (portrait tablet) ----------
    pg.set_viewport_size({'width': 768, 'height': 1024})
    pg.click('#random-btn'); pg.click('#start-btn')
    enemy = {tuple(c) for s in S('window.__battleship.state.enemy.ships.map(s=>s.cells)') for c in s}
    misses = [(r, c) for r in range(10) for c in range(10) if (r, c) not in enemy]
    shotsTaken = 0
    for (r, c) in misses:
        pg.wait_for_function('(window.__battleship.state.turn === "player" && !window.__battleship.state.busy) || window.__battleship.state.phase === "over"', timeout=15000)
        if S('window.__battleship.state.phase') == 'over': break
        cell('enemy', r, c).click(); shotsTaken += 1
        if shotsTaken == 20:
            pg.wait_for_function('(window.__battleship.state.turn === "player" && !window.__battleship.state.busy)', timeout=15000)
            pg.screenshot(path=OUT + 'battle_portrait.png')
    pg.wait_for_selector('#modal:not(.hidden)')
    pg.wait_for_timeout(1800)
    pg.screenshot(path=OUT + 'defeat_screen.png')
    check(pg.locator('#modal.lose').count() == 1, 'Defeat screen styling')
    check(pg.inner_text('#modal-title').lower() == 'defeat', f'Winner announced: computer (after {shotsTaken} player shots)')
    st = S('window.__battleship.state.stats')
    check(st['playerShots'] == st['computerShots'], f'Turns alternated evenly {st}')
    pg.click('#view-board-btn')
    check(pg.locator('#enemy-board .ship-el.revealed').count() == 5, 'Enemy ships revealed after losing')
    check(pg.locator('#player-board .ship-el.sunk').count() == 5, 'All your sunk ships shown as wrecks')
    pg.screenshot(path=OUT + 'lose_portrait.png')

    # ---------- 5. Touch / phone ----------
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True)
    tp = ctx.new_page(); tp.on('pageerror', lambda e: errors.append(str(e)))
    tp.goto(URL)
    tp.locator('#player-board .cell[data-r="3"][data-c="3"]').tap()
    check(tp.evaluate('window.__battleship.state.player.ships.length') == 1, 'Tap places ship on touch device')
    tp.click('#random-btn'); tp.click('#start-btn')
    tp.locator('#enemy-board .cell[data-r="0"][data-c="0"]').tap()
    tp.wait_for_function('window.__battleship.state.stats.playerShots === 1', timeout=5000)
    check(True, 'Tap fires on touch device')
    tp.wait_for_function('(window.__battleship.state.turn === "player" && !window.__battleship.state.busy)', timeout=15000)
    tp.screenshot(path=OUT + 'phone.png', full_page=True)

    # boards fit on common tablet/phone screens without scrolling
    BOTTOM = "Math.max(...[...document.querySelectorAll('.board-card, .panel')].filter(e=>e.offsetParent).map(e=>e.getBoundingClientRect().bottom))"
    for (w, h) in [(1024, 768), (768, 1024), (1180, 820), (820, 1180), (1366, 1024), (1024, 1366), (390, 844), (1440, 900)]:
        tp2 = b.new_context(viewport={'width': w, 'height': h}, has_touch=True).new_page()
        tp2.goto(URL); tp2.click('#random-btn')
        sb = tp2.evaluate(BOTTOM)
        tp2.screenshot(path=OUT + f'setup_{w}x{h}.png')
        tp2.click('#start-btn')
        bb = tp2.evaluate(BOTTOM)
        sw = tp2.evaluate('document.documentElement.scrollWidth')
        if w >= 700:
            check(sb <= h, f'{w}x{h}: setup fits on screen (bottom {sb:.0f})')
        if w >= 700:
            check(bb <= h, f'{w}x{h}: both battle boards fit on screen (bottom {bb:.0f})')
        else:
            eb = tp2.evaluate("document.querySelector('#enemy-board').getBoundingClientRect().bottom")
            check(eb <= h, f'{w}x{h}: enemy board fits on phone screen (bottom {eb:.0f})')
        check(sw <= w, f'{w}x{h}: no sideways scrolling ({sw})')
        tp2.screenshot(path=OUT + f'battle_{w}x{h}.png')
        tp2.click('#new-game-btn') if False else None
        tp2.context.close()

    # ---------- 6. Animation demo ----------
    pg = b.new_page(viewport={'width': 1024, 'height': 768})
    pg.on('pageerror', lambda e: errors.append(str(e)))
    pg.goto(URL); pg.click('#random-btn'); pg.click('#start-btn')
    pg.locator('#enemy-board .cell[data-r="0"][data-c="0"]').click()
    pg.wait_for_function('(window.__battleship.state.turn === "player" && !window.__battleship.state.busy)', timeout=15000)
    before = S2 = pg.evaluate('JSON.stringify([window.__battleship.state.stats, window.__battleship.state.enemy.shots, window.__battleship.state.player.shots, window.__battleship.state.turn])')
    pg.click('#demo-btn')
    check(pg.locator('#demo').is_visible(), 'Demo panel opens')
    check(pg.locator('#demo-board .ship-el').count() == 5, 'Demo board shows all five ship classes')
    DEMO_IDLE = 'window.__battleship.demo.busy === false'
    for kind in ['hit', 'miss', 'sink', 'hit', 'miss', 'sink', 'sink', 'sink', 'sink', 'sink', 'hit']:
        shots_before = pg.evaluate('window.__battleship.demo.side.shots.flat().filter(Boolean).length')
        pg.click(f'[data-demo="{kind}"]')
        pg.wait_for_timeout(100)
        check(any(l['missiles'] for l in pg.evaluate('window.__battleship.fx.stats()')), f'Demo {kind.upper()}: missile launched')
        if kind == 'sink':
            pg.wait_for_function('document.querySelector("#demo-board .ship-el.sinking")', timeout=5000)
            check(True, 'Demo SINK: ship sinking animation runs')
        pg.wait_for_function(DEMO_IDLE, timeout=10000)
        if kind == 'hit':
            check(pg.locator('#demo-board .dmg').count() >= 1, 'Demo HIT: damage visible on ship')
        if kind == 'miss':
            check(pg.locator('#demo-board .cell.miss').count() >= 1, 'Demo MISS: splash marker left on water')
        if kind == 'sink':
            check(pg.locator('#demo-board .ship-el.sunk').count() >= 1, 'Demo SINK: wreck remains afterwards')
    pg.click('#demo-reset')
    check(pg.locator('#demo-board .ship-el.sunk').count() == 0 and pg.locator('#demo-board .dmg').count() == 0, 'Demo reset restores practice board')
    pg.click('#demo-close')
    after = pg.evaluate('JSON.stringify([window.__battleship.state.stats, window.__battleship.state.enemy.shots, window.__battleship.state.player.shots, window.__battleship.state.turn])')
    check(before == after, 'Demo did not change the real game')
    pg.locator('#enemy-board .cell[data-r="0"][data-c="1"]').click()
    pg.wait_for_function('window.__battleship.state.stats.playerShots === 2', timeout=5000)
    check(True, 'Game continues normally after using the demo')
    # Demo pauses the computer: open demo during the computer's turn
    pg.wait_for_function('window.__battleship.state.turn === "computer"', timeout=5000)
    pg.click('#demo-btn')
    cs = pg.evaluate('window.__battleship.state.stats.computerShots')
    pg.wait_for_timeout(2500)
    check(pg.evaluate('window.__battleship.state.stats.computerShots') == cs, 'Computer waits while the demo is open')
    pg.click('#demo-close')
    pg.wait_for_function('(window.__battleship.state.turn === "player" && !window.__battleship.state.busy)', timeout=15000)
    check(pg.evaluate('window.__battleship.state.stats.computerShots') == cs + 1, 'Computer resumes after closing the demo')

    # ---------- 7. Smoothness (frames per second during heavy effects) ----------
    for ctx_ in list(b.contexts): ctx_.close()
    b.close()
    b = p.chromium.launch(executable_path=CHROME, headless=True) if CHROME else p.chromium.launch(headless=True)
    for (w, h, name) in [(1280, 800, 'desktop'), (1024, 768, 'tablet landscape'), (768, 1024, 'tablet portrait')]:
        fp = b.new_page(viewport={'width': w, 'height': h})
        fp.goto(URL); fp.click('#demo-btn')
        fp.evaluate("""() => { window.__frames = []; let last = performance.now();
            const tick = (t) => { window.__frames.push(t - last); last = t; if (window.__frames.length < 400) requestAnimationFrame(tick); };
            requestAnimationFrame(tick); }""")
        fp.click('[data-demo="sink"]')
        fp.wait_for_timeout(2600)
        frames = fp.evaluate('window.__frames.slice(5)')
        avg = sum(frames) / len(frames); fps = 1000 / avg; worst = max(frames)
        print(f'   {name}: {fps:.0f} fps average, slowest frame {worst:.0f} ms during SINK')
        check(fps >= 40, f'{name}: smooth animation during sinking ({fps:.0f} fps)')
        fp.close()

    # ---------- 8. Reduced motion ----------
    rm = b.new_context(viewport={'width': 1024, 'height': 768}, reduced_motion='reduce').new_page()
    rm.on('pageerror', lambda e: errors.append(str(e)))
    rm.goto(URL); rm.click('#random-btn'); rm.click('#start-btn')
    tg = rm.evaluate('window.__battleship.state.enemy.ships[4].cells')
    t0 = time.time()
    rm.locator(f'#enemy-board .cell[data-r="{tg[0][0]}"][data-c="{tg[0][1]}"]').click()
    rm.wait_for_function('window.__battleship.state.stats.playerShots === 1', timeout=3000)
    check(time.time() - t0 < 0.5, f'Reduced motion: result shown immediately ({time.time() - t0:.2f}s)')
    check(not any(l['missiles'] for l in rm.evaluate('window.__battleship.fx.stats()')), 'Reduced motion: no flying missile')
    check(all(l['parts'] == 0 for l in rm.evaluate('window.__battleship.fx.stats()')), 'Reduced motion: no particle effects')
    check(not rm.evaluate('document.getElementById("main").className'), 'Reduced motion: no screen shake')
    anim = rm.evaluate('getComputedStyle(document.querySelector("#enemy-board .ocean .water")).animationName')
    check(anim == 'none', f'Reduced motion: ocean is still ({anim})')
    rm.wait_for_function('(window.__battleship.state.turn === "player" && !window.__battleship.state.busy)', timeout=8000)
    rm.locator(f'#enemy-board .cell[data-r="{tg[1][0]}"][data-c="{tg[1][1]}"]').click()
    rm.wait_for_function('document.querySelector("#enemy-board .ship-el.sinking, #enemy-board .ship-el.sunk")', timeout=3000)
    check(True, 'Reduced motion: sunk ship still clearly shown')
    rm.wait_for_function('(window.__battleship.state.turn === "player" && !window.__battleship.state.busy)', timeout=8000)
    rm.screenshot(path=OUT + 'reduced_motion.png')

    # ---------- 9. Phase 3 polish: sound toggle, reticle, radar, confirm dialog, end screens ----------
    pp = b.new_page(viewport={'width': 1024, 'height': 768})
    pp.on('pageerror', lambda e: errors.append(str(e)))
    pp.goto(URL)
    check(pp.get_attribute('#sound-btn', 'aria-pressed') == 'false', 'Sound is on by default')
    pp.click('#sound-btn')
    check(pp.get_attribute('#sound-btn', 'aria-pressed') == 'true' and pp.evaluate('window.__battleship.sound.muted'), 'Mute button mutes sound')
    pp.reload()
    check(pp.get_attribute('#sound-btn', 'aria-pressed') == 'true', 'Mute choice is remembered after reload')
    pp.click('#sound-btn')
    check(pp.get_attribute('#sound-btn', 'aria-pressed') == 'false', 'Unmute works')
    check(not pp.locator('#enemy-board .radar').is_visible(), 'Radar hidden during setup')
    pp.click('#random-btn'); pp.click('#start-btn')
    check(pp.locator('#stage-banner.show').count() == 1, '"Battle stations" banner plays when the battle starts')
    check(pp.locator('#enemy-board .radar').is_visible(), 'Radar sweep visible on enemy waters during battle')
    check(pp.inner_text('#turn-tag').upper() == 'TURN 01', f"Turn counter shown ({pp.inner_text('#turn-tag')})")
    check(pp.locator('#force-you').is_visible() and pp.locator('#you-hull i').count() == 17, 'Fleet strength meters shown')
    pp.locator('#enemy-board .cell[data-r="4"][data-c="6"]').hover()
    check(pp.locator('#enemy-board .reticle.show').count() == 1 and pp.inner_text('#enemy-board .reticle .tag') == 'G5', 'Targeting reticle follows the mouse with coordinates')
    check(pp.locator('#enemy-board .cols span.hot').inner_text() == 'G' and pp.locator('#enemy-board .rows span.hot').inner_text() == '5', 'Row and column labels light up under the reticle')
    pp.locator('#enemy-board .cell[data-r="4"][data-c="6"]').click()
    pp.wait_for_timeout(100)
    check(pp.locator('#enemy-board .reticle.locked').count() == 1, 'Reticle locks red while the missile flies')
    pp.wait_for_function('document.querySelector("#enemy-board .float-tag")', timeout=5000)
    check(True, 'Floating HIT/MISS label appears at impact')
    pp.wait_for_function('document.querySelector("#player-board .reticle.locked")', timeout=8000)
    check('Incoming' in pp.inner_text('#player-board .reticle .tag'), 'Incoming missile is marked on your board')
    pp.wait_for_function('(window.__battleship.state.turn === "player" && !window.__battleship.state.busy)', timeout=15000)
    check(pp.inner_text('#turn-tag').upper() == 'TURN 02', 'Turn counter advances')
    pp.click('#new-game-btn')
    check(pp.locator('#confirm').is_visible(), 'New game during battle asks for confirmation')
    pp.click('#confirm-no')
    check(pp.evaluate('window.__battleship.state.phase') == 'battle' and not pp.locator('#confirm').is_visible(), '"Keep fighting" keeps the battle')
    pp.click('#new-game-btn'); pp.click('#confirm-yes')
    check(pp.evaluate('window.__battleship.state.phase') == 'setup', '"Abandon" returns to fleet deployment')
    # quick win to check the victory screen
    pp.click('#random-btn'); pp.click('#start-btn')
    for (r, c) in [tuple(x) for s in pp.evaluate('window.__battleship.state.enemy.ships.map(s=>s.cells)') for x in s]:
        pp.wait_for_function('(window.__battleship.state.turn === "player" && !window.__battleship.state.busy) || window.__battleship.state.phase === "over"', timeout=15000)
        if pp.evaluate('window.__battleship.state.phase') == 'over': break
        pp.locator(f'#enemy-board .cell[data-r="{r}"][data-c="{c}"]').click()
    pp.wait_for_selector('#modal:not(.hidden)', timeout=15000)
    check(pp.locator('#modal.win').count() == 1 and pp.locator('#modal-stats div').count() == 6, 'Cinematic victory screen with 6 battle stats')
    pp.wait_for_timeout(1600)
    st = {l['board']: l for l in pp.evaluate('window.__battleship.fx.stats()')}
    check(st['global']['parts'] > 0, 'Victory fireworks play')
    pp.screenshot(path=OUT + 'victory_screen.png')
    check(pp.inner_text('#modal-kicker').lower() == 'mission accomplished', 'Victory kicker text')

    # ---------- 10. QA regression tests (DEBUGGING_REPORT.md) ----------
    IDLE = '(window.__battleship.state.turn === "player" && !window.__battleship.state.busy)'
    gl = lambda pg_, name: [l for l in pg_.evaluate('window.__battleship.fx.stats()') if l['board'] == name][0]
    q = b.new_page(viewport={'width': 1024, 'height': 768})
    q.on('pageerror', lambda e: errors.append(str(e)))
    q.goto(URL); q.click('#random-btn'); q.click('#start-btn')
    cells = q.evaluate('window.__battleship.state.enemy.ships[4].cells')
    q.click(f'#enemy-board .cell[data-r="{cells[0][0]}"][data-c="{cells[0][1]}"]'); q.wait_for_function(IDLE, timeout=20000)
    q.click(f'#enemy-board .cell[data-r="{cells[1][0]}"][data-c="{cells[1][1]}"]')
    q.wait_for_function('document.querySelector("#enemy-board .ship-el.sinking")', timeout=5000)
    q.click('#new-game-btn'); q.click('#confirm-yes'); q.click('#random-btn'); q.click('#start-btn')
    q.wait_for_timeout(700)
    check(gl(q, 'enemy-board')['parts'] == 0, f"BUG-1: no leftover explosions after abandoning mid-sink ({gl(q, 'enemy-board')['parts']})")
    # BUG-2: fireworks stop after Play again
    for s in q.evaluate('window.__battleship.state.enemy.ships.map(s=>s.cells)'):
        for r, c in s:
            q.wait_for_function(IDLE + ' || window.__battleship.state.phase === "over"', timeout=20000)
            if q.evaluate('window.__battleship.state.phase') == 'over': break
            q.click(f'#enemy-board .cell[data-r="{r}"][data-c="{c}"]')
    q.wait_for_selector('#modal:not(.hidden)', timeout=20000); q.wait_for_timeout(1600)
    q.click('#play-again-btn'); q.wait_for_timeout(300)
    check(gl(q, 'global')['parts'] == 0, f"BUG-2: fireworks stop after Play again ({gl(q, 'global')['parts']})")
    # BUG-3: missile follows its target through a resize
    q.click('#random-btn'); q.click('#start-btn'); q.wait_for_timeout(600)
    q.click('#enemy-board .cell[data-r="9"][data-c="9"]'); q.wait_for_timeout(120)
    q.set_viewport_size({'width': 768, 'height': 1024}); q.wait_for_timeout(250)
    end = q.evaluate('(()=>{const m=window.__battleship.fx.missileEnds(); return m.length ? m[0] : null})()')
    want = q.evaluate('(()=>{const r=document.querySelector(\'#enemy-board .cell[data-r="9"][data-c="9"]\').getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2]})()')
    check(end is not None and abs(end[0]-want[0]) < 2 and abs(end[1]-want[1]) < 2, f'BUG-3: missile retargets after resize (end {end}, square {want})')
    q.close()
    # BUG-5: keyboard play
    k = b.new_page(viewport={'width': 1024, 'height': 768})
    k.on('pageerror', lambda e: errors.append(str(e)))
    k.goto(URL)
    check(k.evaluate('[...document.querySelectorAll("#player-board .cell")].filter(c=>c.tabIndex===0).length') == 1, 'BUG-5: one keyboard stop on your board during setup')
    k.focus('#player-board .cell[data-r="0"][data-c="0"]')
    k.keyboard.press('Enter')
    check(k.evaluate('window.__battleship.state.player.ships.length') == 1, 'BUG-5: Enter places a ship')
    for key in ['ArrowDown', 'ArrowDown', 'Enter', 'ArrowDown', 'ArrowDown', 'Enter', 'ArrowDown', 'ArrowDown', 'Enter', 'ArrowDown', 'ArrowDown', 'Enter']:
        k.keyboard.press(key)
    check(k.evaluate('window.__battleship.state.player.ships.length') == 5, 'BUG-5: whole fleet placed with keyboard only')
    k.click('#start-btn')
    k.focus('#enemy-board .cell[data-r="0"][data-c="0"]')
    k.keyboard.press('ArrowRight'); k.keyboard.press('ArrowDown')
    check(k.evaluate('document.activeElement.dataset.r + document.activeElement.dataset.c') == '11', 'BUG-5: arrow keys move between squares')
    check(k.inner_text('#enemy-board .reticle .tag') == 'B2', 'BUG-5: reticle follows keyboard focus')
    k.keyboard.press(' ')
    k.wait_for_function('window.__battleship.state.stats.playerShots === 1', timeout=5000)
    check(k.evaluate('window.__battleship.state.enemy.shots[1][1]') is not None, 'BUG-5: Space fires at the focused square')
    k.close()

    check(not errors, f'No JavaScript errors {errors}')
    b.close()
print('\nFAILURES:', fails if fails else 'none')
