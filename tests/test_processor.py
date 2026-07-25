import io
import json
import os

from gmail_parser.rules import Action, Rule
from gmail_parser.archive import parse_archive_meta
from gmail_parser.progress import ProgressReporter
from gmail_parser.processor import process_messages


class FakeMessage:
    def __init__(self, id, labels, subject="Subj", sender="a@b.co",
                 date="2026-07-24T09:30:00", body="<p>body</p>"):
        self.id = id
        self.labels = list(labels)
        self.subject = subject
        self.sender = sender
        self.date = date
        self.body = body
        self.trashed = False
        self.read = False

    def getId(self):
        return self.id

    def getLabels(self):
        return self.labels

    def getSubject(self):
        return self.subject

    def getSenderEmail(self):
        return self.sender

    def getDate(self):
        return self.date

    def getArchiveBody(self):
        return self.body

    def markAsRead(self):
        self.read = True

    def moveToTrash(self):
        self.trashed = True


# rule labels are user-facing NAMES; message.getLabels() returns Gmail label IDs.
NAME_TO_ID = {"Newsletters": "Label_1", "Social": "Label_2", "Receipts": "Label_3"}


def test_archive_writes_selfcontained_html_and_trashes(tmp_path):
    msg = FakeMessage("m1", ["Label_3"], subject="Receipt #9", body="<p>marker</p>")
    rules = [Rule("Receipts", Action.ARCHIVE)]
    process_messages([msg], rules, NAME_TO_ID, str(tmp_path))

    path = tmp_path / "Receipts" / "m1.html"
    assert path.exists()
    content = path.read_text()
    assert "marker" in content
    assert parse_archive_meta(content)["subject"] == "Receipt #9"
    assert msg.trashed is True


def test_delete_trashes_without_writing_file(tmp_path):
    msg = FakeMessage("m1", ["Label_2"])
    process_messages([msg], [Rule("Social", Action.DELETE)], NAME_TO_ID, str(tmp_path))
    assert msg.trashed is True
    assert not any(tmp_path.rglob("*.html"))


def test_mark_read_does_not_trash(tmp_path):
    msg = FakeMessage("m1", ["Label_1"])
    process_messages([msg], [Rule("Newsletters", Action.MARK_READ)], NAME_TO_ID, str(tmp_path))
    assert msg.read is True
    assert msg.trashed is False


def test_message_matching_no_rule_is_skipped(tmp_path):
    msg = FakeMessage("m1", ["INBOX"])
    summary = process_messages([msg], [Rule("Social", Action.DELETE)], NAME_TO_ID, str(tmp_path))
    assert msg.trashed is False
    assert summary["skipped"] == 1


def test_first_matching_rule_wins(tmp_path):
    msg = FakeMessage("m1", ["Label_1", "Label_2"])
    rules = [Rule("Newsletters", Action.MARK_READ), Rule("Social", Action.DELETE)]
    process_messages([msg], rules, NAME_TO_ID, str(tmp_path))
    assert msg.read is True
    assert msg.trashed is False


def test_archive_creates_missing_directories(tmp_path):
    root = tmp_path / "does" / "not" / "exist"
    msg = FakeMessage("m1", ["Label_3"])
    process_messages([msg], [Rule("Receipts", Action.ARCHIVE)], NAME_TO_ID, str(root))
    assert (root / "Receipts" / "m1.html").exists()


def test_cancellation_stops_processing(tmp_path):
    msgs = [FakeMessage(f"m{i}", ["Label_2"]) for i in range(5)]
    calls = {"n": 0}

    def cancel():
        calls["n"] += 1
        return calls["n"] > 2  # allow 2 through, then cancel

    summary = process_messages(
        msgs, [Rule("Social", Action.DELETE)], NAME_TO_ID, str(tmp_path), cancel=cancel
    )
    assert summary["cancelled"] is True
    assert sum(1 for m in msgs if m.trashed) == 2


def test_progress_events_emitted_for_apply_stage(tmp_path):
    buf = io.StringIO()
    msgs = [FakeMessage(f"m{i}", ["Label_2"]) for i in range(3)]
    process_messages(
        msgs, [Rule("Social", Action.DELETE)], NAME_TO_ID, str(tmp_path),
        reporter=ProgressReporter(buf),
    )
    events = [json.loads(l) for l in buf.getvalue().splitlines() if l.strip()]
    assert [e["i"] for e in events] == [1, 2, 3]
    assert all(e["stage"] == "apply" and e["n"] == 3 for e in events)


def test_summary_counts(tmp_path):
    msgs = [
        FakeMessage("a", ["Label_1"]),   # mark read
        FakeMessage("b", ["Label_2"]),   # delete
        FakeMessage("c", ["Label_3"]),   # archive
        FakeMessage("d", ["INBOX"]),     # skipped
    ]
    rules = [
        Rule("Newsletters", Action.MARK_READ),
        Rule("Social", Action.DELETE),
        Rule("Receipts", Action.ARCHIVE),
    ]
    summary = process_messages(msgs, rules, NAME_TO_ID, str(tmp_path))
    assert summary["R"] == 1
    assert summary["D"] == 1
    assert summary["A"] == 1
    assert summary["skipped"] == 1
    assert summary["cancelled"] is False
