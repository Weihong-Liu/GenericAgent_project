#!/usr/bin/env bash
# Build the TypeScript / Ink frontend and stage the bundle for the wheel.
#
#   $ scripts/build_tui.sh
#
# Steps:
#   1. ``npm install`` inside ``ui-tui/`` (if node_modules is missing)
#   2. ``npm run type-check && npm test && npm run build``
#   3. Copy ``ui-tui/dist/bundle.js`` to
#      ``src/generic_agent_engineered/_tui_dist/bundle.js`` so
#      ``setuptools`` includes it in the wheel via package-data.
#
# Honours the ``SKIP_INSTALL=1`` env var to bypass ``npm install`` even
# when ``node_modules`` is missing. Useful for offline / sandboxed CI
# runs where deps were vendored ahead of time. When ``node_modules``
# already exists, ``npm install`` is skipped regardless of this flag.
#
# Requires bash (uses ``set -o pipefail``); does not run on minimal
# ash/sh-only images.
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT_DIR="$( cd "${SCRIPT_DIR}/.." && pwd )"
UI_DIR="${ROOT_DIR}/ui-tui"
DIST_DIR="${ROOT_DIR}/src/generic_agent_engineered/_tui_dist"
BUNDLE="${UI_DIR}/dist/bundle.js"

if [[ ! -d "${UI_DIR}" ]]; then
  echo "build_tui: ${UI_DIR} not found" >&2
  exit 1
fi

cd "${UI_DIR}"

if [[ -z "${SKIP_INSTALL:-}" ]] && [[ ! -d node_modules ]]; then
  echo "build_tui: installing npm deps"
  npm install
fi

echo "build_tui: type-check"
npm run type-check
echo "build_tui: test"
npm test --silent
echo "build_tui: bundle"
npm run build

if [[ ! -f "${BUNDLE}" ]]; then
  echo "build_tui: ${BUNDLE} did not appear after build" >&2
  exit 1
fi

mkdir -p "${DIST_DIR}"
cp "${BUNDLE}" "${DIST_DIR}/bundle.js"
# bundle.js is loaded by ``node bundle.js`` from the launcher, never
# exec'd directly, so the file does not need an executable bit.
echo "build_tui: staged $(wc -c < "${DIST_DIR}/bundle.js") bytes -> ${DIST_DIR}/bundle.js"
