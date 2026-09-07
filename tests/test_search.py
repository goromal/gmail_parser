from datetime import datetime

from gmail_parser.search import (
    parse_sender,
    parse_metadata_message,
    aggregate_senders,
    chunked,
)


def test_parse_sender_with_angle_brackets():
    assert parse_sender("TikTok <no-reply@account.tiktok.com>") == (
        "TikTok",
        "no-reply@account.tiktok.com",
    )


def test_parse_sender_bare_address():
    assert parse_sender("plain@example.com") == (
        "plain@example.com",
        "plain@example.com",
    )


def test_parse_sender_empty():
    assert parse_sender("") == ("", "")
    assert parse_sender(None) == ("", "")


def _meta_json(id, from_header, subject, ts_ms, labels=("INBOX",)):
    return {
        "id": id,
        "threadId": "t" + id,
        "labelIds": list(labels),
        "internalDate": str(ts_ms),
        "payload": {
            "headers": [
                {"name": "From", "value": from_header},
                {"name": "Subject", "value": subject},
                {"name": "To", "value": "me@example.com"},
            ]
        },
    }


def test_parse_metadata_message_extracts_fields():
    ts = int(datetime(2026, 7, 24, 9, 30, 0).timestamp() * 1000)
    meta = parse_metadata_message(
        _meta_json("m1", "TikTok <hi@tiktok.com>", "Your feed", ts, labels=("INBOX", "UNREAD"))
    )
    assert meta["id"] == "m1"
    assert meta["threadId"] == "tm1"
    assert meta["sender"] == "hi@tiktok.com"
    assert meta["sender_name"] == "TikTok"
    assert meta["subject"] == "Your feed"
    assert meta["labels"] == ["INBOX", "UNREAD"]
    assert meta["date"].startswith("2026-07-24T09:30")


def test_parse_metadata_message_tolerates_missing_pieces():
    meta = parse_metadata_message({"id": "x", "payload": {}})
    assert meta["id"] == "x"
    assert meta["sender"] == ""
    assert meta["subject"] == ""
    assert meta["labels"] == []
    assert meta["date"] == ""


def test_aggregate_senders_counts_and_orders():
    metas = [
        {"sender": "a@x.com", "sender_name": "A"},
        {"sender": "b@y.com", "sender_name": "B"},
        {"sender": "a@x.com", "sender_name": "A"},
        {"sender": "a@x.com", "sender_name": "A"},
        {"sender": "b@y.com", "sender_name": "B"},
    ]
    stats = aggregate_senders(metas)
    assert stats == [
        {"sender": "a@x.com", "sender_name": "A", "count": 3},
        {"sender": "b@y.com", "sender_name": "B", "count": 2},
    ]


def test_aggregate_senders_ties_break_on_address():
    metas = [
        {"sender": "b@y.com", "sender_name": "B"},
        {"sender": "a@x.com", "sender_name": "A"},
    ]
    stats = aggregate_senders(metas)
    assert [s["sender"] for s in stats] == ["a@x.com", "b@y.com"]


def test_aggregate_senders_keeps_first_seen_name():
    metas = [
        {"sender": "a@x.com", "sender_name": "First"},
        {"sender": "a@x.com", "sender_name": "Second"},
    ]
    assert aggregate_senders(metas)[0]["sender_name"] == "First"


def test_chunked_splits_evenly_and_remainder():
    assert list(chunked([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]
    assert list(chunked([], 2)) == []
    assert list(chunked([1, 2], 5)) == [[1, 2]]
