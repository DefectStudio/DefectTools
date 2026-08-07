"""Hand-written Natron callbacks for the Smart Read PyPlug.

Keep custom behavior in this module so SmartRead.py can later be regenerated
or replaced without losing the callback implementation.
"""

from smart_read_core import (
    find_exr_versions,
    latest_exr_version,
    project_directory_from_paths,
)


EMPTY_VERSION_LABEL = "No EXR versions found"
PLUGIN_ID = "com.portablepipetools.SmartRead"
_PENDING_GUI_REFRESHES = []
_REFRESHING_GROUPS = []


def _replace_version_param(group, labels, selected_index, default_index):
    """Recreate the File menu so Natron also replaces its restored widget."""

    previous_param = group.getParam("version")
    if previous_param is not None:
        group.removeParam(previous_param)

    choice_param = group.createChoiceParam("version", "File")
    for label in labels:
        choice_param.addOption(label, "")
    choice_param.setAnimationEnabled(False)
    choice_param.setHelp(
        "Available EXR versions for this element. Latest automatically selects "
        "the newest entry when versions are refreshed."
    )
    choice_param.setDefaultValue(default_index)
    choice_param.setValue(selected_index)
    group.getParam("smartRead").addParam(choice_param)
    group.refreshUserParamsGUI()
    return choice_param


def _project_directory(app):
    project_paths = app.getProjectParam("projectPaths")
    if project_paths is None:
        return None
    return project_directory_from_paths(project_paths.getTable())


def _element(group):
    return str(group.getParam("element").get()).strip()


def _update_node_label(group):
    element = _element(group)
    group.setLabel("SmartRead - {0}".format(element) if element else "SmartRead")


def _apply_version(group, exr_version):
    reader = group.getNode("Read1")
    if reader is None:
        return
    group.beginChanges()
    try:
        reader.getParam("filename").set(exr_version.sequence_path.as_posix())
        reader.getParam("firstFrame").set(exr_version.first_frame)
        reader.getParam("lastFrame").set(exr_version.last_frame)
    finally:
        group.endChanges()


def refreshVersions(app, group, select_latest=None):
    """Rescan this shot and update the menu and internal Read source."""

    version_param = group.getParam("version")
    project_directory = _project_directory(app)
    try:
        versions = (
            find_exr_versions(project_directory, _element(group))
            if project_directory is not None
            else ()
        )
    except (OSError, ValueError):
        versions = ()

    _REFRESHING_GROUPS.append(group)
    try:
        if not versions:
            _replace_version_param(
                group,
                [EMPTY_VERSION_LABEL],
                selected_index=0,
                default_index=0,
            )
            reader = group.getNode("Read1")
            if reader is not None:
                reader.getParam("filename").set("")
            return

        # Keep stable oldest-to-newest indices. Natron restores a serialized
        # ChoiceParam GUI before this rescan, and changing the order underneath
        # that widget can make a displayed label refer to the wrong index.
        labels = [item.label for item in versions]
        previously_selected = None
        selected_index = version_param.get()
        if 0 <= selected_index < version_param.getNumOptions():
            previously_selected = version_param.getOption(selected_index)

        use_latest = bool(group.getParam("latest").get())
        if select_latest is not None:
            use_latest = bool(select_latest)

        latest = latest_exr_version(versions)
        selected = latest if use_latest else None
        if selected is None and previously_selected in labels:
            selected = versions[labels.index(previously_selected)]
        if selected is None:
            selected = latest

        # Natron's red X resets a parameter to its default. Make the current
        # latest version the File menu's default while preserving stable menu
        # indices; an intentionally pinned older version can still be reset.
        latest_index = labels.index(latest.label)
        _replace_version_param(
            group,
            labels,
            selected_index=labels.index(selected.label),
            default_index=latest_index,
        )
        _apply_version(group, selected)
    finally:
        for index, refreshing_group in enumerate(_REFRESHING_GROUPS):
            if refreshing_group is group:
                del _REFRESHING_GROUPS[index]
                break


def onParamChanged(thisParam, thisNode, thisGroup, app, userEdited):
    """React to Latest and Version changes from the Smart Read GUI."""

    del thisGroup
    param_name = thisParam.getScriptName()
    if param_name == "element":
        _update_node_label(thisNode)
        refreshVersions(app, thisNode)
    elif param_name == "refresh":
        refreshVersions(app, thisNode)
    elif param_name == "latest":
        # Selecting a File turns Latest off programmatically. Natron may queue
        # that BooleanParam callback until after the File callback returns, so
        # use its own edit flag instead of a short-lived recursion guard.
        if not userEdited:
            return
        refreshVersions(app, thisNode, select_latest=thisParam.get())
    elif param_name == "version":
        if any(group is thisNode for group in _REFRESHING_GROUPS):
            return
        selected_index = thisParam.get()
        if not 0 <= selected_index < thisParam.getNumOptions():
            return
        selected_label = thisParam.getOption(selected_index)
        latest_param = thisNode.getParam("latest")
        # Refreshing the menu changes the ChoiceParam programmatically, which
        # also invokes this callback with userEdited=False. Only an actual
        # dropdown selection should switch Latest off.
        if userEdited and latest_param.get():
            latest_param.set(False)
        project_directory = _project_directory(app)
        if project_directory is None:
            return
        try:
            versions = find_exr_versions(project_directory, _element(thisNode))
        except (OSError, ValueError):
            return
        for exr_version in versions:
            if exr_version.label == selected_label:
                _apply_version(thisNode, exr_version)
                break


def _refresh_smart_reads_in(container, app):
    for node in container.getChildren():
        if node.getPluginID() == PLUGIN_ID:
            refreshVersions(app, node)
        _refresh_smart_reads_in(node, app)


def afterProjectLoaded(app):
    """Refresh Smart Reads after Natron restores all serialized node values."""

    _refresh_smart_reads_in(app, app)


def _finish_gui_refresh():
    if _PENDING_GUI_REFRESHES:
        app = _PENDING_GUI_REFRESHES.pop(0)
        afterProjectLoaded(app)


def scheduleGuiRefresh(app):
    """Refresh after Natron finishes constructing its properties widgets."""

    from PySide import QtCore

    _PENDING_GUI_REFRESHES.append(app)
    # Keep the callback in this imported module rather than the transient
    # --onload script namespace. A short delay also lets project layout and
    # properties-panel restoration finish before the dynamic menu is rebuilt.
    QtCore.QTimer.singleShot(100, _finish_gui_refresh)


def createInstanceExt(app, group):
    """Install Smart Read callbacks after the internal graph is constructed."""

    callback = group.getParam("onParamChanged")
    if callback is not None:
        # Natron imports this extension into the main PyPlug module. Callback
        # names must therefore be resolved through SmartRead, not SmartReadExt.
        callback.set("SmartRead.onParamChanged")
    _update_node_label(group)
    refreshVersions(app, group)
