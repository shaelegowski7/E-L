"""Everything the Today page shows, worked out from the vault.

No model is involved here: these are counts, dates and lists read straight from
notes, so they stay fast and exact. Nemotron's brief and ranking come later.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from el.areas import UNSORTED, Area, AreaIndex
from el.vault import Session, Task, Vault

HORIZON_DAYS = 70
COUNTDOWN_DAYS = 30  # an area card leads with a countdown only for events this close
NEXT_UP_COUNT = 6
NEXT_UP_PER_AREA = 2
SESSION_COUNT = 6


@dataclass(frozen=True)
class TaskItem:
    task: Task
    area: Area
    overdue: bool


@dataclass(frozen=True)
class DatedItem:
    day: date
    title: str
    area: Area
    days: int  # days from today; negative when overdue
    time: str = ""
    kind: str = "event"  # "event" or "task"


@dataclass(frozen=True)
class SessionItem:
    session: Session
    area: Area


@dataclass
class AreaCard:
    area: Area
    open: int = 0
    done: int = 0
    headline: str = "–"
    headline_label: str = "nothing tracked yet"
    lines: list[str] = field(default_factory=list)
    next_task: TaskItem | None = None
    last_active: date | None = None


@dataclass
class TodayView:
    today: date
    cards: list[AreaCard]
    unsorted: AreaCard
    coming_up: list[DatedItem]
    next_up: list[TaskItem]
    sessions: list[SessionItem]
    note_count: int


def _rank_key(item: TaskItem) -> tuple:
    task = item.task
    bucket = 0 if item.overdue else 1 if task.due else 2
    return (
        bucket,
        task.due or date.max,
        -(task.origin or date.min).toordinal(),
        -task.line,
    )


def _pick_next_up(ranked: list[TaskItem]) -> list[TaskItem]:
    """Best-ranked tasks, at most NEXT_UP_PER_AREA per area until the list is full."""
    picked: list[TaskItem] = []
    per_area: dict[str, int] = {}
    for item in ranked:
        if per_area.get(item.area.key, 0) < NEXT_UP_PER_AREA:
            picked.append(item)
            per_area[item.area.key] = per_area.get(item.area.key, 0) + 1
        if len(picked) == NEXT_UP_COUNT:
            return picked
    for item in ranked:
        if item not in picked:
            picked.append(item)
        if len(picked) == NEXT_UP_COUNT:
            break
    return picked


def short_date(day: date) -> str:
    return day.strftime("%a %d %b")


def build_today(vault: Vault, index: AreaIndex, today: date) -> TodayView:
    all_areas = (*index.areas, UNSORTED)
    cards = {area.key: AreaCard(area) for area in all_areas}

    open_items: list[TaskItem] = []
    for task in vault.tasks:
        area = index.for_task(task)
        card = cards[area.key]
        if task.done:
            card.done += 1
            continue
        card.open += 1
        open_items.append(TaskItem(task, area, overdue=bool(task.due and task.due < today)))
    ranked = sorted(open_items, key=_rank_key)

    for item in ranked:
        card = cards[item.area.key]
        if card.next_task is None:
            card.next_task = item

    sessions = [SessionItem(s, index.for_session(s)) for s in vault.sessions]
    for item in sessions:
        card = cards[item.area.key]
        if item.session.day and (card.last_active is None or item.session.day > card.last_active):
            card.last_active = item.session.day
    for note in vault.session_notes:
        card = cards[index.for_path(note.path).key]
        if note.date and (card.last_active is None or note.date > card.last_active):
            card.last_active = note.date

    coming_up: list[DatedItem] = []
    for event in vault.events:
        days = (event.day - today).days
        if 0 <= days <= HORIZON_DAYS:
            coming_up.append(DatedItem(event.day, event.title, index.for_event(event), days, event.start))
    for item in open_items:
        due = item.task.due
        if due and (due - today).days <= HORIZON_DAYS:
            coming_up.append(DatedItem(due, item.task.text, item.area, (due - today).days, kind="task"))
    coming_up.sort(key=lambda d: (d.day, d.time))

    for area in all_areas:
        card = cards[area.key]
        next_event = next((d for d in coming_up if d.area.key == area.key and d.days >= 0), None)
        if next_event and next_event.kind == "event" and next_event.days <= COUNTDOWN_DAYS:
            card.headline = str(next_event.days)
            card.headline_label = f"days to {next_event.title}"
        elif card.open:
            card.headline = str(card.open)
            card.headline_label = "open task" if card.open == 1 else "open tasks"
        if card.open or card.done:
            card.lines.append(f"{card.open} open · {card.done} done")
        deals = [d for d in vault.deals if index.for_path(d.path).key == area.key]
        if deals:
            flagged = sum(d.verdict == "PASS_WITH_FLAGS" for d in deals)
            card.lines.append(f"{len(deals)} deal notes · {flagged} flagged")
        if card.last_active:
            quiet = (today - card.last_active).days
            suffix = f" ({quiet} days ago)" if quiet >= 14 else ""
            card.lines.append(f"Last active {short_date(card.last_active)}{suffix}")

    return TodayView(
        today=today,
        cards=[cards[area.key] for area in index.areas],
        unsorted=cards[UNSORTED.key],
        coming_up=coming_up,
        next_up=_pick_next_up(ranked),
        sessions=sessions[:SESSION_COUNT],
        note_count=len(vault.notes),
    )
