#!/usr/bin/env bash
# Run E-L's tests inside WSL. Extra args go to pytest.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export PATH="$HOME/.local/bin:$PATH"
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$HOME/.e-l/venv}"
exec uv run pytest "$@"
