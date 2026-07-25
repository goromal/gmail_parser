"""The label -> action rule engine.

Applies a list of :class:`~gmail_parser.rules.Rule` to already-loaded messages:
the first rule whose label the message carries wins. Delete trashes; MarkRead
marks read; Archive writes a self-contained HTML file under
``<archive_root>/<label>/<id>.html`` and then trashes the original.

The loop is decoupled from the Gmail API: it operates on any object exposing the
small message interface used below, so it is exercised with fakes in tests and
with real ``GMailMessage`` objects in production. Cancellation is cooperative -
``cancel()`` is polled before each message.
"""

import os

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


def _archive(message, label, archive_root):
    directory = os.path.join(archive_root, label)
    os.makedirs(directory, exist_ok=True)
    html = build_archive_html(
        id=message.getId(),
        sender=message.getSenderEmail(),
        subject=message.getSubject(),
        date=_iso(message.getDate()),
        body_html=message.getArchiveBody(),
    )
    path = os.path.join(directory, message.getId() + ".html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def process_messages(messages, rules, label_name_to_id, archive_root,
                     reporter=None, cancel=None):
    """Apply rules to messages; return a summary dict of action counts.

    Summary keys: ``D``/``R``/``A`` (per-action counts), ``skipped`` (no rule
    matched), ``processed``, and ``cancelled``.
    """
    reporter = reporter or ProgressReporter(None)
    summary = {"D": 0, "R": 0, "A": 0, "skipped": 0, "processed": 0, "cancelled": False}
    total = len(messages)

    for index, message in enumerate(messages):
        if cancel is not None and cancel():
            summary["cancelled"] = True
            break

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
            _archive(message, rule.label, archive_root)
            message.moveToTrash()
            summary["A"] += 1

        summary["processed"] += 1
        reporter.emit(
            STAGE_APPLY,
            index + 1,
            total,
            action=(rule.action.value if rule is not None else None),
            id=message.getId(),
        )

    return summary
