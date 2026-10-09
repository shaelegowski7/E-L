"""E-L's web app: the Today page, area pages, and the Ask E-L endpoint.

Run with scripts/dev.sh. The vault is re-read on each page load, so edits made
in Obsidian show up on refresh.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from el.areas import AreaIndex, load_areas
from el.brief import brief_facts, instructions, load_brief, parse_items, save_brief
from el.config import get_settings
from el.hermes import Hermes, HermesError, vault_map
from el.sync import VaultSync
from el.today import build_today, short_date
from el.vault import Vault

HERE = Path(__file__).parent
log = logging.getLogger("el")
_hermes: Hermes | None = None
_sync: VaultSync | None = None


def _vault_sync() -> VaultSync:
    global _sync
    settings = get_settings()
    if _sync is None or _sync.root != settings.vault:
        _sync = VaultSync(settings.vault, settings.sandbox)
    return _sync


async def _sync_loop(interval: int) -> None:
    """Keep Hermes's copy of the vault current while the app runs."""
    while True:
        try:
            if await asyncio.to_thread(_vault_sync().sync_if_changed) == "failed":
                log.warning("vault sync failed: %s", _vault_sync().status().last_error)
        except Exception:  # keep checking whatever went wrong this time
            log.exception("vault sync check crashed")
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(_: FastAPI):
    interval = get_settings().sync_interval
    task = asyncio.create_task(_sync_loop(interval)) if interval > 0 else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="E-L", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")
templates.env.filters["short_date"] = short_date


def _today() -> date:
    return date.today()


def _load() -> tuple[Vault, AreaIndex]:
    vault = Vault(get_settings().vault)
    return vault, AreaIndex(load_areas(vault))


def _hermes_client() -> Hermes:
    global _hermes
    if _hermes is None:
        settings = get_settings()
        _hermes = Hermes(settings.hermes_url, settings.sandbox, settings.hermes_token)
    return _hermes


@app.get("/", response_class=HTMLResponse)
def today_page(request: Request):
    vault, index = _load()
    view = build_today(vault, index, _today())
    brief = load_brief(vault, index, view.today)
    return templates.TemplateResponse(request, "today.html", {
        "view": view, "brief": brief, "sync": _vault_sync().status(), "active": "today",
    })


@app.get("/area/{key}", response_class=HTMLResponse)
def area_page(request: Request, key: str):
    vault, index = _load()
    area = index.get(key)
    if area is None:
        raise HTTPException(status_code=404, detail="No such area")
    view = build_today(vault, index, _today())
    card = next((c for c in [*view.cards, view.unsorted] if c.area.key == key))
    tasks = [t for t in vault.tasks if not t.done and index.for_task(t).key == key]
    sessions = [s for s in vault.sessions if index.for_session(s).key == key][:10]
    events = [d for d in view.coming_up if d.area.key == key]
    return templates.TemplateResponse(request, "area.html", {
        "view": view, "card": card, "tasks": tasks, "sessions": sessions,
        "events": events, "sync": _vault_sync().status(), "active": key,
    })


@app.get("/api/today")
def today_api():
    vault, index = _load()
    return build_today(vault, index, _today())


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


@app.post("/api/ask")
def ask(body: Question):
    _, index = _load()
    if get_settings().sync_interval > 0:
        _vault_sync().sync_if_changed()  # so a note edited a moment ago is in Hermes's copy
    try:
        answer = _hermes_client().ask(body.question, system=vault_map(index))
    except HermesError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"answer": answer}


@app.post("/api/brief")
def write_brief():
    """Have Hermes write today's brief from the Today facts, then save it to the vault."""
    vault, index = _load()
    view = build_today(vault, index, _today())
    try:
        text = _hermes_client().ask(brief_facts(view), system=instructions(index))
    except HermesError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    items = parse_items(text, index)
    if not items:
        raise HTTPException(status_code=502, detail="Hermes didn't return any brief bullets. Try again.")
    bullets = "\n".join(f"- **{item.label}:** {item.text}" if item.label else f"- {item.text}" for item in items)
    path = save_brief(get_settings().vault, view.today, bullets)
    return {"saved": path.name, "items": [{"label": i.label, "text": i.text} for i in items]}


@app.get("/api/sync")
def sync_status():
    return _vault_sync().status()


@app.post("/api/sync")
def sync_now():
    """Sync Hermes's vault copy now if the notes changed since the last sync."""
    sync = _vault_sync()
    return {"result": sync.sync_if_changed(), "status": sync.status()}


@app.get("/healthz")
def healthz():
    return {"ok": True}
