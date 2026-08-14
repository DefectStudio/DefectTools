"""Render every enabled output on every SmartWrite in a loaded project."""

import json
import os

import SmartWriteExt


STATUS_ENV = "PORTABLE_PIPE_SMART_WRITE_RENDER_STATUS"


def _write_status(state, message="", rendered_smart_writes=0):
    status_path = os.environ.get(STATUS_ENV)
    if not status_path:
        return
    with open(status_path, "w") as status_file:
        json.dump(
            {
                "state": state,
                "message": message,
                "rendered_smart_writes": rendered_smart_writes,
            },
            status_file,
        )


def _find_smart_writes(container):
    found = []
    for candidate in container.getChildren():
        if candidate.getPluginID() == SmartWriteExt.PLUGIN_ID:
            found.append(candidate)
        found.extend(_find_smart_writes(candidate))
    return found


try:
    SmartWriteExt.afterProjectLoaded(app)
    smart_writes = _find_smart_writes(app)
    if not smart_writes:
        raise RuntimeError("No SmartWrite node was found in the comp.")

    checkbox_names = [spec[0] for spec in SmartWriteExt.WRITER_SPECS]
    rendered_smart_writes = 0
    for smart_write in smart_writes:
        if SmartWriteExt._render_enabled_outputs(
            app,
            smart_write,
            checkbox_names,
        ):
            rendered_smart_writes += 1

    if rendered_smart_writes == 0:
        raise RuntimeError("No enabled SmartWrite outputs were available to render.")
    _write_status(
        "complete",
        rendered_smart_writes=rendered_smart_writes,
    )
except Exception as error:
    _write_status("failed", message=str(error))
    raise
