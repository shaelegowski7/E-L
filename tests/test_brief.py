import shutil
from datetime import datetime

from conftest import FIXTURE_VAULT, TODAY
from fastapi.testclient import TestClient

from el import app as app_module
from el.brief import brief_facts, load_brief, parse_items, save_brief
from el.config import get_settings
from el.today import build_today
from el.vault import Vault

REPLY = """Here is your brief:
- **Uni:** The CS316 class test is in 25 days.
- **Brightside:** Apply to the Q4 distributors by Tue 20 Oct.
- **Nonsense area:** Still kept, just without a colour.
That's all."""


def test_facts_carry_exact_numbers(index, vault):
    facts = brief_facts(build_today(vault, index, TODAY))
    assert "Today is Friday 02 October 2026." in facts
    assert "[Brightside] 3 open tasks" in facts
    assert "[Uni] CS316 class test on Tue 27 Oct, in 25 days." in facts
    assert "Overdue:" not in facts  # empty sections are left out
    assert "[Daily life]" not in facts  # nothing tracked there


def test_parse_items_keeps_bullets_only(index):
    items = parse_items(REPLY, index)
    assert [(i.label, i.area.key if i.area else None) for i in items] == [
        ("Uni", "uni"), ("Brightside", "brightside"), ("Nonsense area", None),
    ]
    assert items[0].text == "The CS316 class test is in 25 days."


def test_save_then_load(tmp_path, index):
    shutil.copytree(FIXTURE_VAULT, tmp_path / "vault")
    root = tmp_path / "vault"
    path = save_brief(root, TODAY, "- **Uni:** Revise Week 1.", now=datetime(2026, 10, 2, 7, 0))
    assert path.name == "2026-10-02.md"
    brief = load_brief(Vault(root), index, TODAY)
    assert brief.generated == "07:00"
    assert [(i.label, i.text) for i in brief.items] == [("Uni", "Revise Week 1.")]


def test_brief_endpoint_saves_to_the_vault(tmp_path, monkeypatch):
    shutil.copytree(FIXTURE_VAULT, tmp_path / "vault")
    monkeypatch.setenv("EL_VAULT", str(tmp_path / "vault"))
    monkeypatch.setattr(app_module, "_today", lambda: TODAY)
    get_settings.cache_clear()

    class FakeHermes:
        def ask(self, question, system=""):
            assert "Use only the facts given below" in system
            return REPLY

    monkeypatch.setattr(app_module, "_hermes_client", lambda: FakeHermes())
    client = TestClient(app_module.app)
    response = client.post("/api/brief")
    assert response.status_code == 200
    assert (tmp_path / "vault" / "E-L" / "Briefs" / "2026-10-02.md").is_file()
    page = client.get("/")
    assert "The CS316 class test is in 25 days." in page.text
    get_settings.cache_clear()
