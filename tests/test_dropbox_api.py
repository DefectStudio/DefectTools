from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from portable_pipe_tools.render_farm.dropbox_api import (
    DROPBOX_ACCESS_TOKEN_ENV,
    DROPBOX_APP_KEY_ENV,
    DROPBOX_REFRESH_TOKEN_ENV,
    DropboxConfigurationError,
    DropboxCredentials,
    DropboxHttpJsonStore,
    DropboxLocalAccount,
    resolve_dropbox_api_path,
)


class DropboxApiConfigurationTests(unittest.TestCase):
    def test_credentials_accept_access_token_or_refresh_pair(self) -> None:
        access = DropboxCredentials.from_environment(
            {DROPBOX_ACCESS_TOKEN_ENV: "access-token"}
        )
        refresh = DropboxCredentials.from_environment(
            {
                DROPBOX_APP_KEY_ENV: "app-key",
                DROPBOX_REFRESH_TOKEN_ENV: "refresh-token",
            }
        )

        self.assertEqual("access-token", access.access_token)
        self.assertEqual("app-key", refresh.app_key)
        self.assertEqual("refresh-token", refresh.refresh_token)

    def test_missing_credentials_fail_only_when_requested(self) -> None:
        with self.assertRaises(DropboxConfigurationError):
            DropboxCredentials.from_environment({})

    def test_team_root_maps_local_farm_to_api_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "Defect Dropbox"
            farm = root / "defect" / "s3bishop" / "renderFarm"
            account = DropboxLocalAccount(
                account_type="business",
                path=root / "Kat Francis",
                root_path=root,
            )

            api_path = resolve_dropbox_api_path(farm, (account,))

        self.assertEqual("/defect/s3bishop/renderFarm", api_path)

    def test_path_outside_dropbox_account_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            account = DropboxLocalAccount(
                account_type="business",
                path=root / "Dropbox" / "User",
                root_path=root / "Dropbox",
            )

            with self.assertRaises(DropboxConfigurationError):
                resolve_dropbox_api_path(root / "Elsewhere" / "renderFarm", (account,))

    def test_revision_update_uses_dropbox_compare_and_swap_mode(self) -> None:
        captured_requests = []

        class FakeResponse:
            headers: dict[str, str] = {}

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                del exc_type, exc_value, traceback

            @staticmethod
            def read() -> bytes:
                return b'{"rev":"new-revision"}'

        def fake_urlopen(request, timeout):
            del timeout
            captured_requests.append(request)
            return FakeResponse()

        store = DropboxHttpJsonStore(
            DropboxCredentials(access_token="secret-token")
        )
        store._path_root_header = '{".tag":"root","root":"123"}'

        with patch(
            "portable_pipe_tools.render_farm.dropbox_api.urlopen",
            side_effect=fake_urlopen,
        ):
            snapshot = store.update_json(
                "/show/renderFarm/Coordination/job.json",
                "expected-revision",
                {"state": "claimed"},
            )

        request = captured_requests[0]
        argument = json.loads(request.get_header("Dropbox-api-arg"))
        self.assertEqual(
            {".tag": "update", "update": "expected-revision"},
            argument["mode"],
        )
        self.assertTrue(argument["strict_conflict"])
        self.assertFalse(argument["autorename"])
        self.assertEqual("new-revision", snapshot.revision)


if __name__ == "__main__":
    unittest.main()
