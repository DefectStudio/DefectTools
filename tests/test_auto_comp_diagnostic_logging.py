from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from portable_pipe_tools.auto_comp_natron.diagnostic_logging import (
    VerboseDiagnosticLog,
    get_dropbox_host_id,
    get_shared_diagnostic_log_directory,
)


class VerboseDiagnosticLogTests(unittest.TestCase):
    def test_enabled_log_records_details_and_exception_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            log_path = Path(temporary_directory) / "verbose.log"
            diagnostic_log = VerboseDiagnosticLog(log_path, enabled=True)

            diagnostic_log.write("User selected shot", shot="BSH_000_0020")
            try:
                raise RuntimeError("Natron launch failed")
            except RuntimeError as error:
                diagnostic_log.exception("Open comp failed", error)

            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn("Verbose logging enabled", log_text)
            self.assertIn("User selected shot", log_text)
            self.assertIn("shot='BSH_000_0020'", log_text)
            self.assertIn("windows_username=", log_text)
            self.assertIn("computer_name=", log_text)
            self.assertIn("Open comp failed", log_text)
            self.assertIn("RuntimeError: Natron launch failed", log_text)

    def test_disabled_log_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            log_path = Path(temporary_directory) / "verbose.log"
            diagnostic_log = VerboseDiagnosticLog(log_path)

            diagnostic_log.write("This is disabled")

            self.assertFalse(log_path.exists())

    def test_shared_directory_fallback_includes_windows_user_and_computer(
        self,
    ) -> None:
        repository = Path("F:/Dropbox/defect")

        log_directory = get_shared_diagnostic_log_directory(
            repository,
            windows_username='Artist:One/Compositing',
            computer_name="WORKSTATION:07",
            dropbox_info_paths=(),
        )

        self.assertEqual(
            repository
            / "Development"
            / "Logs"
            / "AutoComp Natron"
            / "Windows-Artist_One_Compositing@WORKSTATION_07",
            log_directory,
        )

    def test_shared_directory_uses_matching_dropbox_host_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            dropbox_root = temporary_path / "Dropbox Business"
            repository = dropbox_root / "defect"
            repository.mkdir(parents=True)
            info_path = temporary_path / "info.json"
            info_path.write_text(
                json.dumps(
                    {
                        "personal": {
                            "path": str(temporary_path / "Personal Dropbox"),
                            "host": 111,
                        },
                        "business": {
                            "path": str(dropbox_root / "Artist Name"),
                            "root_path": str(dropbox_root),
                            "host": 987654321,
                        },
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                "987654321",
                get_dropbox_host_id(repository, info_paths=(info_path,)),
            )
            self.assertEqual(
                repository
                / "Development"
                / "Logs"
                / "AutoComp Natron"
                / "Dropbox-987654321",
                get_shared_diagnostic_log_directory(
                    repository,
                    dropbox_info_paths=(info_path,),
                ),
            )
            self.assertEqual(
                repository
                / "Development"
                / "Logs"
                / "AutoComp Natron"
                / "Kat Francis",
                get_shared_diagnostic_log_directory(
                    repository,
                    log_username="Kat Francis",
                    dropbox_info_paths=(info_path,),
                ),
            )

    def test_daily_directory_starts_a_new_file_after_midnight(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            log_directory = Path(temporary_directory) / "Artist"
            current_time = [
                datetime(2026, 8, 24, 23, 59, tzinfo=timezone.utc)
            ]
            diagnostic_log = VerboseDiagnosticLog(
                Path(temporary_directory) / "fallback.log",
                enabled=True,
                daily_directory=log_directory,
                now=lambda: current_time[0],
            )
            diagnostic_log.write("First day action")

            current_time[0] = datetime(
                2026,
                8,
                25,
                0,
                1,
                tzinfo=timezone.utc,
            )
            diagnostic_log.write("Second day action")

            first_log = log_directory / "2026-08-24.log"
            second_log = log_directory / "2026-08-25.log"
            self.assertIn("First day action", first_log.read_text("utf-8"))
            self.assertNotIn("Second day action", first_log.read_text("utf-8"))
            self.assertIn("Second day action", second_log.read_text("utf-8"))

    def test_natron_output_uses_the_same_daily_log_as_auto_comp(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            current_time = datetime(
                2026,
                8,
                24,
                13,
                45,
                tzinfo=timezone.utc,
            )
            log_directory = Path(temporary_directory) / "Linny"
            diagnostic_log = VerboseDiagnosticLog(
                Path(temporary_directory) / "fallback.log",
                enabled=True,
                daily_directory=log_directory,
                now=lambda: current_time,
            )

            output_path = diagnostic_log.natron_output_log_path(
                "Natron:GUI",
                "ZZZ/1000",
            )

            self.assertEqual(
                log_directory / "2026-08-24.log",
                output_path,
            )
            with output_path.open("a", encoding="utf-8") as output_log:
                output_log.write("Natron stderr example\n")
            diagnostic_log.write("AutoComp action example")

            self.assertEqual([output_path], list(log_directory.rglob("*.*")))
            combined_text = output_path.read_text(encoding="utf-8")
            self.assertIn("Natron stderr example", combined_text)
            self.assertIn("AutoComp action example", combined_text)


if __name__ == "__main__":
    unittest.main()
