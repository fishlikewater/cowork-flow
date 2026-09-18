#!/bin/sh
set -u

RELEASE_TYPES="major minor patch premajor preminor prepatch prerelease"
TEMPLATE_VERSION_FILE="template/.cowork-flow/.version"
SELF_VERSION_FILE=".cowork-flow/.version"
ZCODE_PLUGIN_JSON="template/.zcode/.zcode-plugin/plugin.json"

usage() {
  echo "Usage: scripts/release.sh [release-type|--version <version>] [--no-publish]" >&2
  echo "  release-type    one of: $RELEASE_TYPES (default: patch)" >&2
  echo "  --version <v>   publish exactly <v> instead of bumping" >&2
  echo "  --no-publish    commit and tag the release without running npm publish" >&2
}

EXACT_VERSION=""
RELEASE_TYPE="patch"
NO_PUBLISH=0
# release-type and --version are mutually exclusive and at most one may appear;
# --no-publish is a repeatable flag and may be given anywhere on the line.
TARGET_SET=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --no-publish)
      NO_PUBLISH=1
      shift
      ;;
    --version)
      [ "$#" -ge 2 ] || {
        echo "Expected --version to be followed by exactly one version" >&2
        usage
        exit 1
      }
      [ "$TARGET_SET" -eq 0 ] || {
        echo "Expected at most one release type or --version, received: $*" >&2
        usage
        exit 1
      }
      EXACT_VERSION="$2"
      TARGET_SET=1
      shift 2
      ;;
    major|minor|patch|premajor|preminor|prepatch|prerelease)
      [ "$TARGET_SET" -eq 0 ] || {
        echo "Expected at most one release type or --version, received: $*" >&2
        usage
        exit 1
      }
      RELEASE_TYPE="$1"
      TARGET_SET=1
      shift
      ;;
    *)
      echo "Unsupported release type: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [ -n "$EXACT_VERSION" ]; then
  printf '%s' "$EXACT_VERSION" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+([-.+][0-9A-Za-z][0-9A-Za-z.-]*)?$' || {
    echo "Invalid version: $EXACT_VERSION" >&2
    usage
    exit 1
  }
fi

run_step() {
  echo "> $*"
  "$@"
}

# Live Skill replicas (.agents/skills, .claude/skills) are gitignored and
# drift from template/skills across checkouts. The full test gate loads every
# replica and fails on any conflict, so refresh them before running it.
run_step npm run source:refresh || exit $?

# Uncommitted AGENTS.md edits must not be silently clobbered below.
if ! git diff --quiet -- AGENTS.md; then
  echo "error: AGENTS.md has uncommitted changes; commit or stash first" >&2
  exit 1
fi

# This repository is its own instance: mirror template/ into .cowork-flow so
# the released package ships what this repo actually runs. sync --force
# overwrites AGENTS.md customization slots (项目名称/技术栈) that the template
# does not carry — restore them from HEAD instead of releasing the template
# defaults.
run_step node bin/cowork-flow.js sync --force || exit $?
if ! git diff --quiet -- AGENTS.md; then
  git checkout -- AGENTS.md
  echo "note: sync --force overwrote AGENTS.md customization; restored from HEAD" >&2
fi

# npm test covers package tests only; the Python services suite is the
# runtime gate for the shipped scripts and has caught whole-platform
# regressions (1.2.0 Windows encodings) that the Node tests cannot see.
python3 -m pytest tests/ -q || python -m pytest tests/ -q || exit $?

run_step npm run test:all || exit $?
if [ -n "$EXACT_VERSION" ]; then
  CURRENT_VERSION=$(node -p "require('./package.json').version") || exit $?
  if [ "$CURRENT_VERSION" != "$EXACT_VERSION" ]; then
    run_step npm version "$EXACT_VERSION" --no-git-tag-version || exit $?
  else
    run_step echo "package.json already at $EXACT_VERSION"
  fi
else
  run_step npm version "$RELEASE_TYPE" --no-git-tag-version || exit $?
fi

PACKAGE_VERSION=$(node -p "require('./package.json').version") || exit $?
printf '%s\n' "$PACKAGE_VERSION" > "$TEMPLATE_VERSION_FILE" || exit $?

# In this repository's own checkout the live runtime is a gitignored mirror of
# template/. sync --force ran before the bump, so its marker would trail by one
# version and doctor's distribution check would report drift until the next
# source:refresh. Keep it in step here; installs without that file skip.
if [ -f "$SELF_VERSION_FILE" ]; then
  printf '%s\n' "$PACKAGE_VERSION" > "$SELF_VERSION_FILE" || exit $?
fi

# The changelog must already carry an entry for the version being released;
# release:check (package tests) enforces the same on the current version.
grep -q "^## ${PACKAGE_VERSION} " CHANGELOG.md || {
  echo "error: CHANGELOG.md has no entry for version ${PACKAGE_VERSION}" >&2
  exit 1
}

GIT_ADD_FILES="package.json package-lock.json $TEMPLATE_VERSION_FILE"
if [ -f "$ZCODE_PLUGIN_JSON" ]; then
  node -e "const fs=require('fs');const p='$ZCODE_PLUGIN_JSON';const j=JSON.parse(fs.readFileSync(p));j.version='$PACKAGE_VERSION';fs.writeFileSync(p,JSON.stringify(j,null,2)+'\n')" || exit $?
  GIT_ADD_FILES="$GIT_ADD_FILES $ZCODE_PLUGIN_JSON"
fi

run_step git add $GIT_ADD_FILES || exit $?
echo "> git commit -m \"chore(release): $PACKAGE_VERSION\""
if COMMIT_OUTPUT=$(git commit -m "chore(release): $PACKAGE_VERSION" 2>&1); then
  [ -n "$COMMIT_OUTPUT" ] && printf '%s\n' "$COMMIT_OUTPUT"
else
  COMMIT_RC=$?
  printf '%s\n' "$COMMIT_OUTPUT"
  case "$COMMIT_OUTPUT" in
    *"nothing to commit"*)
      echo "nothing to commit; release files already at $PACKAGE_VERSION, continuing"
      ;;
    *)
      exit "$COMMIT_RC"
      ;;
  esac
fi
if git rev-parse -q --verify "refs/tags/v$PACKAGE_VERSION^{commit}" >/dev/null 2>&1; then
  if [ "$(git rev-parse "refs/tags/v$PACKAGE_VERSION^{commit}")" = "$(git rev-parse HEAD)" ]; then
    echo "tag v$PACKAGE_VERSION already exists at HEAD, continuing"
  else
    echo "error: tag v$PACKAGE_VERSION already exists at a different commit" >&2
    exit 1
  fi
else
  run_step git tag "v$PACKAGE_VERSION" || exit $?
fi

if [ "$NO_PUBLISH" -eq 1 ]; then
  echo "> npm publish skipped (--no-publish)"
  echo "note: tag v$PACKAGE_VERSION is local; publish with 'npm publish' or 'gh release create v$PACKAGE_VERSION'"
else
  run_step npm publish || exit $?
fi
