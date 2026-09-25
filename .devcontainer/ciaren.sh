#!/usr/bin/env bash
# Dev container / GitHub Codespaces lifecycle for Ciaren.
#
#   ciaren.sh install  postCreateCommand: install this version of Ciaren from
#                      PyPI (or build it from this checkout if it is
#                      unreleased) into a virtualenv.
#   ciaren.sh serve    postAttachCommand: run `ciaren serve` on port 8055 in the
#                      foreground while the editor is attached (processes a
#                      postStartCommand leaves in the background are killed
#                      when it returns), or print the link if it is running.
#   ciaren.sh start    Manual restart: start `ciaren serve` in the background,
#                      logging to $DATA_DIR/ciaren.log.
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

editor_url() {
  if [ -n "${CODESPACE_NAME:-}" ] && [ -n "${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-}" ]; then
    echo "https://${CODESPACE_NAME}-${PORT}.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}"
  else
    echo "http://127.0.0.1:$PORT"
  fi
}

prepare_env() {
  if [ -n "${CODESPACE_NAME:-}" ] && [ -n "${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-}" ]; then
    # The browser loads the editor from the forwarded URL and sends it as the
    # Origin of every write. Trust exactly that origin, not the forwarding
    # domain every codespace shares, so the CSRF guard keeps refusing others.
    export CIAREN_CORS_ORIGINS="[\"$(editor_url)\"]"
  fi
  mkdir -p "$DATA_DIR"
  cd "$DATA_DIR"
}

is_running() {
  curl --silent --fail "http://127.0.0.1:$PORT/health" >/dev/null 2>&1
}

serve() {
  if is_running; then
    echo "Ciaren is running. Editor: $(editor_url)"
    return 0
  fi
  prepare_env
  echo "Starting Ciaren. The editor opens in a tab; if it does not, use: $(editor_url)"
  exec "$VENV/bin/ciaren" serve --host 127.0.0.1 --port "$PORT"
}

start() {
  if is_running; then
    echo "Ciaren is already running on port $PORT."
    return 0
  fi
  prepare_env
  # setsid + nohup detach the server from this shell so it keeps running after
  # the terminal closes.
  setsid nohup "$VENV/bin/ciaren" serve --host 127.0.0.1 --port "$PORT" \
    >"$DATA_DIR/ciaren.log" 2>&1 </dev/null &
  echo "Ciaren is starting on port $PORT (log: $DATA_DIR/ciaren.log)."
}

case "${1:-}" in
  install) install ;;
  serve) serve ;;
  start) start ;;
  *)
    echo "usage: $0 {install|serve|start}" >&2
    exit 2
    ;;
esac
