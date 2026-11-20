# Battleship – Debug Report

**Date:** 2026-11-19 (BUG-8 added 2026-11-20) · **Tester:** Devin
**Build tested:** `main` at `e94d9a0` (before fixes) and the fix branch (after fixes).
**Environment:** Ubuntu VM, Chrome for Testing 156, run headless through Playwright (Python) and as a normal Chrome window for the manual play-through. Phones and tablets were emulated (touch, screen size). No physical devices were used.

This report covers only what was actually run. It follows the earlier QA pass in `DEBUGGING_REPORT.md`, whose five bugs (BUG-1 to BUG-5) were already fixed. The new bugs here are numbered BUG-6 to BUG-8. BUG-8 was found afterwards, in a follow-up check of how closing the demo during its sinking animation is cleaned up.

---

## 1. What was tested and how

| Area | How it was tested |
|---|---|
| Ship placement: overlaps, edges, invalid spots | Every ship placed on all 100 squares in both directions (1,000 placements). Every free square tried next to a random fleet (208 overlapping attempts, 832 valid attempts). Clicks on labels and gaps. Start button with an empty board. Manual placement in Chrome. |
| Turns: repeated shots, invalid clicks | Double-click, quick second click, clicks during the computer's turn, clicks on your own board, re-firing at a used square (mouse and Enter key). Repeated manually in Chrome. |
| Computer opponent | 400 simulated games for each difficulty (plus 300 more each in the original suite). Each computer shot checked to be on the board and not fired before. Computer shot count checked against the marks on your board in real browser games. |
| Hit, miss, sunk | Every shot of a full winning game checked on the board, fleet list and message bar. Manual check of markers, the "destroyed" banner and crossed-off fleet chips. |
| Winning and losing | Full win (17 hits) and full loss played in the browser. Checked the screen, stats, that the computer stops firing, and that firing after the end is ignored. Manual win in Chrome. |
| Restarting and resetting | "Play again" after a win. "New game" → Abandon during battle, including while the computer's missile is in the air. Every part of the game state and screen checked after the reset. |
| Phones and tablets | 360×640, 375×667, 390×844, 412×915, 414×896 (upright phones), 640×360 and 844×390 (sideways phones), 768×1024 and 1024×768 (tablets), all with touch emulation. Plus the 8 tablet/desktop sizes in the original suite. |
| Console errors | All JavaScript errors and console errors recorded on every page in both test suites and during the manual play-through. |

**Automated tests**
- `tests/test_game.py`: the existing suite, 154 checks.
- `tests/test_qa_extra.py`: new in this pass, 86 checks (80 at first, plus 6 for BUG-8).

**Manual testing:** a recorded play-through in a real Chrome window, using mouse clicks and device emulation.

## 2. Bugs found and fixed

| ID | Bug | Severity | Status |
|---|---|---|---|
| BUG-6 | Animation demo: closing and reopening it while a missile is in the air causes a JavaScript error | Low | **Fixed & verified** |
| BUG-7 | Phones held sideways: the battle boards shrink to almost nothing (0 px at 640×360), and the New Game button is cut off | Medium | **Fixed & verified** |
| BUG-8 | Animation demo: closing it during the sinking animation leaves that animation running: the ship stays stuck as "sinking", and its leftover explosions shake the real game | Low | **Fixed & verified** |

### BUG-6: Demo close/reopen error
- **Steps:**
  1. Open **Animation demo** and press **SINK SHIP**.
  2. Close the demo within about 0.1 s.
  3. Reopen it and press **SINK SHIP** again.
- **Expected:** the effect plays normally.
- **Actual:** in 5 of 15 attempts, the console showed `Cannot read properties of null (reading 'result')`, and the demo's sinking sequence was left unfinished.
- **Cause:** a missile launched before the demo was closed still landed after it was reopened. It then fired at the same square as the new missile. Firing at a used square returns "nothing", and the demo code didn't expect that.
- **Fix** (`index.html`, `runDemo` / `closeDemo`): each demo shot now carries a run number. Closing the demo starts a new run, so a missile from an earlier run is ignored when it lands. The real game was never affected.

### BUG-7: Sideways phones
- **Steps:** open the game at 640×360 or 844×390 (a phone held sideways), place the fleet and start the battle.
- **Expected:** both boards are big enough to tap, and all buttons are visible.
- **Actual:**
  - The enemy board measured **0 px** wide at 640×360, **3 px** at 667×375 and **109 px** at 844×390 (squares about 11 px). You couldn't fire at all at 640×360.
  - The **New Game** button stuck out past the right edge of the screen at 640–740 px wide.
- **Cause:** the battle board size is calculated from the screen height minus about 370 px for the header and status bar. On a screen only 360–430 px tall, that leaves almost nothing.
- **Fix** (`index.html`, one new CSS rule for sideways screens no taller than 500 px):
  - The boards keep a usable size of at least 230 px, up to the existing 540 px maximum, and the page scrolls.
  - The header buttons use the same compact style the game already uses on small phones.
  - Nothing changes on other screen sizes.

### BUG-8: Demo closed during the sinking animation
- **Steps:**
  1. Open **Animation demo** and press **SINK SHIP**.
  2. Once the missile lands and the ship starts sinking, close the demo.
  3. Place a fleet and press **Start battle** straight away.
  4. Reopen the demo and press **HIT**.
- **Expected:** closing the demo stops its effects. The sunk ship shows as sunk when you reopen it, and the real game is unaffected.
- **Actual:**
  - Within 2 s of starting the battle, the game screen shook 1–2 times. With no demo involved, it doesn't shake at all.
  - The demo's explosion particles kept building up on the hidden demo board (191 → 331).
  - On reopening, the ship and its "destroyed" banner replayed their animations. The ship stayed stuck as "sinking" instead of "sunk", even after later demo shots.
  - No JavaScript error occurred, and the game's shots, turns and rules weren't changed.
- **Cause:**
  - BUG-6's fix stopped the old sequence from continuing, but `closeDemo()` never cleared `demo.sinking`.
  - The explosion timers already scheduled by `FX.sink` kept running, and each one shakes the whole `#main` area.
  - The banner kept its `show` class.
- **Fix** (`index.html`):
  - Effect timers can now be tied to a board, and the new `FX.clearLayer(layer)` cancels one board's timers and particles without touching the others.
  - `FX.sink` ties its explosion timers to its board.
  - `closeDemo()` now clears `demo.sinking` and `demo.aim`, clears the demo board's effects and hides the demo banner.
  - The game's own effects and sounds are unchanged.

## 3. Verification results

| Check | Before fix | After fix |
|---|---|---|
| `tests/test_game.py` (existing suite) | 154 / 154 pass | 154 / 154 pass |
| `tests/test_qa_extra.py` (new suite, first 80 checks) | 74 / 80 pass: 6 failures, all BUG-6 or BUG-7 | **80 / 80 pass** |
| `tests/test_qa_extra.py` with the 6 BUG-8 checks, run on the build with only BUG-6/BUG-7 fixed and then with the BUG-8 fix | 82 / 86 pass: 4 failures, all BUG-8 | **86 / 86 pass** |
| Demo closed mid-sinking, then a battle started | Game screen shook 1–2 times; ship stuck "sinking" | 0 shakes; ship shows as sunk |
| Enemy board width at 640×360 / 844×390 | 0 px / 109 px | 227 px / 255 px (headless run); 250 px / 280 px (manual run) |
| Demo close/reopen, 12–15 tries | 5 console errors | 0 errors |
| Console errors anywhere in both suites | Only the BUG-6 error | None |

The new suite's checks for each bug failed on the build without that bug's fix and pass on the fixed build. The BUG-8 test waits until the ship is actually sinking (fully hit, demo still busy) before closing the demo, so it covers an interruption during the sinking animation itself, not just during the missile's flight.

**Results with no defects found:**
- **Placement:**
  - All 1,000 edge placements stayed on the board and covered the tapped square.
  - All 208 overlapping placements were rejected, and the other ships were left untouched.
  - All 832 valid placements were accepted.
  - Shots outside the 10×10 grid were rejected.
- **Turns:**
  - A double-click or rapid clicks fired only one missile.
  - Clicks during the computer's turn and on your own board did nothing.
  - Re-firing at a used square kept your turn and didn't trigger the computer.
- **Computer opponent:** in 1,200 simulated games (400 per difficulty), there were no illegal shots, no repeated shots, and every game finished in 100 shots or fewer.
- **Win and loss:**
  - Victory came after exactly 17 hits, and the stats matched: 18 shots, 17 hits, 94% accuracy, 5/5 ships sunk.
  - Defeat came only once all 17 of your ship squares were hit, and turns alternated evenly.
  - No firing was possible after either ending.
- **Reset:**
  - Play again and Abandon cleared every ship, shot, statistic, message, marker and fleet list, and disabled Start again.
  - A computer missile in flight during Abandon didn't land on the new game.
  - The chosen difficulty was kept, which is intended.
- **Phones:**
  - No sideways scrolling at any size.
  - Tapping placed ships and fired shots at every size.
  - Upright phones had squares of 27 px or more.
- **Manual play-through (recorded):** placement, rotation, pick-up, Clear, random placement, invalid clicks, sinking, a real win (21 shots, 17 hits, 81%), Play again, Abandon, both fixes and the sideways-phone layouts all behaved correctly. No console errors or warnings appeared.

## 4. Known limitations

- **Devices:** I didn't test on a physical iPhone, iPad or Android device, only on emulated screen sizes and touch.
- **Manual coverage:** the manual play-through covered a win at Intermediate difficulty. Defeat and the other two difficulties were tested only by the automated suites.
- **Sideways phones:**
  - At 640 px wide the two battle boards are stacked rather than side by side, so you scroll between them.
  - In setup, the board sits below the setup panel, so you scroll down to place ships.
  - Both are usable but not as comfortable as on a tablet.
- **Old demo missile:** if you close the demo mid-flight and reopen it, the old missile can still be seen finishing its flight, but it no longer changes anything.
- **Demo sinking sound:** if you close the demo right after a sink starts, the short sinking sound (under 1 s) still finishes playing. It isn't cut off, because doing so would also stop any game sounds playing at the same time.
- **From the earlier report, still open:** screen readers aren't told about hits and sinks as they happen. The animation demo is still marked temporary.
