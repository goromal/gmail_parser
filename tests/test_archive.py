from gmail_parser.archive import build_archive_html, parse_archive_meta

import pytest


META = {
    "id": "18abc123",
    "sender": "News <news@example.com>",
    "subject": "Your weekly digest",
    "date": "2026-07-24T09:30:00",
}


def test_build_then_parse_round_trips_metadata():
    html = build_archive_html(body_html="<p>hello</p>", **META)
    assert parse_archive_meta(html) == META


def test_build_embeds_original_body():
    html = build_archive_html(body_html="<p>unique-body-marker</p>", **META)
    assert "unique-body-marker" in html


def test_build_is_a_full_document():
    html = build_archive_html(body_html="<p>x</p>", **META)
    assert html.lstrip().lower().startswith("<!doctype html>")
    assert "<html" in html.lower() and "</html>" in html.lower()


def test_metadata_with_special_chars_round_trips():
    meta = dict(META, subject='A&B <"quoted"> & more', sender='O\'Brien <a@b.co>')
    html = build_archive_html(body_html="<p>x</p>", **meta)
    assert parse_archive_meta(html) == meta


def test_special_chars_do_not_break_body_marker():
    meta = dict(META, subject='</head><script>evil</script>')
    html = build_archive_html(body_html="<p>safe-body</p>", **meta)
    parsed = parse_archive_meta(html)
    assert parsed["subject"] == '</head><script>evil</script>'
    assert "safe-body" in html


def test_parse_meta_only_needs_the_head():
    html = build_archive_html(body_html="<p>y</p>", **META)
    head_only = html[: html.lower().index("</head>") + len("</head>")]
    assert parse_archive_meta(head_only) == META


def test_parse_returns_none_when_not_an_archive():
    with pytest.raises(ValueError):
        parse_archive_meta("<html><head></head><body>nope</body></html>")
