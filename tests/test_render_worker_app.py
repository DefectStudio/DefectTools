from __future__ import annotations

import logging
from queue import Queue
import unittest

from portable_pipe_tools.apps.render_worker_app import QueueLogHandler


class QueueLogHandlerTests(unittest.TestCase):
    def test_log_records_are_forwarded_to_the_ui_queue(self) -> None:
        output_queue: Queue[str] = Queue()
        handler = QueueLogHandler(output_queue)
        handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        record = logging.LogRecord(
            name="render_worker",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="Claimed test job",
            args=(),
            exc_info=None,
        )

        handler.emit(record)

        self.assertEqual("INFO: Claimed test job", output_queue.get_nowait())


if __name__ == "__main__":
    unittest.main()
