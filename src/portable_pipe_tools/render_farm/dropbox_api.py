from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
import os
from pathlib import Path
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from portable_pipe_tools.render_farm.dropbox_credentials import (
    DropboxCredentialStore,
    load_saved_dropbox_credentials,
)


DROPBOX_ACCESS_TOKEN_ENV = "PORTABLE_PIPE_TOOLS_DROPBOX_ACCESS_TOKEN"
DROPBOX_APP_KEY_ENV = "PORTABLE_PIPE_TOOLS_DROPBOX_APP_KEY"
DROPBOX_APP_SECRET_ENV = "PORTABLE_PIPE_TOOLS_DROPBOX_APP_SECRET"
DROPBOX_REFRESH_TOKEN_ENV = "PORTABLE_PIPE_TOOLS_DROPBOX_REFRESH_TOKEN"

DROPBOX_API_ROOT = "https://api.dropboxapi.com/2"
DROPBOX_CONTENT_ROOT = "https://content.dropboxapi.com/2"
DROPBOX_OAUTH_TOKEN_URL = "https://api.dropboxapi.com/oauth2/token"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30.0


class DropboxApiError(RuntimeError):
    """Base error for Dropbox API coordination requests."""


class DropboxConfigurationError(DropboxApiError):
    """Raised when API credentials or local path mapping are unavailable."""


class DropboxAuthenticationError(DropboxApiError):
    """Raised when Dropbox rejects the configured credentials."""


class DropboxConflictError(DropboxApiError):
    """Raised when a conditional Dropbox write loses its revision race."""


class DropboxNotFoundError(DropboxApiError):
    """Raised when a Dropbox API path does not exist."""


class DropboxUnavailableError(DropboxApiError):
    """Raised when Dropbox cannot be reached."""


@dataclass(frozen=True)
class DropboxCredentials:
    access_token: str = ""
    app_key: str = ""
    app_secret: str = ""
    refresh_token: str = ""

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> DropboxCredentials:
        selected = os.environ if environment is None else environment
        credentials = cls(
            access_token=str(selected.get(DROPBOX_ACCESS_TOKEN_ENV) or "").strip(),
            app_key=str(selected.get(DROPBOX_APP_KEY_ENV) or "").strip(),
            app_secret=str(selected.get(DROPBOX_APP_SECRET_ENV) or "").strip(),
            refresh_token=str(selected.get(DROPBOX_REFRESH_TOKEN_ENV) or "").strip(),
        )
        if credentials.access_token:
            return credentials
        if credentials.app_key and credentials.refresh_token:
            return credentials
        raise DropboxConfigurationError(
            "Dropbox API sync is enabled, but credentials are missing. Configure "
            f"{DROPBOX_ACCESS_TOKEN_ENV}, or configure both "
            f"{DROPBOX_APP_KEY_ENV} and {DROPBOX_REFRESH_TOKEN_ENV}."
        )

    @classmethod
    def from_sources(
        cls,
        environment: Mapping[str, str] | None = None,
        credential_store: DropboxCredentialStore | None = None,
    ) -> DropboxCredentials:
        """Load environment overrides, then Windows Credential Manager."""
        selected = os.environ if environment is None else environment
        environment_access_token = str(
            selected.get(DROPBOX_ACCESS_TOKEN_ENV) or ""
        ).strip()
        environment_app_key = str(
            selected.get(DROPBOX_APP_KEY_ENV) or ""
        ).strip()
        environment_app_secret = str(
            selected.get(DROPBOX_APP_SECRET_ENV) or ""
        ).strip()
        environment_refresh_token = str(
            selected.get(DROPBOX_REFRESH_TOKEN_ENV) or ""
        ).strip()
        if environment_access_token or (
            environment_app_key and environment_refresh_token
        ):
            return cls.from_environment(selected)

        try:
            stored = load_saved_dropbox_credentials(credential_store)
        except (OSError, ValueError) as error:
            raise DropboxConfigurationError(
                f"Could not read Dropbox credentials from Windows: {error}"
            ) from error
        if stored is None and not environment_app_key:
            raise DropboxConfigurationError(
                "Dropbox API sync is enabled, but no credentials are configured. "
                "Use the Dropbox Credentials button in Worker Setup."
            )
        credentials = cls(
            access_token=(
                environment_access_token
                or (stored.access_token if stored is not None else "")
            ),
            app_key=(
                environment_app_key
                or (stored.app_key if stored is not None else "")
            ),
            app_secret=(
                environment_app_secret
                or (stored.app_secret if stored is not None else "")
            ),
            refresh_token=(
                environment_refresh_token
                or (stored.refresh_token if stored is not None else "")
            ),
        )
        if credentials.access_token or (
            credentials.app_key and credentials.refresh_token
        ):
            return credentials
        raise DropboxConfigurationError(
            "The saved Dropbox credentials are incomplete. Reconnect Dropbox."
        )


@dataclass(frozen=True)
class DropboxFileSnapshot:
    path: str
    revision: str
    data: dict[str, Any]


@dataclass(frozen=True)
class DropboxLocalAccount:
    account_type: str
    path: Path
    root_path: Path


def default_dropbox_info_paths() -> tuple[Path, ...]:
    candidates: list[Path] = []
    for variable in ("LOCALAPPDATA", "APPDATA"):
        root = str(os.environ.get(variable) or "").strip()
        if root:
            candidates.append(Path(root) / "Dropbox" / "info.json")
    return tuple(candidates)


def load_dropbox_local_accounts(
    info_paths: tuple[Path, ...] | None = None,
) -> tuple[DropboxLocalAccount, ...]:
    accounts: list[DropboxLocalAccount] = []
    for info_path in info_paths or default_dropbox_info_paths():
        try:
            payload = json.loads(info_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        for account_type, raw_account in payload.items():
            if not isinstance(raw_account, dict):
                continue
            raw_path = str(raw_account.get("path") or "").strip()
            raw_root_path = str(raw_account.get("root_path") or raw_path).strip()
            if not raw_path or not raw_root_path:
                continue
            account = DropboxLocalAccount(
                account_type=str(account_type),
                path=Path(os.path.abspath(Path(raw_path).expanduser())),
                root_path=Path(
                    os.path.abspath(Path(raw_root_path).expanduser())
                ),
            )
            if account not in accounts:
                accounts.append(account)
    return tuple(accounts)


def resolve_dropbox_api_path(
    local_path: str | Path,
    accounts: tuple[DropboxLocalAccount, ...] | None = None,
) -> str:
    selected_path = Path(os.path.abspath(Path(local_path).expanduser()))
    matches: list[tuple[int, Path]] = []
    for account in accounts or load_dropbox_local_accounts():
        for candidate_root in (account.root_path, account.path):
            try:
                relative = selected_path.relative_to(candidate_root)
            except ValueError:
                continue
            matches.append((len(candidate_root.parts), relative))
    if not matches:
        raise DropboxConfigurationError(
            "The selected Render Farm folder is not inside a Dropbox account "
            f"listed by the desktop client: {selected_path}"
        )
    relative_path = max(matches, key=lambda item: item[0])[1]
    api_path = "/" + relative_path.as_posix().strip("/")
    return api_path.rstrip("/") or ""


class DropboxHttpJsonStore:
    """Small dependency-free Dropbox client for coordination JSON documents."""

    def __init__(
        self,
        credentials: DropboxCredentials,
        *,
        timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        self.credentials = credentials
        self.timeout_seconds = timeout_seconds
        self._access_token = credentials.access_token
        self._access_token_expires_at = 0.0
        self._path_root_header = ""

    def prepare(self) -> None:
        self._ensure_access_token()
        account = self._post_json("/users/get_current_account", None, path_root=False)
        root_info = account.get("root_info")
        root_namespace_id = (
            str(root_info.get("root_namespace_id") or "").strip()
            if isinstance(root_info, dict)
            else ""
        )
        if not root_namespace_id:
            raise DropboxConfigurationError(
                "Dropbox did not report a root namespace for this account."
            )
        self._path_root_header = json.dumps(
            {".tag": "root", "root": root_namespace_id},
            separators=(",", ":"),
        )

    def ensure_folder(self, api_path: str) -> None:
        try:
            self._post_json(
                "/files/create_folder_v2",
                {"path": api_path, "autorename": False},
            )
        except DropboxConflictError:
            return

    def download_json(self, api_path: str) -> DropboxFileSnapshot:
        request = Request(
            f"{DROPBOX_CONTENT_ROOT}/files/download",
            data=b"",
            method="POST",
            headers=self._headers(
                {"Dropbox-API-Arg": json.dumps({"path": api_path})}
            ),
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                metadata = json.loads(response.headers.get("Dropbox-API-Result") or "{}")
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            self._raise_http_error(error)
        except (URLError, TimeoutError, OSError) as error:
            raise DropboxUnavailableError(
                f"Dropbox download failed for {api_path}: {error}"
            ) from error
        except (UnicodeDecodeError, ValueError) as error:
            raise DropboxApiError(
                f"Dropbox coordination JSON is invalid: {api_path}"
            ) from error
        if not isinstance(data, dict):
            raise DropboxApiError(
                f"Dropbox coordination document is not a JSON object: {api_path}"
            )
        revision = str(metadata.get("rev") or "").strip()
        if not revision:
            raise DropboxApiError(
                f"Dropbox did not return a revision for {api_path}"
            )
        return DropboxFileSnapshot(api_path, revision, data)

    def create_json(
        self,
        api_path: str,
        data: dict[str, Any],
    ) -> DropboxFileSnapshot:
        return self._upload_json(api_path, data, mode="add")

    def update_json(
        self,
        api_path: str,
        expected_revision: str,
        data: dict[str, Any],
    ) -> DropboxFileSnapshot:
        mode = {".tag": "update", "update": expected_revision}
        return self._upload_json(api_path, data, mode=mode)

    def _upload_json(
        self,
        api_path: str,
        data: dict[str, Any],
        *,
        mode: str | dict[str, str],
    ) -> DropboxFileSnapshot:
        content = (
            json.dumps(data, indent=4, ensure_ascii=False) + "\n"
        ).encode("utf-8")
        api_argument = {
            "path": api_path,
            "mode": mode,
            "autorename": False,
            "mute": True,
            "strict_conflict": True,
        }
        request = Request(
            f"{DROPBOX_CONTENT_ROOT}/files/upload",
            data=content,
            method="POST",
            headers=self._headers(
                {
                    "Content-Type": "application/octet-stream",
                    "Dropbox-API-Arg": json.dumps(
                        api_argument,
                        separators=(",", ":"),
                    ),
                }
            ),
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                metadata = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            self._raise_http_error(error)
        except (URLError, TimeoutError, OSError) as error:
            raise DropboxUnavailableError(
                f"Dropbox upload failed for {api_path}: {error}"
            ) from error
        except (UnicodeDecodeError, ValueError) as error:
            raise DropboxApiError(
                f"Dropbox returned invalid upload metadata for {api_path}"
            ) from error
        revision = str(metadata.get("rev") or "").strip()
        if not revision:
            raise DropboxApiError(
                f"Dropbox did not return a revision after updating {api_path}"
            )
        return DropboxFileSnapshot(api_path, revision, dict(data))

    def _post_json(
        self,
        route: str,
        payload: dict[str, Any] | None,
        *,
        path_root: bool = True,
    ) -> dict[str, Any]:
        request = Request(
            f"{DROPBOX_API_ROOT}{route}",
            data=(
                b"null"
                if payload is None
                else json.dumps(payload, separators=(",", ":")).encode("utf-8")
            ),
            method="POST",
            headers=self._headers(
                {"Content-Type": "application/json"},
                path_root=path_root,
            ),
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            self._raise_http_error(error)
        except (URLError, TimeoutError, OSError) as error:
            raise DropboxUnavailableError(
                f"Dropbox request failed for {route}: {error}"
            ) from error
        except (UnicodeDecodeError, ValueError) as error:
            raise DropboxApiError(
                f"Dropbox returned invalid JSON for {route}"
            ) from error
        if not isinstance(data, dict):
            raise DropboxApiError(f"Dropbox returned an invalid response for {route}")
        return data

    def _headers(
        self,
        additional: Mapping[str, str] | None = None,
        *,
        path_root: bool = True,
    ) -> dict[str, str]:
        self._ensure_access_token()
        headers = {"Authorization": f"Bearer {self._access_token}"}
        if path_root:
            if not self._path_root_header:
                self.prepare()
            headers["Dropbox-API-Path-Root"] = self._path_root_header
        if additional:
            headers.update(additional)
        return headers

    def _ensure_access_token(self) -> None:
        if self.credentials.access_token:
            self._access_token = self.credentials.access_token
            return
        if self._access_token and time.monotonic() < self._access_token_expires_at:
            return

        fields = {
            "grant_type": "refresh_token",
            "refresh_token": self.credentials.refresh_token,
            "client_id": self.credentials.app_key,
        }
        if self.credentials.app_secret:
            fields["client_secret"] = self.credentials.app_secret
        request = Request(
            DROPBOX_OAUTH_TOKEN_URL,
            data=urlencode(fields).encode("ascii"),
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                token_data = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise DropboxAuthenticationError(
                "Dropbox rejected the configured refresh credentials."
            ) from error
        except (URLError, TimeoutError, OSError) as error:
            raise DropboxUnavailableError(
                f"Dropbox token refresh failed: {error}"
            ) from error
        access_token = str(token_data.get("access_token") or "").strip()
        if not access_token:
            raise DropboxAuthenticationError(
                "Dropbox token refresh returned no access token."
            )
        try:
            expires_in = max(60, int(token_data.get("expires_in", 14_400)))
        except (TypeError, ValueError):
            expires_in = 14_400
        self._access_token = access_token
        self._access_token_expires_at = time.monotonic() + expires_in - 30

    def _raise_http_error(self, error: HTTPError) -> None:
        try:
            body = error.read().decode("utf-8", errors="replace")
            payload = json.loads(body)
        except ValueError:
            payload = {}
        summary = str(payload.get("error_summary") or "").casefold()
        if error.code in {401, 403}:
            raise DropboxAuthenticationError(
                "Dropbox rejected the configured API credentials or permissions."
            ) from error
        if error.code == 409:
            if "not_found" in summary:
                raise DropboxNotFoundError("Dropbox API path was not found.") from error
            raise DropboxConflictError(
                "Dropbox rejected a stale or conflicting coordination update."
            ) from error
        raise DropboxApiError(
            f"Dropbox API request failed with HTTP {error.code}."
        ) from error
