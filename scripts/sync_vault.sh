#!/usr/bin/env bash
# Copy the Obsidian vault's notes into the E-L sandbox as a snapshot.
#
# The real vault never enters the sandbox: Hermes reads and edits this copy, and
# changes reach the real vault only through E-L's host side (not built yet).
# Hermes's bundled Obsidian skill falls back to ~/Documents/Obsidian Vault when
# OBSIDIAN_VAULT_PATH is unset, and NemoClaw seals the sandbox .env, so the copy
# goes to that default path.
#
# Settings come from the environment, or from EL_VAULT / EL_SANDBOX in the repo's
# .env (see .env.example). Only those two keys are read from .env.
#
# Run inside WSL:  bash scripts/sync_vault.sh
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

env_value() {
  [ -f "$REPO/.env" ] || return 0
  grep -E "^$1=" "$REPO/.env" | tail -1 | cut -d= -f2- | tr -d '\r' | sed -E 's/^["'\'']//; s/["'\'']$//'
}

VAULT="${EL_VAULT:-$(env_value EL_VAULT)}"
SANDBOX="${EL_SANDBOX:-$(env_value EL_SANDBOX)}"
SANDBOX="${SANDBOX:-e-l}"
STAGE_ROOT="${HOME}/.e-l/stage"
STAGE="${STAGE_ROOT}/Obsidian Vault"
DEST_PARENT=/sandbox/Documents

if [ -z "$VAULT" ]; then
  echo "EL_VAULT is not set. Add it to $REPO/.env (see .env.example)." >&2
  exit 1
fi
if [ ! -d "$VAULT" ]; then
  echo "EL_VAULT points to $VAULT, which is not a folder." >&2
  exit 1
fi

export NVM_DIR="$HOME/.nvm"
# shellcheck disable=SC1091
. "$NVM_DIR/nvm.sh" >/dev/null 2>&1

set -e
rm -rf "$STAGE_ROOT"
mkdir -p "$STAGE"

# Notes only: skip Obsidian's own settings, the trash, and the scanner's raw data files.
rsync -a --prune-empty-dirs \
  --exclude='.obsidian/' --exclude='.trash/' --exclude='.git/' \
  --include='*/' --include='*.md' --exclude='*' \
  "$VAULT/" "$STAGE/"

nemohermes "$SANDBOX" exec --no-tty --timeout 60 -- \
  sh -c "rm -rf '$DEST_PARENT/Obsidian Vault' && mkdir -p '$DEST_PARENT'"
nemohermes "$SANDBOX" upload "$STAGE" "$DEST_PARENT/"

echo "synced $(find "$STAGE" -name '*.md' | wc -l) notes to $SANDBOX:$DEST_PARENT/Obsidian Vault"
