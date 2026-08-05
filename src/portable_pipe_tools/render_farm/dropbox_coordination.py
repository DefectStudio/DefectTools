from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
import time
from typing import Any, Protocol
from uuid import uuid4

from portable_pipe_tools.render_farm.dropbox_api import (
    DropboxConflictError,
    DropboxCredentials,
    DropboxFileSnapshot,
    DropboxHttpJsonStore,
    DropboxNotFoundError,
    resolve_dropbox_api_path,
)
from portable_pipe_tools.render_farm.queue import safe_name, utc_now


COORDINATION_FOLDER_NAME = "Coordination"
COORDINATION_SCHEMA_VERSION = 1
DEFAULT_LOCAL_SETTLE_SECONDS = 30.0


class DropboxCoordinationError(RuntimeError):
    """Base error for a Dropbox-coordinated render job."""


class DropboxClaimLostError(DropboxCoordinationError):
    """Raised when a worker no longer owns the expected claim token."""


class DropboxJsonStore(Protocol):
    def ensure_folder(self, api_path: str) -> None: ...

    def download_json(self, api_path: str) -> DropboxFileSnapshot: ...

    def create_json(
        self,
        api_path: str,
        data: dict[str, Any],
    ) -> DropboxFileSnapshot: ...

    def update_json(
        self,
        api_path: str,
        expected_revision: str,
        data: dict[str, Any],
    ) -> DropboxFileSnapshot: ...


@dataclass(frozen=True)
class DropboxJobClaim:
    job_id: str
    coordination_path: str
    worker_name: str
    session_id: str
    claim_token: str
    generation: int
    attempt: int
    revision: str
    state: str


def _api_join(root: str, *parts: str) -> str:
    selected = PurePosixPath("/" + root.strip("/"))
    for part in parts:
        selected /= part.strip("/")
    return str(selected)


def _blacklisted_workers(job: dict[str, Any]) -> list[str]:
    value = job.get("blacklisted_workers", [])
    if not isinstance(value, list):
        return []
    return [
        worker.strip()
        for worker in value
        if isinstance(worker, str) and worker.strip()
    ]


def _job_attempt(job: dict[str, Any]) -> int:
    """Read a local queue attempt without making malformed jobs unclaimable."""
    value = job.get("attempt", 0)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return 0


def _coordination_attempt(data: dict[str, Any], path: str) -> int:
    value = data.get("attempt", 0)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise DropboxCoordinationError(
            f"Invalid Dropbox coordination attempt in {path}."
        )
    return value


class DropboxJobCoordinator:
    """Use Dropbox server revisions as decentralized job claim arbitration."""

    def __init__(
        self,
        store: DropboxJsonStore,
        api_farm_root: str,
        *,
        session_id: str | None = None,
        local_settle_seconds: float = DEFAULT_LOCAL_SETTLE_SECONDS,
    ) -> None:
        if local_settle_seconds < 0:
            raise ValueError("local_settle_seconds cannot be negative")
        self.store = store
        self.api_farm_root = api_farm_root.rstrip("/")
        self.coordination_folder = _api_join(
            self.api_farm_root,
            COORDINATION_FOLDER_NAME,
        )
        self.session_id = session_id or uuid4().hex
        self.local_settle_seconds = local_settle_seconds
        self._folder_ready = False

    @classmethod
    def from_environment(
        cls,
        local_farm_root: str | Path,
    ) -> DropboxJobCoordinator:
        credentials = DropboxCredentials.from_sources()
        store = DropboxHttpJsonStore(credentials)
        store.prepare()
        return cls(
            store,
            resolve_dropbox_api_path(local_farm_root),
            local_settle_seconds=DEFAULT_LOCAL_SETTLE_SECONDS,
        )

    def try_claim(
        self,
        job: dict[str, Any],
        worker_name: str,
    ) -> DropboxJobClaim | None:
        worker = safe_name(worker_name, "WORKER")
        job_id = safe_name(str(job.get("job_id") or ""), "UNKNOWN-JOB")
        snapshot = self._ensure_document(job_id, job)

        # Merge state written by the default filesystem mode before an API claim
        # is attempted. Conditional updates keep concurrent migrations safe.
        local_blacklist = _blacklisted_workers(job)
        local_attempt = _job_attempt(job)
        for _merge_attempt in range(5):
            data = self._validated_document(snapshot, job_id)
            if str(data.get("state") or "") != "queued":
                return None
            remote_blacklist = _blacklisted_workers(data)
            remote_attempt = _coordination_attempt(data, snapshot.path)
            merged_blacklist = list(remote_blacklist)
            for blacklisted_worker in local_blacklist:
                if not any(
                    existing.casefold() == blacklisted_worker.casefold()
                    for existing in merged_blacklist
                ):
                    merged_blacklist.append(blacklisted_worker)

            # A lower local attempt means Dropbox has not synchronized the latest
            # requeued package to this computer yet. Do not claim the stale copy.
            if local_attempt < remote_attempt:
                return None
            if (
                merged_blacklist == remote_blacklist
                and local_attempt == remote_attempt
            ):
                break
            updated = dict(data)
            updated["blacklisted_workers"] = merged_blacklist
            updated["attempt"] = local_attempt
            updated["updated_utc"] = utc_now()
            try:
                snapshot = self.store.update_json(
                    snapshot.path,
                    snapshot.revision,
                    updated,
                )
                break
            except DropboxConflictError:
                snapshot = self.store.download_json(snapshot.path)
        else:
            raise DropboxCoordinationError(
                "Dropbox coordination changed repeatedly while merging local state."
            )

        data = self._validated_document(snapshot, job_id)
        if str(data.get("state") or "") != "queued":
            return None
        if any(
            blacklisted.casefold() == worker.casefold()
            for blacklisted in _blacklisted_workers(data)
        ):
            return None

        generation = int(data.get("generation", 0)) + 1
        attempt = _coordination_attempt(data, snapshot.path) + 1
        claim_token = uuid4().hex
        claimed = dict(data)
        claimed.update(
            {
                "state": "claimed",
                "generation": generation,
                "attempt": attempt,
                "owner_worker": worker,
                "owner_session": self.session_id,
                "claim_token": claim_token,
                "claimed_utc": utc_now(),
                "updated_utc": utc_now(),
            }
        )
        try:
            updated_snapshot = self.store.update_json(
                snapshot.path,
                snapshot.revision,
                claimed,
            )
        except DropboxConflictError:
            return None
        return DropboxJobClaim(
            job_id=job_id,
            coordination_path=snapshot.path,
            worker_name=worker,
            session_id=self.session_id,
            claim_token=claim_token,
            generation=generation,
            attempt=attempt,
            revision=updated_snapshot.revision,
            state="claimed",
        )

    def settle_and_verify(self, claim: DropboxJobClaim) -> DropboxJobClaim:
        if self.local_settle_seconds > 0:
            time.sleep(self.local_settle_seconds)
        return self.verify_claim(claim, expected_state="claimed")

    def verify_claim(
        self,
        claim: DropboxJobClaim,
        *,
        expected_state: str | None = None,
    ) -> DropboxJobClaim:
        snapshot = self.store.download_json(claim.coordination_path)
        data = self._validated_document(snapshot, claim.job_id)
        self._require_owner(data, claim, expected_state=expected_state)
        return replace(
            claim,
            revision=snapshot.revision,
            state=str(data.get("state") or ""),
        )

    def mark_rendering(self, claim: DropboxJobClaim) -> DropboxJobClaim:
        return self._transition_owned(claim, "claimed", "rendering")

    def mark_complete(self, claim: DropboxJobClaim) -> DropboxJobClaim:
        return self._transition_owned(claim, "rendering", "complete")

    def release_claim(self, claim: DropboxJobClaim, reason: str) -> None:
        self._release_owned(
            claim,
            expected_states={"claimed", "rendering"},
            reason=reason,
            blacklist_worker=False,
            final_state="queued",
        )

    def requeue_failed_claim(self, claim: DropboxJobClaim, reason: str) -> None:
        self._release_owned(
            claim,
            expected_states={"rendering"},
            reason=reason,
            blacklist_worker=True,
            final_state="queued",
        )

    def mark_invalid_failed(self, claim: DropboxJobClaim, reason: str) -> None:
        self._release_owned(
            claim,
            expected_states={"rendering"},
            reason=reason,
            blacklist_worker=False,
            final_state="failed_invalid",
        )

    def _transition_owned(
        self,
        claim: DropboxJobClaim,
        expected_state: str,
        next_state: str,
    ) -> DropboxJobClaim:
        verified = self.verify_claim(claim, expected_state=expected_state)
        snapshot = self.store.download_json(verified.coordination_path)
        data = self._validated_document(snapshot, verified.job_id)
        self._require_owner(data, verified, expected_state=expected_state)
        updated = dict(data)
        updated["state"] = next_state
        updated["updated_utc"] = utc_now()
        if next_state == "complete":
            updated["completed_utc"] = utc_now()
        try:
            result = self.store.update_json(
                snapshot.path,
                snapshot.revision,
                updated,
            )
        except DropboxConflictError as error:
            raise DropboxClaimLostError(
                f"Dropbox claim changed while transitioning to {next_state}."
            ) from error
        return replace(verified, revision=result.revision, state=next_state)

    def _release_owned(
        self,
        claim: DropboxJobClaim,
        *,
        expected_states: set[str],
        reason: str,
        blacklist_worker: bool,
        final_state: str,
    ) -> None:
        snapshot = self.store.download_json(claim.coordination_path)
        data = self._validated_document(snapshot, claim.job_id)
        current_state = str(data.get("state") or "")
        if current_state not in expected_states:
            raise DropboxClaimLostError(
                f"Expected Dropbox claim state {sorted(expected_states)}, got "
                f"{current_state!r}."
            )
        self._require_owner(data, claim)
        updated = dict(data)
        blacklist = _blacklisted_workers(data)
        if blacklist_worker and not any(
            existing.casefold() == claim.worker_name.casefold()
            for existing in blacklist
        ):
            blacklist.append(claim.worker_name)
        updated.update(
            {
                "state": final_state,
                "owner_worker": None,
                "owner_session": None,
                "claim_token": None,
                "blacklisted_workers": blacklist,
                "last_failure_reason": reason if blacklist_worker else None,
                "updated_utc": utc_now(),
            }
        )
        try:
            self.store.update_json(snapshot.path, snapshot.revision, updated)
        except DropboxConflictError as error:
            raise DropboxClaimLostError(
                "Dropbox claim changed before it could be released."
            ) from error

    def _ensure_document(
        self,
        job_id: str,
        job: dict[str, Any],
    ) -> DropboxFileSnapshot:
        coordination_path = _api_join(
            self.coordination_folder,
            f"{job_id}.json",
        )
        try:
            return self.store.download_json(coordination_path)
        except DropboxNotFoundError:
            if not self._folder_ready:
                self.store.ensure_folder(self.coordination_folder)
                self._folder_ready = True
            now = utc_now()
            document = {
                "schema_version": COORDINATION_SCHEMA_VERSION,
                "job_id": job_id,
                "generation": 0,
                "attempt": _job_attempt(job),
                "state": "queued",
                "owner_worker": None,
                "owner_session": None,
                "claim_token": None,
                "blacklisted_workers": _blacklisted_workers(job),
                "created_utc": now,
                "updated_utc": now,
            }
            try:
                return self.store.create_json(coordination_path, document)
            except DropboxConflictError:
                return self.store.download_json(coordination_path)

    @staticmethod
    def _validated_document(
        snapshot: DropboxFileSnapshot,
        expected_job_id: str,
    ) -> dict[str, Any]:
        data = snapshot.data
        if data.get("schema_version") != COORDINATION_SCHEMA_VERSION:
            raise DropboxCoordinationError(
                f"Unsupported Dropbox coordination schema in {snapshot.path}."
            )
        if str(data.get("job_id") or "") != expected_job_id:
            raise DropboxCoordinationError(
                f"Dropbox coordination job ID mismatch in {snapshot.path}."
            )
        generation = data.get("generation")
        if not isinstance(generation, int) or isinstance(generation, bool):
            raise DropboxCoordinationError(
                f"Invalid Dropbox coordination generation in {snapshot.path}."
            )
        _coordination_attempt(data, snapshot.path)
        return data

    @staticmethod
    def _require_owner(
        data: dict[str, Any],
        claim: DropboxJobClaim,
        *,
        expected_state: str | None = None,
    ) -> None:
        checks = (
            str(data.get("owner_worker") or "") == claim.worker_name,
            str(data.get("owner_session") or "") == claim.session_id,
            str(data.get("claim_token") or "") == claim.claim_token,
            data.get("generation") == claim.generation,
            expected_state is None or data.get("state") == expected_state,
        )
        if not all(checks):
            raise DropboxClaimLostError(
                "This worker no longer owns the Dropbox coordination claim."
            )
