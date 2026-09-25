#!/usr/bin/env bash
# Dev container / GitHub Codespaces lifecycle for Ciaren.
#
#   ciaren.sh install  postCreateCommand: install this version of Ciaren from
#                      PyPI (or build it from this checkout if it is
#                      unreleased) into a virtualenv.
#   ciaren.sh start    postStartCommand: start `ciaren serve` on port 8055 in
#                      the background, logging to $DATA_DIR/ciaren.log.
#
# The virtualenv path must match the PATH entry in devcontainer.json remoteEnv.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# /workspaces is the large persistent volume of a codespace; the container's
# home directory is too small for Ciaren's dependencies (scipy, scikit-learn,
# MLflow). Both paths sit next to the checkout, so they never show up in
# `git status`.
STATE_DIR="/workspaces/.ciaren"
VENV="$STATE_DIR/venv"
DATA_DIR="$STATE_DIR/data"
PORT=8055

pick_python() {
  # Ciaren needs Python 3.12 or newer; use the first interpreter that fits.
  local candidate
  for candidate in python3.13 python3.12 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 &&
      "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>/dev/null; then
      echo "$candidate"
      return 0
    fi
  done
  echo "Ciaren needs Python 3.12 or newer, and none was found." >&2
  return 1
}

install() {
  mkdir -p "$STATE_DIR"
  "$(pick_python)" -m venv "$VENV"
  local version
  version="$(grep -m1 '^version = ' "$REPO/backend/pyproject.toml" | cut -d '"' -f2)"
  # The released wheel on PyPI already bundles the built editor, so a
  # codespace for a released version is ready in about a minute.
  if curl --silent --fail --output /dev/null "https://pypi.org/pypi/ciaren/$version/json"; then
    "$VENV/bin/python" -m pip install --quiet --no-cache-dir "ciaren==$version"
    return 0
  fi
  # An unreleased version (a development branch) needs Node.js to build the
  # editor from this checkout.
  echo "ciaren==$version is not on PyPI yet; building it from this checkout."
  if ! command -v npm >/dev/null 2>&1; then
    echo "Building an unreleased version needs Node.js 20+, which this image does not include." >&2
    echo "Install Node.js, then run: bash .devcontainer/ciaren.sh install" >&2
    return 1
  fi
  npm ci --prefix "$REPO/frontend" --no-audit --no-fund
  npm run build --prefix "$REPO/frontend"
  "$VENV/bin/python" -m pip install --quiet --no-cache-dir --editable "$REPO/backend"
}

start() {
  if curl --silent --fail "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
    echo "Ciaren is already running on port $PORT."
    return 0
  fi
  if [ -n "${CODESPACE_NAME:-}" ] && [ -n "${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-}" ]; then
    # The browser loads the editor from the forwarded URL and sends it as the
    # Origin of every write. Trust exactly that origin, not the forwarding
    # domain every codespace shares, so the CSRF guard keeps refusing others.
    export CIAREN_CORS_ORIGINS="[\"https://${CODESPACE_NAME}-${PORT}.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}\"]"
  fi
  mkdir -p "$DATA_DIR"
  cd "$DATA_DIR"
  # setsid + nohup detach the server from the lifecycle command's session,
  # which the dev container runtime tears down when this script returns.
  setsid nohup "$VENV/bin/ciaren" serve --host 127.0.0.1 --port "$PORT" \
    >"$DATA_DIR/ciaren.log" 2>&1 </dev/null &
  echo "Ciaren is starting on port $PORT (log: $DATA_DIR/ciaren.log)."
}

url() {
  # postAttachCommand: print the editor link in the terminal, as a fallback
  # when the preview tab does not open by itself.
  for _ in $(seq 1 60); do
    curl --silent --fail "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && break
    sleep 2
  done
  if [ -n "${CODESPACE_NAME:-}" ] && [ -n "${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-}" ]; then
    echo "Ciaren editor: https://${CODESPACE_NAME}-${PORT}.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}"
  else
    echo "Ciaren editor: http://127.0.0.1:$PORT"
  fi
}

case "${1:-}" in
  install) install ;;
  start) start ;;
  url) url ;;
  *)
    echo "usage: $0 {install|start|url}" >&2
    exit 2
    ;;
esac
