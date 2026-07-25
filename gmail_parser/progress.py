"""Structured progress events for the two-stage cleaning run.

The ``process`` CLI emits one JSON object per line to stdout. The Mail UI's
RunStore captures those lines and drives two progress bars keyed on ``stage``
(download, then apply). Keeping the format here makes it the shared contract
between the parser and the UI.
"""

import json

STAGE_DOWNLOAD = "download"
STAGE_APPLY = "apply"


class ProgressReporter:
    """Writes single-line JSON progress events to a stream.

    A ``None`` stream makes every emit a no-op, so callers (e.g. the interactive
    shell or tests) need no conditional logic.
    """

    def __init__(self, stream):
        self.stream = stream

    def emit(self, stage, i, n, **extra):
        if self.stream is None:
            return
        record = {"stage": stage, "i": i, "n": n}
        record.update(extra)
        self.stream.write(json.dumps(record) + "\n")
        self.stream.flush()
