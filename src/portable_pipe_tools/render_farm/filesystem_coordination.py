from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging
import os
from pathlib import Path
import time
from typing import Any
from uuid import uuid4

from portable_pipe_tools.render_farm.queue import (
    create_directory_with_retry,
    read_json_object,
    retry_transient_windows_lock,
    safe_name,
    utc_now,
)


LOGGER = logging.getLogger("render_worker.filesystem_coordination")
FILESYSTEM_COORDINATION_FOLDER = "FilesystemCoordination"
FILESYSTEM_COORDINATION_SCHEMA_VERSION = 1
DEFAULT_INITIAL_JITTER_SECONDS = 5.0
DEFAULT_CLAIM_SETTLE_SECONDS = 30.0
DEFAULT_ELECTION_VERIFY_SECONDS = 10.0
DEFAULT_POST_CLAIM_VERIFY_SECONDS = 15.0


class FilesystemCoordinationError(RuntimeError):
    """Base error for a filesystem-coordinated render claim."""


class FilesystemClaimAmbiguousError(FilesystemCoordinationError):
    """Raised when synchronized claim records do not describe one safe owner."""


class FilesystemClaimLostError(FilesystemCoordinationError):
    """Raised when a worker's sealed claim is no longer the unique owner."""


@dataclass(frozen=True)
class FilesystemJobClaim:
    job_id: str
    attempt: int
    worker_name: str
    session_id: str
    claim_token: str
    package_fingerprint: str
    coordination_folder: Path


@dataclass(frozen=True)
class _ElectionSnapshot:
    all_claim_tokens: frozenset[str]
    active_claim_tokens: frozenset[str]
    active_seal_tokens: frozenset[str]


def _job_attempt(job: dict[str, Any]) -> int:
    value = job.get("attempt", 0)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return 0


def _package_fingerprint(folder: Path) -> str:
    """Hash the immutable queued package so workers can reject stale replicas."""
    digest = hashlib.sha256()
    files = retry_transient_windows_lock(
        operation=lambda: sorted(
            (path for path in folder.rglob("*") if path.is_file()),
            key=lambda path: path.relative_to(folder).as_posix().casefold(),
        ),
        description=f"Scan queued package for claim verification {folder}",
    )
    for file_path in files:
        relative = file_path.relative_to(folder).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")

        def hash_file() -> bytes:
            file_digest = hashlib.sha256()
            with file_path.open("rb") as handle:
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    file_digest.update(chunk)
            return file_digest.digest()

        digest.update(
            retry_transient_windows_lock(
                operation=hash_file,
                description=f"Hash queued package file {file_path}",
            )
        )
        digest.update(b"\0")
    return digest.hexdigest()


def _write_json_exclusive(path: Path, data: dict[str, Any]) -> None:
    create_directory_with_retry(path.parent, parents=True, exist_ok=True)

    def write() -> None:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, indent=4, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

    retry_transient_windows_lock(
        operation=write,
        description=f"Publish append-only coordination record {path}",
    )


class FilesystemJobCoordinator:
    """Best-effort decentralized election over Dropbox-synchronized files."""

    def __init__(
        self,
        farm_root: str | Path,
        *,
        session_id: str | None = None,
        initial_jitter_seconds: float = DEFAULT_INITIAL_JITTER_SECONDS,
        claim_settle_seconds: float = DEFAULT_CLAIM_SETTLE_SECONDS,
        election_verify_seconds: float = DEFAULT_ELECTION_VERIFY_SECONDS,
        post_claim_verify_seconds: float = DEFAULT_POST_CLAIM_VERIFY_SECONDS,
        sleep=None,
    ) -> None:
        delays = (
            initial_jitter_seconds,
            claim_settle_seconds,
            election_verify_seconds,
            post_claim_verify_seconds,
        )
        if any(delay < 0 for delay in delays):
            raise ValueError("Filesystem coordination delays cannot be negative")
        self.root = Path(farm_root) / FILESYSTEM_COORDINATION_FOLDER
        self.session_id = session_id or uuid4().hex
        self.initial_jitter_seconds = initial_jitter_seconds
        self.claim_settle_seconds = claim_settle_seconds
        self.election_verify_seconds = election_verify_seconds
        self.post_claim_verify_seconds = post_claim_verify_seconds
        self.sleep = sleep or time.sleep

    def try_claim(
        self,
        queued_folder: Path,
        job: dict[str, Any],
        worker_name: str,
    ) -> FilesystemJobClaim | None:
        worker = safe_name(worker_name, "WORKER")
        job_id = safe_name(
            str(job.get("job_id") or queued_folder.name),
            queued_folder.name,
        )
        attempt = _job_attempt(job)
        fingerprint = _package_fingerprint(queued_folder)
        coordination_folder = self.root / job_id / f"attempt-{attempt:06d}"
        claim_token = uuid4().hex
        claim = FilesystemJobClaim(
            job_id=job_id,
            attempt=attempt,
            worker_name=worker,
            session_id=self.session_id,
            claim_token=claim_token,
            package_fingerprint=fingerprint,
            coordination_folder=coordination_folder,
        )

        # A visible active seal already fences this attempt. Avoid producing a
        # pair of losing intent/release files on every automatic queue poll.
        if coordination_folder.is_dir():
            existing = self._snapshot(claim, allow_empty=True)
            if existing.active_seal_tokens:
                return None

        jitter = self._deterministic_jitter(job_id, worker)
        if jitter > 0:
            self.sleep(jitter)
        self._publish_claim_marker(claim)
        LOGGER.info(
            "Published filesystem claim intent for %s attempt %s; settling "
            "for %.1f seconds",
            claim.job_id,
            claim.attempt,
            self.claim_settle_seconds,
        )
        if self.claim_settle_seconds > 0:
            self.sleep(self.claim_settle_seconds)

        try:
            first = self._snapshot(claim)
            self._require_package_unchanged(claim, queued_folder)
            if self.election_verify_seconds > 0:
                self.sleep(self.election_verify_seconds)
            second = self._snapshot(claim)
            self._require_package_unchanged(claim, queued_folder)
            if first != second:
                self.release_claim(
                    claim,
                    "Claim records changed during the verification interval.",
                )
                return None
            winner = self._winner(second)
            if winner != claim.claim_token:
                self.release_claim(
                    claim,
                    f"Deterministic filesystem election winner was {winner}.",
                )
                return None
            self._publish_seal(claim)
            return claim
        except Exception:
            self.release_claim(
                claim,
                "Claim attempt aborted because ownership could not be verified.",
            )
            raise

    def settle_after_local_claim(self, claim: FilesystemJobClaim) -> None:
        if self.post_claim_verify_seconds > 0:
            self.sleep(self.post_claim_verify_seconds)
        self.verify_claim(claim)

    def verify_claim(self, claim: FilesystemJobClaim) -> None:
        snapshot = self._snapshot(claim)
        if snapshot.active_seal_tokens != frozenset({claim.claim_token}):
            raise FilesystemClaimLostError(
                "This worker is not the unique active sealed filesystem owner."
            )
        if claim.claim_token not in snapshot.active_claim_tokens:
            raise FilesystemClaimLostError(
                "This worker's filesystem claim has been released."
            )

    def release_claim(self, claim: FilesystemJobClaim, reason: str) -> None:
        release_path = claim.coordination_folder / "Releases" / (
            f"{claim.claim_token}.json"
        )
        try:
            _write_json_exclusive(
                release_path,
                {
                    "schema_version": FILESYSTEM_COORDINATION_SCHEMA_VERSION,
                    "job_id": claim.job_id,
                    "attempt": claim.attempt,
                    "claim_token": claim.claim_token,
                    "worker_name": claim.worker_name,
                    "session_id": claim.session_id,
                    "reason": reason,
                    "released_utc": utc_now(),
                },
            )
        except FileExistsError:
            return

    def _publish_claim_marker(self, claim: FilesystemJobClaim) -> None:
        _write_json_exclusive(
            claim.coordination_folder / "Claims" / f"{claim.claim_token}.json",
            {
                "schema_version": FILESYSTEM_COORDINATION_SCHEMA_VERSION,
                "job_id": claim.job_id,
                "attempt": claim.attempt,
                "worker_name": claim.worker_name,
                "session_id": claim.session_id,
                "claim_token": claim.claim_token,
                "package_fingerprint": claim.package_fingerprint,
                "created_utc": utc_now(),
            },
        )

    def _publish_seal(self, claim: FilesystemJobClaim) -> None:
        _write_json_exclusive(
            claim.coordination_folder / "Seals" / f"{claim.claim_token}.json",
            {
                "schema_version": FILESYSTEM_COORDINATION_SCHEMA_VERSION,
                "job_id": claim.job_id,
                "attempt": claim.attempt,
                "worker_name": claim.worker_name,
                "session_id": claim.session_id,
                "claim_token": claim.claim_token,
                "package_fingerprint": claim.package_fingerprint,
                "sealed_utc": utc_now(),
            },
        )

    def _snapshot(
        self,
        claim: FilesystemJobClaim,
        *,
        allow_empty: bool = False,
    ) -> _ElectionSnapshot:
        claim_records = self._read_records(
            claim.coordination_folder / "Claims",
            claim,
        )
        seal_records = self._read_records(
            claim.coordination_folder / "Seals",
            claim,
        )
        release_records = self._read_records(
            claim.coordination_folder / "Releases",
            claim,
            require_fingerprint=False,
        )
        all_claim_tokens = frozenset(claim_records)
        released_tokens = frozenset(release_records)
        active_claim_tokens = all_claim_tokens - released_tokens
        active_seal_tokens = frozenset(seal_records) - released_tokens
        if not active_claim_tokens and not allow_empty:
            raise FilesystemClaimAmbiguousError(
                "No active filesystem claim markers remain."
            )
        if not active_seal_tokens.issubset(active_claim_tokens):
            raise FilesystemClaimAmbiguousError(
                "A filesystem seal does not have a matching active claim."
            )
        if len(active_seal_tokens) > 1:
            raise FilesystemClaimAmbiguousError(
                "Multiple active filesystem claim seals were observed."
            )
        return _ElectionSnapshot(
            all_claim_tokens=all_claim_tokens,
            active_claim_tokens=active_claim_tokens,
            active_seal_tokens=active_seal_tokens,
        )

    @staticmethod
    def _winner(snapshot: _ElectionSnapshot) -> str:
        if snapshot.active_seal_tokens:
            return next(iter(snapshot.active_seal_tokens))
        return min(snapshot.active_claim_tokens)

    @staticmethod
    def _read_records(
        folder: Path,
        claim: FilesystemJobClaim,
        *,
        require_fingerprint: bool = True,
    ) -> dict[str, dict[str, Any]]:
        try:
            paths = sorted(folder.glob("*.json"))
        except OSError as error:
            raise FilesystemClaimAmbiguousError(
                f"Could not scan filesystem coordination records: {folder}"
            ) from error
        records: dict[str, dict[str, Any]] = {}
        for path in paths:
            try:
                data = read_json_object(path)
            except (OSError, ValueError) as error:
                raise FilesystemClaimAmbiguousError(
                    f"Unreadable filesystem coordination record: {path}"
                ) from error
            token = str(data.get("claim_token") or "").strip()
            valid = (
                data.get("schema_version")
                == FILESYSTEM_COORDINATION_SCHEMA_VERSION
                and str(data.get("job_id") or "") == claim.job_id
                and data.get("attempt") == claim.attempt
                and token
                and path.stem == token
            )
            if require_fingerprint:
                valid = valid and (
                    str(data.get("package_fingerprint") or "")
                    == claim.package_fingerprint
                )
            if not valid or token in records:
                raise FilesystemClaimAmbiguousError(
                    f"Invalid filesystem coordination record: {path}"
                )
            records[token] = data
        return records

    @staticmethod
    def _require_package_unchanged(
        claim: FilesystemJobClaim,
        queued_folder: Path,
    ) -> None:
        if not queued_folder.is_dir():
            raise FilesystemClaimLostError(
                "The queued package disappeared during claim verification."
            )
        if _package_fingerprint(queued_folder) != claim.package_fingerprint:
            raise FilesystemClaimAmbiguousError(
                "The queued package changed during claim verification."
            )

    def _deterministic_jitter(self, job_id: str, worker: str) -> float:
        if self.initial_jitter_seconds <= 0:
            return 0.0
        value = int.from_bytes(
            hashlib.sha256(f"{job_id}\0{worker}".encode("utf-8")).digest()[:8],
            "big",
        )
        return (value / ((1 << 64) - 1)) * self.initial_jitter_seconds
