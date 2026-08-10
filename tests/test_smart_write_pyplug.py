from __future__ import annotations

import runpy
from pathlib import Path


PLUGIN_FILE = Path(__file__).resolve().parents[1] / "natron_plugins" / "SmartWrite.py"


class FakeParam:
    def __init__(self, name: str, label: str) -> None:
        self.name = name
        self.label = label
        self.default_value = None
        self.value = None

    def setDefaultValue(self, value) -> None:
        self.default_value = value

    def restoreDefaultValue(self) -> None:
        self.value = self.default_value

    def setAnimationEnabled(self, _enabled: bool) -> None:
        pass

    def setHelp(self, _help: str) -> None:
        pass


class FakePage(FakeParam):
    def __init__(self, name: str, label: str) -> None:
        super().__init__(name, label)
        self.children = []

    def addParam(self, param) -> None:
        self.children.append(param)


class FakeNode:
    def __init__(self, plugin_id: str) -> None:
        self.plugin_id = plugin_id
        self.inputs = {}

    def setScriptName(self, name: str) -> None:
        self.script_name = name

    def setLabel(self, label: str) -> None:
        self.label = label

    def setPosition(self, x: int, y: int) -> None:
        self.position = (x, y)

    def connectInput(self, index: int, node) -> bool:
        self.inputs[index] = node
        return True


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

    def createBooleanParam(self, name: str, label: str):
        param = FakeParam(name, label)
        self.params[name] = param
        return param

    def setPagesOrder(self, pages) -> None:
        self.pages_order = list(pages)

    def refreshUserParamsGUI(self) -> None:
        self.refreshed = True

    def setSubGraphEditable(self, editable: bool) -> None:
        self.editable = editable


class FakeApp:
    def __init__(self) -> None:
        self.nodes = []

    def createNode(self, plugin_id: str, _major_version: int, _group):
        node = FakeNode(plugin_id)
        self.nodes.append(node)
        return node


def test_smart_write_metadata_and_initial_scaffold() -> None:
    plugin = runpy.run_path(str(PLUGIN_FILE))

    assert plugin["getPluginID"]() == "com.portablepipetools.SmartWrite"
    assert plugin["getLabel"]() == "SmartWrite"
    assert plugin["getVersion"]() == 1
    assert plugin["getGrouping"]() == "PortablePipeTools"

    app = FakeApp()
    group = FakeGroup()
    plugin["createInstance"](app, group)

    page = group.params["smartWrite"]
    assert [param.name for param in page.children] == [
        "exrOutput",
        "mp4Output",
        "movOutput",
        "heroOutput",
    ]
    assert [param.label for param in page.children] == [
        "EXR Output",
        "MP4 Output",
        "MOV Output",
        "Hero Output",
    ]
    assert all(param.value is False for param in page.children)
    assert group.pages_order == ["smartWrite", "Node", "Settings"]
    assert group.refreshed is True
    assert group.editable is False

    assert [node.plugin_id for node in app.nodes] == [
        "fr.inria.built-in.Input",
        "fr.inria.built-in.Write",
        "fr.inria.built-in.Output",
    ]
    input_node, writer, output = app.nodes
    assert writer.inputs[0] is input_node
    assert output.inputs[0] is writer
