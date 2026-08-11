from __future__ import annotations

import runpy
import sys
from pathlib import Path


PLUGIN_FILE = Path(__file__).resolve().parents[1] / "natron_plugins" / "SmartWrite.py"


class FakeParam:
    def __init__(self, name: str, label: str = "") -> None:
        self.name = name
        self.label = label
        self.default_value = None
        self.value = None
        self.alias = None
        self.opened = None
        self.options = []
        self.add_new_line = True
        self.enabled = True
        self.help = ""
        self.visible = True

    def setDefaultValue(self, value) -> None:
        self.default_value = value

    def restoreDefaultValue(self) -> None:
        self.value = self.default_value

    def setAnimationEnabled(self, _enabled: bool) -> None:
        pass

    def setHelp(self, help_text: str) -> None:
        self.help = help_text

    def setAddNewLine(self, add_new_line: bool) -> None:
        self.add_new_line = add_new_line

    def setEnabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def setVisible(self, visible: bool) -> None:
        self.visible = visible

    def set(self, value) -> None:
        self.value = value

    def get(self):
        return self.value

    def getScriptName(self) -> str:
        return self.name

    def getLabel(self) -> str:
        return self.label or self.name

    def setAsAlias(self, other) -> bool:
        self.alias = other
        return True

    def setOptions(self, options) -> None:
        self.options = [
            option[0] if isinstance(option, tuple) else option
            for option in options
        ]

    def getOptions(self):
        return list(self.options)

    def setOpened(self, opened: bool) -> None:
        self.opened = opened


class FakePage(FakeParam):
    def __init__(self, name: str, label: str) -> None:
        super().__init__(name, label)
        self.children = []

    def addParam(self, param) -> None:
        self.children.append(param)


class FakeNode:
    def __init__(
        self,
        plugin_id: str,
        app=None,
        group=None,
        include_format_params: bool = False,
    ) -> None:
        self.plugin_id = plugin_id
        self.app = app
        self.group = group
        self.destroyed = False
        self.inputs = {}
        self.params = {}
        if plugin_id == "fr.inria.built-in.Write":
            common_param_names = (
                "filename",
                "disableNode",
                "outputComponents",
                "inputPremult",
                "ocioInputSpaceIndex",
                "ocioOutputSpaceIndex",
                "frameRange",
                "firstFrame",
                "lastFrame",
                "frameIncr",
                "readBack",
            )
            format_param_names = (
                "bitDepth",
                "compression",
                "quality",
                "dwaCompressionLevel",
                "outputChannels",
                "processAllPlanes",
                "partSplitting",
                "viewsSelector",
                "tileSize",
                "codec",
                "fps",
                "prefPixelCoding",
                "prefBitDepth",
                "crf",
                "x26xSpeed",
                "bitrateMbps",
                "gopSize",
                "bFrames",
                "fastStart",
                "enableAlpha",
                "DNxHDCodecProfile",
                "HapFormat",
            )
            param_names = common_param_names + (
                format_param_names if include_format_params else ()
            )
            self.params = {
                name: FakeParam(name, name) for name in param_names
            }

    def setScriptName(self, name: str) -> None:
        self.script_name = name

    def setLabel(self, label: str) -> None:
        self.label = label

    def setPosition(self, x: int, y: int) -> None:
        self.position = (x, y)

    def connectInput(self, index: int, node) -> bool:
        self.inputs[index] = node
        return True

    def getInput(self, index: int):
        return self.inputs.get(index)

    def getParam(self, name: str):
        return self.params.get(name)

    def getPluginID(self) -> str:
        return self.plugin_id

    def getChildren(self):
        return []

    def destroy(self, _auto_reconnect=True) -> None:
        self.destroyed = True
        if self.app is not None and self in self.app.nodes:
            self.app.nodes.remove(self)
        if self.group is not None and self in self.group.nodes:
            self.group.nodes.remove(self)


class FakeGroup:
    def __init__(self) -> None:
        self.plugin_id = "com.portablepipetools.SmartWrite"
        self.params = {"onParamChanged": FakeParam("onParamChanged")}
        self.nodes = []
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

    def createButtonParam(self, name: str, label: str):
        return self.createBooleanParam(name, label)

    def createIntParam(self, name: str, label: str):
        return self.createBooleanParam(name, label)

    def createDoubleParam(self, name: str, label: str):
        return self.createBooleanParam(name, label)

    def createChoiceParam(self, name: str, label: str):
        return self.createBooleanParam(name, label)

    def createGroupParam(self, name: str, label: str):
        page = FakePage(name, label)
        self.params[name] = page
        return page

    def removeParam(self, param) -> bool:
        self.params.pop(param.name, None)
        for container in self.params.values():
            if isinstance(container, FakePage):
                container.children = [
                    child for child in container.children if child is not param
                ]
        return True

    def setPagesOrder(self, pages) -> None:
        self.pages_order = list(pages)

    def refreshUserParamsGUI(self) -> None:
        self.refreshed = True

    def setSubGraphEditable(self, editable: bool) -> None:
        self.editable = editable

    def getParam(self, name: str):
        return self.params.get(name)

    def getNode(self, name: str):
        return next(
            (node for node in self.nodes if node.script_name == name),
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
    def __init__(self, app) -> None:
        self.app = app

    def getTable(self):
        return [("Project", str(self.app.project_directory))]


class FakeApp:
    def __init__(self, project_directory: Path | None = None) -> None:
        self.nodes = []
        self.groups = []
        self.project_directory = project_directory
        self.timeline_bounds = (1001, 1040)
        self.render_calls = []

    def createNode(self, plugin_id: str, _major_version: int, group):
        node = FakeNode(plugin_id, self, group)
        self.nodes.append(node)
        group.nodes.append(node)
        return node

    def createWriter(self, filename: str, group):
        node = FakeNode(
            "fr.inria.built-in.Write",
            self,
            group,
            include_format_params=True,
        )
        node.getParam("filename").set(filename)
        node.getParam("compression").setOptions(["Zip", "Piz", "DWAA"])
        node.getParam("compression").set(0)
        node.getParam("codec").setOptions(["prores_ksap4h", "libx264"])
        node.getParam("codec").set(0)
        node.getParam("bitDepth").setOptions(["16f", "32f"])
        node.getParam("bitDepth").set(0)
        self.nodes.append(node)
        group.nodes.append(node)
        return node

    def getProjectParam(self, name: str):
        if name != "projectPaths" or self.project_directory is None:
            return None
        return FakeProjectPaths(self)

    def getChildren(self):
        return self.groups

    def timelineGetLeftBound(self) -> int:
        return self.timeline_bounds[0]

    def timelineGetRightBound(self) -> int:
        return self.timeline_bounds[1]

    def render(self, tasks) -> None:
        self.render_calls.append(list(tasks))


def _load_plugin_with_extension(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_FILE.parent))
    sys.modules.pop("SmartWriteExt", None)
    sys.modules.pop("smart_write_core", None)
    return runpy.run_path(str(PLUGIN_FILE))


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
    visible_controls = [param for param in page.children if param.visible]
    assert [param.name for param in visible_controls[:9]] == [
        "renderAll",
        "exrOutput",
        "renderEXR",
        "mp4Output",
        "renderMP4",
        "movOutput",
        "renderMOV",
        "heroOutput",
        "renderHero",
    ]
    output_controls = [
        group.getParam(name)
        for name in ("exrOutput", "mp4Output", "movOutput", "heroOutput")
    ]
    assert [param.label for param in output_controls] == [
        "EXR Output",
        "MP4 Output",
        "MOV Output",
        "Hero Output",
    ]
    assert [param.value for param in output_controls] == [True, True, False, True]
    assert all(param.add_new_line is True for param in output_controls)
    assert group.getParam("renderAll").add_new_line is True
    assert all(
        group.getParam(name).add_new_line is False
        for name in ("renderEXR", "renderMP4", "renderMOV", "renderHero")
    )
    assert group.getParam("renderMOV").enabled is False
    assert group.pages_order == ["smartWrite", "Node", "Settings"]
    assert group.refreshed is True
    assert group.editable is False

    assert [node.plugin_id for node in app.nodes] == [
        "fr.inria.built-in.Input",
        "fr.inria.built-in.Write",
        "fr.inria.built-in.Write",
        "fr.inria.built-in.Write",
        "fr.inria.built-in.Write",
        "fr.inria.built-in.Output",
    ]
    input_node, *writers, output = app.nodes
    assert all(writer.inputs[0] is input_node for writer in writers)
    assert output.inputs[0] is input_node


def test_render_buttons_submit_enabled_writers_over_project_range(
    monkeypatch, tmp_path: Path
) -> None:
    plugin = _load_plugin_with_extension(monkeypatch)
    project_directory = (
        tmp_path
        / "defect"
        / "s3bishop"
        / "sequences"
        / "BSH"
        / "BSH_000_0020"
        / "comp"
        / "natron"
    )
    project_directory.mkdir(parents=True)
    app = FakeApp(project_directory)
    group = FakeGroup()
    app.groups.append(group)
    plugin["createInstance"](app, group)

    plugin["onParamChanged"](
        group.getParam("renderAll"), group, group, app, True
    )

    assert len(app.render_calls) == 1
    assert [task[0].script_name for task in app.render_calls[0]] == [
        "EXRWrite",
        "MP4Write",
        "HeroWrite",
    ]
    assert [task[1:] for task in app.render_calls[0]] == [
        (1001, 1040, 1),
        (1001, 1040, 1),
        (1001, 1040, 1),
    ]

    plugin["onParamChanged"](
        group.getParam("renderMOV"), group, group, app, True
    )
    assert len(app.render_calls) == 1

    group.getParam("movOutput").set(True)
    plugin["onParamChanged"](
        group.getParam("movOutput"), group, group, app, True
    )
    assert group.getParam("renderMOV").enabled is True

    plugin["onParamChanged"](
        group.getParam("renderMOV"), group, group, app, True
    )
    assert len(app.render_calls) == 2
    assert [task[0].script_name for task in app.render_calls[1]] == ["MOVWrite"]
    assert app.render_calls[1][0][1:] == (1001, 1040, 1)

    for checkbox_name in ("exrOutput", "mp4Output", "movOutput", "heroOutput"):
        checkbox = group.getParam(checkbox_name)
        checkbox.set(False)
        plugin["onParamChanged"](checkbox, group, group, app, True)
    assert group.getParam("renderAll").enabled is False


def test_project_load_adds_render_buttons_to_legacy_smart_write(
    monkeypatch, tmp_path: Path
) -> None:
    plugin = _load_plugin_with_extension(monkeypatch)
    project_directory = (
        tmp_path
        / "show"
        / "sequences"
        / "BSH"
        / "BSH_000_0020"
        / "comp"
        / "natron"
    )
    project_directory.mkdir(parents=True)
    app = FakeApp(project_directory)
    group = FakeGroup()
    app.groups.append(group)
    plugin["createInstance"](app, group)
    group.getParam("exr_compression").set(2)

    render_names = {
        "smartWriteUiVersion",
        "renderAll",
        "renderEXR",
        "renderMP4",
        "renderMOV",
        "renderHero",
    }
    for name in render_names:
        group.params.pop(name)
    page = group.getParam("smartWrite")
    legacy_page = page
    page.children = [
        param for param in page.children if param.name not in render_names
    ]

    sys.modules["SmartWriteExt"].afterProjectLoaded(app)

    assert all(group.getParam(name) is not None for name in render_names)
    assert group.getParam("renderMOV").enabled is False
    assert group.getParam("exr_compression").get() == 2
    page = group.getParam("smartWrite")
    assert page is not legacy_page
    visible_controls = [param for param in page.children if param.visible]
    assert [param.name for param in visible_controls[:9]] == [
        "renderAll",
        "exrOutput",
        "renderEXR",
        "mp4Output",
        "renderMP4",
        "movOutput",
        "renderMOV",
        "heroOutput",
        "renderHero",
    ]


def test_smart_write_configures_exact_shot_output_paths(
    monkeypatch, tmp_path: Path
) -> None:
    plugin = _load_plugin_with_extension(monkeypatch)
    shot_root = (
        tmp_path
        / "defect"
        / "s3bishop"
        / "sequences"
        / "BSH"
        / "BSH_000_0020"
    )
    project_directory = shot_root / "comp" / "natron"
    project_directory.mkdir(parents=True)
    app = FakeApp(project_directory)
    group = FakeGroup()
    app.groups.append(group)

    plugin["createInstance"](app, group)

    expected_base = (shot_root / "comp" / "_output").as_posix()
    assert group.getNode("EXRWrite").getParam("filename").get() == (
        expected_base
        + "/BSH_000_0020_beauty_v001/"
        "BSH_000_0020_beauty_v001.####.exr"
    )
    assert group.getNode("MP4Write").getParam("filename").get() == (
        expected_base + "/BSH_000_0020_beauty_v001.mp4"
    )
    assert group.getNode("MOVWrite").getParam("filename").get() == (
        expected_base + "/BSH_000_0020_beauty_v001.mov"
    )
    assert group.getNode("HeroWrite").getParam("filename").get() == (
        expected_base + "/_hero/BSH_000_0020.####.exr"
    )
    assert (shot_root / "comp" / "_output").is_dir()
    assert (
        shot_root
        / "comp"
        / "_output"
        / "BSH_000_0020_beauty_v001"
    ).is_dir()
    assert (shot_root / "comp" / "_output" / "_hero").is_dir()
    assert [
        group.getNode(name).getParam("disableNode").get()
        for name in ("EXRWrite", "MP4Write", "MOVWrite", "HeroWrite")
    ] == [False, False, True, False]
    assert group.getParam("onParamChanged").get() == "SmartWrite.onParamChanged"
    assert not any(
        node.script_name.endswith("Placeholder") for node in group.nodes
    )
    page = group.getParam("smartWrite")
    assert [param.name for param in page.children[-4:]] == [
        "exrSettings",
        "mp4Settings",
        "movSettings",
        "heroSettings",
    ]
    assert [group.getParam(name).opened for name in (
        "exrSettings",
        "mp4Settings",
        "movSettings",
        "heroSettings",
    )] == [True, True, False, True]
    assert group.getParam("exr_compression").alias is None
    assert group.getParam("mp4_codec").alias is None
    assert group.getParam("hero_bitDepth").alias is None
    assert group.getParam("mp4_codec").get() == 1
    assert group.getNode("MP4Write").getParam("codec").get() == 1
    assert group.getNode("MOVWrite").getParam("codec").get() == 0
    assert group.getParam("exr_compression").getOptions() == [
        "Zip",
        "Piz",
        "DWAA",
    ]
    group.getParam("exr_compression").set(2)
    plugin["onParamChanged"](
        group.getParam("exr_compression"), group, group, app, True
    )
    assert group.getNode("EXRWrite").getParam("compression").get() == 2

    group.getParam("movOutput").set(True)
    plugin["onParamChanged"](
        group.getParam("movOutput"), group, group, app, True
    )
    assert group.getNode("MOVWrite").getParam("disableNode").get() is False
    assert group.getNode("MOVWrite").getParam("filename").get().endswith(
        "/BSH_000_0020_beauty_v001.mov"
    )
    assert group.getParam("movSettings").opened is True

    group.getParam("exrOutput").set(False)
    plugin["onParamChanged"](
        group.getParam("exrOutput"), group, group, app, True
    )
    assert group.getNode("EXRWrite").getParam("disableNode").get() is True
    assert group.getParam("exrSettings").opened is False


def test_smart_write_refreshes_paths_after_template_copy(
    monkeypatch, tmp_path: Path
) -> None:
    plugin = _load_plugin_with_extension(monkeypatch)
    first_project = (
        tmp_path
        / "show"
        / "sequences"
        / "BSH"
        / "BSH_000_0020"
        / "comp"
        / "natron"
    )
    first_project.mkdir(parents=True)
    app = FakeApp(first_project)
    group = FakeGroup()
    app.groups.append(group)
    plugin["createInstance"](app, group)

    group.getParam("exr_compression").setOptions([])
    group.getParam("mp4_codec").setOptions([])
    group.getNode("EXRWrite").getParam("compression").setOptions([])
    group.getNode("MP4Write").getParam("codec").setOptions([])
    group.getNode("MOVWrite").getParam("codec").setOptions([])
    group.getNode("HeroWrite").getParam("compression").setOptions([])
    assert group.getParam("exr_compression").getOptions() == []
    assert group.getParam("mp4_codec").getOptions() == []

    app.project_directory = (
        tmp_path
        / "show"
        / "sequences"
        / "BSH"
        / "BSH_000_0030"
        / "comp"
        / "natron"
    )
    app.project_directory.mkdir(parents=True)
    sys.modules["SmartWriteExt"].afterProjectLoaded(app)

    assert group.getNode("EXRWrite").getParam("filename").get().endswith(
        "/BSH_000_0030_beauty_v001/BSH_000_0030_beauty_v001.####.exr"
    )
    assert group.getParam("exr_compression").getOptions() == [
        "Zip",
        "Piz",
        "DWAA",
    ]
    assert group.getParam("mp4_codec").getOptions() == [
        "prores_ksap4h",
        "libx264",
    ]


def test_each_new_smart_write_reserves_the_next_version(
    monkeypatch, tmp_path: Path
) -> None:
    plugin = _load_plugin_with_extension(monkeypatch)
    project_directory = (
        tmp_path
        / "show"
        / "sequences"
        / "BSH"
        / "BSH_000_0020"
        / "comp"
        / "natron"
    )
    project_directory.mkdir(parents=True)
    app = FakeApp(project_directory)

    first_group = FakeGroup()
    app.groups.append(first_group)
    plugin["createInstance"](app, first_group)

    second_group = FakeGroup()
    app.groups.append(second_group)
    plugin["createInstance"](app, second_group)

    assert first_group.getNode("EXRWrite").getParam("filename").get().endswith(
        "/BSH_000_0020_beauty_v001/BSH_000_0020_beauty_v001.####.exr"
    )
    assert second_group.getNode("EXRWrite").getParam("filename").get().endswith(
        "/BSH_000_0020_beauty_v002/BSH_000_0020_beauty_v002.####.exr"
    )
