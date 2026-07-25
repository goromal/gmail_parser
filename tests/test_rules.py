from gmail_parser.rules import Action, Rule, parse_rules, serialize_rules

import pytest


def test_parse_single_archive_rule():
    rules = parse_rules("Newsletters|A\n")
    assert rules == [Rule(label="Newsletters", action=Action.ARCHIVE)]


def test_parse_all_three_actions():
    text = "Promotions|D\nSocial|R\nReceipts|A\n"
    assert parse_rules(text) == [
        Rule(label="Promotions", action=Action.DELETE),
        Rule(label="Social", action=Action.MARK_READ),
        Rule(label="Receipts", action=Action.ARCHIVE),
    ]


def test_parse_ignores_blank_lines_and_trims_whitespace():
    text = "  Newsletters | A \n\n\n"
    assert parse_rules(text) == [Rule(label="Newsletters", action=Action.ARCHIVE)]


def test_parse_preserves_labels_with_slashes_and_spaces():
    rules = parse_rules("Parent/Child Label|D\n")
    assert rules == [Rule(label="Parent/Child Label", action=Action.DELETE)]


def test_parse_rejects_unknown_action():
    with pytest.raises(ValueError):
        parse_rules("Newsletters|X\n")


def test_parse_rejects_line_without_delimiter():
    with pytest.raises(ValueError):
        parse_rules("Newsletters\n")


def test_serialize_round_trips():
    rules = [
        Rule(label="Promotions", action=Action.DELETE),
        Rule(label="Receipts", action=Action.ARCHIVE),
    ]
    assert parse_rules(serialize_rules(rules)) == rules


def test_serialize_produces_pipe_delimited_lines():
    out = serialize_rules([Rule(label="Social", action=Action.MARK_READ)])
    assert out == "Social|R\n"
