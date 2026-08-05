from __future__ import annotations

from dataclasses import asdict, dataclass
import ctypes
from ctypes import wintypes
import json
import os
from typing import Protocol


DROPBOX_CREDENTIAL_TARGET = "PortablePipeTools/DropboxApiSync"
_CRED_TYPE_GENERIC = 1
_CRED_PERSIST_LOCAL_MACHINE = 2
_ERROR_NOT_FOUND = 1168


@dataclass(frozen=True)
class StoredDropboxCredentials:
    app_key: str
    refresh_token: str
    app_secret: str = ""
    access_token: str = ""


class DropboxCredentialStore(Protocol):
    def load(self) -> StoredDropboxCredentials | None: ...

    def save(self, credentials: StoredDropboxCredentials) -> None: ...

    def delete(self) -> None: ...


class _CREDENTIALW(ctypes.Structure):
    _fields_ = (
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(wintypes.BYTE)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", wintypes.LPVOID),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    )


class WindowsDropboxCredentialStore:
    """Persist the Dropbox refresh token in Windows Credential Manager."""

    def __init__(self, target_name: str = DROPBOX_CREDENTIAL_TARGET) -> None:
        self.target_name = target_name

    @staticmethod
    def _advapi32():
        if os.name != "nt":
            raise OSError("Dropbox credential storage requires Windows.")
        library = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        library.CredReadW.argtypes = (
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.POINTER(_CREDENTIALW)),
        )
        library.CredReadW.restype = wintypes.BOOL
        library.CredWriteW.argtypes = (
            ctypes.POINTER(_CREDENTIALW),
            wintypes.DWORD,
        )
        library.CredWriteW.restype = wintypes.BOOL
        library.CredDeleteW.argtypes = (
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
        )
        library.CredDeleteW.restype = wintypes.BOOL
        library.CredFree.argtypes = (wintypes.LPVOID,)
        library.CredFree.restype = None
        return library

    def load(self) -> StoredDropboxCredentials | None:
        library = self._advapi32()
        credential_pointer = ctypes.POINTER(_CREDENTIALW)()
        if not library.CredReadW(
            self.target_name,
            _CRED_TYPE_GENERIC,
            0,
            ctypes.byref(credential_pointer),
        ):
            error_code = ctypes.get_last_error()
            if error_code == _ERROR_NOT_FOUND:
                return None
            raise ctypes.WinError(error_code)

        try:
            credential = credential_pointer.contents
            raw_payload = ctypes.string_at(
                credential.CredentialBlob,
                credential.CredentialBlobSize,
            )
            payload = json.loads(raw_payload.decode("utf-8"))
        finally:
            library.CredFree(credential_pointer)

        if not isinstance(payload, dict):
            raise ValueError("Stored Dropbox credentials are invalid.")
        app_key = str(payload.get("app_key") or "").strip()
        refresh_token = str(payload.get("refresh_token") or "").strip()
        access_token = str(payload.get("access_token") or "").strip()
        if not access_token and not (app_key and refresh_token):
            raise ValueError("Stored Dropbox credentials are incomplete.")
        return StoredDropboxCredentials(
            app_key=app_key,
            refresh_token=refresh_token,
            app_secret=str(payload.get("app_secret") or "").strip(),
            access_token=access_token,
        )

    def save(self, credentials: StoredDropboxCredentials) -> None:
        library = self._advapi32()
        payload = json.dumps(
            asdict(credentials),
            separators=(",", ":"),
        ).encode("utf-8")
        payload_buffer = ctypes.create_string_buffer(payload)
        credential = _CREDENTIALW()
        credential.Type = _CRED_TYPE_GENERIC
        credential.TargetName = self.target_name
        credential.Comment = "PortablePipeTools Dropbox API sync"
        credential.CredentialBlobSize = len(payload)
        credential.CredentialBlob = ctypes.cast(
            payload_buffer,
            ctypes.POINTER(wintypes.BYTE),
        )
        credential.Persist = _CRED_PERSIST_LOCAL_MACHINE
        credential.UserName = "PortablePipeTools"
        if not library.CredWriteW(ctypes.byref(credential), 0):
            raise ctypes.WinError(ctypes.get_last_error())

    def delete(self) -> None:
        library = self._advapi32()
        if library.CredDeleteW(
            self.target_name,
            _CRED_TYPE_GENERIC,
            0,
        ):
            return
        error_code = ctypes.get_last_error()
        if error_code != _ERROR_NOT_FOUND:
            raise ctypes.WinError(error_code)


def load_saved_dropbox_credentials(
    store: DropboxCredentialStore | None = None,
) -> StoredDropboxCredentials | None:
    return (store or WindowsDropboxCredentialStore()).load()


def save_dropbox_credentials(
    credentials: StoredDropboxCredentials,
    store: DropboxCredentialStore | None = None,
) -> None:
    (store or WindowsDropboxCredentialStore()).save(credentials)


def delete_dropbox_credentials(
    store: DropboxCredentialStore | None = None,
) -> None:
    (store or WindowsDropboxCredentialStore()).delete()
