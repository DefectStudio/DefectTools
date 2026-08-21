"""Report SmartWrite frame progress to the process status file."""

import json
import os
import re
import sys
import threading
import time


STATUS_ENV = "PORTABLE_PIPE_SMART_WRITE_RENDER_STATUS"
CALLBACK_NAME = "SmartWriteRenderProgress.afterFrameRender"
WRITE_INTERVAL_SECONDS = 0.2
MIN_VIDEO_BYTES = 1024
_VIDEO_EXTENSIONS = {".mp4", ".mov"}

_LOCK = threading.Lock()
_status_path = ""
_state = "rendering"
_message = ""
_total_frames = 0
_completed_frames = set()
_output_totals = {}
_output_completed = {}
_output_details = {}
_output_aliases = {}
_output_filenames = {}
_current_frame = None
_rendered_smart_writes = 0
_last_write_time = 0.0


def log_event(event, **details):
    """Write one durable, machine-readable milestone to captured Natron output."""

    if not os.environ.get(STATUS_ENV):
        return
    try:
        payload = {
            "event": str(event),
            "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        payload.update(details)
        sys.stdout.write(
            "[SmartWriteRender] {0}\n".format(
                json.dumps(payload, sort_keys=True, default=str)
            )
        )
        sys.stdout.flush()
    except Exception:
        # Logging must never interrupt a render.
        return


def _writer_name(writer):
    for method_name in ("getFullyQualifiedName", "getScriptName"):
        method = getattr(writer, method_name, None)
        if method is None:
            continue
        try:
            value = method()
        except Exception:
            continue
        if value:
            return str(value)
    return str(id(writer))


def _writer_aliases(writer):
    aliases = set()
    for method_name in (
        "getFullyQualifiedName",
        "getScriptName",
        "getLabel",
    ):
        method = getattr(writer, method_name, None)
        if method is None:
            continue
        try:
            value = method()
        except Exception:
            continue
        if not value:
            continue
        value = str(value)
        aliases.add(value)
        aliases.add(value.rsplit(".", 1)[-1])
        if value.startswith("app."):
            aliases.add(value[4:])
    return aliases


def _writer_filename(writer):
    try:
        filename = writer.getParam("filename")
        if filename is not None and filename.get():
            return str(filename.get())
    except Exception:
        pass
    return ""


def _normalized_filename(filename):
    if not filename:
        return ""
    return os.path.normcase(os.path.normpath(str(filename)))


def _task_frame_count(first_frame, last_frame, frame_increment):
    first_frame = int(first_frame)
    last_frame = int(last_frame)
    frame_increment = max(1, int(frame_increment))
    if last_frame < first_frame:
        return 0
    return ((last_frame - first_frame) // frame_increment) + 1


def _resolve_output_name_locked(writer):
    writer_name = _writer_name(writer)
    if writer_name in _output_totals:
        return writer_name

    filename = _normalized_filename(_writer_filename(writer))
    filename_matches = _output_filenames.get(filename, set())
    if len(filename_matches) == 1:
        return next(iter(filename_matches))

    alias_matches = set()
    for alias in _writer_aliases(writer):
        alias_matches.update(_output_aliases.get(alias, set()))
    if len(alias_matches) == 1:
        return next(iter(alias_matches))
    if len(_output_totals) == 1:
        return next(iter(_output_totals))
    return None


def _frame_path(filename, frame):
    hash_match = re.search(r"#+", filename)
    if hash_match is not None:
        width = len(hash_match.group(0))
        return (
            filename[: hash_match.start()]
            + str(int(frame)).zfill(width)
            + filename[hash_match.end() :]
        )

    printf_match = re.search(r"%0?(\d*)d", filename)
    if printf_match is not None:
        width_text = printf_match.group(1)
        rendered_frame = (
            str(int(frame)).zfill(int(width_text))
            if width_text
            else str(int(frame))
        )
        return (
            filename[: printf_match.start()]
            + rendered_frame
            + filename[printf_match.end() :]
        )
    return None


def _task_frames(detail):
    return range(
        int(detail["first_frame"]),
        int(detail["last_frame"]) + 1,
        max(1, int(detail["frame_increment"])),
    )


def _scan_output(detail):
    filename = detail["filename"]
    frames = list(_task_frames(detail))
    if not filename or not frames:
        return set(), "has no usable filename or frame range"

    first_frame_path = _frame_path(filename, frames[0])
    if first_frame_path is not None:
        completed = set()
        for frame in frames:
            frame_filename = _frame_path(filename, frame)
            try:
                if os.path.isfile(frame_filename) and os.path.getsize(frame_filename) > 0:
                    completed.add(frame)
            except OSError:
                continue
        missing_count = len(frames) - len(completed)
        error = (
            "is missing {0} of {1} frame files".format(
                missing_count,
                len(frames),
            )
            if missing_count
            else ""
        )
        return completed, error

    try:
        file_size = os.path.getsize(filename) if os.path.isfile(filename) else 0
    except OSError:
        file_size = 0
    extension = os.path.splitext(filename)[1].lower()
    minimum_size = MIN_VIDEO_BYTES if extension in _VIDEO_EXTENSIONS else 1
    if file_size < minimum_size:
        if file_size == 0:
            return set(), "was not created"
        return set(), "is smaller than {0} bytes ({1} bytes)".format(
            minimum_size,
            file_size,
        )
    return set(frames), ""


def _payload_locked():
    completed_count = len(_completed_frames)
    percent = (
        min(100.0, (float(completed_count) / float(_total_frames)) * 100.0)
        if _total_frames
        else 0.0
    )
    if _state == "complete":
        completed_count = _total_frames
        percent = 100.0
    elif _state == "rendering" and _total_frames and completed_count >= _total_frames:
        percent = 99.0
    return {
        "state": _state,
        "message": _message,
        "completed_frames": completed_count,
        "total_frames": _total_frames,
        "percent": round(percent, 2),
        "current_frame": _current_frame,
        "rendered_smart_writes": _rendered_smart_writes,
        "outputs": {
            name: dict(
                _output_details.get(name, {}),
                completed=len(_output_completed.get(name, set())),
                total=total,
            )
            for name, total in _output_totals.items()
        },
    }


def _write_status_locked(force=False):
    global _status_path
    global _last_write_time

    if not _status_path:
        _status_path = os.environ.get(STATUS_ENV, "")
    if not _status_path:
        return
    now = time.time()
    if not force and now - _last_write_time < WRITE_INTERVAL_SECONDS:
        return

    temporary_path = _status_path + ".tmp"
    payload = _payload_locked()
    try:
        with open(temporary_path, "w") as status_file:
            json.dump(payload, status_file)
        os.replace(temporary_path, _status_path)
    except Exception as error:
        log_event(
            "status_write_failed",
            error=repr(error),
            status_path=_status_path,
        )
        try:
            os.remove(temporary_path)
        except OSError:
            pass
        return
    _last_write_time = now
    log_event(
        "status_written",
        status_path=_status_path,
        state=payload.get("state"),
        completed_frames=payload.get("completed_frames"),
        total_frames=payload.get("total_frames"),
        percent=payload.get("percent"),
        current_frame=payload.get("current_frame"),
    )


def configure(tasks):
    """Initialize progress totals and attach one callback to every writer."""

    global _status_path
    global _state
    global _message
    global _total_frames
    global _completed_frames
    global _output_totals
    global _output_completed
    global _output_details
    global _output_aliases
    global _output_filenames
    global _current_frame
    global _rendered_smart_writes
    global _last_write_time

    with _LOCK:
        _status_path = os.environ.get(STATUS_ENV, "")
        _state = "rendering"
        _message = ""
        _total_frames = 0
        _completed_frames = set()
        _output_totals = {}
        _output_completed = {}
        _output_details = {}
        _output_aliases = {}
        _output_filenames = {}
        _current_frame = None
        _rendered_smart_writes = 0
        _last_write_time = 0.0

        for writer, first_frame, last_frame, frame_increment in tasks:
            writer_name = _writer_name(writer)
            frame_count = _task_frame_count(
                first_frame,
                last_frame,
                frame_increment,
            )
            _output_totals[writer_name] = (
                _output_totals.get(writer_name, 0) + frame_count
            )
            _output_completed.setdefault(writer_name, set())
            filename = _writer_filename(writer)
            _output_details[writer_name] = {
                "filename": filename,
                "first_frame": int(first_frame),
                "last_frame": int(last_frame),
                "frame_increment": max(1, int(frame_increment)),
            }
            for alias in _writer_aliases(writer):
                _output_aliases.setdefault(alias, set()).add(writer_name)
            normalized_filename = _normalized_filename(filename)
            if normalized_filename:
                _output_filenames.setdefault(normalized_filename, set()).add(
                    writer_name
                )
            _total_frames += frame_count

            try:
                callback = writer.getParam("afterFrameRender")
                if callback is not None:
                    callback.set(CALLBACK_NAME)
            except Exception:
                pass

        log_event(
            "progress_configured",
            task_count=len(tasks),
            total_frames=_total_frames,
            outputs=_output_details,
        )
        _write_status_locked(force=True)


def validate_outputs():
    """Verify enabled writer files and reconcile any silent callbacks."""

    errors = []
    with _LOCK:
        for writer_name, detail in _output_details.items():
            completed, error = _scan_output(detail)
            log_event(
                "output_validated",
                writer=writer_name,
                filename=detail.get("filename"),
                completed=len(completed),
                expected=_output_totals.get(writer_name, 0),
                error=error,
            )
            _output_completed[writer_name].update(completed)
            for frame in completed:
                _completed_frames.add((writer_name, frame))
            if error:
                errors.append("{0}: {1}".format(writer_name, error))
        _write_status_locked(force=True)

    if errors:
        raise RuntimeError(
            "SmartWrite output validation failed: " + "; ".join(errors)
        )


def afterFrameRender(frame, thisNode, app):
    """Natron callback invoked after one writer finishes one frame."""

    global _current_frame
    del app

    try:
        normalized_frame = int(frame) if float(frame).is_integer() else float(frame)
        with _LOCK:
            if _state != "rendering":
                return
            writer_name = _resolve_output_name_locked(thisNode)
            if writer_name is None:
                return
            detail = _output_details.get(writer_name, {})
            first_frame = int(detail.get("first_frame", normalized_frame))
            last_frame = int(detail.get("last_frame", normalized_frame))
            frame_increment = max(1, int(detail.get("frame_increment", 1)))
            if (
                normalized_frame < first_frame
                or normalized_frame > last_frame
                or (normalized_frame - first_frame) % frame_increment != 0
            ):
                return
            key = (writer_name, normalized_frame)
            if key in _completed_frames:
                return
            _completed_frames.add(key)
            _output_completed[writer_name].add(normalized_frame)
            _current_frame = normalized_frame
            log_event(
                "frame_completed",
                writer=writer_name,
                frame=normalized_frame,
                completed_frames=len(_completed_frames),
                total_frames=_total_frames,
            )
            _write_status_locked()
    except Exception:
        # Natron aborts a render when a frame callback raises. Progress reporting
        # must therefore never be allowed to interrupt the actual render.
        return


def complete(rendered_smart_writes):
    global _state
    global _rendered_smart_writes

    with _LOCK:
        if len(_completed_frames) != _total_frames:
            raise RuntimeError(
                "SmartWrite completed without all expected output frames "
                "({0}/{1}).".format(len(_completed_frames), _total_frames)
            )
        _state = "complete"
        _rendered_smart_writes = int(rendered_smart_writes)
        log_event(
            "render_complete",
            rendered_smart_writes=_rendered_smart_writes,
            completed_frames=len(_completed_frames),
            total_frames=_total_frames,
        )
        _write_status_locked(force=True)


def failed(message):
    global _state
    global _message

    with _LOCK:
        _state = "failed"
        _message = str(message)
        log_event("render_failed", message=_message)
        _write_status_locked(force=True)
