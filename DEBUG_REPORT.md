# Battleship – Debug Report

**Date:** 2026-11-19 (BUG-8 to BUG-10 added 2026-11-20) · **Tester:** Devin
**Build tested:** `main` at `e94d9a0` (before fixes) and the fix branch (after fixes).
**Environment:** Ubuntu VM, Chrome for Testing 156, run headless through Playwright (Python) and as a normal Chrome window for the manual play-through. Phones and tablets were emulated (touch, screen size). No physical devices were used.

This report covers only what was actually run. It follows the earlier QA pass in `DEBUGGING_REPORT.md`, whose five bugs (BUG-1 to BUG-5) were already fixed. The new bugs here are numbered BUG-6 to BUG-10.
- BUG-8 was found afterwards, in a follow-up check of how closing the demo during its sinking animation is cleaned up.
- BUG-9 is in the test tooling, not the game. It was found while reviewing the new release process (section 5).
- BUG-10 is also in the test tooling. It made CI fail at random, and first showed up on GitHub after the BUG-9 push.

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
- `tests/test_qa_extra.py`: new in this pass, 99 checks (80 at first, plus 7 for BUG-8 and 12 for the version label).
- `scripts/run_tests.sh`: runs both suites, as CI does.

**Manual testing:** a recorded play-through in a real Chrome window, using mouse clicks and device emulation.

## 2. Bugs found and fixed

| ID | Bug | Severity | Status |
|---|---|---|---|
| BUG-6 | Animation demo: closing and reopening it while a missile is in the air causes a JavaScript error | Low | **Fixed & verified** |
| BUG-7 | Phones held sideways: the battle boards shrink to almost nothing (0 px at 640×360), and the New Game button is cut off | Medium | **Fixed & verified** |
| BUG-8 | Animation demo: closing it during the sinking animation leaves that animation running: the ship stays stuck as "sinking", and its leftover explosions shake the real game | Low | **Fixed & verified** |
| BUG-9 | Test tooling: failures in `tests/test_game.py` didn't fail CI, and a failure there stopped `tests/test_qa_extra.py` from running | Medium (CI could pass a broken release) | **Fixed & verified** |
| BUG-10 | Test tooling: the defeat test in `tests/test_game.py` could run out of shots and time out | Low (CI failed at random) | **Fixed & verified** |

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
  - The screen shake that the sink starts kept going for up to 0.6 s after the demo closed.
  - Within 2 s of starting the battle, the game screen shook 1–2 more times. With no demo involved, it doesn't shake at all.
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
  - `closeDemo()` now clears `demo.sinking` and `demo.aim`, clears the demo board's effects, stops any screen shake already in progress (`FX.stopShake()`) and hides the demo banner.
  - The game's own effects and sounds are unchanged.

### BUG-9: Test failures could pass CI or hide other failures
This is in the test tooling, not the game.
- **Actual:**
  1. `tests/test_game.py` printed `FAIL` lines but always exited with code 0, so CI stayed green whatever failed. Devin Review found this.
  2. Once (1) was fixed, CI ran both suites as one shell step, and GitHub runs it with `bash -e`. Any failure in `tests/test_game.py` stopped the step, so `tests/test_qa_extra.py` never ran, and its failures went unreported.
- **Reproduced (2):**
  - Made a copy with one forced failing check at the end of `tests/test_game.py`, then ran the old CI step exactly as GitHub does (`bash --noprofile --norc -eo pipefail`).
  - Result: 154 PASS lines, 1 FAIL, exit code 1, and no output at all from `tests/test_qa_extra.py`.
- **Fix:**
  - `tests/test_game.py` now ends with `sys.exit(1 if fails else 0)`, matching `tests/test_qa_extra.py`.
  - The new `scripts/run_tests.sh` starts the local server if one isn't running, then runs every suite even if an earlier one fails. It lists the failed suites and exits 1 if any failed.
  - CI (`.github/workflows/tests.yml`) runs that script, and it works the same way locally.
- **Verified:**
  - On the same copy with the forced failure: both suites ran in full. That was 154 PASS lines plus 93 from the extra suite, a copy made before the newest version-label checks were added. Output ended with `Failed suites: tests/test_game.py`, exit code 1.
  - On the real branch: both suites pass, exit code 0.

### BUG-10: The defeat test could run out of shots
This is in the test tooling, not the game.
- **Actual:** the "lose" part of `tests/test_game.py` fired only at the 83 empty enemy squares and then waited for the defeat screen. The computer (Intermediate) sometimes needs more than 83 shots (up to 98 in the simulations), so the player ran out of shots, the defeat screen never came, and the test crashed after 30 s. This happened on GitHub after the push for BUG-9.
- **Reproduced:** ran the same loop at Beginner, where the computer averages 84 shots. Both games timed out after 83 shots, with the computer on 15 of 17 hits.
- **Fix:** the defeat game now runs at Advanced, where the computer needed at most 69 shots in the simulations. If even that runs out, the test hits every enemy ship except its last square, so no enemy ship is sunk and the player can't win; that gives 95 shots in total.
  - A first version of this fix (keep firing at enemy squares, leaving only one square) was flagged by the next Devin Review, and both points were correct. It could sink enemy ships, which made the "enemy ships revealed" check fail, and the computer can need 100 shots (Beginner did in the simulations), which is more turns than the player can take without winning.
- **Verified:**
  - To exercise the fallback, ran the same loop at Beginner (random shots). The 2 games that went past 83 shots (84 and 85) ended in defeat, with all 5 enemy ships shown as revealed and none sunk. 2 of 7 Beginner games needed more than 95 shots, which is why the real test uses Advanced.
  - The full run passes (section 3); its defeat came after 45 player shots.

## 3. Verification results

| Check | Before fix | After fix |
|---|---|---|
| `tests/test_game.py` (existing suite) | 154 / 154 pass | 154 / 154 pass |
| `tests/test_qa_extra.py` (new suite, first 80 checks) | 74 / 80 pass: 6 failures, all BUG-6 or BUG-7 | **80 / 80 pass** |
| `tests/test_qa_extra.py` with the first 6 BUG-8 checks, on the build with only BUG-6 and BUG-7 fixed | 82 / 86 pass: 4 failures, all BUG-8 | 86 / 86 pass |
| `tests/test_qa_extra.py` with all 7 BUG-8 checks. A second review found that a shake already in progress kept going after the demo closed. The "before" column is the first BUG-8 fix, without `FX.stopShake()`. | 86 / 87 pass: the only failure is the in-progress shake | **87 / 87 pass** |
| Demo closed mid-sinking, then a battle started | Shake kept going after close; the game screen shook 1–2 more times; ship stuck "sinking" | Shake stops on close; 0 more shakes; ship shows as sunk |
| Enemy board width at 640×360 / 844×390 | 0 px / 109 px | 227 px / 255 px (headless run); 250 px / 280 px (manual run) |
| Demo close/reopen, 12–15 tries | 5 console errors | 0 errors |
| Console errors anywhere in both suites | Only the BUG-6 error | None |
| Forced failure in `tests/test_game.py` (BUG-9) | CI step stopped and `test_qa_extra.py` never ran | Both suites ran, the failure was reported, exit code 1 |
| Full run on this branch (`scripts/run_tests.sh`) | n/a | **154 / 154 and 99 / 99 pass**, exit code 0 |

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

## 5. Release-process review findings (2026-11-20)

Devin Review raised four findings on the release changes. Each one was checked:

| Finding | Verdict | What was done |
|---|---|---|
| A failure in the first suite skips the extra QA suite | **Real: BUG-9** | Fixed, see above. |
| Unversioned merges go live immediately | **Real gap in the process** (not a game defect) | GitHub Pages deploys every merge to `main`, so a pull request that changed the game without raising its version would go live under the old version number. `RELEASING.md` now says clearly that merging deploys, and that tags and GitHub Releases only track versions and hold release notes. CI's new `scripts/release.sh bumped` step fails any pull request that changes `index.html` without raising the version. Checked locally: it passes this branch (none → 1.0.1), passes an unchanged `index.html`, and compares versions correctly (1.0.10 > 1.0.9; 1.0.1 is not higher than 1.0.1). |
| The version label is missing on narrow phones | **Intended, not a defect** | Below 461 px the existing header already hides the whole title block (`.brand-text`, with the "Battleship" title) to leave room for the sound, demo and New game buttons. The label belongs to that block, so it hides with the title, and showing it would mean crowding those buttons or changing the header design. The version is still in the page as `<meta name="app-version">`. The test now states this: at 1280, 1024 and 540 px it requires the label to be visible inside the header; at 390 px it requires it to be hidden. |
| Closing the demo cuts off a battle shake | **Real, but not a meaningful problem; no change** | Reproduced 3 times: fire a hit and open the demo while the missile is in flight. The hit lands while the demo is open, and its shake starts while the battle screen is hidden (`body.demo-open main { visibility: hidden }`). Closing the demo about 190 ms later ends the shake, so the remaining ~0.45 s is never seen. This only affects a shake that started out of view. Shots, turns and results are unchanged, and the shakes from the sink explosions that follow still play. Keeping the shake running would let a demo shake leak into the game again (BUG-8). |

The next two review rounds raised four more findings (the first row covers two of them):

| Finding | Verdict | What was done |
|---|---|---|
| The defeat test can fail the "enemy ships revealed" check, and can time out if the computer needs 100 shots | **Real, in the first BUG-10 fix** | Reworked, see BUG-10. |
| At Advanced the computer can win on its 20th shot, while the test waits for a 21st player turn before its mid-game screenshot | **Real, in the reworked BUG-10 fix** (rare: it needs a near-perfect computer game) | That wait now also accepts the game being over, like every other wait in the loop. |
| `scripts/run_tests.sh` reuses any server already on port 8080, which could be serving another checkout | **Real** (test tooling) | The script now checks that the server's `index.html` matches this checkout and stops with an error if it doesn't. Checked with a copy whose `index.html` differed: it exited 1 with that message before running any test. |
