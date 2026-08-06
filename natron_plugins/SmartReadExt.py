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


def _replace_choice_options(choice_param, labels):
    """Replace a Natron choice menu without its broken list-of-strings binding."""

    # Natron 2.5 on Windows accepts an empty list here, but its Shiboken
    # binding rejects strings nested inside setOptions(list). Add each string
    # through the binding-safe scalar API after clearing the menu.
    choice_param.setOptions([])
    for label in labels:
        choice_param.addOption(label, "")


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

    if not versions:
        _replace_choice_options(version_param, [EMPTY_VERSION_LABEL])
        version_param.set(0)
        reader = group.getNode("Read1")
        if reader is not None:
            reader.getParam("filename").set("")
        return

    labels = [item.label for item in versions]
    previously_selected = None
    selected_index = version_param.get()
    if 0 <= selected_index < version_param.getNumOptions():
        previously_selected = version_param.getOption(selected_index)

    _replace_choice_options(version_param, labels)
    use_latest = bool(group.getParam("latest").get())
    if select_latest is not None:
        use_latest = bool(select_latest)

    selected = latest_exr_version(versions) if use_latest else None
    if selected is None and previously_selected in labels:
        selected = versions[labels.index(previously_selected)]
    if selected is None:
        selected = latest_exr_version(versions)

    version_param.set(selected.label)
    _apply_version(group, selected)


def onParamChanged(thisParam, thisNode, thisGroup, app, userEdited):
    """React to Latest and Version changes from the Smart Read GUI."""

    del thisGroup, userEdited
    param_name = thisParam.getScriptName()
    if param_name == "element":
        _update_node_label(thisNode)
        refreshVersions(app, thisNode)
    elif param_name == "refresh":
        refreshVersions(app, thisNode)
    elif param_name == "latest":
        refreshVersions(app, thisNode, select_latest=thisParam.get())
    elif param_name == "version":
        latest_param = thisNode.getParam("latest")
        if latest_param.get():
            latest_param.set(False)
        project_directory = _project_directory(app)
        if project_directory is None:
            return
        try:
            versions = find_exr_versions(project_directory, _element(thisNode))
        except (OSError, ValueError):
            return
        selected_label = thisParam.getOption(thisParam.get())
        for exr_version in versions:
            if exr_version.label == selected_label:
                _apply_version(thisNode, exr_version)
                break


def createInstanceExt(app, group):
    """Install Smart Read callbacks after the internal graph is constructed."""

    callback = group.getParam("onParamChanged")
    if callback is not None:
        callback.set("SmartReadExt.onParamChanged")
    _update_node_label(group)
    refreshVersions(app, group)
