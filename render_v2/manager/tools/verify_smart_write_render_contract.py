from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


WRITER_SENTINEL = "CODEX_SMARTWRITE_CONTRACT_DO_NOT_RENDER"
COMPLETE_MARKER = "CODEX_SMARTWRITE_RENDER_CONTRACT_COMPLETE"


ONLOAD_SOURCE = r'''import SmartWriteExt


def find_smart_writes(container):
    found = []
    for candidate in container.getChildren():
        if candidate.getPluginID() == SmartWriteExt.PLUGIN_ID:
            found.append(candidate)
        found.extend(find_smart_writes(candidate))
    return found


def value_for(exposed, native_name, creator_name, index):
    if creator_name == "createChoiceParam":
        options = [str(option).casefold() for option in exposed.getOptions()]
        if native_name == "frameRange":
            if "manual" not in options:
                raise RuntimeError("Frame Range has no Manual option")
            return options.index("manual")
        if not options:
            return exposed.get()
        return (int(exposed.get()) + 1) % len(options)
    if creator_name == "createBooleanParam":
        return not bool(exposed.get())
    if native_name == "firstFrame":
        return 1002
    if native_name == "lastFrame":
        return 1006
    if native_name == "frameIncr":
        return 2
    if creator_name == "createDoubleParam":
        safe_doubles = {
            "dwaCompressionLevel": 35.5,
            "fps": 25.0,
            "bitrateMbps": 50.0,
        }
        return safe_doubles.get(native_name, float(exposed.get()) + 1.25)
    safe_ints = {
        "quality": 87,
        "gopSize": 12,
        "bFrames": 2,
    }
    if native_name in safe_ints:
        return safe_ints[native_name]
    return int(exposed.get()) + index + 1


def poison(native, creator_name):
    current = native.get()
    if creator_name == "createChoiceParam":
        options = list(native.getOptions())
        if len(options) > 1:
            native.set((int(current) + 1) % len(options))
    elif creator_name == "createBooleanParam":
        native.set(not bool(current))
    elif creator_name == "createDoubleParam":
        native.set(float(current) + 10.0)
    else:
        native.set(int(current) + 10)


SmartWriteExt.afterProjectLoaded(app)
nodes = find_smart_writes(app)
if len(nodes) != 1:
    raise RuntimeError("Expected one SmartWrite node, found {0}".format(len(nodes)))
node = nodes[0]

submitted = []


def capture_submission(_app, tasks):
    submitted.append(list(tasks))


SmartWriteExt._submit_render_tasks = capture_submission
button_by_checkbox = {
    checkbox: button
    for button, _label, checkbox in SmartWriteExt.RENDER_BUTTON_SPECS
}
verified_fields = 0
verified_submissions = 0

for section in SmartWriteExt.SETTINGS_SECTIONS:
    checkbox_name = section[0]
    writer_name = section[3]
    prefix = section[4]
    setting_specs = section[5]
    for render_all in (False, True):
        for candidate, _writer_name, _path in SmartWriteExt.WRITER_SPECS:
            checkbox = node.getParam(candidate)
            checkbox.set(candidate == checkbox_name)
            SmartWriteExt.onParamChanged(checkbox, node, node, app, True)

        writer = SmartWriteExt._active_writers(node).get(writer_name) or node.getNode(writer_name)
        if writer is None:
            raise RuntimeError("Missing writer: " + writer_name)
        baseline = {
            native_name: node.getParam("{0}_{1}".format(prefix, native_name)).get()
            for native_name, _creator_name in setting_specs
        }
        for index, (native_name, creator_name) in enumerate(setting_specs):
            # Restore a coherent writer configuration before independently
            # exercising this one field.
            for baseline_name, _baseline_creator in setting_specs:
                baseline_exposed = node.getParam(
                    "{0}_{1}".format(prefix, baseline_name)
                )
                baseline_exposed.set(baseline[baseline_name])
                SmartWriteExt.onParamChanged(
                    baseline_exposed, node, node, app, True
                )

            frame_range = node.getParam("{0}_frameRange".format(prefix))
            frame_options = [
                str(option).casefold() for option in frame_range.getOptions()
            ]
            if "manual" not in frame_options:
                raise RuntimeError(prefix + " Frame Range has no Manual option")
            manual_values = (
                ("frameRange", frame_options.index("manual")),
                ("firstFrame", 1002),
                ("lastFrame", 1006),
                ("frameIncr", 2),
            )
            for range_name, range_value in manual_values:
                range_exposed = node.getParam(
                    "{0}_{1}".format(prefix, range_name)
                )
                range_exposed.set(range_value)
                SmartWriteExt.onParamChanged(
                    range_exposed, node, node, app, True
                )

            writer = SmartWriteExt._active_writers(node).get(writer_name) or node.getNode(writer_name)
            exposed = node.getParam("{0}_{1}".format(prefix, native_name))
            native = writer.getParam(native_name)
            if exposed is None or native is None:
                raise RuntimeError(
                    "Missing field: {0}.{1}".format(writer_name, native_name)
                )
            exposed.set(value_for(exposed, native_name, creator_name, index))
            SmartWriteExt.onParamChanged(exposed, node, node, app, True)
            expected = exposed.get()
            if native.get() != expected:
                raise RuntimeError(
                    "Immediate sync failed: {0}.{1}, expected {2!r}, got {3!r}".format(
                        writer_name,
                        native_name,
                        expected,
                        native.get(),
                    )
                )
            poison(writer.getParam(native_name), creator_name)

            submitted[:] = []
            button_name = "renderAll" if render_all else button_by_checkbox[checkbox_name]
            SmartWriteExt.onParamChanged(
                node.getParam(button_name), node, node, app, True
            )
            if len(submitted) != 1 or len(submitted[0]) != 1:
                raise RuntimeError(
                    "{0}/{1} submitted unexpected tasks: {2}".format(
                        button_name, native_name, submitted
                    )
                )
            task = submitted[0][0]
            if task[0].getScriptName() != writer_name:
                raise RuntimeError(
                    "{0}/{1} submitted {2}, expected {3}".format(
                        button_name,
                        native_name,
                        task[0].getScriptName(),
                        writer_name,
                    )
                )
            expected_task = (
                int(node.getParam("{0}_firstFrame".format(prefix)).get()),
                int(node.getParam("{0}_lastFrame".format(prefix)).get()),
                max(1, int(node.getParam("{0}_frameIncr".format(prefix)).get())),
            )
            if tuple(task[1:]) != expected_task:
                raise RuntimeError(
                    "{0}/{1} ignored manual range: expected {2}, got {3}".format(
                        button_name, native_name, expected_task, task[1:]
                    )
                )
            actual = task[0].getParam(native_name).get()
            if actual != expected:
                try:
                    exposed_options = [str(option) for option in exposed.getOptions()]
                except Exception:
                    exposed_options = []
                try:
                    native_options = [str(option) for option in task[0].getParam(native_name).getOptions()]
                except Exception:
                    native_options = []
                raise RuntimeError(
                    "Final sync failed: {0}.{1}, expected {2!r}, got {3!r}, "
                    "exposed={4!r}, exposed_options={5!r}, native_options={6!r}".format(
                        writer_name,
                        native_name,
                        expected,
                        actual,
                        exposed.get(),
                        exposed_options,
                        native_options,
                    )
                )
            verified_fields += 1
            verified_submissions += 1
        print(
            "CODEX_SMARTWRITE_CONTRACT_OK|{0}|{1}|{2}".format(
                writer_name, button_name, len(setting_specs)
            )
        )

print(
    "CODEX_SMARTWRITE_RENDER_CONTRACT_COMPLETE|submissions={0}|field_checks={1}".format(
        verified_submissions, verified_fields
    )
)
'''


def verify_render_contract(project: Path, renderer: Path, plugin_directory: Path) -> str:
    project = project.resolve()
    renderer = renderer.resolve()
    plugin_directory = plugin_directory.resolve()
    if not project.is_file():
        raise FileNotFoundError(project)
    if not renderer.is_file():
        raise FileNotFoundError(renderer)
    if not plugin_directory.is_dir():
        raise NotADirectoryError(plugin_directory)

    with tempfile.TemporaryDirectory(prefix="smart-write-contract-") as raw_temp:
        temporary = Path(raw_temp)
        copied_project = (
            temporary
            / "defect"
            / "s3bishop"
            / "sequences"
            / "TST"
            / "TST_000_0001"
            / "comp"
            / "natron"
            / "TST_000_0001_comp_v001.ntp"
        )
        copied_project.parent.mkdir(parents=True)
        shutil.copy2(project, copied_project)
        onload = temporary / "verify_contract.py"
        onload.write_text(ONLOAD_SOURCE, encoding="utf-8")

        environment = os.environ.copy()
        existing_plugins = environment.get("NATRON_PLUGIN_PATH")
        plugin_paths = [str(plugin_directory)]
        if existing_plugins:
            plugin_paths.append(existing_plugins)
        environment["NATRON_PLUGIN_PATH"] = os.pathsep.join(plugin_paths)

        result = subprocess.run(
            [
                str(renderer),
                "--onload",
                str(onload),
                "--writer",
                WRITER_SENTINEL,
                str(copied_project),
            ],
            cwd=plugin_directory.parent,
            env=environment,
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        output = "\n".join((result.stdout or "", result.stderr or ""))
        if COMPLETE_MARKER not in output:
            raise RuntimeError("SmartWrite render contract failed:\n" + output)
        return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify every SmartWrite field through every render button in Natron."
    )
    parser.add_argument("project", type=Path)
    parser.add_argument(
        "--renderer",
        type=Path,
        default=Path(r"F:\Natron\bin\NatronRenderer.exe"),
    )
    parser.add_argument(
        "--plugin-directory",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "natron_plugins",
    )
    arguments = parser.parse_args()
    output = verify_render_contract(
        arguments.project, arguments.renderer, arguments.plugin_directory
    )
    markers = [
        line
        for line in output.splitlines()
        if line.startswith("CODEX_SMARTWRITE_CONTRACT")
        or line.startswith(COMPLETE_MARKER)
    ]
    print("\n".join(markers))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
