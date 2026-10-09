from datetime import date
from pathlib import Path

import pytest

from el.areas import DEFAULT_AREAS, AreaIndex
from el.vault import Vault

FIXTURE_VAULT = Path(__file__).parent / "fixtures" / "vault"
TODAY = date(2026, 10, 2)


@pytest.fixture(autouse=True)
def no_background_sync(monkeypatch):
    """Tests never sync to the real sandbox."""
    monkeypatch.setenv("EL_SYNC_INTERVAL", "0")


@pytest.fixture
def vault() -> Vault:
    return Vault(FIXTURE_VAULT)


@pytest.fixture
def index() -> AreaIndex:
    return AreaIndex(DEFAULT_AREAS)
