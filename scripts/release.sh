#!/bin/sh
set -u

RELEASE_TYPES="major minor patch premajor preminor prepatch prerelease"
TEMPLATE_VERSION_FILE="template/.cowork-flow/.version"
ZCODE_PLUGIN_JSON="template/.zcode/.zcode-plugin/plugin.json"

usage() {
  echo "Usage: scripts/release.sh [release-type|--version <version>]" >&2
  echo "  release-type    one of: $RELEASE_TYPES (default: patch)" >&2
  echo "  --version <v>   publish exactly <v> instead of bumping" >&2
}

EXACT_VERSION=""
RELEASE_TYPE="patch"
if [ "$#" -gt 0 ]; then
  case "$1" in
    --version)
      [ "$#" -eq 2 ] || {
        echo "Expected --version to be followed by exactly one version" >&2
        usage
        exit 1
      }
      EXACT_VERSION="$2"
      ;;
    major|minor|patch|premajor|preminor|prepatch|prerelease)
      [ "$#" -eq 1 ] || {
        echo "Expected at most one release type, received: $*" >&2
        usage
        exit 1
      }
      RELEASE_TYPE="$1"
      ;;
    *)
      echo "Unsupported release type: $1" >&2
      usage
      exit 1
      ;;
  esac
fi

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
run_step git commit -m "chore(release): $PACKAGE_VERSION" || exit $?
run_step git tag "v$PACKAGE_VERSION" || exit $?

run_step npm publish || exit $?
