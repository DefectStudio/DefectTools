"""Preparation failures and resource errors shared by queue and GUI code."""

import errno


class PreparationError(RuntimeError):
    pass


class PreparationCancelled(PreparationError):
    pass


class InsufficientDiskSpace(PreparationError):
    def __init__(self, message: str):
        if "insufficient disk space" not in message.casefold():
            message = f"Insufficient disk space: {message}"
        super().__init__(message)


def is_disk_space_error(error: BaseException | str) -> bool:
    """Recognize native, subprocess and wrapped disk-full failures."""
    pending = [error]
    seen = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, InsufficientDiskSpace):
            return True
        if isinstance(current, OSError) and (
            current.errno in (errno.ENOSPC, getattr(errno, "EDQUOT", -1))
            or getattr(current, "winerror", None) in (39, 112)
        ):
            return True
        text = str(current).casefold()
        if any(fragment in text for fragment in (
            "no space left on device", "there is not enough space on the disk",
            "insufficient disk space", "disk full", "disk is full",
            "disk quota exceeded", "[errno 28]", "[winerror 112]",
        )):
            return True
        if isinstance(current, BaseException):
            pending.extend(cause for cause in (current.__cause__, current.__context__)
                           if cause is not None)
    return False
