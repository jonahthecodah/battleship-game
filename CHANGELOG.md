# Changelog

All notable changes to the Battleship game. Versions follow [Semantic Versioning](https://semver.org/): MAJOR.MINOR.PATCH. The release process is described in `RELEASING.md`.

## [1.0.1] - 2026-11-20

### Fixed
- Phones held sideways: the battle boards no longer shrink to almost nothing, and the header buttons fit on screen.
- Animation demo: closing and reopening it while a missile is in the air no longer causes a JavaScript error.
- Animation demo: closing it during the sinking animation now stops its effects. The ship is no longer stuck "sinking", and leftover explosions no longer shake the game.

### Added
- The game version is shown under the title (for example `v1.0.1`).
- Extra automated tests, and automatic test runs on every pull request.
- A documented release process (`RELEASING.md`) and this changelog.

## [1.0.0] - 2026-11-13

First stable release (commit `e94d9a0`), the game as published on GitHub Pages.

- Single-player Battleship against the computer on a 10×10 board, for computers, tablets and phones.
- Manual or random fleet placement, three computer difficulty levels, sound effects and animated battle effects.
- Victory and defeat screens with statistics, keyboard play and a reduced-motion mode.
