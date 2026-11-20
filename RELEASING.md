# Releasing

The game uses [Semantic Versioning](https://semver.org/): **MAJOR.MINOR.PATCH**.

| Part | Increase it when… | Example |
|---|---|---|
| PATCH | you fix bugs, change wording, or change tests and docs, with no new gameplay | 1.0.0 → 1.0.1 |
| MINOR | you add a feature without breaking how the game is played, such as a new difficulty or a new setting | 1.0.1 → 1.1.0 |
| MAJOR | you make a change that breaks something players or saved settings rely on, such as new rules or a new board size | 1.4.2 → 2.0.0 |

The version lives in one place, `<meta name="app-version" content="X.Y.Z">` in `index.html`. The same number is shown under the title in the game (`id="app-version"`), and it heads the newest entry in `CHANGELOG.md`. `scripts/release.sh check` makes sure all three agree.

## Hosting

The live game is published by **GitHub Pages** from the `main` branch, root folder: https://jonahthecodah.github.io/battleship-game/. Every push to `main` is published automatically within a few minutes. **Merging to `main` is therefore the deployment.** Only merge pull requests that are ready to go live.

## Release steps

1. **Pull request.** Make every change on a branch and open a pull request to `main`. Never push directly to `main`.
2. **Version and notes.** In the same pull request:
   - Raise the version in both places in `index.html` (the `<meta>` tag and the `app-version` label).
   - Add a new `## [X.Y.Z] - YYYY-MM-DD` entry at the top of `CHANGELOG.md` with short release notes under *Fixed*, *Added* or *Changed*.
   - A pull request that shouldn't be released yet can leave the version alone, and it will go out with the next release.
3. **Automated tests.** The **Tests** workflow (`.github/workflows/tests.yml`) runs the version check, `tests/test_game.py` and `tests/test_qa_extra.py` on every pull request. It must be green.
4. **Human approval.** The owner reviews and approves the pull request, then merges it. Merging deploys it.
5. **Tag.** Tag the merge commit on `main` and push the tag:
   ```bash
   git checkout main && git pull
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```
6. **Release notes and live check.** Pushing the tag starts the **Release** workflow (`.github/workflows/release.yml`). It:
   - checks that the tag matches the version in `index.html`, and that the tag is on `main`
   - waits until the live site serves that version (`scripts/release.sh verify-live X.Y.Z`)
   - publishes a GitHub release using the notes from `CHANGELOG.md`

   Finally, open the live site and check that the version under the title is correct.

## One-time GitHub settings (repository owner)

Steps 3 and 4 are only enforced once `main` is protected. In **Settings → Rules → Rulesets → New branch ruleset**, target the default branch (`main`) and enable:
- **Require a pull request before merging**, with **Required approvals: 1**.
- **Require status checks to pass**: add the **tests** check. It appears after the workflow has run once.
- **Block force pushes**.

GitHub doesn't let you approve your own pull request. If you open a pull request yourself, add yourself to the ruleset's **bypass list** so you can still merge after the tests pass. Pull requests opened by Devin can be approved normally.

Optionally, add a **tag ruleset** for `v*` that blocks deletion and updates, so released tags can't be moved.

## Rolling back

To undo a bad release:
1. Open a pull request that reverts the change and raises the PATCH version, for example 1.0.2.
2. Release it with the steps above.

Don't move or reuse an existing tag.
