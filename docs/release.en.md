# Release and maintenance

[中文](release.md) | English

This document is for maintainers of the cowork-flow repository. Regular users only need the [README](../README.en.md); before submitting code, read [Contributing](../CONTRIBUTING.en.md) first.

## Pre-release checks

Choose tests according to the scope of the change; you do not have to start from the heaviest command every time.

| Command | When to run |
|---|---|
| `npm run test:fast` | The minimum check after everyday changes |
| `npm run test:smoke` | Verifies that the CLI loads and runs a minimal initialization after installation from a real npm tarball |
| `npm run test:integration` | Changes to `project init` / `project sync` |
| `npm run test:node:full` | Changes to the Node CLI, installers, or shared modules |
| `npm run test:template` | Changes to core paths of the project template |
| `npm run test:template:full` | Changes to the Python runtime, specs, hooks, or host adaptations |
| `npm run test:windows:core` | Anything involving Windows, paths, line endings, or release behavior |
| `python -m pytest -q` | Changes to `template/.cowork-flow/`, `tests/`, or Python contracts |
| `npm run test:all` | The full Node, template, and packaging check when preparing a release |
| `npm run release:check` | The release confidence gate: `test:all` plus checks that tests cannot express — drift of the self-instance and live-copy assets (`.claude/**`, `.codex/**`, skills) from `template/`, and `error`-level problems from `doctor --all` |

When platform prerequisites are not met, tests may skip explicitly. Skips must be recorded as they are and never treated as passes.

For stability-related changes, run the template tests repeatedly:

```bash
COWORK_TEMPLATE_TEST_REPEAT=3 \
COWORK_TEMPLATE_TEST_SEED=<fixed-value> \
npm run test:template:full
```

## Release commands

| Command | Behavior |
|---|---|
| `npm run release` | Release a patch version |
| `npm run release -- minor` | Release a minor version |
| `npm run release -- --version 0.1.0` | Use the given version number and skip the automatic bump |
| `npm run release -- minor --no-publish` | Finish the version, commit, and tag, push the commit and tag, but do not run `npm publish`; CI publishes |
| `npm run release -- --dry-run` | Run the pre-release checks and stop before the version bump |

`npm run release` runs `test:all` internally, not `release:check`: before running the tests it executes `source:refresh` and `sync --force`, so drift is already erased and only the `doctor` half is missing. Before releasing, run `release:check` separately as the standard flow requires.

`--dry-run` is not a read-only command. It first requires a clean Git worktree and index, then runs `source:refresh` and `sync --force`, so it may refresh ignored runtime copies in the repository and temporarily overwrite and then restore `AGENTS.md`. It does not change version files, commit, tag, or publish; if local changes exist when the check starts, the script stops before any refresh.

The target version is only known after the bump, so `--dry-run` does not run the CHANGELOG version-section gate.

## Standard release flow

1. Confirm that the worktree and the changelog are as expected.
2. Run `npm run release:check` and `git diff --check`.
3. For stability changes, repeat the template tests as described in the previous section.
4. Run `npm run release -- <release-type>`; the CI route uses `--no-publish`, which pushes the tag to CI.
5. The script syncs `package.json`, the lockfile, `template/.cowork-flow/.version`, and every plugin manifest bundled with the package.
6. Check the commit and tag, then publish through the CI route below.

`scripts/release.sh` checks after the bump whether `CHANGELOG.md` has a section for the current version. This check happens after the version has already changed; if it fails, restore `package.json`, `package-lock.json`, and `.version` with the rollback commands printed by the script, then run `npm run source:refresh`.

## CI publishing route

We recommend letting GitHub Actions run `npm publish`:

1. Run `npm run release -- <release-type> --no-publish` locally. The script completes the checks, the version, the commit, and the tag, then pushes the branch and tag:

   ```bash
   git push
   git push origin v<v>
   ```

2. Pushing the tag triggers `.github/workflows/publish.yml`. After the Ubuntu and Windows verification jobs pass, the workflow publishes only from the existing `v<version>` tag and verifies that the tag, `package.json`, and `template/.cowork-flow/.version` agree on the version.

3. If you want release notes for this tag, create them manually (not required for publishing):

   ```bash
   gh release create v<v>
   ```

Do not run `gh release create` while the tag does not exist on the remote, or GitHub may create the tag from the latest commit on the default branch and point the release at the wrong commit.

Repeated triggers on the same tag are serialized by the concurrency lock, so they never race; if that version is already published to npm, a repeated run is rejected by npm at the `npm publish` stage, which is expected. To publish again after a failed CI run, rerun with `workflow_dispatch` on the same tag.

Pull requests and releases use the same core gates.

Release credentials use **Trusted Publishing**: the publish job declares `id-token: write`, hands a GitHub OIDC token to npm in exchange for short-lived credentials, and no long-lived token is stored in the repository. Register it on the npm package page (Settings → Trusted Publishers), declaring the repository `fishlikewater/cowork-flow` and the workflow file `publish.yml`.

That exchange is implemented by the npm CLI (since 11.5.1), while Node 20 bundles npm 10, so **only the publish job runs on Node 24**; the two verification jobs still use Node 20, matching the `engines` declared in `package.json`.

The publish job's `setup-node` **keeps `registry-url`** but supplies no `NODE_AUTH_TOKEN`. npm starts the OIDC exchange only after reading a registry from `.npmrc` — remove it and publishing fails with `ENEEDAUTH` without ever contacting the token endpoint. The `${NODE_AUTH_TOKEN}` placeholder written by `setup-node` is **deliberately left unresolved**: npm first tries the exchange with that empty credential and falls back to it only when the exchange is rejected.

Earlier versions used the `NPM_TOKEN` secret. With two-factor authentication enabled on the account, a classic token cannot complete an interactive OTP, so CI publishing failed with `EOTP` — which is also why we switched to Trusted Publishing. The verification jobs (Ubuntu / Windows) touch no release credentials and only run `release:check`.

## Maintainer commands

```bash
npm run source:refresh:dry-run  # Preview refreshing the source repository's runtime copies
npm run source:refresh          # Refresh the root .cowork-flow, .agents/skills, .claude/skills
npm run icons:export            # Re-export PNGs from assets/icon.svg
```

`source:refresh` treats `template/.cowork-flow/` and `template/skills/` as the only distribution source and does not overwrite tasks, plans, developer identity, project configuration, or custom Skills. After refreshing, run:

```bash
./.cowork-flow/run doctor --all --json
```

`icons:export` requires Edge or Chrome on the machine; `COWORK_FLOW_BROWSER` can point at an executable. When the browser is missing, the command fails rather than treating the old images as updated.
