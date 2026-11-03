"""Self-contained HTML archive documents.

An archived email is written as a single portable HTML file: the original
message body wrapped in a full document whose ``<head>`` carries the sender,
subject, date, and message id as ``<meta>`` tags. The Mail UI's archive index
reads just those tags (cheaply, from the head) to build its list without
parsing every body.

Attachments are saved beside the document in ``<id>/`` and listed at the end of
the body with links relative to the document, so they work both from disk and
from the Mail UI's path-style archive URLs.
"""

import html as _html
import re
from urllib.parse import quote

_FIELDS = ("id", "sender", "subject", "date")


def _attachments_section(id, attachments):
    items = "\n".join(
        f'        <li><a href="{_html.escape(quote(id) + "/" + quote(name), quote=True)}"'
        f' target="_blank">{_html.escape(name)}</a> ({size:,} bytes)</li>'
        for name, size in attachments
    )
    return (
        '<hr>\n<div class="gmail-archive-attachments">\n'
        f"    <p><b>Attachments ({len(attachments)})</b></p>\n"
        f"    <ul>\n{items}\n    </ul>\n</div>\n"
    )


def build_archive_html(id, sender, subject, date, body_html, attachments=()):
    """Wrap an email body into a self-contained archive document.

    Metadata is HTML-escaped into meta tags so arbitrary subjects/senders
    (quotes, angle brackets, ampersands) round-trip and cannot break the head
    or inject markup. ``attachments`` is a sequence of ``(filename, size)``
    for files saved under ``<id>/`` next to the document.
    """
    meta = {"id": id, "sender": sender, "subject": subject, "date": date}
    meta_tags = "\n".join(
        f'    <meta name="gmail-archive-{key}" content="{_html.escape(str(value), quote=True)}">'
        for key, value in meta.items()
    )
    return (
        "<!DOCTYPE html>\n"
        "<html>\n"
        "<head>\n"
        '    <meta charset="utf-8">\n'
        f"{meta_tags}\n"
        f"    <title>{_html.escape(str(subject), quote=True)}</title>\n"
        "</head>\n"
        "<body>\n"
        f"{body_html}\n"
        f"{_attachments_section(id, attachments) if attachments else ''}"
        "</body>\n"
        "</html>\n"
    )


def parse_archive_meta(text):
    """Extract the archive metadata dict from an archive document's head.

    Raises ValueError if the text is not a gmail archive document.
    """
    result = {}
    for key in _FIELDS:
        match = re.search(
            rf'<meta name="gmail-archive-{key}" content="([^"]*)"', text
        )
        if match is None:
            raise ValueError(f"not a gmail archive document (missing {key})")
        result[key] = _html.unescape(match.group(1))
    return result
