from __future__ import annotations

from pathlib import Path
import runpy

import pytest


VERIFIER = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "verify_smart_write_render_contract.py"
)


def _files(tmp_path: Path) -> tuple[Path, Path, Path]:
    project = tmp_path / "source.ntp"
    renderer = tmp_path / "NatronRenderer.exe"
    plugin_directory = tmp_path / "natron_plugins"
    project.write_text("source", encoding="utf-8")
    renderer.write_text("renderer", encoding="utf-8")
    plugin_directory.mkdir()
    return project, renderer, plugin_directory


def test_render_contract_verifier_uses_a_copy_and_intercepts_all_submissions(
    monkeypatch, tmp_path: Path
) -> None:
    verifier = runpy.run_path(str(VERIFIER))
    project, renderer, plugin_directory = _files(tmp_path)
    captured = {}

    class Result:
        stdout = (
            "CODEX_SMARTWRITE_CONTRACT_OK|EXRWrite|renderEXR|18\n"
            "CODEX_SMARTWRITE_RENDER_CONTRACT_COMPLETE|"
            "submissions=154|field_checks=154"
        )
        stderr = "sentinel writer does not belong to the project file"

    def fake_subprocess_run(command, **kwargs):
        copied_project = Path(command[-1])
        onload = Path(command[command.index("--onload") + 1])
        assert copied_project != project
        assert copied_project.read_text(encoding="utf-8") == "source"
        source = onload.read_text(encoding="utf-8")
        compile(source, str(onload), "exec")
        assert "SmartWriteExt._submit_render_tasks = capture_submission" in source
        assert (
            "for index, (native_name, creator_name) in enumerate(setting_specs)"
            in source
        )
        assert "for render_all in (False, True)" in source
        captured["command"] = command
        captured["kwargs"] = kwargs
        return Result()

    monkeypatch.setattr(
        verifier["verify_render_contract"].__globals__["subprocess"],
        "run",
        fake_subprocess_run,
    )

    output = verifier["verify_render_contract"](
        project, renderer, plugin_directory
    )

    assert "submissions=154|field_checks=154" in output
    assert captured["command"][3:5] == [
        "--writer",
        verifier["WRITER_SENTINEL"],
    ]
    assert captured["kwargs"]["check"] is False


def test_render_contract_verifier_rejects_missing_completion_marker(
    monkeypatch, tmp_path: Path
) -> None:
    verifier = runpy.run_path(str(VERIFIER))
    project, renderer, plugin_directory = _files(tmp_path)

    class Result:
        stdout = "CODEX_SMARTWRITE_CONTRACT_OK|EXRWrite|renderEXR|18"
        stderr = "RuntimeError: final sync failed"

    monkeypatch.setattr(
        verifier["verify_render_contract"].__globals__["subprocess"],
        "run",
        lambda *_args, **_kwargs: Result(),
    )

    with pytest.raises(RuntimeError, match="render contract failed"):
        verifier["verify_render_contract"](
            project, renderer, plugin_directory
        )
