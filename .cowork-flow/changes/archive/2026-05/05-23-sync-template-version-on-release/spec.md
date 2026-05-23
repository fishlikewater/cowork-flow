# Release Template Version Sync Spec

## Version sync

- Given `package.json` version is `0.0.5`
- When `scripts/release.sh patch` runs successfully
- Then `template/.cowork-flow/.version` MUST be updated to the new package version before publish.
- And the release commit/tag MUST include `package.json`, `package-lock.json`, and `template/.cowork-flow/.version`.

## Command order

- The script MUST run verification before changing versions.
- The script MUST stop if verification fails.
- The script MUST stop if version update, template version sync, git commit/tag, or publish fails.
- The script MUST reject unsupported release types before running any npm command.

## Safety

- The script MUST still accept one optional npm version release type.
- The script MUST use the computed package version as the source of truth for `.version`.
