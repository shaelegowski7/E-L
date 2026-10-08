"""The morning brief: Hermes writes a few bullets from facts E-L has already worked out.

Hermes gets the Today view's numbers and dates as text and is told to use only
those, so the brief can't disagree with the dashboard. The result is saved in
the vault at E-L/Briefs/YYYY-MM-DD.md, E-L's own folder, so past briefs stay
readable in Obsidian.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from el.areas import UNSORTED, Area, AreaIndex
from el.today import TodayView, short_date
from el.vault import Vault

BRIEFS_DIR = "E-L/Briefs"
SOON_DAYS = 30
QUIET_DAYS = 10
def _days(n: int) -> str:
    return f"{n} day" if n == 1 else f"{n} days"


_BULLET_RE = re.compile(r"^\s*[-*]\s+(?:\*\*(?P<label>[^*]+?):?\*\*:?\s*)?(?P<text>.+?)\s*$")


def instructions(index: AreaIndex) -> str:
    names = ", ".join(area.name for area in (*index.areas, UNSORTED))
    return f"""You write E-L's morning brief for the user.
Use only the facts given below. Do not read files, search, or use any tools.
Write 3 to 5 bullets, most important first:
1. anything overdue;
2. deadlines in the next {SOON_DAYS} days, and what would help with each;
3. an area with a deadline coming that has gone quiet;
4. the single most useful next task.
Each bullet is one line in this exact form:
- **<Area>:** <one or two short, plain sentences>
<Area> must be exactly one of: {names}.
Skip anything with nothing to report; never write a bullet saying there is nothing.
Shorten long task text to its main action. Copy numbers and dates exactly.
No heading, no preamble, nothing after the bullets."""


@dataclass(frozen=True)
class BriefItem:
    label: str
    text: str
    area: Area | None


@dataclass(frozen=True)
class Brief:
    day: date
    generated: str  # HH:MM
    items: list[BriefItem]


def brief_facts(view: TodayView) -> str:
    """The Today view as plain lines of fact, each starting with its area in brackets."""
    today = view.today
    lines = [f"Today is {today.strftime('%A %d %B %Y')}."]

    overdue = [d for d in view.coming_up if d.days < 0]
    if overdue:
        lines.append("Overdue:")
        lines += [f"[{d.area.name}] {d.title}, due {short_date(d.day)}, {_days(-d.days)} ago." for d in overdue]

    soon = [d for d in view.coming_up if 0 <= d.days <= SOON_DAYS]
    if soon:
        lines.append("Deadlines, most urgent first:")
        for d in soon:
            at = f" at {d.time}" if d.time else ""
            when = "today" if d.days == 0 else f"in {_days(d.days)}"
            lines.append(f"[{d.area.name}] {d.title} on {short_date(d.day)}{at}, {when}.")

    lines.append("Areas:")
    for card in [*view.cards, view.unsorted]:
        if not card.open and not card.last_active:
            continue  # nothing tracked here yet
        parts = [f"{card.open} open tasks"]
        if card.last_active:
            quiet = (today - card.last_active).days
            label = "no activity for" if quiet >= QUIET_DAYS else "last active"
            parts.append(f"{label} {_days(quiet)} (since {short_date(card.last_active)})")
        if card.next_task:
            parts.append(f"next task: {card.next_task.task.text}")
        lines.append(f"[{card.area.name}] " + "; ".join(parts) + ".")
    return "\n".join(lines)


def parse_items(text: str, index: AreaIndex) -> list[BriefItem]:
    names = {area.name.lower(): area for area in (*index.areas, UNSORTED)}
    items = []
    for line in text.splitlines():
        match = _BULLET_RE.match(line)
        if not match:
            continue
        label = (match.group("label") or "").strip()
        items.append(BriefItem(label, match.group("text").strip(), names.get(label.lower())))
    return items


def brief_path(root: Path, day: date) -> Path:
    return root / BRIEFS_DIR / f"{day.isoformat()}.md"


def save_brief(root: Path, day: date, text: str, now: datetime | None = None) -> Path:
    """Write the brief note atomically, replacing any earlier brief for the same day."""
    now = now or datetime.now()
    bullets = "\n".join(line.rstrip() for line in text.strip().splitlines() if line.strip())
    note = (
        "---\n"
        "type: brief\n"
        f"date: {day.isoformat()}\n"
        f'generated: "{now.strftime("%H:%M")}"\n'
        "source: hermes-agent\n"
        "---\n\n"
        f"# Morning brief, {day.strftime('%A %d %B %Y')}\n\n"
        "Written by E-L (Hermes Agent, Nemotron 3 Super) from the Today page's facts.\n\n"
        f"{bullets}\n"
    )
    path = brief_path(root, day)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".md.tmp")
    tmp.write_text(note, encoding="utf-8")
    os.replace(tmp, path)
    return path


def load_brief(vault: Vault, index: AreaIndex, day: date) -> Brief | None:
    note = vault.note(f"{BRIEFS_DIR}/{day.isoformat()}.md")
    if note is None:
        return None
    items = parse_items(note.body, index)
    if not items:
        return None
    return Brief(day=day, generated=str(note.meta.get("generated") or ""), items=items)
