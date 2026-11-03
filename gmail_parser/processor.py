"""The label -> action rule engine.

Applies a list of :class:`~gmail_parser.rules.Rule` to already-loaded messages:
the first rule whose label the message carries wins. Delete trashes; MarkRead
marks read; Archive writes a self-contained HTML file under
``<archive_root>/<label>/<id>.html``, saves its attachments under
``<archive_root>/<label>/<id>/``, and then trashes the original. If archiving
fails (e.g. an attachment cannot be downloaded) the original is left untouched
and counted under ``failed``.

The loop is decoupled from the Gmail API: it operates on any object exposing the
small message interface used below, so it is exercised with fakes in tests and
with real ``GMailMessage`` objects in production. Cancellation is cooperative -
``cancel()`` is polled before each message.
"""

import base64
import os
import re

from gmail_parser.archive import build_archive_html
from gmail_parser.progress import ProgressReporter, STAGE_APPLY
from gmail_parser.rules import Action


def _iso(date):
    return date.isoformat() if hasattr(date, "isoformat") else str(date)


def _match_rule(message, rules, label_name_to_id):
    """First rule whose (name-resolved) label id the message carries, else None."""
    message_labels = set(message.getLabels())
    for rule in rules:
        label_id = label_name_to_id.get(rule.label, rule.label)
        if label_id in message_labels:
            return rule
    return None


def _safe_filename(name, taken):
    """A filesystem-safe, unique basename for an attachment."""
    name = os.path.basename(name.replace("\\", "/")).replace("\0", "").strip()
    if name in ("", ".", ".."):
        name = "attachment"
    stem, ext = os.path.splitext(name)
    candidate, n = name, 1
    while candidate in taken:
        n += 1
        candidate = f"{stem} ({n}){ext}"
    taken.add(candidate)
    return candidate


def _embed_inline_images(body, attachments):
    """Replace ``cid:`` references with data URIs; return (body, leftovers).

    Attachments referenced inline are embedded so the archive renders without
    external files; everything else is returned to be saved as a file.
    """
    leftovers = []
    for att in attachments:
        cid = att.get("content_id")
        pattern = re.compile(r"cid:" + re.escape(cid), re.IGNORECASE) if cid else None
        if pattern is not None and pattern.search(body):
            uri = "data:%s;base64,%s" % (
                att["mime_type"], base64.b64encode(att["data"]).decode("ascii")
            )
            body = pattern.sub(lambda _m: uri, body)
        else:
            leftovers.append(att)
    return body, leftovers


def _archive(message, label, archive_root):
    directory = os.path.join(archive_root, label)
    os.makedirs(directory, exist_ok=True)
    attachments = message.getAttachments()
    body, files = _embed_inline_images(message.getArchiveBody(), attachments)
    saved = []
    if files:
        attachment_dir = os.path.join(directory, message.getId())
        os.makedirs(attachment_dir, exist_ok=True)
        taken = set()
        for att in files:
            name = _safe_filename(att.get("filename", ""), taken)
            with open(os.path.join(attachment_dir, name), "wb") as f:
                f.write(att["data"])
            saved.append((name, len(att["data"])))
    html = build_archive_html(
        id=message.getId(),
        sender=message.getSenderEmail(),
        subject=message.getSubject(),
        date=_iso(message.getDate()),
        body_html=body,
        attachments=saved,
    )
    path = os.path.join(directory, message.getId() + ".html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def process_messages(messages, rules, label_name_to_id, archive_root,
                     reporter=None, cancel=None):
    """Apply rules to messages; return a summary dict of action counts.

    Summary keys: ``D``/``R``/``A`` (per-action counts), ``skipped`` (no rule
    matched), ``failed`` (archive errors; message left untouched),
    ``processed``, and ``cancelled``.
    """
    reporter = reporter or ProgressReporter(None)
    summary = {"D": 0, "R": 0, "A": 0, "skipped": 0, "failed": 0, "processed": 0, "cancelled": False}
    total = len(messages)

    for index, message in enumerate(messages):
        if cancel is not None and cancel():
            summary["cancelled"] = True
            break

        error = None
        rule = _match_rule(message, rules, label_name_to_id)
        if rule is None:
            summary["skipped"] += 1
        elif rule.action is Action.DELETE:
            message.moveToTrash()
            summary["D"] += 1
        elif rule.action is Action.MARK_READ:
            message.markAsRead()
            summary["R"] += 1
        elif rule.action is Action.ARCHIVE:
            try:
                _archive(message, rule.label, archive_root)
            except Exception as e:
                error = str(e)
                summary["failed"] += 1
            else:
                message.moveToTrash()
                summary["A"] += 1

        summary["processed"] += 1
        extra = {"error": error} if error else {}
        reporter.emit(
            STAGE_APPLY,
            index + 1,
            total,
            action=(rule.action.value if rule is not None else None),
            id=message.getId(),
            **extra,
        )

    return summary
