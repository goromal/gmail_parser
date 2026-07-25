"""Self-contained HTML archive documents.

An archived email is written as a single portable HTML file: the original
message body wrapped in a full document whose ``<head>`` carries the sender,
subject, date, and message id as ``<meta>`` tags. The Mail UI's archive index
reads just those tags (cheaply, from the head) to build its list without
parsing every body.
"""

import html as _html
import re

_FIELDS = ("id", "sender", "subject", "date")


def build_archive_html(id, sender, subject, date, body_html):
    """Wrap an email body into a self-contained archive document.

    Metadata is HTML-escaped into meta tags so arbitrary subjects/senders
    (quotes, angle brackets, ampersands) round-trip and cannot break the head
    or inject markup.
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
