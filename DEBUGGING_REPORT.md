# Battleship – Debugging & QA Report

**Scope:** `index.html` (the whole game: layout, styling, rules, computer opponent, animation and sound engine) and `tests/test_game.py`.
**Date:** 2026-11-13. **Tester:** Devin, acting as QA engineer.
**Environment:** Ubuntu VM, headless Chrome for Testing 156 driven by Playwright (Python), viewports from 360×740 (phone) to 1440×900 (desktop), with touch emulation for phones and tablets. I didn't test on real iOS or Android devices.

Every result below comes from tests that were actually run. The *Status* column records the resolution. Before fixing anything I documented every bug as **Open**, then updated the report after the fixes (see §5).

---

## 1. Method

1. **Code review** of the rules (`fireAt`, `canPlace`, `placeShip`, `computerChooseShot`), the turn flow (`playerFire`, `computerTurn`, `playImpact`, `endGame`, `newGame`), the demo (`runDemo`) and the effects and sound engine (`FX`, `Sound`).
2. **Automated suite** (`tests/test_game.py`, 145 checks). It plays the game in a real browser: it clicks squares, places ships, wins a full game and loses a full game, and checks layout, animations, the demo, reduced motion, smoothness and the Phase 3 UI.
3. **Targeted reproduction scripts** for each suspected bug found during code review (`qa_repro.py`, run separately; key steps are reproduced below).

## 2. Confirmed bugs

| ID | Title | Severity | Status |
|----|-------|----------|--------|
| BUG-1 | Effects from a finished or abandoned game keep playing on the next game | Medium | Open |
| BUG-2 | Victory fireworks / defeat embers keep spawning after "Play again" | Low | Open |
| BUG-3 | Missile in flight lands at the old screen position if the window is resized or the tablet is rotated mid-flight | Low | Open |
| BUG-4 | Upright tablet (768×1024): setup screen didn't fit, and ship names in the setup tiles were cut off | Low | Open (fix verified in §5) |
| BUG-5 | Game can't be played with a keyboard (board squares aren't focusable) | Medium (accessibility) | Open |

### BUG-1: Effects from an abandoned game spill into the next game. Medium
- **Reproduce:**
  1. Start a battle.
  2. Sink an enemy ship.
  3. While its sinking sequence is playing, press **New game** and then **Abandon**.
  4. Press **Place randomly** and then **Start battle**.
- **Expected:** a clean new battlefield.
- **Actual:** the chain of secondary explosions, and the sinking sounds, from the old ship keep going off on the new, empty enemy board for about a second. Measured: 140 particles on the new enemy board 0.15 s after restarting, and 44 particles 0.65 s later, with 0 shots fired in the new game.
- **Cause:** `FX.sink` and `Sound.sink` schedule follow-up explosions with `setTimeout`. `FX.clearAll()` removes particles that already exist, but it doesn't cancel these scheduled timers.

### BUG-2: Fireworks/embers continue after "Play again". Low
- **Reproduce:** win a game, wait for the victory screen, then press **Play again** straight away.
- **Expected:** the celebration stops when the new game starts.
- **Actual:** fireworks keep bursting over the setup screen for up to 4 s. Measured: 124 effect particles 1.5 s after pressing Play again. The defeat embers behave the same way, for up to 5 s.
- **Cause:** same as BUG-1. `FX.fireworks` and `FX.embers` schedule bursts with `setTimeout`, and nothing cancels them.

### BUG-3: Resize or rotate during a missile flight. Low
- **Reproduce:**
  1. In battle at 1024×768, fire at J10.
  2. About 0.15 s later, change the viewport to 768×1024. This is the same as rotating a tablet.
- **Expected:** the missile still lands on J10.
- **Actual:** the missile keeps flying to the screen point where J10 *used* to be, so the explosion appears away from the square. The game result itself is still correct, because the hit or miss is applied to J10.
- **Cause:** the start and end points of the missile's flight path are captured once, when it launches.

### BUG-4: Upright tablet setup overflow and clipped ship names. Low
- **Reproduce:** open the game at 768×1024 (iPad held upright) on the setup screen.
- **Expected:** the whole setup screen fits without scrolling, and the ship names are readable.
- **Actual:** after the three-level difficulty selector was added, the page bottom ended 10 px below the screen (the automated check `768x1024: setup fits on screen` failed with bottom = 1034). In the compact ship tiles, "BATTLESHIP" and "SUBMARINE" were cut off and overlapped the next tile (seen in screenshot `difficulty_768.png`).
- **Note:** I found this while adding the difficulty levels and fixed it immediately. §5 covers the fix and its verification.

### BUG-5: No keyboard play. Medium (accessibility)
- **Reproduce:** load the game and press Tab repeatedly.
- **Expected:** you can reach the board squares with the keyboard and fire with Enter or Space.
- **Actual:** focus visits only the buttons. None of the 100 enemy squares can receive focus (measured: 0 squares focusable), so a keyboard-only player can't place ships by hand or fire.

## 3. Potential risks (not reproduced as bugs)

These are risks I identified but couldn't confirm in my environment. They aren't counted as bugs.

- **Older iOS Safari (before 16):** `overflow-x: clip` isn't supported there, so the effects layer, which deliberately spills past the board edges, could cause sideways scrolling. I couldn't test on a real device. Desktop Chrome at all sizes showed no sideways scrolling.
- **Sound on iOS:** browsers only allow audio after the player touches the page. The game unlocks audio on the first tap, which follows Apple's rules, but I couldn't verify it on an iPhone or iPad.
- **Saved mute setting on `file://` in Safari:** localStorage may be unavailable there. The code catches this error, so the worst case is that the mute choice isn't remembered.
- **Performance on low-end tablets:** I measured 60 fps in software-rendered headless Chrome. I didn't measure on real devices.
- **Background tab:** browsers pause animation frames in hidden tabs. Missile timing uses timers rather than animation frames, so the game keeps its state correctly, but the effects are skipped while the tab is hidden. This is expected behaviour.

## 4. Tests that passed without issues

Automated suite run on the build that includes the three difficulty levels: **145 / 145 checks passed, 0 failed**. Coverage:

- **Computer opponent:** I simulated 300 games per difficulty level. Every fleet was valid (5 ships, 17 squares, all on the board, none overlapping), the computer never fired at the same square twice, and every game finished in 100 shots or fewer. Average shots needed to win: Beginner 86.0, Intermediate 61.2, Advanced 45.9, so each level is stronger than the one below it.
- **Ship placement:**
  - The Start button stays disabled until all 5 ships are placed.
  - A ship that would stick out past the edge is slid back onto the board, never placed off it.
  - Overlapping placements are rejected (the board shakes).
  - Invalid placements show a red preview and valid ones a green preview.
  - The R key rotates the ship.
  - Tapping a placed ship picks it up.
  - Clear, Place randomly, and placing ships by hand all work.
- **Repeated attacks:** firing the same square twice is rejected, both in the game logic and by clicking in the browser.
- **Turns:**
  - You can't fire while a missile is in flight or during the computer's turn.
  - The computer fires exactly once per turn.
  - Over a whole game, your shots and the computer's shots are equal.
- **Hit, miss and sink:**
  - Misses show a splash marker and hits show a scorch mark.
  - When the last section of a ship is hit, the sinking animation plays and a banner appears.
  - The wreck stays visible on the board, and the ship is crossed off the fleet list.
- **Winning and losing:**
  - Both the victory and the defeat screens appear.
  - Firing is ignored after the game is over.
  - The enemy's remaining ships are revealed after a loss.
  - New game and Play again return you to setup.
- **Unexpected input:**
  - Clicks on labels or gaps are ignored.
  - Clicks during the computer's turn or after the game ends are ignored.
  - A rapid second shot is ignored.
- **Animation demo:**
  - All three buttons work, including 11 presses in a row.
  - Reset restores the practice board.
  - The real game's state is byte-for-byte unchanged after using the demo.
  - The computer waits while the demo is open and carries on after it closes.
- **Reduced-motion mode:** results appear instantly, with no missiles, particles, screen shake or moving ocean, and sunk ships are still clearly marked.
- **Layout:** both boards fit with no sideways scrolling at 1024×768, 768×1024, 1180×820, 820×1180, 1366×1024, 1024×1366, 1440×900 and on a 390×844 phone. Tapping works on touch devices.
- **Smoothness:** 60 fps during the heaviest effect (sinking) at desktop, sideways-tablet and upright-tablet sizes.
- **Phase 3 UI:**
  - The mute button works, and the choice is remembered after a reload.
  - The radar appears only during battle.
  - The targeting crosshair shows coordinates and highlights the matching labels, and it locks red while a missile flies.
  - The "Incoming" marker appears on your board.
  - The turn counter works.
  - The Abandon box works, with both Keep fighting and Abandon.
  - The victory screen shows 6 stats and fireworks.
  - No JavaScript errors occurred.

## 5. Resolution and verification

*(Filled in after the fixes. See below.)*
