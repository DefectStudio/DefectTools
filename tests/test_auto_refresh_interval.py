from __future__ import annotations

import unittest

from portable_pipe_tools.render_farm.auto_refresh_interval import (
    AUTO_REFRESH_INTERVAL_LABELS,
    format_auto_refresh_interval,
    parse_auto_refresh_interval,
)


class AutoRefreshIntervalTests(unittest.TestCase):
    def test_labels_match_the_supported_toolbar_choices(self) -> None:
        self.assertEqual(
            ("1 minute", "2 minutes", "5 minutes", "10 minutes"),
            AUTO_REFRESH_INTERVAL_LABELS,
        )

    def test_labels_and_minute_values_round_trip(self) -> None:
        for minutes in (1, 2, 5, 10):
            with self.subTest(minutes=minutes):
                label = format_auto_refresh_interval(minutes)
                self.assertEqual(minutes, parse_auto_refresh_interval(label))

    def test_unsupported_interval_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_auto_refresh_interval("3 minutes")


if __name__ == "__main__":
    unittest.main()
