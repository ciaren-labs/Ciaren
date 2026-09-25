#!/usr/bin/env bash
# Dev container / GitHub Codespaces lifecycle for Ciaren.
#
#   ciaren.sh install  postCreateCommand: build the editor and install Ciaren
#                      from this checkout into a virtualenv.
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

install() {
  # An editable install serves the editor straight from frontend/dist, so the
  # same steps work before and after a PyPI release.
  npm ci --prefix "$REPO/frontend" --no-audit --no-fund
  npm run build --prefix "$REPO/frontend"
  python -m venv "$VENV"
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

case "${1:-}" in
  install) install ;;
  start) start ;;
  *)
    echo "usage: $0 {install|start}" >&2
    exit 2
    ;;
esac
