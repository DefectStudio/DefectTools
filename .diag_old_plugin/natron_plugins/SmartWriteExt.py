"""Natron callbacks and output-path behavior for the Smart Write PyPlug."""

from smart_read_core import project_directory_from_paths
from smart_write_core import build_output_paths


PLUGIN_ID = "com.portablepipetools.SmartWrite"
WRITER_SPECS = (
    ("exrOutput", "EXRWrite", "exr_sequence"),
    ("mp4Output", "MP4Write", "mp4_file"),
    ("movOutput", "MOVWrite", "mov_file"),
    ("heroOutput", "HeroWrite", "hero_sequence"),
)
GUI_REFRESH_DELAY_MS = 100
_PENDING_GUI_REFRESHES = []
_GROUP_OUTPUT_SELECTIONS = []


def _project_directory(app):
    project_paths = app.getProjectParam("projectPaths")
    if project_paths is None:
        return None
    return project_directory_from_paths(project_paths.getTable())


def _configure_writer(writer, filename, enabled):
    if writer is None:
        return
    filename_param = writer.getParam("filename")
    if filename_param is not None:
        filename_param.set(filename)
    disable_param = writer.getParam("disableNode")
    if disable_param is not None:
        disable_param.set(not enabled or not bool(filename))


def _project_key(project_directory):
    return str(project_directory).replace("\\", "/").casefold()


def _cached_paths(group, project_directory):
    key = _project_key(project_directory)
    for selected_group, selected_key, paths in _GROUP_OUTPUT_SELECTIONS:
        if selected_group is group and selected_key == key:
            return paths
    return None


def _remember_paths(group, project_directory, paths):
    for index, selection in enumerate(_GROUP_OUTPUT_SELECTIONS):
        if selection[0] is group:
            _GROUP_OUTPUT_SELECTIONS[index] = (
                group,
                _project_key(project_directory),
                paths,
            )
            return
    _GROUP_OUTPUT_SELECTIONS.append(
        (group, _project_key(project_directory), paths)
    )


def _create_output_directories(paths, enabled_outputs):
    versioned_outputs = ("exrOutput", "mp4Output", "movOutput")
    if any(enabled_outputs[name] for name in versioned_outputs):
        paths.mp4_file.parent.mkdir(parents=True, exist_ok=True)
    if enabled_outputs["exrOutput"]:
        paths.exr_sequence.parent.mkdir(parents=True, exist_ok=True)
    if enabled_outputs["heroOutput"]:
        paths.hero_sequence.parent.mkdir(parents=True, exist_ok=True)


def refreshOutputs(app, group, select_next_version=False):
    """Rebuild all writer targets from the current saved project location."""

    project_directory = _project_directory(app)
    try:
        paths = None
        if project_directory is not None:
            if not select_next_version:
                paths = _cached_paths(group, project_directory)
            if paths is None:
                paths = build_output_paths(project_directory)
                _remember_paths(group, project_directory, paths)
    except (OSError, ValueError):
        paths = None

    enabled_outputs = {}
    for checkbox_name, _writer_name, _path_attribute in WRITER_SPECS:
        checkbox = group.getParam(checkbox_name)
        enabled_outputs[checkbox_name] = (
            bool(checkbox.get()) if checkbox is not None else False
        )
    if paths is not None:
        try:
            _create_output_directories(paths, enabled_outputs)
        except OSError:
            paths = None

    group.beginChanges()
    try:
        for checkbox_name, writer_name, path_attribute in WRITER_SPECS:
            writer = group.getNode(writer_name)
            path = getattr(paths, path_attribute).as_posix() if paths else ""
            _configure_writer(writer, path, enabled_outputs[checkbox_name])
    finally:
        group.endChanges()


def onParamChanged(thisParam, thisNode, thisGroup, app, userEdited):
    """Apply checkbox edits to the corresponding internal writers."""

    del thisGroup, userEdited
    if any(thisParam.getScriptName() == spec[0] for spec in WRITER_SPECS):
        refreshOutputs(app, thisNode)


def _refresh_smart_writes_in(container, app):
    for node in container.getChildren():
        if node.getPluginID() == PLUGIN_ID:
            refreshOutputs(app, node)
        _refresh_smart_writes_in(node, app)


def afterProjectLoaded(app):
    """Refresh Smart Writes after Natron restores a copied comp template."""

    _refresh_smart_writes_in(app, app)


def _finish_gui_refresh():
    if _PENDING_GUI_REFRESHES:
        afterProjectLoaded(_PENDING_GUI_REFRESHES.pop(0))


def scheduleGuiRefresh(app):
    """Refresh after Natron finishes restoring the project and properties UI."""

    from PySide import QtCore

    _PENDING_GUI_REFRESHES.append(app)
    QtCore.QTimer.singleShot(GUI_REFRESH_DELAY_MS, _finish_gui_refresh)


def _ensure_natron_callback_inspection():
    import inspect

    if not hasattr(inspect, "getargspec"):
        inspect.getargspec = inspect.getfullargspec


def createInstanceExt(app, group):
    """Install callbacks and configure a newly created Smart Write."""

    callback = group.getParam("onParamChanged")
    if callback is not None:
        _ensure_natron_callback_inspection()
        callback.set("SmartWrite.onParamChanged")
    refreshOutputs(app, group, select_next_version=True)
