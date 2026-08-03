from __future__ import annotations

import logging
from queue import Queue
import unittest

from portable_pipe_tools.apps.render_worker_app import (
    QueueLogHandler,
    format_job_activity,
)


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


class RenderWorkerAppTests(unittest.TestCase):
    def test_job_activity_uses_short_graph_name_and_padded_version(self) -> None:
        activity = format_job_activity(
            {
                "shot_name": "BSH_000_0030",
                "render_version": 10,
                "render_config": (
                    "/Game/_S3Bishop/RenderSettings/beauty_LowHDsRGB."
                    "beauty_LowHDsRGB"
                ),
            }
        )

        self.assertEqual(
            "Shot: BSH_000_0030  —  Version: v010  —  "
            "Render Setting: beauty_LowHDsRGB",
            activity,
        )

    def test_job_activity_preserves_an_existing_version_prefix(self) -> None:
        activity = format_job_activity(
            {
                "shot_name": "SH010",
                "render_version": "v002",
                "render_config": "/Game/Render/Hero.Hero",
            }
        )

        self.assertIn("Version: v002", activity)


if __name__ == "__main__":
    unittest.main()
