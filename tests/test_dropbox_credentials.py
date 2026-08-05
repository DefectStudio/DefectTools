from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse
import unittest
from unittest.mock import patch

from portable_pipe_tools.render_farm.dropbox_api import (
    DROPBOX_ACCESS_TOKEN_ENV,
    DROPBOX_APP_KEY_ENV,
    DropboxCredentials,
)
from portable_pipe_tools.render_farm.dropbox_credentials import (
    StoredDropboxCredentials,
    delete_dropbox_credentials,
    load_saved_dropbox_credentials,
    save_dropbox_credentials,
)
from portable_pipe_tools.render_farm.dropbox_oauth import (
    create_pkce_authorization,
    exchange_authorization_code,
)


class InMemoryCredentialStore:
    def __init__(self) -> None:
        self.credentials: StoredDropboxCredentials | None = None

    def load(self) -> StoredDropboxCredentials | None:
        return self.credentials

    def save(self, credentials: StoredDropboxCredentials) -> None:
        self.credentials = credentials

    def delete(self) -> None:
        self.credentials = None


class DropboxCredentialTests(unittest.TestCase):
    def test_saved_credentials_round_trip_without_local_json(self) -> None:
        store = InMemoryCredentialStore()
        credentials = StoredDropboxCredentials(
            app_key="studio-app",
            refresh_token="refresh-token",
        )

        save_dropbox_credentials(credentials, store)
        loaded = load_saved_dropbox_credentials(store)
        delete_dropbox_credentials(store)

        self.assertEqual(credentials, loaded)
        self.assertIsNone(store.credentials)

    def test_api_credentials_load_from_secure_store(self) -> None:
        store = InMemoryCredentialStore()
        store.credentials = StoredDropboxCredentials(
            app_key="studio-app",
            refresh_token="refresh-token",
        )

        credentials = DropboxCredentials.from_sources({}, store)

        self.assertEqual("studio-app", credentials.app_key)
        self.assertEqual("refresh-token", credentials.refresh_token)

    def test_environment_credentials_override_secure_store(self) -> None:
        store = InMemoryCredentialStore()
        store.credentials = StoredDropboxCredentials(
            app_key="stored-app",
            refresh_token="stored-refresh",
        )

        credentials = DropboxCredentials.from_sources(
            {DROPBOX_ACCESS_TOKEN_ENV: "environment-token"},
            store,
        )

        self.assertEqual("environment-token", credentials.access_token)

    def test_environment_app_key_combines_with_stored_refresh_token(self) -> None:
        store = InMemoryCredentialStore()
        store.credentials = StoredDropboxCredentials(
            app_key="old-app",
            refresh_token="stored-refresh",
        )

        credentials = DropboxCredentials.from_sources(
            {DROPBOX_APP_KEY_ENV: "studio-app"},
            store,
        )

        self.assertEqual("studio-app", credentials.app_key)
        self.assertEqual("stored-refresh", credentials.refresh_token)

    def test_pkce_authorization_requests_offline_refresh_access(self) -> None:
        authorization = create_pkce_authorization("studio-app")
        query = parse_qs(urlparse(authorization.authorization_url).query)

        self.assertEqual(["studio-app"], query["client_id"])
        self.assertEqual(["code"], query["response_type"])
        self.assertEqual(["offline"], query["token_access_type"])
        self.assertEqual(["S256"], query["code_challenge_method"])
        self.assertGreaterEqual(len(authorization.code_verifier), 43)

    def test_authorization_code_exchange_returns_refresh_credentials(self) -> None:
        captured_requests = []

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                del exc_type, exc_value, traceback

            @staticmethod
            def read() -> bytes:
                return json.dumps(
                    {
                        "access_token": "short-lived",
                        "refresh_token": "long-lived-refresh",
                    }
                ).encode("utf-8")

        def fake_urlopen(request, timeout):
            del timeout
            captured_requests.append(request)
            return FakeResponse()

        authorization = create_pkce_authorization("studio-app")
        with patch(
            "portable_pipe_tools.render_farm.dropbox_oauth.urlopen",
            side_effect=fake_urlopen,
        ):
            credentials = exchange_authorization_code(
                authorization,
                "authorization-code",
            )

        request_body = parse_qs(captured_requests[0].data.decode("ascii"))
        self.assertEqual(["authorization_code"], request_body["grant_type"])
        self.assertEqual([authorization.code_verifier], request_body["code_verifier"])
        self.assertEqual("studio-app", credentials.app_key)
        self.assertEqual("long-lived-refresh", credentials.refresh_token)


if __name__ == "__main__":
    unittest.main()
