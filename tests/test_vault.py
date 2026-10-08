from datetime import date

from el.vault import clean_text, split_frontmatter


def test_frontmatter_offset_counts_the_whole_block():
    meta, body, offset = split_frontmatter("---\ntype: backlog\n---\n\n- [ ] one\n")
    assert meta == {"type": "backlog"}
    assert offset == 3
    assert body.startswith("\n- [ ] one")


def test_tasks_skip_code_fences_and_obsidian_folder(vault):
    texts = [task.text for task in vault.tasks]
    assert "not a task, it sits inside a code fence" not in texts
    assert "hidden, Obsidian's own folder is skipped" not in texts
    assert len(vault.tasks) == 8


def test_task_fields(vault):
    tasks = {task.text: task for task in vault.tasks}
    lego = tasks["Brightside: reply to the LEGO approval decline"]
    assert not lego.done
    assert lego.path == "Backlog/brightside.md"
    assert lego.line == 8
    assert lego.origin == date(2026, 9, 27)

    q4 = tasks["Brightside: apply to the Q4 distributors"]
    assert q4.due == date(2026, 10, 20)

    assert tasks["Brightside: rescan old feeds dropped"].done
    assert "Brightside: check the deal views by hand" in tasks


def test_clean_text_strips_markup():
    raw = "**Brightside:** check [[Projects/Brightside/Deals|Deals]] 📅 2026-10-20 ([[2026-09-06 0021 Model opus|06 Sep]])"
    assert clean_text(raw) == "Brightside: check Deals"


def test_sessions_newest_first(vault):
    assert [s.title for s in vault.sessions] == ["Repository check", "Design analysis"]
    assert vault.sessions[0].time == "03:57"


def test_events_and_deals(vault):
    assert [e.title for e in vault.events] == ["Old event", "CS316 class test"]
    assert vault.events[1].area == "uni"
    assert sorted(d.verdict for d in vault.deals) == ["PASS", "PASS_WITH_FLAGS"]
