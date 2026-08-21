"""Render every enabled output on every SmartWrite in a loaded project."""

import SmartWriteExt
import SmartWriteRenderProgress


def _find_smart_writes(container):
    found = []
    for candidate in container.getChildren():
        if candidate.getPluginID() == SmartWriteExt.PLUGIN_ID:
            found.append(candidate)
        found.extend(_find_smart_writes(candidate))
    return found


try:
    SmartWriteRenderProgress.log_event("script_started")
    SmartWriteExt.afterProjectLoaded(app)
    SmartWriteRenderProgress.log_event("project_loaded")
    smart_writes = _find_smart_writes(app)
    SmartWriteRenderProgress.log_event(
        "smart_writes_discovered",
        count=len(smart_writes),
    )
    if not smart_writes:
        raise RuntimeError("No SmartWrite node was found in the comp.")

    checkbox_names = [spec[0] for spec in SmartWriteExt.WRITER_SPECS]
    task_batches = []
    for smart_write in smart_writes:
        tasks = SmartWriteExt._enabled_render_tasks(
            app,
            smart_write,
            checkbox_names,
        )
        if tasks:
            task_batches.append(tasks)

    if not task_batches:
        raise RuntimeError("No enabled SmartWrite outputs were available to render.")

    SmartWriteRenderProgress.configure(
        [task for tasks in task_batches for task in tasks]
    )
    for batch_index, tasks in enumerate(task_batches, 1):
        SmartWriteRenderProgress.log_event(
            "render_batch_started",
            batch=batch_index,
            batch_count=len(task_batches),
            task_count=len(tasks),
        )
        SmartWriteExt._submit_render_tasks(app, tasks)
        SmartWriteRenderProgress.log_event(
            "render_batch_finished",
            batch=batch_index,
            batch_count=len(task_batches),
        )

    SmartWriteRenderProgress.log_event("output_validation_started")
    SmartWriteRenderProgress.validate_outputs()
    SmartWriteRenderProgress.complete(len(task_batches))
except Exception as error:
    SmartWriteRenderProgress.log_event(
        "script_exception",
        error=repr(error),
    )
    SmartWriteRenderProgress.failed(str(error))
    raise
finally:
    # Loading the project from --cmd leaves Natron's normal background render
    # phase pending after this script returns. Closing the project quits the
    # background application before it can render the full project range again.
    SmartWriteRenderProgress.log_event("project_close_requested")
    app.closeProject()
