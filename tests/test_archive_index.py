import os

from gmail_parser.archive import build_archive_html
from gmail_parser.archive_index import list_archives, delete_archive


def _write(root, label, id, subject="S", sender="a@b.co", date="2026-07-24T00:00:00"):
    directory = os.path.join(root, label)
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, id + ".html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(build_archive_html(id=id, sender=sender, subject=subject,
                                   date=date, body_html="<p>x</p>"))
    return path


def test_list_empty_or_missing_root(tmp_path):
    assert list_archives(str(tmp_path / "nope")) == []


def test_list_returns_entries_with_metadata(tmp_path):
    _write(str(tmp_path), "Receipts", "m1", subject="Receipt 1")
    _write(str(tmp_path), "News", "m2", subject="Digest")
    entries = list_archives(str(tmp_path))
    by_id = {e["id"]: e for e in entries}
    assert by_id["m1"]["label"] == "Receipts"
    assert by_id["m1"]["subject"] == "Receipt 1"
    assert by_id["m2"]["label"] == "News"
    assert os.path.exists(by_id["m1"]["path"])


def test_list_sorted_by_date_descending(tmp_path):
    _write(str(tmp_path), "L", "old", date="2026-01-01T00:00:00")
    _write(str(tmp_path), "L", "new", date="2026-07-01T00:00:00")
    ids = [e["id"] for e in list_archives(str(tmp_path))]
    assert ids == ["new", "old"]


def test_delete_removes_the_file(tmp_path):
    path = _write(str(tmp_path), "L", "m1")
    assert os.path.exists(path)
    delete_archive(str(tmp_path), "L", "m1")
    assert not os.path.exists(path)


def test_delete_missing_is_noop(tmp_path):
    delete_archive(str(tmp_path), "L", "ghost")  # must not raise


def test_delete_rejects_path_escape(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        delete_archive(str(tmp_path), "..", "../../etc/passwd")
