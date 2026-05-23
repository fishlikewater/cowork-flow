#!/bin/sh
set -u

RELEASE_TYPES="major minor patch premajor preminor prepatch prerelease"
RELEASE_TYPE="${1:-patch}"
TEMPLATE_VERSION_FILE="template/.cowork-flow/.version"

if [ "$#" -gt 1 ]; then
  echo "Expected at most one release type, received: $*" >&2
  exit 1
fi

case "$RELEASE_TYPE" in
  major|minor|patch|premajor|preminor|prepatch|prerelease)
    ;;
  *)
    echo "Unsupported release type: $RELEASE_TYPE" >&2
    echo "Allowed values: $RELEASE_TYPES" >&2
    exit 1
    ;;
esac

run_step() {
  echo "> $*"
  "$@"
}

run_step npm run test:all || exit $?
run_step npm version "$RELEASE_TYPE" --no-git-tag-version || exit $?

PACKAGE_VERSION=$(node -p "require('./package.json').version") || exit $?
printf '%s
' "$PACKAGE_VERSION" > "$TEMPLATE_VERSION_FILE" || exit $?

run_step git add package.json package-lock.json "$TEMPLATE_VERSION_FILE" || exit $?
run_step git commit -m "chore(release): $PACKAGE_VERSION" || exit $?
run_step git tag "v$PACKAGE_VERSION" || exit $?
run_step npm publish || exit $?
