"""Read-only access to an Obsidian vault.

Parses each note's YAML frontmatter and its `- [ ]` tasks, plus the note types
E-L uses: Claude Log session entries, project session notes, calendar events
and Brightside deal notes. Nothing in this module writes to the vault.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from functools import cached_property
from pathlib import Path, PurePosixPath

import yaml

SKIP_DIRS = {".obsidian", ".trash", ".git"}
CALENDAR_DIR = "Calendar"
DEALS_DIR = "Brightside Deals"

_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)
_TASK_RE = re.compile(r"^\s*[-*+] \[(?P<mark>[ xX])\] (?P<text>.*\S)\s*$")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_DUE_RE = re.compile(r"\s*📅\s*(\d{4}-\d{2}-\d{2})")
# The logging hook ends each backlog item with a link to its session: ([[2026-09-06 0021 Model opus|06 Sep]])
_ORIGIN_RE = re.compile(r"\s*\(\[\[(\d{4}-\d{2}-\d{2})[^\]]*\]\]\)\s*$")
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
_STRIKE_RE = re.compile(r"~~(.*?)~~")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def as_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def split_frontmatter(text: str) -> tuple[dict, str, int]:
    """Return (frontmatter, body, number of lines the frontmatter block takes)."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text, 0
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    return meta, text[match.end():], match.group(0).count("\n")


def clean_text(raw: str) -> str:
    """Task text for display: no session link, due marker, strikethrough, bold or wikilink syntax."""
    text = _ORIGIN_RE.sub("", raw)
    text = _DUE_RE.sub("", text)
    text = _STRIKE_RE.sub(r"\1", text)
    text = _BOLD_RE.sub(r"\1", text)
    text = _WIKILINK_RE.sub(lambda m: m.group(2) or PurePosixPath(m.group(1)).name, text)
    return text.strip()


@dataclass(frozen=True)
class Task:
    text: str
    raw: str
    done: bool
    path: str
    line: int  # 1-based line in the file, for write-back later
    due: date | None = None
    origin: date | None = None  # date of the session that added it, if the line links one


@dataclass(frozen=True, eq=False)
class Note:
    path: str  # vault-relative, forward slashes
    meta: dict = field(repr=False)
    body: str = field(repr=False)
    body_offset: int = 0  # lines taken by the frontmatter block

    @property
    def name(self) -> str:
        return PurePosixPath(self.path).stem

    @property
    def type(self) -> str:
        return str(self.meta.get("type") or "")

    @property
    def date(self) -> date | None:
        return as_date(self.meta.get("date"))

    def in_folder(self, folder: str) -> bool:
        return self.path.startswith(folder.rstrip("/") + "/")

    def tasks(self) -> list[Task]:
        tasks: list[Task] = []
        in_fence = False
        for index, line in enumerate(self.body.splitlines()):
            if _FENCE_RE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            match = _TASK_RE.match(line)
            if not match:
                continue
            raw = match.group("text")
            due = _DUE_RE.search(raw)
            origin = _ORIGIN_RE.search(raw)
            tasks.append(Task(
                text=clean_text(raw),
                raw=raw,
                done=match.group("mark") != " ",
                path=self.path,
                line=self.body_offset + index + 1,
                due=as_date(due.group(1)) if due else None,
                origin=as_date(origin.group(1)) if origin else None,
            ))
        return tasks


@dataclass(frozen=True)
class Session:
    """One Claude Log entry, written by the logging hook after each Claude Code session."""
    path: str
    title: str
    project: str
    day: date | None
    time: str

    @property
    def sort_key(self) -> tuple[date, str]:
        return (self.day or date.min, self.time)


@dataclass(frozen=True)
class Event:
    """A note in Calendar/, in the frontmatter format the Obsidian Full Calendar plugin uses."""
    path: str
    title: str
    day: date
    start: str = ""
    area: str = ""


@dataclass(frozen=True)
class Deal:
    path: str
    asin: str
    title: str
    verdict: str


class Vault:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        if not self.root.is_dir():
            raise FileNotFoundError(f"Vault folder not found: {self.root}")
        self.notes = self._load()
        self._by_path = {note.path: note for note in self.notes}

    def _load(self) -> list[Note]:
        notes = []
        for path in sorted(self.root.rglob("*.md")):
            rel = path.relative_to(self.root)
            if any(part in SKIP_DIRS for part in rel.parts[:-1]):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            meta, body, offset = split_frontmatter(text)
            notes.append(Note(rel.as_posix(), meta, body, offset))
        return notes

    def note(self, path: str) -> Note | None:
        return self._by_path.get(path)

    @cached_property
    def tasks(self) -> list[Task]:
        return [task for note in self.notes for task in note.tasks()]

    @cached_property
    def sessions(self) -> list[Session]:
        """Claude Log entries, newest first."""
        sessions = [
            Session(
                path=note.path,
                title=str(note.meta.get("title") or note.name),
                project=str(note.meta.get("project") or ""),
                day=note.date,
                time=str(note.meta.get("time") or ""),
            )
            for note in self.notes
            if note.type == "claude-log"
        ]
        return sorted(sessions, key=lambda s: s.sort_key, reverse=True)

    @cached_property
    def session_notes(self) -> list[Note]:
        """Hand-written project session notes (type: session), newest first."""
        notes = [note for note in self.notes if note.type == "session"]
        return sorted(notes, key=lambda n: n.date or date.min, reverse=True)

    @cached_property
    def events(self) -> list[Event]:
        events = []
        for note in self.notes:
            day = note.date
            if not note.in_folder(CALENDAR_DIR) or day is None:
                continue
            events.append(Event(
                path=note.path,
                title=str(note.meta.get("title") or note.name),
                day=day,
                start=str(note.meta.get("startTime") or ""),
                area=str(note.meta.get("area") or ""),
            ))
        return sorted(events, key=lambda e: (e.day, e.start))

    @cached_property
    def deals(self) -> list[Deal]:
        return [
            Deal(
                path=note.path,
                asin=str(note.meta["asin"]),
                title=str(note.meta.get("title") or ""),
                verdict=str(note.meta.get("verdict") or ""),
            )
            for note in self.notes
            if note.in_folder(DEALS_DIR) and note.meta.get("asin")
        ]
