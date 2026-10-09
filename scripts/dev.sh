#!/usr/bin/env bash
# Run the E-L dashboard inside WSL at http://127.0.0.1:8000 (open it from Windows too).
#
# Makes sure Hermes's API port is forwarded, so Ask E-L works. The app itself
# keeps Hermes's copy of the vault current (EL_SYNC_INTERVAL, default 120s).
# Extra args go to uvicorn, e.g. --reload.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export PATH="$HOME/.local/bin:$PATH"
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$HOME/.e-l/venv}"

if [ "${EL_SKIP_SANDBOX:-}" != "1" ] && ! curl -s -m 5 -o /dev/null http://127.0.0.1:8642/health; then
  export NVM_DIR="$HOME/.nvm"
  # shellcheck disable=SC1091
  . "$NVM_DIR/nvm.sh" >/dev/null 2>&1
  nemohermes "${EL_SANDBOX:-e-l}" recover >/dev/null 2>&1 || echo "Hermes recover failed; Ask E-L may not work" >&2
fi

exec uv run uvicorn el.app:app --host 127.0.0.1 --port "${EL_PORT:-8000}" "$@"
