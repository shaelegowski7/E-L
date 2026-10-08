from conftest import TODAY

from el.today import build_today


def _area_of(index, vault, text):
    task = next(t for t in vault.tasks if t.text == text)
    return index.for_task(task).key


def test_backlog_prefix_beats_the_file_it_was_filed_in(index, vault):
    # The logging hook filed this E-L item in Brightside's backlog.
    assert _area_of(index, vault, "E-L: decide the agent stack") == "business"
    assert _area_of(index, vault, "Brightside: reply to the LEGO approval decline") == "brightside"
    assert _area_of(index, vault, "Vault: tidy the seeded items in Backlog") == "unsorted"


def test_project_folder_wins_outside_backlog(index, vault):
    # Prefixes only apply in Backlog/; this eBay session task stays with eBay's area.
    assert _area_of(index, vault, "Brightside: photograph the 19 rows waiting on photos") == "business"


def test_today_view(index, vault):
    view = build_today(vault, index, TODAY)
    cards = {card.area.key: card for card in view.cards}

    brightside = cards["brightside"]
    assert (brightside.open, brightside.done) == (3, 2)
    assert "2 deal notes · 1 flagged" in brightside.lines

    uni = cards["uni"]
    assert (uni.headline, uni.headline_label) == ("25", "days to CS316 class test")

    assert [(d.title, d.days) for d in view.coming_up] == [
        ("Brightside: apply to the Q4 distributors", 18),
        ("CS316 class test", 25),
    ]
    assert view.unsorted.open == 1
    assert [s.session.title for s in view.sessions] == ["Repository check", "Design analysis"]
    assert view.sessions[0].area.key == "business"


def test_next_up_puts_dated_tasks_first_and_caps_each_area(index, vault):
    view = build_today(vault, index, TODAY)
    keys = [item.area.key for item in view.next_up]
    assert view.next_up[0].task.text == "Brightside: apply to the Q4 distributors"
    assert keys[:4].count("brightside") <= 2
