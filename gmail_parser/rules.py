"""Label -> action rules for the GMail cleaner.

The on-disk config (``~/configs/mail-clean.csv``) is a pipe-delimited list of
``LABEL|ACTION`` lines, mirroring the convention used by task_tools'
intervaled-tasks.csv. This module is the single source of truth for parsing and
serializing that format so the CLI and the Mail flask UI agree on it.
"""

from dataclasses import dataclass
from enum import Enum


class Action(Enum):
    DELETE = "D"
    MARK_READ = "R"
    ARCHIVE = "A"


@dataclass(frozen=True)
class Rule:
    label: str
    action: Action


def parse_rules(text):
    """Parse pipe-delimited ``LABEL|ACTION`` lines into a list of Rules.

    Blank lines are ignored; surrounding whitespace is trimmed. Raises
    ValueError on a line missing the delimiter or with an unknown action code.
    """
    rules = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if "|" not in line:
            raise ValueError(f"rule line missing '|' delimiter: {line!r}")
        label, _, code = line.partition("|")
        label = label.strip()
        code = code.strip()
        try:
            action = Action(code)
        except ValueError:
            raise ValueError(f"unknown action code {code!r} in line: {line!r}")
        rules.append(Rule(label=label, action=action))
    return rules


def serialize_rules(rules):
    """Serialize Rules back into pipe-delimited text (trailing newline per rule)."""
    return "".join(f"{rule.label}|{rule.action.value}\n" for rule in rules)
