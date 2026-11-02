"""Exercise the real Unreal queue script with a small, read-only Unreal stand-in."""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from types import ModuleType
import unittest
from unittest import mock


_PLUGIN_PYTHON = (
    Path(__file__).resolve().parents[1]
    / "Unreal/DefectToolsDev/Plugins/QuickWidgetTools/Content/Python"
)
_SHOT = "DEV_000_0010"
_PREFIX = f"{_SHOT}_beauty"


class _DirectoryPath:
    def __init__(self, path: str = "") -> None:
        self.path = str(path)

    def export_text(self) -> str:
        return f"(Path={json.dumps(self.path)})"

    def import_text(self, content: str) -> bool:
        match = re.fullmatch(r"\(Path=(.*)\)", str(content))
        if match is None:
            return False
        try:
            self.path = json.loads(match.group(1))
        except (ValueError, TypeError):
            return False
        return isinstance(self.path, str)

    def get_editor_property(self, name: str):
        if name != "path":
            raise AttributeError(name)
        return self.path


class _Variable:
    def __init__(self, name: str, value: str) -> None:
        self.name = name
        self.value = value

    def get_member_name(self) -> str:
        return self.name

    def get_value_serialized_string(self) -> str:
        return self.value

    def get_value_string(self) -> str:
        return self.value


class _Graph:
    def __init__(self, path: str, defaults: dict[str, str]) -> None:
        self.path = path
        self.variables = {
            name: _Variable(name, value) for name, value in defaults.items()
        }

    def get_path_name(self) -> str:
        return self.path

    def get_variable_by_name(self, name: str):
        return self.variables.get(name)

    def get_variables(self):
        return list(self.variables.values())


class _Assignments:
    def __init__(
        self,
        graph: _Graph,
        values: dict[str, str],
        *,
        enabled: bool = True,
        state_shape: str = "bool",
    ) -> None:
        self.graph = graph
        self.values = dict(values)
        self.enabled = enabled
        self.state_shape = state_shape

    def get_graph_config(self):
        return self.graph

    def get_variable_assignment_enable_state(self, variable: _Variable):
        present = variable.name in self.values
        if self.state_shape == "tuple":
            return present, self.enabled if present else False
        return self.enabled if present else None

    def get_value_serialized_string(self, variable: _Variable) -> str:
        return self.values.get(variable.name, "")

    def get_value_string(self, variable: _Variable):
        return self.values.get(variable.name)

    def update_graph_variable_overrides(self):
        raise AssertionError("Reading queued versions must not refresh overrides")

    def set_variable_assignment_enable_state(self, *args):
        raise AssertionError("Reading queued versions must not change overrides")

    def set_value_serialized_string(self, *args):
        raise AssertionError("Reading queued versions must not change values")


class _Job:
    def __init__(
        self,
        graph: _Graph,
        assignments: list[_Assignments],
        *,
        enabled: bool = True,
    ) -> None:
        self.graph = graph
        self.assignments = assignments
        self.enabled = enabled
        self.job_name = _SHOT

    def get_graph_preset(self):
        return self.graph

    def is_using_graph_configuration(self) -> bool:
        return True

    def get_editor_property(self, name: str):
        return {
            "graph_variable_assignments": self.assignments,
            "job_name": self.job_name,
            "enabled": self.enabled,
        }[name]

    def get_or_create_variable_overrides(self, *args):
        raise AssertionError("Reading queued versions must not create overrides")

    def get_configuration(self):
        raise AssertionError("Graph reservations must not create legacy settings")


class _Queue:
    def __init__(self) -> None:
        self.jobs: list[_Job] = []
        self.read_error: Exception | None = None

    def get_jobs(self):
        if self.read_error is not None:
            raise self.read_error
        return list(self.jobs)


class _QueueSubsystem:
    def __init__(self, queue: _Queue) -> None:
        self.queue = queue

    def get_queue(self):
        return self.queue


def _load_actual_script():
    """Import both real modules without leaking a fake Unreal into other tests."""
    fake_unreal = ModuleType("unreal")
    fake_unreal.DirectoryPath = _DirectoryPath
    fake_unreal.MoviePipelineQueueSubsystem = _QueueSubsystem
    fake_unreal.log = lambda *args: None
    fake_unreal.log_warning = lambda *args: None
    fake_unreal.log_error = lambda *args: None
    fake_unreal.get_editor_subsystem = mock.Mock()

    with mock.patch.dict(sys.modules, {"unreal": fake_unreal}):
        sys.modules.pop("add_to_render_queue", None)
        sys.modules.pop("add_to_render_queue_impl", None)
        with mock.patch.object(sys, "path", [str(_PLUGIN_PYTHON), *sys.path]):
            script = importlib.import_module("add_to_render_queue")
    return script, fake_unreal


class UnrealRenderQueueVersionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script, cls.unreal = _load_actual_script()

    def setUp(self) -> None:
        # tempfile deliberately follows TEMP/TMP supplied by the test runner.
        self.temp = tempfile.TemporaryDirectory(prefix="unreal-render-versions-")
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name) / "output"
        self.parent.mkdir()
        self.queue = _Queue()
        self.unreal.get_editor_subsystem.reset_mock()
        self.unreal.get_editor_subsystem.side_effect = None
        self.unreal.get_editor_subsystem.return_value = _QueueSubsystem(self.queue)

    def _values(
        self,
        version: int,
        *,
        parent: Path | str | None = None,
        prefix: str = _PREFIX,
        exr: bool = True,
        mp4: bool = True,
    ) -> dict[str, str]:
        stem = f"{prefix}_v{version:03d}"
        values = {
            "OutputDirectory": _DirectoryPath(
                str(self.parent if parent is None else parent)
            ).export_text(),
        }
        if exr:
            values["FileNameFormat"] = f"{stem}/{stem}.{{frame_number}}"
        if mp4:
            values["MP4FileNameFormat"] = stem
        return values

    def _job(
        self,
        version: int,
        *,
        parent: Path | str | None = None,
        prefix: str = _PREFIX,
        graph_path: str = "/Game/Render/beauty_HD.beauty_HD",
        exr: bool = True,
        mp4: bool = True,
        enabled: bool = True,
        state_shape: str = "bool",
    ) -> _Job:
        values = self._values(version, parent=parent, prefix=prefix, exr=exr, mp4=mp4)
        graph = _Graph(graph_path, {name: "" for name in values})
        return _Job(
            graph,
            [_Assignments(graph, values, state_shape=state_shape)],
            enabled=enabled,
        )

    def _disk_exr(self, version: int, prefix: str = _PREFIX) -> None:
        (self.parent / f"{prefix}_v{version:03d}").mkdir()

    def _disk_mp4(self, version: int, prefix: str = _PREFIX) -> None:
        (self.parent / f"{prefix}_v{version:03d}.mp4").write_bytes(b"test")

    def _next(self, parent: Path | str | None = None) -> int:
        return self.script._find_next_render_version_number(
            str(self.parent if parent is None else parent), _PREFIX
        )

    def _queued(self) -> set[int]:
        return set(self.script._get_queued_render_versions(str(self.parent), _PREFIX))

    def test_disk_one_and_queue_two_allocate_three_then_four(self) -> None:
        self._disk_exr(1)
        self.queue.jobs.append(self._job(2))
        self.assertEqual(3, self._next())
        self.queue.jobs.append(self._job(3))
        self.assertEqual(4, self._next())

    def test_disk_five_allocates_six_then_seven(self) -> None:
        self._disk_mp4(5)
        self.assertEqual(6, self._next())
        self.queue.jobs.append(self._job(6))
        self.assertEqual(7, self._next())

    def test_queue_versions_count_when_disk_parent_does_not_exist(self) -> None:
        missing_parent = self.parent / "not-created"
        self.queue.jobs.append(self._job(4, parent=missing_parent))
        self.assertEqual(5, self._next(missing_parent))
        self.assertFalse(missing_parent.exists())

    def test_exr_only_and_mp4_only_graphs_reserve_versions(self) -> None:
        self.queue.jobs.extend(
            [self._job(3, exr=True, mp4=False), self._job(5, exr=False, mp4=True)]
        )
        self.assertEqual({3, 5}, self._queued())
        self.assertEqual(6, self._next())

    def test_other_output_roots_and_render_prefixes_do_not_leak(self) -> None:
        self.queue.jobs.extend(
            [
                self._job(2),
                self._job(90, parent=self.parent / "other-root"),
                self._job(91, prefix=f"{_SHOT}_matte"),
                self._job(92, prefix="DEV_000_0020_beauty"),
            ]
        )
        self.assertEqual({2}, self._queued())
        self.assertEqual(3, self._next())

    def test_disabled_overrides_use_graph_defaults_for_both_state_shapes(self) -> None:
        for shape in ("bool", "tuple"):
            with self.subTest(state_shape=shape):
                graph = _Graph("/Game/Render/beauty.beauty", self._values(3))
                overrides = _Assignments(
                    graph,
                    self._values(99, parent=self.parent / "wrong-root"),
                    enabled=False,
                    state_shape=shape,
                )
                self.queue.jobs[:] = [_Job(graph, [overrides])]
                self.assertEqual({3}, self._queued())

    def test_enabled_tuple_state_reads_override_values(self) -> None:
        self.queue.jobs.append(self._job(7, state_shape="tuple"))
        self.assertEqual({7}, self._queued())

    def test_disabled_jobs_still_reserve_and_removed_jobs_release(self) -> None:
        self.queue.jobs.append(self._job(4, enabled=False))
        self.assertEqual(5, self._next())
        self.queue.jobs.clear()
        self.assertEqual(1, self._next())

    def test_versions_cross_the_three_digit_boundary(self) -> None:
        self._disk_exr(999)
        self.assertEqual(1000, self._next())
        self.queue.jobs.append(self._job(1000))
        self.assertEqual(1001, self._next())

    def test_presets_sharing_the_physical_render_stem_share_versions(self) -> None:
        self.queue.jobs.extend(
            [
                self._job(2, graph_path="/Game/Render/beauty_HD.beauty_HD"),
                self._job(5, graph_path="/Game/Render/beauty_4K.beauty_4K"),
            ]
        )
        self.assertEqual(6, self._next())

    def test_unrelated_assignment_container_cannot_override_primary_graph(self) -> None:
        job = self._job(3)
        unrelated = _Graph("/Game/Render/matte.matte", self._values(88))
        job.assignments.insert(0, _Assignments(unrelated, self._values(88)))
        self.queue.jobs.append(job)
        self.assertEqual({3}, self._queued())

    def test_queue_reads_leave_existing_jobs_and_values_unchanged(self) -> None:
        job = self._job(3)
        self.queue.jobs.append(job)
        original_values = dict(job.assignments[0].values)
        original_defaults = {name: var.value for name, var in job.graph.variables.items()}
        self.assertEqual(4, self._next())
        self.assertEqual([job], self.queue.jobs)
        self.assertEqual(original_values, job.assignments[0].values)
        self.assertEqual(
            original_defaults,
            {name: var.value for name, var in job.graph.variables.items()},
        )

    def test_queue_read_failure_stops_version_allocation(self) -> None:
        self._disk_exr(1)
        self.queue.read_error = RuntimeError("Queue snapshot failed")
        with self.assertRaises((RuntimeError, OSError, ValueError)):
            self._next()

    def test_queue_subsystem_failure_stops_version_allocation(self) -> None:
        self.unreal.get_editor_subsystem.side_effect = RuntimeError("Unreal unavailable")
        with self.assertRaises((RuntimeError, OSError, ValueError)):
            self._next()

    @unittest.skipUnless(os.name == "nt", "Windows path identity")
    def test_windows_case_separators_and_trailing_slash_share_namespace(self) -> None:
        equivalent_parent = str(self.parent).upper().replace("\\", "/") + "/"
        self.queue.jobs.append(self._job(3, parent=equivalent_parent))
        self.assertEqual({3}, self._queued())


if __name__ == "__main__":
    unittest.main()
