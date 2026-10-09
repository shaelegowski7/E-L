import shutil
import sys

import pytest
from conftest import FIXTURE_VAULT
from fastapi.testclient import TestClient

from el import app as app_module
from el.config import get_settings
from el.sync import VaultSync, vault_fingerprint


@pytest.fixture
def root(tmp_path):
    shutil.copytree(FIXTURE_VAULT, tmp_path / "vault")
    return tmp_path / "vault"


def _append(path, text="\nedited\n"):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(text)


def _recorder(tmp_path, exit_code=0, stderr=""):
    """A stand-in for sync_vault.sh that records each run in calls.txt."""
    calls = tmp_path / "calls.txt"
    code = (
        f"import sys; open({str(calls)!r}, 'a').write('run\\n'); "
        f"sys.stderr.write({stderr!r}); sys.exit({exit_code})"
    )
    return [sys.executable, "-c", code], calls


def test_fingerprint_tracks_notes_but_not_obsidian_settings(root):
    before = vault_fingerprint(root)
    assert vault_fingerprint(root) == before
    _append(root / ".obsidian" / "scratch.md")
    assert vault_fingerprint(root) == before
    _append(root / "Backlog" / "vault.md")
    assert vault_fingerprint(root) != before


def test_syncs_only_when_notes_change(root, tmp_path):
    command, calls = _recorder(tmp_path)
    sync = VaultSync(root, command=command)
    assert sync.status().synced_at is None
    assert sync.sync_if_changed() == "synced"
    assert sync.sync_if_changed() == "unchanged"
    _append(root / "Backlog" / "vault.md")
    assert sync.sync_if_changed() == "synced"
    assert calls.read_text().count("run") == 2
    assert sync.status().synced_at is not None


def test_failed_sync_is_reported_and_retried(root, tmp_path):
    command, calls = _recorder(tmp_path, exit_code=1, stderr="upload failed\n")
    sync = VaultSync(root, command=command)
    assert sync.sync_if_changed() == "failed"
    assert sync.status().last_error == "upload failed"
    assert sync.sync_if_changed() == "failed"  # not marked as synced, so it tries again
    assert calls.read_text().count("run") == 2


def test_sync_status_endpoint(monkeypatch):
    monkeypatch.setenv("EL_VAULT", str(FIXTURE_VAULT))
    get_settings.cache_clear()
    response = TestClient(app_module.app).get("/api/sync")
    assert response.status_code == 200
    assert response.json() == {"synced_at": None, "last_error": None, "running": False}
    get_settings.cache_clear()
