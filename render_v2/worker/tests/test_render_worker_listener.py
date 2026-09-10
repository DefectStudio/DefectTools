from __future__ import annotations

import unittest

from portable_pipe_tools.render_farm.listener import (
    ContinuousWorkerState,
    ListenerAction,
    adaptive_poll_interval_seconds,
    parse_poll_interval_seconds,
    waiting_status,
)


class ContinuousWorkerStateTests(unittest.TestCase):
    def test_second_start_cannot_create_another_listener(self) -> None:
        state = ContinuousWorkerState()

        self.assertTrue(state.start())
        self.assertFalse(state.start())

    def test_stop_during_job_finishes_current_then_stops(self) -> None:
        state = ContinuousWorkerState()
        state.start()
        self.assertTrue(state.begin_job_check())

        self.assertEqual(ListenerAction.FINISH_CURRENT, state.request_stop())
        self.assertTrue(state.job_running)
        self.assertEqual(
            ListenerAction.STOPPED,
            state.finish_job_check(job_was_available=True),
        )
        self.assertFalse(state.active)

    def test_completed_or_failed_job_checks_again_immediately(self) -> None:
        state = ContinuousWorkerState()
        state.start()
        state.begin_job_check()

        self.assertEqual(
            ListenerAction.CHECK_NOW,
            state.finish_job_check(job_was_available=True),
        )
        self.assertTrue(state.active)

    def test_empty_queue_waits_before_checking_again(self) -> None:
        state = ContinuousWorkerState()
        state.start()
        state.begin_job_check()

        self.assertEqual(
            ListenerAction.WAIT,
            state.finish_job_check(job_was_available=False),
        )

    def test_unexpected_job_error_keeps_listener_active(self) -> None:
        state = ContinuousWorkerState()
        state.start()
        state.begin_job_check()

        self.assertEqual(ListenerAction.WAIT, state.finish_job_check_with_error())
        self.assertTrue(state.active)


class PollIntervalTests(unittest.TestCase):
    def test_poll_interval_and_waiting_status(self) -> None:
        self.assertEqual(15, parse_poll_interval_seconds("15"))
        self.assertEqual("Waiting for jobs — next check in 1 second", waiting_status(1))
        self.assertEqual(
            "Waiting for jobs — next check in 12 seconds",
            waiting_status(12),
        )

    def test_poll_interval_rejects_invalid_values(self) -> None:
        for value in ("", "1.5", "zero", "0", "3601"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_poll_interval_seconds(value)

    def test_adaptive_polling_doubles_and_caps_at_two_minutes(self) -> None:
        intervals = [
            adaptive_poll_interval_seconds(15, empty_checks, random_value=0.5)
            for empty_checks in range(6)
        ]

        self.assertEqual([15, 30, 60, 120, 120, 120], intervals)

    def test_adaptive_polling_adds_ten_percent_jitter(self) -> None:
        self.assertEqual(
            108,
            adaptive_poll_interval_seconds(15, 3, random_value=0.0),
        )
        self.assertEqual(
            132,
            adaptive_poll_interval_seconds(15, 3, random_value=1.0),
        )

    def test_adaptive_polling_respects_a_slower_operator_setting(self) -> None:
        self.assertEqual(
            300,
            adaptive_poll_interval_seconds(300, 5, random_value=0.5),
        )


if __name__ == "__main__":
    unittest.main()
