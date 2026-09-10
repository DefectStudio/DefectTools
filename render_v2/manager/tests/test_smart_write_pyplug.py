from __future__ import annotations

import runpy
import sys
from pathlib import Path

import pytest


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
        if plugin_id in (
            "fr.inria.built-in.Write",
            "fr.inria.openfx.WriteOIIO",
            "fr.inria.openfx.WriteFFmpeg",
        ):
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
                format_param_names
                if include_format_params or plugin_id != "fr.inria.built-in.Write"
                else ()
            )
            self.params = {
                name: FakeParam(name, name) for name in param_names
            }
            if plugin_id == "fr.inria.openfx.WriteOIIO":
                self.params["compression"].setOptions(["Zip", "Piz", "DWAA"])
                self.params["compression"].set(0)
                self.params["bitDepth"].setOptions(["16f", "32f"])
                self.params["bitDepth"].set(0)
            if plugin_id == "fr.inria.openfx.WriteFFmpeg":
                self.params["codec"].setOptions(["prores_ksap4h", "libx264"])
                self.params["codec"].set(0)

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

    def getMaxInputCount(self) -> int:
        return max(self.inputs, default=-1) + 1

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
        self.inputs = {}

    def createPageParam(self, name: str, label: str):
        page = FakePage(name, label)
        self.params[name] = page
        return page

    def connectInput(self, index: int, node) -> bool:
        self.inputs[index] = node
        return True

    def getScriptName(self) -> str:
        return "SmartWrite1"

    def getInput(self, index: int):
        return self.inputs.get(index)

    def getMaxInputCount(self) -> int:
        return max(self.inputs, default=-1) + 1

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
            (
                node
                for node in self.nodes
                if getattr(node, "script_name", None) == name
            ),
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


def test_submit_render_tasks_uses_natrons_python_task_sequence_contract(
    monkeypatch,
) -> None:
    monkeypatch.syspath_prepend(str(PLUGIN_FILE.parent))
    extension = runpy.run_path(str(PLUGIN_FILE.with_name("SmartWriteExt.py")))
    writers = [object(), object(), object()]
    tasks = [
        (writers[0], 1001, 1040, 1),
        (writers[1], 1101, 1123, 2),
        (writers[2], 1200, 1204, 1),
    ]
    calls = []

    class RenderApp:
        def render(self, *args) -> None:
            calls.append(args)

    extension["_submit_render_tasks"](RenderApp(), tasks)

    assert calls == [(tasks,)]


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
        "fr.inria.openfx.WriteOIIO",
        "fr.inria.openfx.WriteFFmpeg",
        "fr.inria.openfx.WriteFFmpeg",
        "fr.inria.openfx.WriteOIIO",
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


def test_render_buttons_prefer_upstream_reader_range_over_stale_project_range(
    monkeypatch, tmp_path: Path
) -> None:
    plugin = _load_plugin_with_extension(monkeypatch)
    project_directory = (
        tmp_path
        / "defect"
        / "s3bishop"
        / "sequences"
        / "ZZZ"
        / "ZZZ_000_0850"
        / "comp"
        / "natron"
    )
    project_directory.mkdir(parents=True)
    app = FakeApp(project_directory)
    app.timeline_bounds = (1, 1099)
    group = FakeGroup()
    app.groups.append(group)
    plugin["createInstance"](app, group)

    reader = FakeNode("fr.inria.built-in.Read")
    reader.params["firstFrame"] = FakeParam("firstFrame")
    reader.params["firstFrame"].set(1001)
    reader.params["lastFrame"] = FakeParam("lastFrame")
    reader.params["lastFrame"].set(1040)
    smart_read = FakeNode("com.portablepipetools.SmartRead")
    smart_read.getChildren = lambda: [reader]
    grade = FakeNode("net.sf.openfx.GradePlugin")
    grade.connectInput(0, smart_read)
    group.connectInput(0, grade)

    plugin["onParamChanged"](
        group.getParam("renderAll"), group, group, app, True
    )

    assert len(app.render_calls) == 1
    assert [task[1:] for task in app.render_calls[0]] == [
        (1001, 1040, 1),
        (1001, 1040, 1),
        (1001, 1040, 1),
    ]


def test_exr_render_buttons_sync_every_exposed_setting_before_render(
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
    expected_settings = {
        "outputComponents": 11,
        "inputPremult": 12,
        "ocioInputSpaceIndex": 13,
        "ocioOutputSpaceIndex": 14,
        "frameRange": 15,
        "firstFrame": 1011,
        "lastFrame": 1037,
        "frameIncr": 3,
        "readBack": True,
        "bitDepth": 1,
        "compression": 2,
        "quality": 87,
        "dwaCompressionLevel": 42.5,
        "outputChannels": 16,
        "processAllPlanes": True,
        "partSplitting": 17,
        "viewsSelector": 18,
        "tileSize": 19,
    }

    for expected_version, button_name in enumerate(
        ("renderEXR", "renderAll"), start=1
    ):
        app = FakeApp(project_directory)
        group = FakeGroup()
        app.groups.append(group)
        plugin["createInstance"](app, group)
        writer = group.getNode("EXRWrite")

        exposed_names = {
            name.removeprefix("exr_")
            for name in group.params
            if name.startswith("exr_")
        }
        assert exposed_names == set(expected_settings)
        for native_name, value in expected_settings.items():
            group.getParam(f"exr_{native_name}").set(value)

        writer.getParam("filename").set("stale.exr")
        writer.getParam("disableNode").set(True)
        render_snapshots = []

        def capture_render(tasks) -> None:
            tasks = list(tasks)
            render_snapshots.append(
                {
                    "tasks": list(tasks),
                    "filename": writer.getParam("filename").get(),
                    "disableNode": writer.getParam("disableNode").get(),
                    "settings": {
                        name: writer.getParam(name).get()
                        for name in expected_settings
                    },
                }
            )

        app.render = capture_render
        plugin["onParamChanged"](
            group.getParam(button_name), group, group, app, True
        )

        assert len(render_snapshots) == 1
        snapshot = render_snapshots[0]
        assert snapshot["filename"].endswith(
            (
                "/BSH_000_0020_beauty_v{0:03d}/"
                "BSH_000_0020_beauty_v{0:03d}.####.exr"
            ).format(expected_version)
        )
        assert snapshot["disableNode"] is False
        assert snapshot["settings"] == expected_settings
        assert snapshot["tasks"][0][0] is writer
        assert snapshot["tasks"][0][1:] == (1001, 1040, 3)


@pytest.mark.parametrize("button_name", ["renderHero", "renderAll"])
def test_hero_render_buttons_sync_every_exposed_setting_before_submission(
    monkeypatch, tmp_path: Path, button_name: str
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
    app.timeline_bounds = (1101, 1123)
    group = FakeGroup()
    app.groups.append(group)
    plugin["createInstance"](app, group)

    expected_settings = {
        "outputComponents": 3,
        "inputPremult": 4,
        "ocioInputSpaceIndex": 5,
        "ocioOutputSpaceIndex": 6,
        "frameRange": 7,
        "firstFrame": 2001,
        "lastFrame": 2010,
        "frameIncr": 2,
        "readBack": True,
        "bitDepth": 1,
        "compression": 2,
        "quality": 91,
        "dwaCompressionLevel": 33.5,
        "outputChannels": 8,
        "processAllPlanes": True,
        "partSplitting": 9,
        "viewsSelector": 10,
        "tileSize": 11,
    }
    extension = sys.modules["SmartWriteExt"]
    hero_section = next(
        section for section in extension.SETTINGS_SECTIONS if section[3] == "HeroWrite"
    )
    exposed_names = [native_name for native_name, _creator in hero_section[5]]
    assert set(exposed_names) == set(expected_settings)

    hero_writer = group.getNode("HeroWrite")
    for native_name, expected_value in expected_settings.items():
        group.getParam(f"hero_{native_name}").set(expected_value)
        hero_writer.getParam(native_name).set(None)

    render_calls = []

    def capture_render(tasks) -> None:
        tasks = list(tasks)
        hero_task = next(task for task in tasks if task[0] is hero_writer)
        assert hero_task[1:] == (1101, 1123, 2)
        assert {
            name: hero_writer.getParam(name).get() for name in exposed_names
        } == expected_settings
        render_calls.append(list(tasks))

    app.render = capture_render
    plugin["onParamChanged"](
        group.getParam(button_name), group, group, app, True
    )

    assert len(render_calls) == 1
    if button_name == "renderHero":
        assert [task[0].script_name for task in render_calls[0]] == ["HeroWrite"]
    else:
        assert "HeroWrite" in [task[0].script_name for task in render_calls[0]]


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
    assert group.getParam("smartWriteUiVersion").visible is False
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


def test_refresh_rehides_current_ui_version_marker(monkeypatch, tmp_path: Path) -> None:
    plugin = _load_plugin_with_extension(monkeypatch)
    project_directory = tmp_path / "show" / "shot" / "comp" / "natron"
    project_directory.mkdir(parents=True)
    app = FakeApp(project_directory)
    group = FakeGroup()
    app.groups.append(group)
    plugin["createInstance"](app, group)
    marker = group.getParam("smartWriteUiVersion")
    assert marker.get() == sys.modules["SmartWriteExt"].SMART_WRITE_UI_VERSION

    marker.setVisible(True)
    plugin["refreshOutputs"](app, group)

    assert marker.visible is False


def test_refresh_preserves_saved_layer_choices_when_writer_menu_is_empty(
    monkeypatch, tmp_path: Path
) -> None:
    plugin = _load_plugin_with_extension(monkeypatch)
    project_directory = tmp_path / "show" / "shot" / "comp" / "natron"
    project_directory.mkdir(parents=True)
    app = FakeApp(project_directory)
    group = FakeGroup()
    app.groups.append(group)
    plugin["createInstance"](app, group)

    saved_options = [
        "uk.co.thefoundry.OfxImagePlaneColour",
        "uk.co.thefoundry.OfxImagePlaneStereoDisparityLeft",
        "uk.co.thefoundry.OfxImagePlaneStereoDisparityRight",
        "uk.co.thefoundry.OfxImagePlaneBackMotionVector",
        "uk.co.thefoundry.OfxImagePlaneForwardMotionVector",
    ]
    layer_choice = group.getParam("exr_outputChannels")
    layer_choice.setOptions(saved_options)
    layer_choice.set(0)
    assert group.getNode("EXRWrite").getParam("outputChannels").getOptions() == []

    plugin["refreshOutputs"](app, group)

    assert layer_choice.getOptions() == saved_options
    assert layer_choice.get() == 0


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

    assert {
        name: group.getNode(name).getPluginID()
        for name in ("EXRWrite", "MP4Write", "MOVWrite", "HeroWrite")
    } == {
        "EXRWrite": "fr.inria.openfx.WriteOIIO",
        "MP4Write": "fr.inria.openfx.WriteFFmpeg",
        "MOVWrite": "fr.inria.openfx.WriteFFmpeg",
        "HeroWrite": "fr.inria.openfx.WriteOIIO",
    }

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
    for checkbox_name, button_name, writer_name in (
        ("exrOutput", "renderEXR", "EXRWrite"),
        ("mp4Output", "renderMP4", "MP4Write"),
        ("movOutput", "renderMOV", "MOVWrite"),
        ("heroOutput", "renderHero", "HeroWrite"),
    ):
        writer_enabled = not group.getNode(writer_name).getParam("disableNode").get()
        assert bool(group.getParam(checkbox_name).get()) is writer_enabled
        assert group.getParam(button_name).enabled is writer_enabled
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
    assert group.getParam("renderEXR").enabled is False
    assert group.getParam("exrSettings").opened is False

    group.getParam("heroOutput").set(False)
    plugin["onParamChanged"](
        group.getParam("heroOutput"), group, group, app, True
    )
    assert group.getNode("HeroWrite").getParam("disableNode").get() is True
    assert group.getParam("renderHero").enabled is False
    group.getParam("heroOutput").set(True)
    plugin["onParamChanged"](
        group.getParam("heroOutput"), group, group, app, True
    )
    assert group.getNode("HeroWrite").getParam("disableNode").get() is False
    assert group.getParam("renderHero").enabled is True


def test_new_writers_use_artist_template_defaults(monkeypatch, tmp_path: Path) -> None:
    plugin = _load_plugin_with_extension(monkeypatch)
    project_directory = tmp_path / "show" / "shot" / "comp" / "natron"
    project_directory.mkdir(parents=True)
    app = FakeApp(project_directory)
    group = FakeGroup()
    app.groups.append(group)
    plugin["createInstance"](app, group)

    extension = sys.modules["SmartWriteExt"]
    exr_choice_options = {
        "outputComponents": ["RGB", "RGBA"],
        "inputPremult": ["opaque", "premult"],
        "ocioInputSpaceIndex": ["linear/Linear", "scene_linear"],
        "ocioOutputSpaceIndex": ["display/sRGB", "linear/Linear"],
        "frameRange": ["union", "project", "manual"],
        "bitDepth": ["auto", "16f", "32f"],
        "compression": ["default", "zip", "dwaa"],
        "partSplitting": ["single", "layers", "views_layers"],
        "viewsSelector": ["All", "Main"],
        "tileSize": ["0", "64"],
    }
    mp4_choice_options = {
        "codec": ["prores_ks", "libx264"],
        "outputComponents": ["RGB", "RGBA"],
        "inputPremult": ["opaque", "premult"],
        "ocioInputSpaceIndex": ["linear/Linear", "scene_linear"],
        "ocioOutputSpaceIndex": ["linear/Linear", "display/nuke_rec709"],
        "frameRange": ["union", "project", "manual"],
        "prefPixelCoding": ["rgb", "yuv422"],
        "prefBitDepth": ["8", "10"],
        "crf": ["crf18", "crf23"],
        "x26xSpeed": ["fast", "medium"],
    }

    for writer_name in ("EXRWrite", "HeroWrite"):
        writer = group.getNode(writer_name)
        for name, options in exr_choice_options.items():
            writer.getParam(name).setOptions(options)
        extension._configure_new_writer(writer_name, writer)
        assert {
            name: writer.getParam(name).get() for name in exr_choice_options
        } == {
            "outputComponents": 1,
            "inputPremult": 1,
            "ocioInputSpaceIndex": 0,
            "ocioOutputSpaceIndex": 1,
            "frameRange": 1,
            "bitDepth": 0,
            "compression": 0,
            "partSplitting": 2,
            "viewsSelector": 0,
            "tileSize": 0,
        }
        assert writer.getParam("quality").get() == 100
        assert writer.getParam("dwaCompressionLevel").get() == 45.0
        assert writer.getParam("outputChannels").get() == 0
        assert writer.getParam("processAllPlanes").get() is False

    mp4_writer = group.getNode("MP4Write")
    for name, options in mp4_choice_options.items():
        mp4_writer.getParam(name).setOptions(options)
    extension._configure_new_writer("MP4Write", mp4_writer)
    assert {
        name: mp4_writer.getParam(name).get() for name in mp4_choice_options
    } == {
        "codec": 1,
        "outputComponents": 1,
        "inputPremult": 1,
        "ocioInputSpaceIndex": 0,
        "ocioOutputSpaceIndex": 1,
        "frameRange": 1,
        "prefPixelCoding": 1,
        "prefBitDepth": 0,
        "crf": 1,
        "x26xSpeed": 1,
    }
    assert mp4_writer.getParam("fps").get() == 24.0
    assert mp4_writer.getParam("bitrateMbps").get() == 185.0
    assert mp4_writer.getParam("gopSize").get() == -1
    assert mp4_writer.getParam("bFrames").get() == -1
    assert mp4_writer.getParam("fastStart").get() is False


def test_refresh_recreates_a_missing_internal_writer(monkeypatch, tmp_path: Path) -> None:
    plugin = _load_plugin_with_extension(monkeypatch)
    project_directory = (
        tmp_path
        / "defect"
        / "s3bishop"
        / "sequences"
        / "ZZZ"
        / "ZZZ_000_0850"
        / "comp"
        / "natron"
    )
    project_directory.mkdir(parents=True)
    app = FakeApp(project_directory)
    group = FakeGroup()
    app.groups.append(group)
    plugin["createInstance"](app, group)

    group.getNode("MP4Write").destroy(False)
    assert group.getNode("MP4Write") is None

    plugin["refreshOutputs"](app, group)

    writer = group.getNode("MP4Write")
    assert writer is not None
    assert writer.getPluginID() == "fr.inria.openfx.WriteFFmpeg"
    assert writer.getParam("filename").get().endswith("_beauty_v001.mp4")
    assert writer.getInput(0) is group.getNode("Input1")


@pytest.mark.parametrize(
    "prefix,writer_name",
    [
        ("exr", "EXRWrite"),
        ("mp4", "MP4Write"),
        ("mov", "MOVWrite"),
        ("hero", "HeroWrite"),
    ],
)
def test_frame_range_gui_hides_project_fields_and_initializes_manual_range(
    monkeypatch,
    tmp_path: Path,
    prefix: str,
    writer_name: str,
) -> None:
    plugin = _load_plugin_with_extension(monkeypatch)
    project_directory = (
        tmp_path
        / prefix
        / "sequences"
        / "ZZZ"
        / "ZZZ_000_0850"
        / "comp"
        / "natron"
    )
    project_directory.mkdir(parents=True)
    app = FakeApp(project_directory)
    app.timeline_bounds = (1001, 1040)
    group = FakeGroup()
    app.groups.append(group)
    plugin["createInstance"](app, group)

    frame_range = group.getParam(f"{prefix}_frameRange")
    first_frame = group.getParam(f"{prefix}_firstFrame")
    last_frame = group.getParam(f"{prefix}_lastFrame")
    writer = group.getNode(writer_name)
    frame_range.setOptions(["union", "project", "manual"])
    writer.getParam("frameRange").setOptions(["union", "project", "manual"])

    frame_range.set(1)
    plugin["onParamChanged"](frame_range, group, group, app, True)
    assert first_frame.visible is False
    assert last_frame.visible is False

    frame_range.set(2)
    plugin["onParamChanged"](frame_range, group, group, app, True)
    assert first_frame.visible is True
    assert last_frame.visible is True
    assert (first_frame.get(), last_frame.get()) == (1001, 1040)
    assert (
        writer.getParam("firstFrame").get(),
        writer.getParam("lastFrame").get(),
    ) == (1001, 1040)


def test_refresh_repairs_zero_manual_frame_range_values(monkeypatch, tmp_path: Path) -> None:
    plugin = _load_plugin_with_extension(monkeypatch)
    project_directory = tmp_path / "show" / "shot" / "comp" / "natron"
    project_directory.mkdir(parents=True)
    app = FakeApp(project_directory)
    app.timeline_bounds = (1101, 1124)
    group = FakeGroup()
    app.groups.append(group)
    plugin["createInstance"](app, group)

    writer = group.getNode("EXRWrite")
    writer.getParam("frameRange").setOptions(["union", "project", "manual"])
    group.getParam("exr_frameRange").setOptions(["union", "project", "manual"])
    group.getParam("exr_frameRange").set(2)
    group.getParam("exr_firstFrame").set(0)
    group.getParam("exr_lastFrame").set(0)

    plugin["refreshOutputs"](app, group)

    assert group.getParam("exr_firstFrame").visible is True
    assert group.getParam("exr_lastFrame").visible is True
    assert group.getParam("exr_firstFrame").get() == 1101
    assert group.getParam("exr_lastFrame").get() == 1124
    assert writer.getParam("firstFrame").get() == 1101
    assert writer.getParam("lastFrame").get() == 1124


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
    expected_hero = "/_hero/BSH_000_0020.####.exr"
    assert first_group.getNode("HeroWrite").getParam("filename").get().endswith(
        expected_hero
    )
    assert second_group.getNode("HeroWrite").getParam("filename").get().endswith(
        expected_hero
    )


def test_video_render_buttons_resync_every_writer_option_before_submit(
    monkeypatch, tmp_path: Path
) -> None:
    plugin = _load_plugin_with_extension(monkeypatch)
    common_values = {
        "outputComponents": 11,
        "inputPremult": 12,
        "ocioInputSpaceIndex": 13,
        "ocioOutputSpaceIndex": 14,
        "frameRange": 15,
        "firstFrame": 101,
        "lastFrame": 202,
        "frameIncr": 3,
        "readBack": True,
    }
    mp4_values = {
        **common_values,
        "codec": 1,
        "fps": 23.976,
        "prefPixelCoding": 21,
        "prefBitDepth": 22,
        "crf": 23,
        "x26xSpeed": 24,
        "bitrateMbps": 42.5,
        "gopSize": 48,
        "bFrames": 4,
        "fastStart": True,
    }
    mov_values = {
        **{
            name: value + 100 if type(value) is int else value
            for name, value in common_values.items()
        },
        "codec": 1,
        "fps": 29.97,
        "prefPixelCoding": 121,
        "prefBitDepth": 122,
        "crf": 123,
        "x26xSpeed": 124,
        "bitrateMbps": 85.0,
        "gopSize": 96,
        "bFrames": 8,
        "fastStart": False,
        "enableAlpha": True,
        "DNxHDCodecProfile": 131,
        "HapFormat": 132,
    }
    writer_values = {
        "MP4Write": ("mp4", mp4_values),
        "MOVWrite": ("mov", mov_values),
    }
    cases = (
        (
            "renderMP4",
            {"mp4Output": True, "movOutput": False},
            ["MP4Write"],
        ),
        (
            "renderMOV",
            {"mp4Output": False, "movOutput": True},
            ["MOVWrite"],
        ),
        (
            "renderAll",
            {"mp4Output": True, "movOutput": True},
            ["MP4Write", "MOVWrite"],
        ),
    )

    for case_index, (button_name, video_enabled, expected_tasks) in enumerate(cases):
        project_directory = (
            tmp_path
            / button_name
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
        app.timeline_bounds = (1101 + case_index, 1124 + case_index)
        group = FakeGroup()
        app.groups.append(group)
        plugin["createInstance"](app, group)
        assert {
            name.removeprefix("mp4_")
            for name in group.params
            if name.startswith("mp4_")
        } == set(mp4_values)
        assert {
            name.removeprefix("mov_")
            for name in group.params
            if name.startswith("mov_")
        } == set(mov_values)

        output_states = {
            "exrOutput": False,
            **video_enabled,
            "heroOutput": False,
        }
        for checkbox_name, enabled in output_states.items():
            checkbox = group.getParam(checkbox_name)
            checkbox.set(enabled)
            plugin["onParamChanged"](checkbox, group, group, app, True)

        expected_filenames = {}
        for writer_name, (proxy_prefix, expected_values) in writer_values.items():
            writer = group.getNode(writer_name)
            expected_filenames[writer_name] = writer.getParam("filename").get()
            for param_name, expected_value in expected_values.items():
                exposed = group.getParam(f"{proxy_prefix}_{param_name}")
                assert exposed is not None
                exposed.set(expected_value)
                writer.getParam(param_name).set("stale")
            writer.getParam("filename").set(f"stale/{writer_name}")
            writer.getParam("disableNode").set("stale")

        snapshots = []

        def capture_render(tasks) -> None:
            tasks = list(tasks)
            snapshots.append(
                {
                    "tasks": [(task[0].script_name, *task[1:]) for task in tasks],
                    "writers": {
                        writer_name: {
                            "filename": group.getNode(writer_name)
                            .getParam("filename")
                            .get(),
                            "disabled": group.getNode(writer_name)
                            .getParam("disableNode")
                            .get(),
                            "settings": {
                                param_name: group.getNode(writer_name)
                                .getParam(param_name)
                                .get()
                                for param_name in expected_values
                            },
                        }
                        for writer_name, (
                            _proxy_prefix,
                            expected_values,
                        ) in writer_values.items()
                    },
                }
            )

        app.render = capture_render
        plugin["onParamChanged"](
            group.getParam(button_name), group, group, app, True
        )

        assert len(snapshots) == 1
        snapshot = snapshots[0]
        assert [task[0] for task in snapshot["tasks"]] == expected_tasks
        assert [task[1:] for task in snapshot["tasks"]] == [
            (
                *app.timeline_bounds,
                writer_values[expected_writer][1]["frameIncr"],
            )
            for expected_writer in expected_tasks
        ]
        assert expected_filenames["MP4Write"].endswith(".mp4")
        assert expected_filenames["MOVWrite"].endswith(".mov")
        for writer_name, (_proxy_prefix, expected_values) in writer_values.items():
            writer_snapshot = snapshot["writers"][writer_name]
            assert writer_snapshot["filename"] == expected_filenames[writer_name]
            checkbox_name = (
                "mp4Output" if writer_name == "MP4Write" else "movOutput"
            )
            assert (
                writer_snapshot["disabled"]
                is not video_enabled[checkbox_name]
            )
            assert writer_snapshot["settings"] == expected_values


@pytest.mark.parametrize(
    "checkbox_name,button_name,writer_name,prefix,render_all",
    [
        ("exrOutput", "renderEXR", "EXRWrite", "exr", False),
        ("exrOutput", "renderAll", "EXRWrite", "exr", True),
        ("mp4Output", "renderMP4", "MP4Write", "mp4", False),
        ("mp4Output", "renderAll", "MP4Write", "mp4", True),
        ("movOutput", "renderMOV", "MOVWrite", "mov", False),
        ("movOutput", "renderAll", "MOVWrite", "mov", True),
        ("heroOutput", "renderHero", "HeroWrite", "hero", False),
        ("heroOutput", "renderAll", "HeroWrite", "hero", True),
    ],
)
def test_every_exposed_field_reaches_writer_before_every_render_submission(
    monkeypatch,
    tmp_path: Path,
    checkbox_name: str,
    button_name: str,
    writer_name: str,
    prefix: str,
    render_all: bool,
) -> None:
    """Contract test for all 77 settings through individual and Render All paths."""

    plugin = _load_plugin_with_extension(monkeypatch)
    extension = sys.modules["SmartWriteExt"]
    project_directory = (
        tmp_path
        / (prefix + ("_all" if render_all else "_single"))
        / "sequences"
        / "TST"
        / "TST_000_0001"
        / "comp"
        / "natron"
    )
    project_directory.mkdir(parents=True)
    app = FakeApp(project_directory)
    app.timeline_bounds = (1001, 1040)
    group = FakeGroup()
    app.groups.append(group)
    plugin["createInstance"](app, group)

    for candidate, _writer, _path in extension.WRITER_SPECS:
        checkbox = group.getParam(candidate)
        checkbox.set(candidate == checkbox_name)
        plugin["onParamChanged"](checkbox, group, group, app, True)

    section = next(
        candidate
        for candidate in extension.SETTINGS_SECTIONS
        if candidate[3] == writer_name
    )
    writer = group.getNode(writer_name)
    expected = {}
    for index, (native_name, creator_name) in enumerate(section[5], start=1):
        exposed = group.getParam(f"{prefix}_{native_name}")
        native = writer.getParam(native_name)
        assert exposed is not None, f"missing exposed field {prefix}_{native_name}"
        assert native is not None, f"missing native field {writer_name}.{native_name}"

        if creator_name == "createChoiceParam":
            options = (
                ["union", "project", "manual"]
                if native_name == "frameRange"
                else ["choice0", "choice1", "choice2"]
            )
            exposed.setOptions(options)
            native.setOptions(options)
            value = 2 if native_name == "frameRange" else 1
        elif creator_name == "createBooleanParam":
            value = not bool(exposed.get())
        elif creator_name == "createDoubleParam":
            value = 40.25 + index
        else:
            special_ints = {
                "firstFrame": 1011,
                "lastFrame": 1037,
                "frameIncr": 3,
            }
            value = special_ints.get(native_name, 30 + index)

        exposed.set(value)
        plugin["onParamChanged"](exposed, group, group, app, True)
        expected[native_name] = exposed.get()
        assert native.get() == expected[native_name], (
            f"immediate sync failed for {writer_name}.{native_name}"
        )

    # Prove the button path performs a final full resync, rather than merely
    # inheriting the values from individual field-change callbacks.
    for native_name, expected_value in expected.items():
        native = writer.getParam(native_name)
        if isinstance(expected_value, bool):
            poisoned = not expected_value
        elif native_name == "frameRange":
            poisoned = 0
        elif isinstance(expected_value, float):
            poisoned = expected_value + 100.0
        else:
            poisoned = expected_value + 100
        native.set(poisoned)

    submissions = []

    def capture_submission(_app, tasks) -> None:
        submissions.append(list(tasks))

    monkeypatch.setattr(extension, "_submit_render_tasks", capture_submission)
    plugin["onParamChanged"](
        group.getParam(button_name), group, group, app, True
    )

    assert len(submissions) == 1
    assert len(submissions[0]) == 1
    task = submissions[0][0]
    assert task[0] is writer
    assert task[1:] == (1011, 1037, 3)
    assert {
        native_name: writer.getParam(native_name).get()
        for native_name in expected
    } == expected
