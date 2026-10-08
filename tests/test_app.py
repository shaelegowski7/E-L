from conftest import FIXTURE_VAULT, TODAY
from fastapi.testclient import TestClient

from el import app as app_module
from el.config import get_settings


def _client(monkeypatch):
    monkeypatch.setenv("EL_VAULT", str(FIXTURE_VAULT))
    monkeypatch.setattr(app_module, "_today", lambda: TODAY)
    get_settings.cache_clear()
    return TestClient(app_module.app)


def test_today_page_renders(monkeypatch):
    response = _client(monkeypatch).get("/")
    assert response.status_code == 200
    for text in ("Today", "Coming up", "Personal business", "CS316 class test", "Repository check"):
        assert text in response.text


def test_area_page_and_unknown_area(monkeypatch):
    client = _client(monkeypatch)
    page = client.get("/area/brightside")
    assert page.status_code == 200
    assert "reply to the LEGO approval decline" in page.text
    assert client.get("/area/nope").status_code == 404


def test_ask_reports_hermes_errors(monkeypatch):
    class Failing:
        def ask(self, question, system=""):
            raise app_module.HermesError("Hermes isn't reachable")

    monkeypatch.setattr(app_module, "_hermes_client", lambda: Failing())
    response = _client(monkeypatch).post("/api/ask", json={"question": "hello"})
    assert response.status_code == 502
    assert "reachable" in response.json()["detail"]
