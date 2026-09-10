from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile


LOAD_FAILURES = (
    "unrecognized or damaged project file",
    "project file loading failed",
    "input stream error",
)
MISSING_WRITER = "does not belong to the project file"
WRITER_SENTINEL = "CODEX_SMARTWRITE_ROUNDTRIP_DO_NOT_RENDER"
EXPECTED_OUTPUTS = {
    "exrOutput": True,
    "mp4Output": False,
    "movOutput": True,
    "heroOutput": True,
}
EXPECTED_SETTINGS = {
    "exr_quality": 83,
    "mp4_bitrateMbps": 18.75,
    "mov_fastStart": True,
    "hero_dwaCompressionLevel": 21.5,
}
RELOAD_MARKERS = (
    "CODEX_SMARTWRITE_RENDER_CONTROLS_OK",
    "CODEX_SMARTWRITE_CHOICES_OK",
    "CODEX_SMARTWRITE_PERSISTED_STATE_OK",
    "CODEX_SMARTWRITE_OUTPUT_DIRECTORIES_OK",
    "CODEX_SMARTWRITE_VERSION_STABLE",
)
ONLOAD_COMPLETION_MARKERS = (
    "CODEX_SMARTWRITE_STATE_PREPARED",
    "CODEX_SMARTWRITE_ROUNDTRIP_SAVED",
) + RELOAD_MARKERS


def _natron_environment(plugin_directory: Path, profile: Path) -> dict[str, str]:
    environment = os.environ.copy()
    existing_plugins = environment.get("NATRON_PLUGIN_PATH")
    plugin_paths = [str(plugin_directory)]
    if existing_plugins:
        plugin_paths.append(existing_plugins)
    environment["NATRON_PLUGIN_PATH"] = os.pathsep.join(plugin_paths)
    environment["LOCALAPPDATA"] = str(profile / "local")
    environment["APPDATA"] = str(profile / "roaming")
    return environment


def _run_natron(
    renderer: Path,
    project: Path,
    plugin_directory: Path,
    profile: Path,
    onload_script: Path | None = None,
) -> str:
    command = [str(renderer)]
    if onload_script is not None:
        command.extend(("--onload", str(onload_script)))
    command.extend(("--writer", WRITER_SENTINEL, str(project)))
    timed_out = False
    try:
        result = subprocess.run(
            command,
            cwd=plugin_directory.parent,
            env=_natron_environment(plugin_directory, profile),
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        streams = (result.stdout, result.stderr)
    except subprocess.TimeoutExpired as error:
        timed_out = True
        streams = (error.stdout, error.stderr)

    def stream_text(stream) -> str:
        if isinstance(stream, bytes):
            return stream.decode(errors="replace")
        return stream or ""

    output = "\n".join(stream_text(stream) for stream in streams)
    lowered = output.casefold()
    failures = [message for message in LOAD_FAILURES if message in lowered]
    if failures:
        raise RuntimeError(
            "Natron could not load the project ({0}):\n{1}".format(
                ", ".join(failures), output
            )
        )
    onload_completed = any(marker in output for marker in ONLOAD_COMPLETION_MARKERS)
    if timed_out and not onload_completed:
        raise RuntimeError(
            "Natron timed out before onload completed:\n{0}".format(output)
        )
    if not timed_out and MISSING_WRITER not in lowered:
        raise RuntimeError(
            "Natron did not reach the expected post-load writer check:\n{0}".format(
                output
            )
        )
    return output


def _save_script_source(saved_project: Path) -> str:
    return (
        "import SmartWriteExt\n"
        "EXPECTED_OUTPUTS = "
        + repr(EXPECTED_OUTPUTS)
        + "\nEXPECTED_SETTINGS = "
        + repr(EXPECTED_SETTINGS)
        + "\nprepared = 0\n"
        "for node in app.getChildren():\n"
        "    if node.getPluginID() != SmartWriteExt.PLUGIN_ID:\n"
        "        continue\n"
        "    for name, value in EXPECTED_OUTPUTS.items():\n"
        "        param = node.getParam(name)\n"
        "        if param is None:\n"
        "            raise RuntimeError('Missing SmartWrite output control: {0}'.format(name))\n"
        "        param.set(value)\n"
        "    for name, value in EXPECTED_SETTINGS.items():\n"
        "        param = node.getParam(name)\n"
        "        if param is None:\n"
        "            raise RuntimeError('Missing SmartWrite setting: {0}'.format(name))\n"
        "        param.set(value)\n"
        "    prepared += 1\n"
        "if not prepared:\n"
        "    raise RuntimeError('No SmartWrite nodes found before save')\n"
        "print('CODEX_SMARTWRITE_STATE_PREPARED')\n"
        "TARGET = "
        + repr(saved_project.as_posix())
        + "\nif not app.saveProjectAs(TARGET):\n"
        "    raise RuntimeError('Natron failed to save round-trip project')\n"
        "print('CODEX_SMARTWRITE_ROUNDTRIP_SAVED')\n"
    )


def _reload_script_source(output_root: Path) -> str:
    return (
        "import os\n"
        "import SmartWriteExt\n"
        "EXPECTED_OUTPUTS = "
        + repr(EXPECTED_OUTPUTS)
        + "\nEXPECTED_SETTINGS = "
        + repr(EXPECTED_SETTINGS)
        + "\nEXPECTED_OUTPUT_ROOT = "
        + repr(output_root.as_posix())
        + "\nSETTING_WRITERS = {'exr': 'EXRWrite', 'mp4': 'MP4Write', "
        "'mov': 'MOVWrite', 'hero': 'HeroWrite'}\n"
        "SmartWriteExt.afterProjectLoaded(app)\n"
        "checked = 0\n"
        "empty = []\n"
        "for node in app.getChildren():\n"
        "    if node.getPluginID() != SmartWriteExt.PLUGIN_ID:\n"
        "        continue\n"
        "    checked += 1\n"
        "    SmartWriteExt.refreshOutputs(app, node)\n"
        "    layout_version = node.getParam('smartWriteUiVersion')\n"
        "    if layout_version is None or layout_version.get() != SmartWriteExt.SMART_WRITE_UI_VERSION:\n"
        "        raise RuntimeError('SmartWrite UI version did not survive reload')\n"
        "    actual_outputs = {name: bool(node.getParam(name).get()) for name in EXPECTED_OUTPUTS}\n"
        "    if actual_outputs != EXPECTED_OUTPUTS:\n"
        "        raise RuntimeError('SmartWrite outputs changed: {0}'.format(actual_outputs))\n"
        "    actual_settings = {name: node.getParam(name).get() for name in EXPECTED_SETTINGS}\n"
        "    if actual_settings != EXPECTED_SETTINGS:\n"
        "        raise RuntimeError('SmartWrite settings changed: {0}'.format(actual_settings))\n"
        "    for exposed_name, expected in EXPECTED_SETTINGS.items():\n"
        "        prefix, native_name = exposed_name.split('_', 1)\n"
        "        writer = node.getNode(SETTING_WRITERS[prefix])\n"
        "        native = writer.getParam(native_name) if writer else None\n"
        "        actual_native = native.get() if native is not None else None\n"
        "        if actual_native != expected:\n"
        "            available = [param.getScriptName() for param in "
        "writer.getParams()] if writer is not None else []\n"
        "            raise RuntimeError('Writer setting was not synchronized: "
        "{0} expected={1!r} actual={2!r} plugin={3!r} filename={4!r} "
        "available={5!r}'.format(exposed_name, expected, actual_native, "
        "writer.getPluginID() if writer else None, "
        "writer.getParam('filename').get() if writer else None, available))\n"
        "    render_controls = ('renderAll', 'renderEXR', 'renderMP4', 'renderMOV', 'renderHero')\n"
        "    missing_controls = [name for name in render_controls if node.getParam(name) is None]\n"
        "    if missing_controls:\n"
        "        raise RuntimeError('Missing SmartWrite render controls: {0}'.format(missing_controls))\n"
        "    expected_rows = {'renderAll': True, 'exrOutput': False, 'renderEXR': True, "
        "'mp4Output': False, 'renderMP4': True, 'movOutput': False, 'renderMOV': True, "
        "'heroOutput': False, 'renderHero': True}\n"
        "    bad_rows = [name for name, expected in expected_rows.items() "
        "if node.getParam(name).getAddNewLine() != expected]\n"
        "    actual_rows = {name: node.getParam(name).getAddNewLine() for name in expected_rows}\n"
        "    wrong_page = [name for name in expected_rows "
        "if node.getParam(name).getParent().getScriptName() != 'smartWrite']\n"
        "    if bad_rows or wrong_page:\n"
        "        raise RuntimeError('Bad SmartWrite row layout: rows={0}, actual={1}, page={2}'.format(bad_rows, actual_rows, wrong_page))\n"
        "    print('CODEX_SMARTWRITE_RENDER_CONTROLS_OK')\n"
        "    for button_name, _label, checkbox_name in SmartWriteExt.RENDER_BUTTON_SPECS:\n"
        "        expected_enabled = bool(node.getParam(checkbox_name).get())\n"
        "        if node.getParam(button_name).getIsEnabled() != expected_enabled:\n"
        "            raise RuntimeError('Render button state mismatch: {0}'.format(button_name))\n"
        "    for section in SmartWriteExt.SETTINGS_SECTIONS:\n"
        "        prefix = section[4]\n"
        "        writer = node.getNode(section[3])\n"
        "        for native_name, creator_name in section[5]:\n"
        "            if creator_name != 'createChoiceParam':\n"
        "                continue\n"
        "            name = '{0}_{1}'.format(prefix, native_name)\n"
        "            param = node.getParam(name)\n"
        "            native = writer.getParam(native_name) if writer else None\n"
        "            native_options = native.getOptions() if native else []\n"
        "            if param is None or (native_options and not param.getOptions()):\n"
        "                empty.append(name)\n"
        "    before_paths = {writer_name: node.getNode(writer_name).getParam('filename').get() "
        "for _checkbox, writer_name, _attribute in SmartWriteExt.WRITER_SPECS}\n"
        "    SmartWriteExt.refreshOutputs(app, node)\n"
        "    middle_paths = {writer_name: node.getNode(writer_name).getParam('filename').get() "
        "for _checkbox, writer_name, _attribute in SmartWriteExt.WRITER_SPECS}\n"
        "    SmartWriteExt.refreshOutputs(app, node)\n"
        "    after_paths = {writer_name: node.getNode(writer_name).getParam('filename').get() "
        "for _checkbox, writer_name, _attribute in SmartWriteExt.WRITER_SPECS}\n"
        "    if before_paths != middle_paths or middle_paths != after_paths:\n"
        "        raise RuntimeError('SmartWrite output version changed across refresh: {0} -> {1} -> {2}'.format(before_paths, middle_paths, after_paths))\n"
        "    print('CODEX_SMARTWRITE_VERSION_STABLE')\n"
        "    wrong_roots = [name for name, filename in after_paths.items() "
        "if not filename.replace('\\\\', '/').startswith(EXPECTED_OUTPUT_ROOT + '/')]\n"
        "    if wrong_roots:\n"
        "        raise RuntimeError('SmartWrite paths use the wrong output root: {0}'.format(wrong_roots))\n"
        "    missing_directories = []\n"
        "    for checkbox_name, writer_name, _attribute in SmartWriteExt.WRITER_SPECS:\n"
        "        writer = node.getNode(writer_name)\n"
        "        enabled = bool(node.getParam(checkbox_name).get())\n"
        "        disabled = bool(writer.getParam('disableNode').get())\n"
        "        if disabled == enabled:\n"
        "            raise RuntimeError('Writer enable state mismatch: {0}'.format(writer_name))\n"
        "        directory = os.path.dirname(writer.getParam('filename').get())\n"
        "        if enabled and not os.path.isdir(directory):\n"
        "            missing_directories.append(directory)\n"
        "    if not os.path.isdir(EXPECTED_OUTPUT_ROOT) or missing_directories:\n"
        "        raise RuntimeError('Missing SmartWrite output directories: {0}'.format(missing_directories))\n"
        "    print('CODEX_SMARTWRITE_OUTPUT_DIRECTORIES_OK')\n"
        "    print('CODEX_SMARTWRITE_PERSISTED_STATE_OK')\n"
        "if not checked:\n"
        "    raise RuntimeError('No SmartWrite nodes found after reload')\n"
        "if empty:\n"
        "    raise RuntimeError('Empty SmartWrite choices: {0}'.format(empty))\n"
        "print('CODEX_SMARTWRITE_CHOICES_OK|{0}'.format(len(empty)))\n"
    )


def verify_roundtrip(
    project: Path,
    renderer: Path,
    plugin_directory: Path,
) -> None:
    project = project.resolve()
    renderer = renderer.resolve()
    plugin_directory = plugin_directory.resolve()
    if not project.is_file():
        raise FileNotFoundError(project)
    if not renderer.is_file():
        raise FileNotFoundError(renderer)
    if not plugin_directory.is_dir():
        raise FileNotFoundError(plugin_directory)

    with tempfile.TemporaryDirectory(prefix="smartwrite-roundtrip-") as temp_name:
        temporary = Path(temp_name)
        saved_project = (
            temporary
            / "show"
            / "sequences"
            / "TST"
            / "TST_000_0001"
            / "comp"
            / "natron"
            / "TST_000_0001_comp_v001.ntp"
        )
        output_root = saved_project.parents[1] / "_output"
        saved_project.parent.mkdir(parents=True)
        save_script = temporary / "save_roundtrip.py"
        reload_script = temporary / "verify_roundtrip.py"
        save_script.write_text(
            _save_script_source(saved_project), encoding="utf-8"
        )
        reload_script.write_text(
            _reload_script_source(output_root), encoding="utf-8"
        )

        first_output = _run_natron(
            renderer,
            project,
            plugin_directory,
            temporary / "save-profile",
            save_script,
        )
        if "CODEX_SMARTWRITE_STATE_PREPARED" not in first_output:
            raise RuntimeError(
                "Natron did not prepare SmartWrite persistence state:\n{0}".format(
                    first_output
                )
            )
        if "CODEX_SMARTWRITE_ROUNDTRIP_SAVED" not in first_output:
            raise RuntimeError(
                "Natron did not confirm the round-trip save:\n{0}".format(
                    first_output
                )
            )
        if not saved_project.is_file():
            raise RuntimeError("Natron did not create the round-trip project")
        if output_root.exists():
            raise RuntimeError(
                "Round-trip output directory existed before reload: {0}".format(
                    output_root
                )
            )

        second_output = _run_natron(
            renderer,
            saved_project,
            plugin_directory,
            temporary / "reload-profile",
            reload_script,
        )
        missing_markers = [
            marker for marker in RELOAD_MARKERS if marker not in second_output
        ]
        if missing_markers:
            raise RuntimeError(
                "Natron round-trip checks did not complete ({0}):\n{1}".format(
                    ", ".join(missing_markers), second_output
                )
            )


def _parser() -> argparse.ArgumentParser:
    repository = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Verify SmartWrite state and paths across a Natron save/reload."
    )
    parser.add_argument("project", type=Path)
    parser.add_argument(
        "--renderer",
        type=Path,
        default=Path(
            os.environ.get(
                "NATRON_RENDERER", r"F:\Natron\bin\NatronRenderer.exe"
            )
        ),
    )
    parser.add_argument(
        "--plugin-directory",
        type=Path,
        default=repository / "natron_plugins",
    )
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    verify_roundtrip(
        arguments.project,
        arguments.renderer,
        arguments.plugin_directory,
    )
    print("SmartWrite Natron save/reload passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
