#!/bin/sh
set -u

RELEASE_TYPES="major minor patch premajor preminor prepatch prerelease"
RELEASE_TYPE="${1:-patch}"

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
run_step npm version "$RELEASE_TYPE" || exit $?
run_step npm publish || exit $?
