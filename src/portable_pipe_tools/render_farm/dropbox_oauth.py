from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import secrets
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from portable_pipe_tools.render_farm.dropbox_api import (
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    DROPBOX_OAUTH_TOKEN_URL,
    DropboxAuthenticationError,
    DropboxCredentials,
    DropboxUnavailableError,
)
from portable_pipe_tools.render_farm.dropbox_credentials import (
    StoredDropboxCredentials,
)


DROPBOX_OAUTH_AUTHORIZE_URL = "https://www.dropbox.com/oauth2/authorize"


@dataclass(frozen=True)
class DropboxPkceAuthorization:
    app_key: str
    code_verifier: str
    authorization_url: str


def create_pkce_authorization(app_key: str) -> DropboxPkceAuthorization:
    selected_app_key = app_key.strip()
    if not selected_app_key:
        raise ValueError("A Dropbox App Key is required.")
    code_verifier = secrets.token_urlsafe(64)
    challenge_digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(challenge_digest).decode("ascii")
    code_challenge = code_challenge.rstrip("=")
    parameters = urlencode(
        {
            "client_id": selected_app_key,
            "response_type": "code",
            "token_access_type": "offline",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    return DropboxPkceAuthorization(
        app_key=selected_app_key,
        code_verifier=code_verifier,
        authorization_url=f"{DROPBOX_OAUTH_AUTHORIZE_URL}?{parameters}",
    )


def exchange_authorization_code(
    authorization: DropboxPkceAuthorization,
    authorization_code: str,
    *,
    timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
) -> StoredDropboxCredentials:
    selected_code = authorization_code.strip()
    if not selected_code:
        raise ValueError("The Dropbox authorization code is required.")
    request = Request(
        DROPBOX_OAUTH_TOKEN_URL,
        data=urlencode(
            {
                "code": selected_code,
                "grant_type": "authorization_code",
                "client_id": authorization.app_key,
                "code_verifier": authorization.code_verifier,
            }
        ).encode("ascii"),
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise DropboxAuthenticationError(
            "Dropbox rejected the authorization code or App Key."
        ) from error
    except (URLError, TimeoutError, OSError) as error:
        raise DropboxUnavailableError(
            f"Dropbox authorization could not be completed: {error}"
        ) from error
    except (UnicodeDecodeError, ValueError) as error:
        raise DropboxAuthenticationError(
            "Dropbox returned an invalid authorization response."
        ) from error

    refresh_token = str(payload.get("refresh_token") or "").strip()
    if not refresh_token:
        raise DropboxAuthenticationError(
            "Dropbox returned no refresh token. Reconnect and approve offline access."
        )
    return StoredDropboxCredentials(
        app_key=authorization.app_key,
        refresh_token=refresh_token,
    )


def api_credentials_from_stored(
    stored: StoredDropboxCredentials,
) -> DropboxCredentials:
    return DropboxCredentials(
        access_token=stored.access_token,
        app_key=stored.app_key,
        app_secret=stored.app_secret,
        refresh_token=stored.refresh_token,
    )
