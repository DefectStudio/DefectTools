from __future__ import annotations

import runpy
import sys
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

    def get(self):
        return self.value

    def getScriptName(self) -> str:
        return self.name

    def setAsAlias(self, other) -> bool:
        self.alias = other
        return True


class FakePage(FakeParam):
    def __init__(self, name: str, label: str = "") -> None:
        super().__init__(name, label)
        self.children = []

    def addParam(self, param) -> None:
        self.children.append(param)


class FakeEffect:
    def __init__(self, plugin_id: str) -> None:
        self.plugin_id = plugin_id
        self.inputs = {}
        self.params = {}
        if plugin_id == "fr.inria.built-in.Read":
            self.params = {
                "filename": FakeParam("filename"),
                "firstFrame": FakeParam("firstFrame"),
                "lastFrame": FakeParam("lastFrame"),
            }

    def getParam(self, name: str):
        return self.params.get(name)

    def setScriptName(self, name: str) -> None:
        self.script_name = name

    def setLabel(self, label: str) -> None:
        self.label = label

    def setPosition(self, x: int, y: int) -> None:
        self.position = (x, y)

    def connectInput(self, index: int, node) -> None:
        self.inputs[index] = node


class FakeGroup:
    def __init__(self) -> None:
        self.params = {"onParamChanged": FakeParam("onParamChanged")}
        self.nodes = []
        self.pages_order = []
        self.refreshed = False
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

    def setSubGraphEditable(self, editable: bool) -> None:
        self.editable = editable

    def setLabel(self, label: str) -> None:
        self.label = label

    def getNode(self, name: str):
        return next(
            (node for node in self.nodes if getattr(node, "script_name", "") == name),
            None,
        )

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
        self.project_directory = project_directory

    def createNode(self, plugin_id: str, _version: int, _group):
        node = FakeEffect(plugin_id)
        self.nodes.append(node)
        _group.nodes.append(node)
        return node

    def getProjectParam(self, name: str):
        return (
            FakeProjectPaths(self.project_directory)
            if name == "projectPaths"
            else None
        )


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
    assert plugin["getVersion"]() == 6
    assert plugin["getGrouping"]() == "PortablePipeTools"


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
    assert group.params["version"].label == "File"
    assert group.params["element"].get() == "beauty"
    assert group.params["latest"].get() is True
    assert group.params["version"].visible is True
    assert group.params["onParamChanged"].get() == "SmartReadExt.onParamChanged"
    assert group.pages_order == ["smartRead", "Node", "Settings"]
    assert group.refreshed is True
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
    assert group.params["version"].visible is True
    reader = app.nodes[0]
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
    reader = app.nodes[0]

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
