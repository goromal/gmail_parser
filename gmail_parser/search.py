"""Fast, query-driven helpers for triaging a mailbox.

The heavy path (``corpus.loadRecent``/``Inbox``) fetches every message's full
body - fine for archiving, far too slow for "how many did TikTok send me?".
These helpers work off the Gmail *metadata* format (headers only, no body) and
off the ``messages().list`` id stream, so decisions can be made cheaply before
any full message is pulled.

Everything here is pure: it parses API response shapes and aggregates them, with
no network or auth. The API mechanics that produce these shapes live in
``corpus`` (batched ``get(format='metadata')`` calls), mirroring how the pure
rule engine in ``processor`` is kept separate from ``corpus``.
"""

import re
from datetime import datetime


def parse_sender(from_header):
    """Split a raw ``From`` header into ``(name, email)``.

    Mirrors the parsing in :class:`~gmail_parser.utils.GMailMessage` so metadata
    and full messages report senders identically. A header without angle
    brackets is treated as both name and email.
    """
    if from_header and "<" in from_header:
        parts = re.split("<|>", from_header)
        return parts[0].strip(), parts[1].strip()
    value = (from_header or "").strip()
    return value, value


def parse_metadata_message(json_object):
    """Build a lightweight metadata dict from a ``format='metadata'`` get.

    Returns ``{id, threadId, labels, sender, sender_name, subject, date}`` where
    ``date`` is an ISO-8601 string derived from ``internalDate``. Missing headers
    default to empty strings; a missing ``internalDate`` yields an empty date.
    Only the ``From``/``Subject`` headers are read, so this is safe to call on
    responses requested with ``metadataHeaders=["From", "Subject"]``.
    """
    headers = json_object.get("payload", {}).get("headers", [])
    from_header = ""
    subject = ""
    for header in headers:
        name = header.get("name", "").lower()
        if name == "from":
            from_header = header.get("value", "")
        elif name == "subject":
            subject = header.get("value", "")
    sender_name, sender_email = parse_sender(from_header)

    date = ""
    if "internalDate" in json_object:
        date = datetime.fromtimestamp(
            float(json_object["internalDate"]) / 1000.0
        ).isoformat()

    return {
        "id": json_object.get("id"),
        "threadId": json_object.get("threadId"),
        "labels": list(json_object.get("labelIds", [])),
        "sender": sender_email,
        "sender_name": sender_name,
        "subject": subject,
        "date": date,
    }


def aggregate_senders(metas):
    """Count metadata dicts by sender, most frequent first.

    Returns a list of ``{"sender", "sender_name", "count"}`` sorted by
    descending count then sender. The first-seen display name for each address
    is kept, so callers get a human-readable label alongside the address.
    """
    counts = {}
    names = {}
    for meta in metas:
        sender = meta.get("sender", "")
        counts[sender] = counts.get(sender, 0) + 1
        if sender not in names:
            names[sender] = meta.get("sender_name", sender)
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [
        {"sender": sender, "sender_name": names[sender], "count": count}
        for sender, count in ordered
    ]


def chunked(items, size):
    """Yield successive ``size``-length chunks of ``items`` (a list)."""
    for start in range(0, len(items), size):
        yield items[start : start + size]
