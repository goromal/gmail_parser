"""On-disk index over archived email HTML files.

Archives live at ``<root>/<label>/<id>.html``. The index scans that tree and
reads each file's ``<meta>`` tags (cheap - only the head is needed) to build the
list the Mail UI renders, and provides safe deletion.
"""

import os

from gmail_parser.archive import parse_archive_meta


def list_archives(root):
    """Return archive entries under root, newest first.

    Each entry is a dict with ``label``, ``id``, ``sender``, ``subject``,
    ``date``, and absolute ``path``. A missing root yields an empty list.
    """
    entries = []
    if not os.path.isdir(root):
        return entries
    for label in os.listdir(root):
        label_dir = os.path.join(root, label)
        if not os.path.isdir(label_dir):
            continue
        for name in os.listdir(label_dir):
            if not name.endswith(".html"):
                continue
            path = os.path.join(label_dir, name)
            try:
                with open(path, encoding="utf-8") as f:
                    meta = parse_archive_meta(f.read())
            except (OSError, ValueError):
                continue
            entry = dict(meta)
            entry["label"] = label
            entry["path"] = path
            entries.append(entry)
    entries.sort(key=lambda e: e.get("date", ""), reverse=True)
    return entries


def _safe_join(root, label, id):
    """Join and confirm the result stays within root (blocks path escapes)."""
    root_abs = os.path.abspath(root)
    path = os.path.abspath(os.path.join(root_abs, label, id + ".html"))
    if os.path.commonpath([root_abs, path]) != root_abs:
        raise ValueError("archive path escapes root")
    return path


def delete_archive(root, label, id):
    """Permanently delete one archived email. Missing file is a no-op."""
    path = _safe_join(root, label, id)
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
