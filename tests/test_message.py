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


class _FakeRequest:
    def __init__(self, response):
        self.response = response

    def execute(self):
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class _FakeCorpus:
    """Just enough of corpus.service for users().messages().attachments().get()."""

    userID = "me"

    def __init__(self, store):
        self.store = store  # attachmentId -> response dict (or Exception)
        self.service = self

    def users(self):
        return self

    def messages(self):
        return self

    def attachments(self):
        return self

    def get(self, userId, messageId, id):
        return _FakeRequest(self.store[id])


def _mixed(parts, id="m1"):
    payload = {
        "headers": [{"name": "Subject", "value": "S"}, {"name": "From", "value": "a@b.co"}],
        "mimeType": "multipart/mixed",
        "parts": parts,
    }
    return [{"id": id, "labelIds": ["INBOX"], "internalDate": "1700000000000",
             "payload": payload}]


def _pdf_part(attachment_id="att1", filename="report.pdf"):
    return {"mimeType": "application/pdf", "filename": filename,
            "body": {"attachmentId": attachment_id, "size": 3}}


def test_archive_body_found_in_deeply_nested_parts():
    msg = GMailMessage(_mixed([
        {"mimeType": "multipart/related", "parts": [
            {"mimeType": "multipart/alternative", "parts": [
                {"mimeType": "text/plain", "body": {"data": _enc("p")}},
                {"mimeType": "text/html", "body": {"data": _enc("<p>deep</p>")}},
            ]},
        ]},
        _pdf_part(),
    ]), None)
    assert "<p>deep</p>" in msg.getArchiveBody()


def test_text_attachment_is_not_merged_into_body():
    msg = GMailMessage(_mixed([
        {"mimeType": "text/plain", "body": {"data": _enc("the body")}},
        {"mimeType": "text/plain", "filename": "notes.txt",
         "body": {"data": _enc("attached notes")}},
    ]), None)
    assert "attached notes" not in msg.getContent()
    assert [a["filename"] for a in msg.getAttachments()] == ["notes.txt"]


def test_get_attachments_downloads_by_attachment_id():
    corpus = _FakeCorpus({"att1": {"data": base64.urlsafe_b64encode(b"%PDF").decode().rstrip("=")}})
    msg = GMailMessage(_mixed([
        {"mimeType": "text/plain", "body": {"data": _enc("hi")}},
        _pdf_part(),
    ]), corpus)
    [att] = msg.getAttachments()
    assert att["filename"] == "report.pdf"
    assert att["mime_type"] == "application/pdf"
    assert att["data"] == b"%PDF"
    assert att["content_id"] is None


def test_get_attachments_reads_content_id():
    part = {"mimeType": "image/png", "filename": "logo.png",
            "headers": [{"name": "Content-ID", "value": "<logo@x>"}],
            "body": {"data": base64.urlsafe_b64encode(b"PNG").decode()}}
    msg = GMailMessage(_mixed([part]), None)
    assert msg.getAttachments()[0]["content_id"] == "logo@x"


def test_get_attachments_raises_when_download_fails():
    corpus = _FakeCorpus({"att1": RuntimeError("network")})
    msg = GMailMessage(_mixed([_pdf_part()]), corpus)
    try:
        msg.getAttachments()
    except RuntimeError:
        return
    raise AssertionError("expected RuntimeError")
