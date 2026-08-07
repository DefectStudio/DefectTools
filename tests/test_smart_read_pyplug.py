from __future__ import annotations

import runpy
import sys
import types
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1] / "natron_plugins"
PLUGIN_FILE = PLUGIN_DIR / "SmartRead.py"


class FakeParam:
    def __init__(self, name: str, label: str = "") -> None:
        self.name = name
        self.label = label
        self.alias = None
        self.sequence_enabled = False
        self.value = 0
        self.default_value = 0
        self.options = []
        self.visible = True
        self.trigger_count = 0

    def setSequenceEnabled(self, enabled: bool) -> None:
        self.sequence_enabled = enabled

    def setHelp(self, _help: str) -> None:
        pass

    def setAnimationEnabled(self, _enabled: bool) -> None:
        pass

    def setDefaultValue(self, value) -> None:
        self.default_value = value

    def restoreDefaultValue(self) -> None:
        self.value = self.default_value

    def setVisible(self, visible: bool) -> None:
        self.visible = visible

    def setOptions(self, options) -> None:
        self.options = list(options)
        self.value = 0

    def addOption(self, option: str, _help: str) -> None:
        self.options.append(option)

    def getNumOptions(self) -> int:
        return len(self.options)

    def getOption(self, index: int) -> str:
        return self.options[index]

    def set(self, value) -> None:
        if isinstance(value, str) and value in self.options:
            self.value = self.options.index(value)
        else:
            self.value = value

    def setValue(self, value) -> None:
        self.set(value)

    def get(self):
        return self.value

    def getDefaultValue(self):
        return self.default_value

    def getScriptName(self) -> str:
        return self.name

    def setAsAlias(self, other) -> bool:
        self.alias = other
        return True

    def trigger(self) -> None:
        self.trigger_count += 1


class FakePage(FakeParam):
    def __init__(self, name: str, label: str = "") -> None:
        super().__init__(name, label)
        self.children = []

    def addParam(self, param) -> None:
        self.children.append(param)


class FakeEffect:
    def __init__(self, plugin_id: str, app=None, group=None) -> None:
        self.plugin_id = plugin_id
        self.app = app
        self.group = group
        self.destroyed = False
        self.inputs = {}
        self.params = {}
        if plugin_id == "fr.inria.built-in.Read":
            self.params = {
                "filename": FakeParam("filename"),
                "firstFrame": FakeParam("firstFrame"),
                "lastFrame": FakeParam("lastFrame"),
                "refreshButton": FakeParam("refreshButton"),
            }
            self.params["filename"].set("")

    def getParam(self, name: str):
        return self.params.get(name)

    def setScriptName(self, name: str) -> None:
        self.script_name = name

    def getScriptName(self) -> str:
        return self.script_name

    def setLabel(self, label: str) -> None:
        self.label = label

    def setPosition(self, x: int, y: int) -> None:
        self.position = (x, y)

    def connectInput(self, index: int, node):
        self.inputs[index] = node
        return True

    def disconnectInput(self, index: int) -> None:
        self.inputs.pop(index, None)

    def getInput(self, index: int):
        return self.inputs.get(index)

    def destroy(self, _auto_reconnect=True) -> None:
        self.destroyed = True
        if self.app is not None and self in self.app.nodes:
            self.app.nodes.remove(self)
        if self.group is not None and self in self.group.nodes:
            self.group.nodes.remove(self)

    def getPluginID(self) -> str:
        return self.plugin_id

    def getChildren(self):
        return []


class FakeGroup:
    def __init__(self) -> None:
        self.plugin_id = "com.portablepipetools.SmartRead"
        self.params = {"onParamChanged": FakeParam("onParamChanged")}
        self.nodes = []
        self.pages_order = []
        self.refreshed = False
        self.refresh_count = 0
        self.editable = True

    def createPageParam(self, name: str, label: str):
        page = FakePage(name, label)
        self.params[name] = page
        return page

    def createFileParam(self, name: str, label: str):
        return self._create_param(name, label)

    def createIntParam(self, name: str, label: str):
        return self._create_param(name, label)

    def createBooleanParam(self, name: str, label: str):
        return self._create_param(name, label)

    def createChoiceParam(self, name: str, label: str):
        return self._create_param(name, label)

    def createStringParam(self, name: str, label: str):
        return self._create_param(name, label)

    def createButtonParam(self, name: str, label: str):
        return self._create_param(name, label)

    def removeParam(self, param) -> bool:
        self.params.pop(param.name, None)
        for candidate in self.params.values():
            if isinstance(candidate, FakePage) and param in candidate.children:
                candidate.children.remove(param)
        return True

    def _create_param(self, name: str, label: str):
        param = FakeParam(name, label)
        self.params[name] = param
        return param

    def getParam(self, name: str):
        return self.params.get(name)

    def setPagesOrder(self, pages) -> None:
        self.pages_order = pages

    def refreshUserParamsGUI(self) -> None:
        self.refreshed = True
        self.refresh_count += 1

    def setSubGraphEditable(self, editable: bool) -> None:
        self.editable = editable

    def setLabel(self, label: str) -> None:
        self.label = label

    def getNode(self, name: str):
        return next(
            (node for node in self.nodes if getattr(node, "script_name", "") == name),
            None,
        )

    def getPluginID(self) -> str:
        return self.plugin_id

    def getChildren(self):
        return self.nodes

    def beginChanges(self) -> None:
        pass

    def endChanges(self) -> None:
        pass


class FakeProjectPaths:
    def __init__(self, project_directory=None) -> None:
        self.project_directory = project_directory

    def getTable(self):
        if self.project_directory is None:
            return []
        return [["Project", str(self.project_directory)]]


class FakeApp:
    def __init__(self, project_directory=None) -> None:
        self.nodes = []
        self.top_level_nodes = []
        self.project_directory = project_directory
        self.created_reader_filenames = []

    def createNode(self, plugin_id: str, _version: int, _group):
        node = FakeEffect(plugin_id, self, _group)
        self.nodes.append(node)
        _group.nodes.append(node)
        return node

    def createReader(self, filename: str, group):
        self.created_reader_filenames.append(filename)
        reader = self.createNode("fr.inria.built-in.Read", 1, group)
        reader.getParam("filename").set(filename)
        return reader

    def getProjectParam(self, name: str):
        if name == "projectPaths":
            return FakeProjectPaths(self.project_directory)
        return None

    def getChildren(self):
        return self.top_level_nodes

    def getAppID(self) -> int:
        return 0


class FakeViewer:
    def __init__(self) -> None:
        self.render_requests = []
        self.current_frame = 0
        self.seek_requests = []

    def renderCurrentFrame(self, use_cache=True) -> None:
        self.render_requests.append(use_cache)

    def getCurrentFrame(self) -> int:
        return self.current_frame

    def seek(self, frame: int) -> None:
        self.current_frame = frame
        self.seek_requests.append(frame)


class FakeGuiApp(FakeApp):
    def __init__(self, project_directory=None) -> None:
        super().__init__(project_directory)
        self.viewers = {}

    def addViewer(self, script_name: str):
        node = FakeEffect("fr.inria.built-in.Viewer")
        node.setScriptName(script_name)
        viewer = FakeViewer()
        self.top_level_nodes.append(node)
        self.viewers[script_name] = viewer
        return viewer

    def getViewer(self, script_name: str):
        return self.viewers.get(script_name)


def load_plugin():
    sys.path.insert(0, str(PLUGIN_DIR))
    try:
        sys.modules.pop("SmartReadExt", None)
        return runpy.run_path(str(PLUGIN_FILE))
    finally:
        sys.path.remove(str(PLUGIN_DIR))


def test_smart_read_metadata_is_stable():
    plugin = load_plugin()

    assert plugin["getPluginID"]() == "com.portablepipetools.SmartRead"
    assert plugin["getLabel"]() == "SmartRead"
    assert plugin["getVersion"]() == 10
    assert plugin["getGrouping"]() == "PortablePipeTools"
    assert callable(plugin["onParamChanged"])


def test_smart_read_builds_read_output_graph_and_public_controls():
    plugin = load_plugin()
    app = FakeApp()
    group = FakeGroup()

    plugin["createInstance"](app, group)

    assert [node.plugin_id for node in app.nodes] == [
        "fr.inria.built-in.Read",
        "fr.inria.built-in.Output",
    ]
    reader, output = app.nodes
    assert output.inputs[0] is reader
    assert "sourceFile" not in group.params
    assert "firstFrame" not in group.params
    assert "lastFrame" not in group.params
    assert group.params["sourceMissing"].visible is False
    assert group.params["version"].label == "File"
    assert group.params["element"].get() == "beauty"
    assert group.params["latest"].get() is True
    assert group.params["version"].visible is True
    assert group.params["onParamChanged"].get() == "SmartRead.onParamChanged"
    assert group.pages_order == ["smartRead", "Node", "Settings"]
    assert group.refreshed is True
    assert group.refresh_count == 2
    assert group.editable is False
    assert group.label == "SmartRead - beauty"


def test_smart_read_selects_latest_and_keeps_version_menu_visible(tmp_path):
    shot_root = tmp_path / "BSH_000_0020"
    project_directory = shot_root / "comp" / "natron"
    project_directory.mkdir(parents=True)
    output_directory = shot_root / "lite" / "unreal" / "_output"
    for version in (1, 28):
        version_name = f"BSH_000_0020_beauty_v{version:03d}"
        version_directory = output_directory / version_name
        version_directory.mkdir(parents=True)
        for frame in (1001, 1002):
            (version_directory / f"{version_name}.{frame}.exr").touch()

    plugin = load_plugin()
    extension = sys.modules["SmartReadExt"]
    app = FakeApp(project_directory)
    group = FakeGroup()
    plugin["createInstance"](app, group)

    assert group.params["version"].options == ["v001", "v028"]
    assert group.params["version"].getOption(group.params["version"].get()) == "v028"
    assert group.params["version"].get() == group.params["version"].getDefaultValue()
    assert group.params["version"].visible is True
    reader = group.getNode("Read1")
    assert app.created_reader_filenames == [reader.params["filename"].get()]
    assert group.getNode("Output1").inputs[0] is reader
    assert reader.params["filename"].get().endswith(
        "BSH_000_0020_beauty_v028.####.exr"
    )
    assert reader.params["firstFrame"].get() == 1001
    assert reader.params["lastFrame"].get() == 1002

    group.params["version"].set("v001")
    extension.onParamChanged(
        group.params["version"], group, app, app, True
    )
    assert reader.params["filename"].get().endswith(
        "BSH_000_0020_beauty_v001.####.exr"
    )
    assert group.params["latest"].get() is False
    assert group.params["version"].get() != group.params["version"].getDefaultValue()

    # Natron queues the programmatic Latest=False callback after the File
    # callback. It must not rebuild and invalidate the menu being handled.
    refresh_count = group.refresh_count
    extension.onParamChanged(
        group.params["latest"], group, app, app, False
    )
    assert group.refresh_count == refresh_count
    assert reader.params["filename"].get().endswith(
        "BSH_000_0020_beauty_v001.####.exr"
    )

    group.params["latest"].set(True)
    refresh_count = group.refresh_count
    extension.onParamChanged(
        group.params["latest"], group, app, app, True
    )
    assert group.refresh_count == refresh_count + 1
    assert group.params["version"].getOption(group.params["version"].get()) == "v028"
    assert group.params["version"].get() == group.params["version"].getDefaultValue()
    assert reader.params["filename"].get().endswith(
        "BSH_000_0020_beauty_v028.####.exr"
    )
    extension.onParamChanged(
        group.params["version"], group, app, app, False
    )
    assert group.params["latest"].get() is True

    group.params["latest"].set(False)
    refresh_count = group.refresh_count
    extension.onParamChanged(
        group.params["latest"], group, app, app, True
    )
    assert group.refresh_count == refresh_count + 1
    assert group.params["version"].getOption(group.params["version"].get()) == "v028"


def test_after_project_load_replaces_values_restored_from_template(tmp_path):
    shot_root = tmp_path / "BSH_000_0020"
    project_directory = shot_root / "comp" / "natron"
    project_directory.mkdir(parents=True)
    version_name = "BSH_000_0020_beauty_v028"
    version_directory = shot_root / "lite" / "unreal" / "_output" / version_name
    version_directory.mkdir(parents=True)
    (version_directory / f"{version_name}.1001.exr").touch()

    plugin = load_plugin()
    extension = sys.modules["SmartReadExt"]
    app = FakeApp(project_directory)
    group = FakeGroup()
    app.top_level_nodes.append(group)
    plugin["createInstance"](app, group)
    reader = group.getNode("Read1")

    # Natron restores serialized PyPlug values after createInstanceExt. A comp
    # copied from a template can therefore temporarily point at another shot.
    group.params["version"].setOptions(["v001"])
    reader.params["filename"].set("F:/old/template/shot.####.exr")
    reader.params["firstFrame"].set(1050)
    reader.params["lastFrame"].set(1099)

    extension.afterProjectLoaded(app)

    assert group.params["version"].options == ["v028"]
    assert reader.params["filename"].get().endswith(
        "BSH_000_0020_beauty_v028.####.exr"
    )
    assert reader.params["firstFrame"].get() == 1001
    assert reader.params["lastFrame"].get() == 1001


def test_gui_refresh_waits_for_persistent_timer_callback(tmp_path, monkeypatch):
    shot_root = tmp_path / "BSH_000_0020"
    project_directory = shot_root / "comp" / "natron"
    project_directory.mkdir(parents=True)
    version_name = "BSH_000_0020_beauty_v028"
    version_directory = shot_root / "lite" / "unreal" / "_output" / version_name
    version_directory.mkdir(parents=True)
    (version_directory / f"{version_name}.1001.exr").touch()

    plugin = load_plugin()
    extension = sys.modules["SmartReadExt"]
    app = FakeApp(project_directory)
    group = FakeGroup()
    app.top_level_nodes.append(group)
    plugin["createInstance"](app, group)
    reader = group.getNode("Read1")
    group.params["version"].setOptions(["v001"])
    reader.params["filename"].set("F:/old/template/shot.####.exr")

    scheduled = []
    fake_pyside = types.ModuleType("PySide")
    fake_pyside.QtCore = types.SimpleNamespace(
        QTimer=types.SimpleNamespace(
            singleShot=lambda delay, callback: scheduled.append((delay, callback))
        )
    )
    monkeypatch.setitem(sys.modules, "PySide", fake_pyside)

    extension.scheduleGuiRefresh(app)

    assert reader.params["filename"].get() == "F:/old/template/shot.####.exr"
    assert len(scheduled) == 1
    delay, callback = scheduled[0]
    assert delay == 100

    callback()

    assert group.params["version"].options == ["v028"]
    assert reader.params["filename"].get().endswith(
        "BSH_000_0020_beauty_v028.####.exr"
    )


def test_element_and_refresh_each_rescan_only_that_stream(tmp_path):
    shot_root = tmp_path / "BSH_000_0020"
    project_directory = shot_root / "comp" / "natron"
    project_directory.mkdir(parents=True)
    output_directory = shot_root / "lite" / "unreal" / "_output"

    def make_version(element: str, version: int) -> None:
        name = f"BSH_000_0020_{element}_v{version:03d}"
        directory = output_directory / name
        directory.mkdir(parents=True)
        (directory / f"{name}.1001.exr").touch()

    make_version("beauty", 4)
    make_version("environment", 2)

    plugin = load_plugin()
    extension = sys.modules["SmartReadExt"]
    app = FakeApp(project_directory)
    group = FakeGroup()
    plugin["createInstance"](app, group)
    reader = group.getNode("Read1")

    group.params["element"].set("environment")
    extension.onParamChanged(group.params["element"], group, app, app, True)
    assert group.label == "SmartRead - environment"
    assert group.params["version"].options == ["v002"]
    assert reader.params["filename"].get().endswith(
        "BSH_000_0020_environment_v002.####.exr"
    )

    make_version("environment", 7)
    extension.onParamChanged(group.params["refresh"], group, app, app, True)
    assert group.params["version"].options == ["v002", "v007"]
    assert reader.params["filename"].get().endswith(
        "BSH_000_0020_environment_v007.####.exr"
    )


def test_element_recovers_preview_after_switching_through_missing_stream(
    tmp_path, monkeypatch
):
    shot_root = tmp_path / "BSH_000_0020"
    project_directory = shot_root / "comp" / "natron"
    project_directory.mkdir(parents=True)
    output_directory = shot_root / "lite" / "unreal" / "_output"
    name = "BSH_000_0020_beauty_v004"
    version_directory = output_directory / name
    version_directory.mkdir(parents=True)
    (version_directory / f"{name}.1001.exr").touch()
    (version_directory / f"{name}.1040.exr").touch()

    scheduled = []
    fake_pyside = types.ModuleType("PySide")
    fake_pyside.QtCore = types.SimpleNamespace(
        QTimer=types.SimpleNamespace(
            singleShot=lambda delay, callback: scheduled.append((delay, callback))
        )
    )
    monkeypatch.setitem(sys.modules, "PySide", fake_pyside)

    app = FakeApp(project_directory)
    gui_app = FakeGuiApp(project_directory)
    viewer = gui_app.addViewer("Viewer1")
    viewer.current_frame = 1099
    app.top_level_nodes = gui_app.top_level_nodes
    fake_natron_engine = types.ModuleType("NatronEngine")
    fake_natron_engine.natron = types.SimpleNamespace(isBackground=lambda: False)
    fake_natron_gui = types.ModuleType("NatronGui")
    fake_natron_gui.natron = types.SimpleNamespace(
        getGuiInstance=lambda app_id: gui_app if app_id == 0 else None
    )
    monkeypatch.setitem(sys.modules, "NatronEngine", fake_natron_engine)
    monkeypatch.setitem(sys.modules, "NatronGui", fake_natron_gui)

    plugin = load_plugin()
    extension = sys.modules["SmartReadExt"]
    group = FakeGroup()
    plugin["createInstance"](app, group)
    original_reader = group.getNode("Read1")

    assert len(scheduled) == 1
    delay, callback = scheduled.pop()
    assert delay == 0
    callback()

    configured_reader = group.getNode("Output1").inputs[0]
    assert configured_reader is not original_reader
    original_reader = configured_reader
    initial_refresh_count = original_reader.params["refreshButton"].trigger_count

    assert len(scheduled) == 1
    delay, callback = scheduled.pop()
    assert delay == 250
    callback()
    assert viewer.render_requests == []
    assert viewer.seek_requests == [1001]

    # Existing v10 comps serialized before sourceMissing was added do not run
    # the new createInstance structure. The extension must migrate them live.
    source_missing = group.params.pop("sourceMissing")
    group.params["smartRead"].children.remove(source_missing)

    group.params["element"].set("hero")
    extension.onParamChanged(group.params["element"], group, app, app, True)
    assert original_reader.params["filename"].get() == ""
    assert group.params["sourceMissing"].get() is True
    assert original_reader.params["refreshButton"].trigger_count == (
        initial_refresh_count + 1
    )
    assert len(scheduled) == 1
    scheduled.pop()[1]()
    assert viewer.render_requests == [False]

    # A native Read can retain its failed state after its filename becomes
    # valid again. Recovery replaces it so Natron sees a new node identity.
    group.params["element"].set("beauty")
    extension.onParamChanged(group.params["element"], group, app, app, True)
    recovered_reader = group.getNode("Read1")
    assert recovered_reader is not original_reader
    assert original_reader.destroyed is True
    assert group.getNode("Output1").inputs[0] is recovered_reader
    assert group.params["sourceMissing"].get() is False
    assert recovered_reader.params["filename"].get().endswith(
        "BSH_000_0020_beauty_v004.####.exr"
    )
    assert app.created_reader_filenames[-1] == (
        recovered_reader.params["filename"].get()
    )
    assert len(app.created_reader_filenames) == 2
    assert recovered_reader.params["refreshButton"].trigger_count == 1
    assert len(scheduled) == 1
    scheduled.pop()[1]()
    assert viewer.render_requests == [False, False]
    assert viewer.current_frame == 1001
    assert viewer.seek_requests == [1001]
