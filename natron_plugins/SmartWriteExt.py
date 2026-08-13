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
RENDER_BUTTON_SPECS = (
    ("renderEXR", "Render EXR", "exrOutput"),
    ("renderMP4", "Render MP4", "mp4Output"),
    ("renderMOV", "Render MOV", "movOutput"),
    ("renderHero", "Render Hero", "heroOutput"),
)
OUTPUT_CONTROL_SPECS = (
    (
        "exrOutput",
        "EXR Output",
        True,
        "Write a versioned beauty EXR sequence under comp/_output.",
    ),
    (
        "mp4Output",
        "MP4 Output",
        True,
        "Write a versioned beauty MP4 under comp/_output.",
    ),
    (
        "movOutput",
        "MOV Output",
        False,
        "Write a versioned beauty MOV under comp/_output.",
    ),
    (
        "heroOutput",
        "Hero Output",
        True,
        "Write the unversioned hero EXR sequence under comp/_output/_hero.",
    ),
)
SMART_WRITE_UI_VERSION = 3
WRITER_LAYOUT = {
    "EXRWrite": ("EXR Write", -300, "compression"),
    "MP4Write": ("MP4 Write", -100, "codec"),
    "MOVWrite": ("MOV Write", 100, "codec"),
    "HeroWrite": ("Hero Write", 300, "compression"),
}
WRITER_PLUGIN_IDS = {
    "EXRWrite": "fr.inria.openfx.WriteOIIO",
    "MP4Write": "fr.inria.openfx.WriteFFmpeg",
    "MOVWrite": "fr.inria.openfx.WriteFFmpeg",
    "HeroWrite": "fr.inria.openfx.WriteOIIO",
}
ARTIST_EXR_CHOICE_DEFAULTS = (
    ("outputComponents", "RGBA"),
    ("inputPremult", "premult"),
    ("ocioInputSpaceIndex", "linear/Linear"),
    ("ocioOutputSpaceIndex", "linear/Linear"),
    ("frameRange", "project"),
    ("bitDepth", "auto"),
    ("compression", "default"),
    ("partSplitting", "views_layers"),
    ("viewsSelector", "All"),
    ("tileSize", "0"),
)
ARTIST_EXR_VALUE_DEFAULTS = (
    ("frameIncr", 1),
    ("readBack", False),
    ("quality", 100),
    ("dwaCompressionLevel", 45.0),
    ("outputChannels", 0),
    ("processAllPlanes", False),
)
ARTIST_MP4_CHOICE_DEFAULTS = (
    ("codec", "libx264"),
    ("outputComponents", "RGBA"),
    ("inputPremult", "premult"),
    ("ocioInputSpaceIndex", "linear/Linear"),
    ("ocioOutputSpaceIndex", "display/nuke_rec709"),
    ("frameRange", "project"),
    ("prefPixelCoding", "yuv422"),
    ("prefBitDepth", "8"),
    ("crf", "crf23"),
    ("x26xSpeed", "medium"),
)
ARTIST_MP4_VALUE_DEFAULTS = (
    ("frameIncr", 1),
    ("readBack", False),
    ("fps", 24.0),
    ("bitrateMbps", 185.0),
    ("gopSize", -1),
    ("bFrames", -1),
    ("fastStart", False),
)
COMMON_SETTING_PARAMS = (
    ("outputComponents", "createChoiceParam"),
    ("inputPremult", "createChoiceParam"),
    ("ocioInputSpaceIndex", "createChoiceParam"),
    ("ocioOutputSpaceIndex", "createChoiceParam"),
    ("frameRange", "createChoiceParam"),
    ("firstFrame", "createIntParam"),
    ("lastFrame", "createIntParam"),
    ("frameIncr", "createIntParam"),
    ("readBack", "createBooleanParam"),
)
EXR_SETTING_PARAMS = COMMON_SETTING_PARAMS + (
    ("bitDepth", "createChoiceParam"),
    ("compression", "createChoiceParam"),
    ("quality", "createIntParam"),
    ("dwaCompressionLevel", "createDoubleParam"),
    ("outputChannels", "createChoiceParam"),
    ("processAllPlanes", "createBooleanParam"),
    ("partSplitting", "createChoiceParam"),
    ("viewsSelector", "createChoiceParam"),
    ("tileSize", "createChoiceParam"),
)
VIDEO_SETTING_PARAMS = COMMON_SETTING_PARAMS + (
    ("codec", "createChoiceParam"),
    ("fps", "createDoubleParam"),
    ("prefPixelCoding", "createChoiceParam"),
    ("prefBitDepth", "createChoiceParam"),
    ("crf", "createChoiceParam"),
    ("x26xSpeed", "createChoiceParam"),
    ("bitrateMbps", "createDoubleParam"),
    ("gopSize", "createIntParam"),
    ("bFrames", "createIntParam"),
    ("fastStart", "createBooleanParam"),
)
MOV_SETTING_PARAMS = VIDEO_SETTING_PARAMS + (
    ("enableAlpha", "createBooleanParam"),
    ("DNxHDCodecProfile", "createChoiceParam"),
    ("HapFormat", "createChoiceParam"),
)
SETTINGS_SECTIONS = (
    (
        "exrOutput",
        "exrSettings",
        "EXR Settings",
        "EXRWrite",
        "exr",
        EXR_SETTING_PARAMS,
    ),
    (
        "mp4Output",
        "mp4Settings",
        "MP4 Settings",
        "MP4Write",
        "mp4",
        VIDEO_SETTING_PARAMS,
    ),
    (
        "movOutput",
        "movSettings",
        "MOV Settings",
        "MOVWrite",
        "mov",
        MOV_SETTING_PARAMS,
    ),
    (
        "heroOutput",
        "heroSettings",
        "Hero Settings",
        "HeroWrite",
        "hero",
        EXR_SETTING_PARAMS,
    ),
)
GUI_REFRESH_DELAY_MS = 100
_PENDING_GUI_REFRESHES = []
_GROUP_OUTPUT_SELECTIONS = []
_GROUP_ACTIVE_WRITERS = []
_MIGRATING_GROUPS = []


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


def _set_choice_option(param, option_name):
    if param is None:
        return False
    try:
        options = list(param.getOptions())
    except (AttributeError, TypeError):
        return False
    wanted = option_name.casefold()
    for index, option in enumerate(options):
        if str(option).casefold() == wanted:
            param.set(index)
            return True
    return False


def _configure_new_writer(writer_name, writer):
    if writer_name in ("EXRWrite", "HeroWrite"):
        choice_defaults = ARTIST_EXR_CHOICE_DEFAULTS
        value_defaults = ARTIST_EXR_VALUE_DEFAULTS
    elif writer_name == "MP4Write":
        choice_defaults = ARTIST_MP4_CHOICE_DEFAULTS
        value_defaults = ARTIST_MP4_VALUE_DEFAULTS
    else:
        return

    for param_name, option_name in choice_defaults:
        _set_choice_option(writer.getParam(param_name), option_name)
    for param_name, value in value_defaults:
        param = writer.getParam(param_name)
        if param is not None:
            param.set(value)


def _has_format_options(writer, format_param_name):
    format_param = writer.getParam(format_param_name)
    if format_param is None:
        return False
    try:
        return bool(format_param.getOptions())
    except (AttributeError, TypeError):
        return True


def _retired_writer_name(group, writer_name):
    base_name = "{0}Placeholder".format(writer_name)
    candidate = base_name
    suffix = 2
    while group.getNode(candidate) is not None:
        candidate = "{0}{1}".format(base_name, suffix)
        suffix += 1
    return candidate


def _ensure_concrete_writer(app, group, writer_name, filename):
    writer = group.getNode(writer_name)
    if not filename:
        return writer

    label, x_position, format_param_name = WRITER_LAYOUT[writer_name]
    if writer is not None and _has_format_options(writer, format_param_name):
        return writer

    replacement = app.createNode(WRITER_PLUGIN_IDS[writer_name], 1, group)
    if replacement is not None:
        replacement_filename = replacement.getParam("filename")
        if replacement_filename is not None:
            replacement_filename.set(filename)
    else:
        replacement = app.createWriter(filename, group)
    if replacement is None:
        return writer

    source = writer.getInput(0) if writer is not None else group.getNode("Input1")
    if source is not None and replacement.connectInput(0, source) is False:
        replacement.destroy(False)
        return writer

    replacement.setLabel(label)
    replacement.setPosition(x_position, 100)
    _configure_new_writer(writer_name, replacement)
    if writer is not None:
        writer.setScriptName(_retired_writer_name(group, writer_name))
    replacement.setScriptName(writer_name)
    if writer is not None:
        _configure_writer(writer, "", False)
        writer.destroy(False)
    return replacement


def _project_key(project_directory):
    return str(project_directory).replace("\\", "/").casefold()


def _group_key(group):
    """Return a stable key across Natron's short-lived Python node proxies."""

    try:
        name = group.getFullyQualifiedName()
    except (AttributeError, RuntimeError):
        try:
            name = group.getScriptName()
        except (AttributeError, RuntimeError):
            name = str(group)
    return str(name).casefold()


def _cached_paths(group, project_directory):
    group_key = _group_key(group)
    key = _project_key(project_directory)
    for selected_group_key, selected_key, paths in _GROUP_OUTPUT_SELECTIONS:
        if selected_group_key == group_key and selected_key == key:
            return paths
    return None


def _remember_paths(group, project_directory, paths):
    group_key = _group_key(group)
    for index, selection in enumerate(_GROUP_OUTPUT_SELECTIONS):
        if selection[0] == group_key:
            _GROUP_OUTPUT_SELECTIONS[index] = (
                group_key,
                _project_key(project_directory),
                paths,
            )
            return
    _GROUP_OUTPUT_SELECTIONS.append(
        (group_key, _project_key(project_directory), paths)
    )


def _remember_active_writers(group, active_writers):
    group_key = _group_key(group)
    for index, selection in enumerate(_GROUP_ACTIVE_WRITERS):
        if selection[0] == group_key:
            _GROUP_ACTIVE_WRITERS[index] = (group_key, dict(active_writers))
            return
    _GROUP_ACTIVE_WRITERS.append((group_key, dict(active_writers)))


def _active_writers(group):
    group_key = _group_key(group)
    for selected_group_key, writers in _GROUP_ACTIVE_WRITERS:
        if selected_group_key == group_key:
            return writers
    return {}


def _create_output_directories(paths, enabled_outputs):
    versioned_outputs = ("exrOutput", "mp4Output", "movOutput")
    if any(enabled_outputs[name] for name in versioned_outputs):
        paths.mp4_file.parent.mkdir(parents=True, exist_ok=True)
    if enabled_outputs["exrOutput"]:
        paths.exr_sequence.parent.mkdir(parents=True, exist_ok=True)
    if enabled_outputs["heroOutput"]:
        paths.hero_sequence.parent.mkdir(parents=True, exist_ok=True)


def _copy_choice_options(native_param, exposed_param):
    """Copy a writer's choice labels without linking the two parameters."""

    try:
        options = native_param.getOptions()
    except (AttributeError, TypeError):
        return False
    if options is None:
        return False
    try:
        exposed_param.setOptions(
            [(str(option), "") for option in options]
        )
    except (AttributeError, TypeError):
        return False
    return True


def _create_setting_proxy(
    group,
    settings_group,
    proxy_prefix,
    writer,
    native_name,
    creator_name,
):
    native_param = writer.getParam(native_name)
    if native_param is None:
        return False

    proxy_name = "{0}_{1}".format(proxy_prefix, native_name)
    existing_proxy = group.getParam(proxy_name)
    if existing_proxy is not None:
        if creator_name != "createChoiceParam":
            return False
        selected_value = existing_proxy.get()
        if not _copy_choice_options(native_param, existing_proxy):
            return False
        existing_proxy.set(selected_value)
        return True

    creator = getattr(group, creator_name)
    proxy = creator(proxy_name, native_param.getLabel())
    if creator_name == "createChoiceParam":
        _copy_choice_options(native_param, proxy)
    proxy.setAnimationEnabled(False)
    proxy.set(native_param.get())
    settings_group.addParam(proxy)
    return True


def _ensure_settings_sections(group, active_writers=None):
    controls = group.getParam("smartWrite")
    if controls is None:
        return

    ui_changed = False
    for (
        checkbox_name,
        section_name,
        section_label,
        writer_name,
        proxy_prefix,
        setting_specs,
    ) in SETTINGS_SECTIONS:
        settings_group = group.getParam(section_name)
        if settings_group is None:
            settings_group = group.createGroupParam(section_name, section_label)
            settings_group.setOpened(bool(group.getParam(checkbox_name).get()))
            controls.addParam(settings_group)
            ui_changed = True

        writer = (
            active_writers.get(writer_name)
            if active_writers is not None
            else group.getNode(writer_name)
        )
        if writer is None:
            continue
        format_param_name = WRITER_LAYOUT[writer_name][2]
        if writer.getParam(format_param_name) is None:
            continue
        for native_name, creator_name in setting_specs:
            if _create_setting_proxy(
                group,
                settings_group,
                proxy_prefix,
                writer,
                native_name,
                creator_name,
            ):
                ui_changed = True

    if ui_changed:
        group.refreshUserParamsGUI()


def _sync_setting_to_writer(group, exposed_param, active_writers=None):
    exposed_name = exposed_param.getScriptName()
    for section in SETTINGS_SECTIONS:
        writer_name = section[3]
        proxy_prefix = section[4]
        for native_name, _creator_name in section[5]:
            if exposed_name != "{0}_{1}".format(proxy_prefix, native_name):
                continue
            writer = (
                active_writers.get(writer_name)
                if active_writers is not None
                else group.getNode(writer_name)
            )
            native_param = writer.getParam(native_name) if writer else None
            if native_param is not None:
                native_param.set(exposed_param.get())
            return True
    return False


def _sync_settings_to_writers(group, active_writers=None):
    for section in SETTINGS_SECTIONS:
        proxy_prefix = section[4]
        for native_name, _creator_name in section[5]:
            exposed = group.getParam(
                "{0}_{1}".format(proxy_prefix, native_name)
            )
            if exposed is not None:
                _sync_setting_to_writer(group, exposed, active_writers)


def _selected_choice_label(param):
    try:
        options = list(param.getOptions())
        selected = int(param.get())
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return ""
    if 0 <= selected < len(options):
        return str(options[selected]).casefold()
    return ""


def _update_frame_range_controls(
    app,
    group,
    proxy_prefix,
    force_manual_values=False,
    active_writers=None,
):
    frame_range = group.getParam("{0}_frameRange".format(proxy_prefix))
    first_frame = group.getParam("{0}_firstFrame".format(proxy_prefix))
    last_frame = group.getParam("{0}_lastFrame".format(proxy_prefix))
    if frame_range is None or first_frame is None or last_frame is None:
        return False

    selected_label = _selected_choice_label(frame_range)
    try:
        selected_value = int(frame_range.get())
    except (TypeError, ValueError, RuntimeError):
        selected_value = -1
    manual = selected_label == "manual" or (
        not selected_label and selected_value == 2
    )
    first_frame.setVisible(manual)
    last_frame.setVisible(manual)

    if manual:
        try:
            first_value = int(first_frame.get())
            last_value = int(last_frame.get())
        except (TypeError, ValueError, RuntimeError):
            first_value, last_value = 0, 0
        uninitialized = (first_value == 0 and last_value == 0) or last_value < first_value
        if force_manual_values or uninitialized:
            actual_first, actual_last = _render_frame_range(app, group)
            first_frame.set(int(actual_first))
            last_frame.set(int(actual_last))
            _sync_setting_to_writer(group, first_frame, active_writers)
            _sync_setting_to_writer(group, last_frame, active_writers)
    return True


def _update_all_frame_range_controls(app, group, active_writers=None):
    updated = False
    for section in SETTINGS_SECTIONS:
        updated = _update_frame_range_controls(
            app,
            group,
            section[4],
            active_writers=active_writers,
        ) or updated
    if updated:
        group.refreshUserParamsGUI()


def _set_settings_section_open(group, checkbox_name, opened):
    for section in SETTINGS_SECTIONS:
        if section[0] != checkbox_name:
            continue
        settings_group = group.getParam(section[1])
        if settings_group is not None:
            settings_group.setOpened(bool(opened))
        return


def _snapshot_setting_values(group):
    values = {}
    for section in SETTINGS_SECTIONS:
        proxy_prefix = section[4]
        for native_name, _creator_name in section[5]:
            name = "{0}_{1}".format(proxy_prefix, native_name)
            param = group.getParam(name)
            if param is not None:
                values[name] = param.get()
    return values


def _remove_legacy_controls(group):
    for section in SETTINGS_SECTIONS:
        proxy_prefix = section[4]
        for native_name, _creator_name in section[5]:
            param = group.getParam(
                "{0}_{1}".format(proxy_prefix, native_name)
            )
            if param is not None:
                group.removeParam(param)
        settings_group = group.getParam(section[1])
        if settings_group is not None:
            group.removeParam(settings_group)

    names = ["smartWriteUiVersion", "renderAll"]
    names.extend(spec[0] for spec in OUTPUT_CONTROL_SPECS)
    names.extend(spec[0] for spec in RENDER_BUTTON_SPECS)
    for name in names:
        param = group.getParam(name)
        if param is not None:
            group.removeParam(param)


def _create_ordered_render_controls(group, controls, checkbox_values):
    layout_version = group.createIntParam("smartWriteUiVersion", "UI Version")
    layout_version.setDefaultValue(SMART_WRITE_UI_VERSION)
    layout_version.restoreDefaultValue()
    layout_version.setAnimationEnabled(False)
    layout_version.setVisible(False)
    controls.addParam(layout_version)

    render_all = group.createButtonParam("renderAll", "Render All")
    render_all.setHelp(
        "Render every enabled Smart Write output over the upstream media frame range."
    )
    render_all.setAddNewLine(True)
    controls.addParam(render_all)

    buttons_by_checkbox = {
        checkbox_name: (button_name, button_label)
        for button_name, button_label, checkbox_name in RENDER_BUTTON_SPECS
    }
    for checkbox_name, label, default_value, help_text in OUTPUT_CONTROL_SPECS:
        checkbox = group.createBooleanParam(checkbox_name, label)
        checkbox.setDefaultValue(default_value)
        checkbox.restoreDefaultValue()
        checkbox.setAnimationEnabled(False)
        checkbox.setAddNewLine(True)
        checkbox.setHelp(help_text)
        if checkbox_name in checkbox_values:
            checkbox.set(checkbox_values[checkbox_name])
        controls.addParam(checkbox)

        button_name, button_label = buttons_by_checkbox[checkbox_name]
        button = group.createButtonParam(button_name, button_label)
        button.setHelp(
            "Render only the enabled {0} output.".format(
                button_label.replace("Render ", "")
            )
        )
        button.setEnabled(bool(checkbox.get()))
        button.setAddNewLine(False)
        controls.addParam(button)

    render_all.setAddNewLine(True)
    for button_name, _button_label, checkbox_name in RENDER_BUTTON_SPECS:
        group.getParam(checkbox_name).setAddNewLine(True)
        group.getParam(button_name).setAddNewLine(False)

    render_all.setEnabled(any(bool(value) for value in checkbox_values.values()))


def _ensure_render_controls(group):
    """Create or migrate render controls into checkbox/button rows."""

    controls = group.getParam("smartWrite")
    if controls is None:
        return None

    layout_version = group.getParam("smartWriteUiVersion")
    if layout_version is not None:
        # This is an internal migration sentinel, never a user-facing control.
        # Reapply visibility because older saved projects can restore it as visible.
        layout_version.setVisible(False)
    if layout_version is None or layout_version.get() != SMART_WRITE_UI_VERSION:
        checkbox_values = {
            name: bool(group.getParam(name).get())
            for name, _label, default_value, _help in OUTPUT_CONTROL_SPECS
            if group.getParam(name) is not None
        }
        for name, _label, default_value, _help in OUTPUT_CONTROL_SPECS:
            checkbox_values.setdefault(name, default_value)
        setting_values = _snapshot_setting_values(group)

        _MIGRATING_GROUPS.append(group)
        group.beginChanges()
        try:
            _remove_legacy_controls(group)
            group.removeParam(controls)
            controls = group.createPageParam("smartWrite", "Smart Write")
            _create_ordered_render_controls(group, controls, checkbox_values)
            group.setPagesOrder(["smartWrite", "Node", "Settings"])
        finally:
            group.endChanges()
            _MIGRATING_GROUPS.remove(group)
        group.refreshUserParamsGUI()
        return setting_values

    render_all = group.getParam("renderAll")
    if render_all is not None:
        render_all.setAddNewLine(True)
    any_output_enabled = False
    for button_name, button_label, checkbox_name in RENDER_BUTTON_SPECS:
        button = group.getParam(button_name)
        checkbox = group.getParam(checkbox_name)
        output_enabled = bool(checkbox.get()) if checkbox is not None else False
        if checkbox is not None:
            checkbox.setAddNewLine(True)
        if button is not None:
            button.setEnabled(output_enabled)
            button.setAddNewLine(False)
        any_output_enabled = any_output_enabled or output_enabled

    if render_all is not None:
        render_all.setEnabled(any_output_enabled)
    return None


def _restore_setting_values(group, setting_values):
    if not setting_values:
        return
    group.beginChanges()
    try:
        for name, value in setting_values.items():
            param = group.getParam(name)
            if param is not None:
                param.set(value)
    finally:
        group.endChanges()


def _input_nodes(node):
    """Return connected inputs without assuming every test/API node has inputs."""

    try:
        count = node.getMaxInputCount()
    except (AttributeError, RuntimeError):
        return []
    inputs = []
    for index in range(count):
        try:
            input_node = node.getInput(index)
        except (AttributeError, RuntimeError):
            continue
        if input_node is not None:
            inputs.append(input_node)
    return inputs


def _upstream_reader_ranges(group):
    """Collect frame ranges from Read nodes feeding this SmartWrite."""

    pending = _input_nodes(group)
    # Keep wrapper objects alive while traversing. Natron may return short-lived
    # Python proxies whose ``id`` values are reused after each hop.
    visited = []
    ranges = []
    while pending:
        node = pending.pop()
        if node in visited:
            continue
        visited.append(node)

        try:
            plugin_id = node.getPluginID()
        except (AttributeError, RuntimeError):
            plugin_id = ""
        if plugin_id == "fr.inria.built-in.Read":
            first_param = node.getParam("firstFrame")
            last_param = node.getParam("lastFrame")
            if first_param is not None and last_param is not None:
                try:
                    first_frame = int(first_param.get())
                    last_frame = int(last_param.get())
                except (TypeError, ValueError, RuntimeError):
                    pass
                else:
                    if last_frame >= first_frame:
                        ranges.append((first_frame, last_frame))

        pending.extend(_input_nodes(node))
        try:
            pending.extend(node.getChildren())
        except (AttributeError, RuntimeError):
            pass
    return ranges


def _render_frame_range(app, group):
    """Prefer the actual upstream media range over a stale project timeline."""

    ranges = _upstream_reader_ranges(group)
    if ranges:
        return min(item[0] for item in ranges), max(item[1] for item in ranges)
    return app.timelineGetLeftBound(), app.timelineGetRightBound()


def _render_enabled_outputs(app, group, checkbox_names):
    """Submit selected, enabled internal writers as one Natron render batch."""

    refreshOutputs(app, group)
    active_writers = _active_writers(group)
    selected_names = set(checkbox_names)
    tasks = []
    first_frame, last_frame = _render_frame_range(app, group)
    for checkbox_name, writer_name, _path_attribute in WRITER_SPECS:
        if checkbox_name not in selected_names:
            continue
        checkbox = group.getParam(checkbox_name)
        if checkbox is None or not bool(checkbox.get()):
            continue
        writer = active_writers.get(writer_name) or group.getNode(writer_name)
        if writer is None:
            continue
        filename = writer.getParam("filename")
        if filename is None or not filename.get():
            continue
        tasks.append((writer, first_frame, last_frame, 1))

    if not tasks:
        return False
    app.render(tasks)
    return True


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

    group.setSubGraphEditable(True)
    group.beginChanges()
    active_writers = {}
    try:
        for checkbox_name, writer_name, path_attribute in WRITER_SPECS:
            path = getattr(paths, path_attribute).as_posix() if paths else ""
            writer = _ensure_concrete_writer(
                app,
                group,
                writer_name,
                path,
            )
            if writer is not None:
                active_writers[writer_name] = writer
            _configure_writer(writer, path, enabled_outputs[checkbox_name])
    finally:
        group.endChanges()
        group.setSubGraphEditable(False)
    _remember_active_writers(group, active_writers)
    migrated_setting_values = _ensure_render_controls(group)
    _ensure_settings_sections(group, active_writers)
    _restore_setting_values(group, migrated_setting_values)
    _sync_settings_to_writers(group, active_writers)
    _update_all_frame_range_controls(app, group, active_writers)


def onParamChanged(thisParam, thisNode, thisGroup, app, userEdited):
    """Apply checkbox edits to the corresponding internal writers."""

    del thisGroup
    if not userEdited or thisNode in _MIGRATING_GROUPS:
        return
    param_name = thisParam.getScriptName()
    if any(param_name == spec[0] for spec in WRITER_SPECS):
        refreshOutputs(app, thisNode)
        _set_settings_section_open(
            thisNode,
            param_name,
            thisParam.get(),
        )
        return
    if param_name == "renderAll":
        _render_enabled_outputs(
            app,
            thisNode,
            [spec[0] for spec in WRITER_SPECS],
        )
        return
    for button_name, _button_label, checkbox_name in RENDER_BUTTON_SPECS:
        if param_name == button_name:
            _render_enabled_outputs(app, thisNode, [checkbox_name])
            return
    if param_name.endswith("_frameRange"):
        _sync_setting_to_writer(thisNode, thisParam)
        _update_frame_range_controls(
            app,
            thisNode,
            param_name[: -len("_frameRange")],
            force_manual_values=True,
            active_writers=_active_writers(thisNode),
        )
        thisNode.refreshUserParamsGUI()
        return
    _sync_setting_to_writer(thisNode, thisParam)


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

    for writer_name in WRITER_LAYOUT:
        writer = group.getNode(writer_name)
        if writer is not None:
            _configure_new_writer(writer_name, writer)
    callback = group.getParam("onParamChanged")
    if callback is not None:
        _ensure_natron_callback_inspection()
        callback.set("SmartWrite.onParamChanged")
    refreshOutputs(app, group, select_next_version=True)
