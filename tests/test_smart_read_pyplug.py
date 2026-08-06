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

    def setSequenceEnabled(self, enabled: bool) -> None:
        self.sequence_enabled = enabled

    def setHelp(self, _help: str) -> None:
        pass

    def setAnimationEnabled(self, _enabled: bool) -> None:
        pass

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
        self.params = {}
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


class FakeApp:
    def __init__(self) -> None:
        self.nodes = []

    def createNode(self, plugin_id: str, _version: int, _group):
        node = FakeEffect(plugin_id)
        self.nodes.append(node)
        return node


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
    assert plugin["getVersion"]() == 1
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
    assert group.params["sourceFile"].alias is reader.params["filename"]
    assert group.params["sourceFile"].sequence_enabled is True
    assert group.params["firstFrame"].alias is reader.params["firstFrame"]
    assert group.params["lastFrame"].alias is reader.params["lastFrame"]
    assert group.pages_order == ["smartRead", "Node", "Settings"]
    assert group.refreshed is True
    assert group.editable is False

