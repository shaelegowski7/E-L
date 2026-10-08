"""E-L's areas, and which area a task, note, session or event belongs to.

The defaults below match the brainz vault. A vault can override them with a
```yaml block in the note E-L/Areas.md (a list under `areas:` with the same
fields), so areas stay editable in Obsidian.

Colours follow the area, never its position: they are the validated
categorical palette from the design (light-surface step, dark-sidebar step).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import yaml

from el.vault import Event, Session, Task, Vault

AREAS_NOTE = "E-L/Areas.md"
_YAML_BLOCK_RE = re.compile(r"```ya?ml[ \t]*\r?\n(.*?)\r?\n```", re.S)
_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(frozen=True)
class Area:
    key: str
    name: str
    color: str  # mark colour on light surfaces
    dark: str  # mark colour on the dark sidebar
    description: str = ""
    folders: tuple[str, ...] = ()
    backlogs: tuple[str, ...] = ()
    log_projects: tuple[str, ...] = ()
    # Text prefixes such as "E-L:" that claim a backlog item for this area, because
    # the logging hook files items by the folder a session ran in, not by topic.
    prefixes: tuple[str, ...] = ()


UNSORTED = Area(
    key="unsorted", name="Unsorted", color="#8B93A1", dark="#A3A9B5",
    description="Vault housekeeping",
    backlogs=("Backlog/vault.md",), log_projects=("vault",), prefixes=("Vault",),
)

DEFAULT_AREAS: tuple[Area, ...] = (
    Area(
        key="brightside", name="Brightside", color="#eb6834", dark="#d95926",
        description="Amazon FBA sourcing",
        folders=("Projects/Brightside", "Brightside Deals"),
        backlogs=("Backlog/brightside.md",),
        log_projects=("brightside",),
        prefixes=("Brightside",),
    ),
    Area(
        key="sentimentfx", name="SentimentFX", color="#2a78d6", dark="#3987e5",
        description="Crypto sentiment dataset and API",
        folders=("Projects/SentimentFX",),
        backlogs=("Backlog/sentimentfx.md",),
        log_projects=("sentimentfx", "crypto-sentiment"),
        prefixes=("SentimentFX",),
    ),
    Area(
        key="business", name="Personal business", color="#eda100", dark="#c98500",
        description="E-L, eBay and Leetcode",
        folders=("Projects/E-L", "Projects/eBay", "Leetcode"),
        backlogs=("Backlog/e-l-1.md", "Backlog/e-l.md", "Backlog/general.md", "Backlog/ebay.md"),
        log_projects=("e-l", "e-l-1", "ebay", "general"),
        prefixes=("E-L", "eBay", "Leetcode"),
    ),
    Area(
        key="uni", name="Uni", color="#4a3aa7", dark="#9085e9",
        description="CS316 Functional Programming",
        folders=("Learning",),
        backlogs=("Backlog/uni.md",),
        log_projects=("cs316-functional-programming",),
        prefixes=("CS316", "Uni"),
    ),
    Area(
        key="life", name="Daily life", color="#1baf7a", dark="#199e70",
        description="Money, running and email",
        folders=("Daily", "Life"),
        backlogs=("Backlog/life.md",),
        prefixes=("Life",),
    ),
)


def _strings(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list):
        return tuple(str(v) for v in value)
    return ()


def load_areas(vault: Vault) -> tuple[Area, ...]:
    """Areas from E-L/Areas.md if it has a valid ```yaml block, else the defaults."""
    note = vault.note(AREAS_NOTE)
    match = _YAML_BLOCK_RE.search(note.body) if note else None
    if not match:
        return DEFAULT_AREAS
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return DEFAULT_AREAS
    items = data.get("areas") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return DEFAULT_AREAS

    defaults = {area.key: area for area in DEFAULT_AREAS}
    areas = []
    for item in items:
        if not isinstance(item, dict) or not item.get("key"):
            continue
        key = str(item["key"])
        base = defaults.get(key, UNSORTED)
        color, dark = str(item.get("color", "")), str(item.get("dark", ""))
        areas.append(Area(
            key=key,
            name=str(item.get("name") or (base.name if key in defaults else key)),
            color=color if _HEX_RE.match(color) else base.color,
            dark=dark if _HEX_RE.match(dark) else base.dark,
            description=str(item.get("description") or ""),
            folders=_strings(item.get("folders")),
            backlogs=_strings(item.get("backlogs")),
            log_projects=_strings(item.get("log_projects")),
            prefixes=_strings(item.get("prefixes")),
        ))
    return tuple(areas) or DEFAULT_AREAS


def _starts_with_prefix(text: str, prefixes: tuple[str, ...]) -> bool:
    return any(re.match(rf"{re.escape(p)}(?=[\s:(]|$)", text, re.I) for p in prefixes)


def _in_folders(path: str, folders: tuple[str, ...]) -> bool:
    return any(path.startswith(folder.rstrip("/") + "/") for folder in folders)


class AreaIndex:
    def __init__(self, areas: tuple[Area, ...]):
        self.areas = areas
        self.by_key = {area.key: area for area in areas}

    def get(self, key: str) -> Area | None:
        return UNSORTED if key == UNSORTED.key else self.by_key.get(key)

    def for_path(self, path: str) -> Area:
        for area in (*self.areas, UNSORTED):
            if path in area.backlogs or _in_folders(path, area.folders):
                return area
        return UNSORTED

    def for_task(self, task: Task) -> Area:
        # Backlog files are where the hook misfiles items, so their text prefix wins there.
        if task.path.startswith("Backlog/"):
            for area in (*self.areas, UNSORTED):
                if _starts_with_prefix(task.text, area.prefixes):
                    return area
        return self.for_path(task.path)

    def for_session(self, session: Session) -> Area:
        for area in (*self.areas, UNSORTED):
            if session.project in area.log_projects:
                return area
        return UNSORTED

    def for_event(self, event: Event) -> Area:
        return self.get(event.area) or self.for_path(event.path)
