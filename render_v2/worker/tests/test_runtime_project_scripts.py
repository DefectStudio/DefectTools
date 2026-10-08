"""Exercise project callback policy without registering an Unreal executor."""

import ast
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch


RUNTIME_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "unreal/RenderWorkerRuntime/Content/Python/render_worker_runtime_executor.py"
)


def _load_runtime_functions():
    """Load actual runtime helpers, excluding the Unreal UClass declaration."""
    source = ast.parse(RUNTIME_SOURCE.read_text(encoding="utf-8"))
    functions = ast.Module(
        body=[
            node
            for node in source.body
            if isinstance(
                node,
                (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign, ast.FunctionDef),
            )
        ],
        type_ignores=[],
    )
    namespace = {"__file__": str(RUNTIME_SOURCE)}
    exec(compile(functions, str(RUNTIME_SOURCE), "exec"), namespace)
    return namespace


class FakeScriptNode:
    def __init__(self, name, properties=None, disabled=False):
        self.path = "/Game/TestGraph." + name
        self.properties = dict(properties or {})
        self.disabled = disabled
        self.disabled_writes = []
        self.property_reads = []
        self.property_writes = []

    def get_path_name(self):
        return self.path

    def get_editor_property(self, name):
        self.property_reads.append(name)
        if name not in self.properties:
            raise AttributeError(name)
        return self.properties[name]

    def set_editor_property(self, name, value):
        self.properties[name] = value
        self.property_writes.append((name, value))

    def set_disabled(self, disabled):
        self.disabled = disabled
        self.disabled_writes.append(disabled)


class FakeGraph:
    def __init__(self, nodes=None, subgraphs=None, branches=None):
        self.branches = branches if branches is not None else {"Globals": list(nodes or [])}
        self.subgraphs = list(subgraphs or [])
        self.subgraph_reads = 0
        self.branch_reads = 0
        self.traversals = []
        self.create_flattened_graph = Mock(
            side_effect=AssertionError("Callback policy must not evaluate graph conditions")
        )

    def get_all_contained_subgraphs(self):
        self.subgraph_reads += 1
        return self.subgraphs

    def get_branch_names(self):
        self.branch_reads += 1
        return list(self.branches)

    def get_nodes_for_branch(self, node_type, branch):
        self.traversals.append(branch)
        return self.branches[branch]


class RuntimeProjectScriptsTests(unittest.TestCase):
    def setUp(self):
        self.logs = []
        self.warnings = []
        self.unreal = types.ModuleType("unreal")
        self.unreal.MovieGraphExecuteScriptNode = FakeScriptNode
        self.unreal.load_class = Mock(
            side_effect=AssertionError("Callback policy must not resolve project classes")
        )
        self.unreal.log = self.logs.append
        self.unreal.log_warning = self.warnings.append
        self.unreal.log_error = self.warnings.append
        self.enterContext(patch.dict(sys.modules, {"unreal": self.unreal}))
        self.runtime = _load_runtime_functions()

    def configure(self, graph, job=None):
        return self.runtime["_configure_project_scripts"](
            graph, {} if job is None else job
        )

    def assert_node_untouched(self, node):
        self.assertEqual([], node.disabled_writes)
        self.assertEqual([], node.property_reads)
        self.assertEqual([], node.property_writes)

    def assert_graph_untouched(self, graph):
        self.assertEqual(0, graph.subgraph_reads)
        self.assertEqual(0, graph.branch_reads)
        self.assertEqual([], graph.traversals)
        graph.create_flattened_graph.assert_not_called()

    def test_job_without_isolation_flag_preserves_any_project_callback(self):
        node = FakeScriptNode("StudioPostRender", {"editor_only_script": "/Game/Studio.PostRender"})
        graph = FakeGraph([node])
        self.configure(graph)
        self.assertFalse(node.disabled)
        self.assert_node_untouched(node)
        self.assert_graph_untouched(graph)
        self.unreal.load_class.assert_not_called()

    def test_false_isolation_flag_preserves_copy_and_reporting_callbacks(self):
        copy = FakeScriptNode("CopyOutputs", {"editor_only_script": "MRGAllRenderScripts"})
        report = FakeScriptNode("ClickUpReporting", {"editor_only_script": "MRGPostRenderScripts"})
        graph = FakeGraph([copy, report])
        self.configure(graph, {"disable_project_scripts": False})
        for node in (copy, report):
            self.assertFalse(node.disabled)
            self.assert_node_untouched(node)
        self.assert_graph_untouched(graph)
        self.assertEqual([], self.warnings)

    def test_allowed_callbacks_keep_artist_selected_modes_and_class_slots(self):
        for mode in ("EDITOR_ONLY", "EDITOR_AND_RUNTIME"):
            with self.subTest(mode=mode):
                properties = {
                    "mode": mode,
                    "editor_only_script": "/Game/Editor.Callback",
                    "editor_and_runtime_script": "/Game/Runtime.Callback",
                    "script": "/Game/Legacy.Callback",
                    "b_override_mode": False,
                    "b_override_editor_only_script": True,
                }
                node = FakeScriptNode(mode, properties)
                self.configure(FakeGraph([node]), {"disable_project_scripts": False})
                self.assertEqual(properties, node.properties)
                self.assert_node_untouched(node)

    def test_missing_callback_dependency_does_not_invoke_a_worker_specific_import(self):
        node = FakeScriptNode("StudioOnly", {"editor_only_script": "/Game/Other.Callback"})
        graph = FakeGraph([node])
        with patch.dict(sys.modules, {"mrg_callbacks_allrenders": None}):
            self.configure(graph, {"disable_project_scripts": False})
        self.assertFalse(node.disabled)
        self.assert_node_untouched(node)
        self.assertEqual([], self.warnings)
        self.unreal.load_class.assert_not_called()

    def test_missing_or_unresolved_classes_remain_for_unreal_to_evaluate(self):
        nodes = [
            FakeScriptNode("MissingClass"),
            FakeScriptNode("UnresolvedClass", {"editor_only_script": "/Engine/PythonTypes.DoesNotExist"}),
        ]
        self.configure(FakeGraph(nodes), {"disable_project_scripts": False})
        for node in nodes:
            self.assertFalse(node.disabled)
            self.assert_node_untouched(node)
        self.unreal.load_class.assert_not_called()

    def test_artist_disabled_callback_stays_disabled_when_scripts_allowed(self):
        node = FakeScriptNode("IntentionallyDisabled", disabled=True)
        self.configure(FakeGraph([node]), {"disable_project_scripts": False})
        self.assertTrue(node.disabled)
        self.assert_node_untouched(node)

    def test_allowed_subgraphs_and_graph_conditions_are_not_traversed(self):
        node = FakeScriptNode("ConditionalCallback", {"condition": False})
        subgraph = FakeGraph([node])
        graph = FakeGraph(branches={"EnabledBranch": [], "DisabledBranch": [node]}, subgraphs=[subgraph])
        before_branches = {name: list(nodes) for name, nodes in graph.branches.items()}
        self.configure(graph, {"disable_project_scripts": False})
        self.assertEqual(before_branches, graph.branches)
        self.assertEqual({"condition": False}, node.properties)
        self.assert_node_untouched(node)
        self.assert_graph_untouched(graph)
        self.assert_graph_untouched(subgraph)

    def test_explicit_isolation_disables_all_classes_including_copy_callback(self):
        nodes = [
            FakeScriptNode("CopyOutputs", {"editor_only_script": "MRGAllRenderScripts"}),
            FakeScriptNode("Reporting", {"editor_and_runtime_script": "MRGPostRenderScripts"}),
            FakeScriptNode("Other"),
        ]
        self.configure(FakeGraph(nodes), {"disable_project_scripts": True})
        for node in nodes:
            self.assertTrue(node.disabled)
            self.assertEqual([True], node.disabled_writes)
            self.assertEqual([], node.property_reads)
            self.assertEqual([], node.property_writes)
        self.unreal.load_class.assert_not_called()

    def test_explicit_isolation_processes_repeated_subgraphs_and_nodes_once(self):
        root_node = FakeScriptNode("RootCallback")
        sub_node = FakeScriptNode("SubgraphCallback")
        subgraph = FakeGraph(branches={"Globals": [sub_node], "EXR": [sub_node]})
        graph = FakeGraph(
            branches={"Globals": [root_node, sub_node], "MP4": [root_node]},
            subgraphs=[subgraph, subgraph],
        )
        self.configure(graph, {"disable_project_scripts": True})
        self.assertEqual([True], root_node.disabled_writes)
        self.assertEqual([True], sub_node.disabled_writes)
        self.assertTrue(root_node.disabled)
        self.assertTrue(sub_node.disabled)
        graph.create_flattened_graph.assert_not_called()
        subgraph.create_flattened_graph.assert_not_called()

    def test_explicit_isolation_tolerates_missing_callback_dependencies(self):
        node = FakeScriptNode("UnavailableCallback")
        with patch.dict(sys.modules, {"mrg_callbacks_allrenders": None}):
            self.configure(FakeGraph([node]), {"disable_project_scripts": True})
        self.assertTrue(node.disabled)
        self.unreal.load_class.assert_not_called()
        self.assertEqual([], self.warnings)

    def test_pipeline_builder_preserves_project_callbacks_and_applies_output_overrides(self):
        node = FakeScriptNode("StudioPostRender", {"editor_only_script": "/Game/Studio.PostRender"})
        graph = FakeGraph([node])
        pipeline_job = Mock()
        pipeline_job.get_graph_preset.return_value = graph
        queue = Mock()
        queue.allocate_new_job.return_value = pipeline_job
        self.unreal.new_object = Mock(return_value=queue)
        self.unreal.MoviePipelineQueue = object()
        self.unreal.MoviePipelineExecutorJob = object()
        self.unreal.SoftObjectPath = lambda value: value
        executor = types.SimpleNamespace()
        job = {
            "job_id": "job-123",
            "shot_name": "SHOT_001",
            "sequence": "/Game/TestSequence",
            "level": "/Game/TestMap",
            "render_config": "/Game/TestGraph",
            "disable_project_scripts": False,
            "graph_variable_overrides": {"OutputDirectory": {"enabled": True, "serialized_value": "scratch/output"}},
        }
        configure = Mock(wraps=self.runtime["_configure_project_scripts"])
        overrides = Mock()
        ordered_calls = Mock()
        ordered_calls.attach_mock(configure, "configure")
        ordered_calls.attach_mock(pipeline_job.set_graph_preset, "assign_graph")
        ordered_calls.attach_mock(overrides, "overrides")
        with patch.dict(
            self.runtime,
            {
                "_load_unreal_object": Mock(return_value=graph),
                "_configure_project_scripts": configure,
                "_apply_graph_overrides": overrides,
            },
        ):
            result = self.runtime["_build_pipeline_job"](executor, job)
        self.assertIs(result, pipeline_job)
        configure.assert_called_once_with(graph, job)
        pipeline_job.set_graph_preset.assert_called_once_with(graph)
        overrides.assert_called_once_with(pipeline_job, graph, job)
        self.assertEqual(
            ["configure", "assign_graph", "overrides"],
            [item[0] for item in ordered_calls.mock_calls],
        )
        self.assertFalse(node.disabled)
        self.assert_node_untouched(node)
        self.assert_graph_untouched(graph)
        self.unreal.load_class.assert_not_called()


    def test_unreal_preparation_generates_a_job_with_project_callbacks_allowed(self):
        preparation_source = RUNTIME_SOURCE.parents[3] / "prepare_project_job.py"
        source = ast.parse(preparation_source.read_text(encoding="utf-8"))
        functions = ast.Module(
            body=[node for node in source.body if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef))],
            type_ignores=[],
        )
        namespace = {"__file__": str(preparation_source)}
        exec(compile(functions, str(preparation_source), "exec"), namespace)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            sequence = types.SimpleNamespace(
                get_playback_start=lambda: 1,
                get_playback_end=lambda: 11,
            )
            graph = FakeGraph()
            graph.get_variables = lambda: [
                types.SimpleNamespace(get_member_name=lambda: "OutputDirectory"),
                types.SimpleNamespace(get_member_name=lambda: "FileNameFormat"),
            ]
            self.unreal.LevelSequence = types.SimpleNamespace
            self.unreal.MovieGraphConfig = FakeGraph
            self.unreal.Paths = types.SimpleNamespace(
                project_dir=lambda: str(root),
                convert_relative_path_to_full=lambda value: value,
            )
            self.unreal.DirectoryPath = lambda value: types.SimpleNamespace(export_text=lambda: value)
            self.unreal.load_asset = Mock(side_effect=[sequence, graph])
            request = {
                "checkout": str(root),
                "shot": "SHOT_001",
                "render": {
                    "sequence": "/Game/{shot}",
                    "graph": "/Game/RenderGraph",
                    "level": "/Game/Map",
                },
                "job_id": "job-123",
                "project_name": "Test Project",
                "project_id": "TestProject",
                "uproject": str(root / "Test.uproject"),
                "output_directory": str(root / "output"),
                "run_root": str(root),
                "job_path": str(root / "job.json"),
                "commit": "a" * 40,
            }
            result = namespace["prepare"](request)
            job = json.loads(Path(request["job_path"]).read_text(encoding="utf-8"))
        self.assertTrue(result["success"])
        self.assertIs(False, job["disable_project_scripts"])
        self.assertEqual(10, job["frame_count"])
        self.assert_graph_untouched(graph)

if __name__ == "__main__":
    unittest.main()
