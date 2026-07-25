import io
import json

from gmail_parser.progress import ProgressReporter, STAGE_DOWNLOAD, STAGE_APPLY


def _lines(buf):
    return [json.loads(line) for line in buf.getvalue().splitlines() if line.strip()]


def test_emit_writes_one_json_line_per_call():
    buf = io.StringIO()
    reporter = ProgressReporter(buf)
    reporter.emit(STAGE_DOWNLOAD, 1, 10)
    reporter.emit(STAGE_DOWNLOAD, 2, 10)
    assert _lines(buf) == [
        {"stage": "download", "i": 1, "n": 10},
        {"stage": "download", "i": 2, "n": 10},
    ]


def test_emit_includes_extra_fields():
    buf = io.StringIO()
    ProgressReporter(buf).emit(STAGE_APPLY, 3, 5, action="D", id="abc")
    assert _lines(buf) == [{"stage": "apply", "i": 3, "n": 5, "action": "D", "id": "abc"}]


def test_each_event_is_a_single_line():
    buf = io.StringIO()
    reporter = ProgressReporter(buf)
    reporter.emit(STAGE_APPLY, 1, 1)
    assert buf.getvalue().count("\n") == 1


def test_none_stream_is_a_no_op():
    reporter = ProgressReporter(None)
    reporter.emit(STAGE_APPLY, 1, 1)  # must not raise
