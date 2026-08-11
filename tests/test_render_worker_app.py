from __future__ import annotations

import logging
from queue import Queue
import unittest

from portable_pipe_tools.apps.render_worker_app import (
    DEFAULT_RENDER_TIMEOUT_HOURS,
    QueueLogHandler,
    format_render_timeout_hours,
    format_job_activity,
    parse_render_timeout_hours,
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
    def test_render_timeout_defaults_to_two_hours(self) -> None:
        self.assertEqual(2.0, DEFAULT_RENDER_TIMEOUT_HOURS)
        self.assertEqual(2.0, parse_render_timeout_hours("2"))
        self.assertEqual(0.25, parse_render_timeout_hours("0.25"))
        self.assertEqual("1 hour", format_render_timeout_hours(1.0))
        self.assertEqual("2 hours", format_render_timeout_hours(2.0))

    def test_render_timeout_rejects_invalid_hours(self) -> None:
        for value in ("", "zero", "0", "0.1", "24.1", "nan"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_render_timeout_hours(value)

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
