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
VENV="$HOME/.venvs/ciaren"
# The database, uploads, and log live outside the checkout so they never show
# up in `git status`.
DATA_DIR="$HOME/ciaren-data"
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
  "$(pick_python)" -m venv "$VENV"
  # Fast path: the released wheel on PyPI already bundles the built editor, so
  # a codespace for a released version is ready in about a minute.
  local version
  version="$(grep -m1 '^version = ' "$REPO/backend/pyproject.toml" | cut -d '"' -f2)"
  if "$VENV/bin/python" -m pip install --quiet "ciaren==$version"; then
    return 0
  fi
  # Unreleased version (a development branch): build the editor and install
  # this checkout instead.
  echo "ciaren==$version is not on PyPI; building from this checkout."
  npm ci --prefix "$REPO/frontend" --no-audit --no-fund
  npm run build --prefix "$REPO/frontend"
  "$VENV/bin/python" -m pip install --quiet --editable "$REPO/backend"
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
