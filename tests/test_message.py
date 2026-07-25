import base64

from gmail_parser.utils import GMailMessage


def _enc(s):
    return base64.urlsafe_b64encode(s.encode()).decode()


def _make(html=None, plain=None, subject="S", sender="N <n@e.co>",
          labels=("INBOX",), id="m1", alternative=False):
    parts = []
    if alternative:
        sub = []
        if plain is not None:
            sub.append({"mimeType": "text/plain", "body": {"data": _enc(plain)}})
        if html is not None:
            sub.append({"mimeType": "text/html", "body": {"data": _enc(html)}})
        parts.append({"mimeType": "multipart/alternative", "parts": sub})
    else:
        if plain is not None:
            parts.append({"mimeType": "text/plain", "body": {"data": _enc(plain)}})
        if html is not None:
            parts.append({"mimeType": "text/html", "body": {"data": _enc(html)}})
    payload = {
        "headers": [
            {"name": "Subject", "value": subject},
            {"name": "From", "value": sender},
        ],
        "parts": parts,
    }
    return [{"id": id, "labelIds": list(labels), "internalDate": "1700000000000",
             "payload": payload}]


def test_get_id():
    msg = GMailMessage(_make(plain="hi"), None)
    assert msg.getId() == "m1"


def test_archive_body_uses_html_part_when_present():
    msg = GMailMessage(_make(html="<h1>rich content</h1>", plain="plain fallback"), None)
    body = msg.getArchiveBody()
    assert "<h1>rich content</h1>" in body


def test_archive_body_captures_nested_html_in_multipart_alternative():
    msg = GMailMessage(_make(html="<p>nested</p>", plain="p", alternative=True), None)
    assert "<p>nested</p>" in msg.getArchiveBody()


def test_archive_body_falls_back_to_plain_text_when_no_html():
    msg = GMailMessage(_make(plain="just plain text"), None)
    body = msg.getArchiveBody()
    assert "just plain text" in body


def test_archive_body_plain_fallback_escapes_html_special_chars():
    msg = GMailMessage(_make(plain="1 < 2 & 3 > 0"), None)
    body = msg.getArchiveBody()
    assert "1 < 2 & 3 > 0" not in body  # must be escaped, not raw
    assert "&lt;" in body and "&amp;" in body
