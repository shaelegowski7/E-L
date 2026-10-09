"""Keep Hermes's copy of the vault current.

The sandbox can't see the real vault, so scripts/sync_vault.sh copies the notes
in. VaultSync runs that script only when the notes have changed, which it checks
cheaply from file paths, sizes and modification times. The app checks on a
timer and again right before each Ask E-L question.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from el.config import REPO
from el.vault import SKIP_DIRS

SYNC_SCRIPT = REPO / "scripts" / "sync_vault.sh"


def vault_fingerprint(root: Path) -> str:
    """A hash that changes whenever a note is added, removed, renamed or edited."""
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts[:-1]):
            continue
        stat = path.stat()
        digest.update(f"{rel.as_posix()}\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode())
    return digest.hexdigest()


@dataclass(frozen=True)
class SyncStatus:
    synced_at: datetime | None
    last_error: str | None
    running: bool


class VaultSync:
    def __init__(self, root: Path, sandbox: str = "e-l", command: list[str] | None = None, timeout: float = 300):
        self.root = Path(root)
        self.sandbox = sandbox
        self.command = command or ["bash", str(SYNC_SCRIPT)]
        self.timeout = timeout
        self._lock = threading.Lock()
        self._fingerprint: str | None = None
        self._synced_at: datetime | None = None
        self._last_error: str | None = None
        self._running = False

    def status(self) -> SyncStatus:
        return SyncStatus(self._synced_at, self._last_error, self._running)

    def sync_if_changed(self) -> str:
        """Run the sync script if the notes changed since the last good sync.

        Returns "synced", "unchanged" or "failed". Waits if another sync is running.
        """
        with self._lock:
            fingerprint = vault_fingerprint(self.root)
            if fingerprint == self._fingerprint:
                return "unchanged"
            self._running = True
            try:
                result = subprocess.run(
                    self.command,
                    capture_output=True, text=True, timeout=self.timeout, check=False,
                    env={**os.environ, "EL_VAULT": str(self.root), "EL_SANDBOX": self.sandbox},
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                self._last_error = f"sync didn't run: {exc}"
                return "failed"
            finally:
                self._running = False
            if result.returncode != 0:
                lines = (result.stderr or result.stdout).strip().splitlines()
                self._last_error = lines[-1] if lines else f"sync exited with code {result.returncode}"
                return "failed"
            # Fingerprint from before the copy: an edit made mid-sync shows up as a change next time.
            self._fingerprint = fingerprint
            self._synced_at = datetime.now()
            self._last_error = None
            return "synced"
