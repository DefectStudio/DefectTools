from __future__ import annotations

from pathlib import Path
import runpy
import subprocess

import pytest

VERIFIER = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "verify_smart_write_roundtrip.py"
)


def test_roundtrip_verifier_checks_persisted_state_and_recreated_outputs(
    monkeypatch, tmp_path: Path
) -> None:
    verifier = runpy.run_path(str(VERIFIER))
    project = tmp_path / "source.ntp"
    renderer = tmp_path / "NatronRenderer.exe"
    plugin_directory = tmp_path / "natron_plugins"
    project.write_text("source", encoding="utf-8")
    renderer.write_text("renderer", encoding="utf-8")
    plugin_directory.mkdir()
    calls = []

    def fake_run_natron(
        _renderer, loaded_project, _plugin_directory, profile, onload_script=None
    ) -> str:
        script = onload_script.read_text(encoding="utf-8")
        compile(script, str(onload_script), "exec")
        calls.append((loaded_project, script))
        temporary = profile.parent
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
        if len(calls) == 1:
            assert "CODEX_SMARTWRITE_STATE_PREPARED" in script
            assert "EXPECTED_OUTPUTS" in script
            assert "EXPECTED_SETTINGS" in script
            saved_project.write_text("saved", encoding="utf-8")
            return (
                "CODEX_SMARTWRITE_STATE_PREPARED\n"
                "CODEX_SMARTWRITE_ROUNDTRIP_SAVED"
            )

        output_root = saved_project.parents[1] / "_output"
        assert not output_root.exists()
        assert "SMART_WRITE_UI_VERSION" in script
        assert "CODEX_SMARTWRITE_PERSISTED_STATE_OK" in script
        assert "CODEX_SMARTWRITE_OUTPUT_DIRECTORIES_OK" in script
        assert "CODEX_SMARTWRITE_VERSION_STABLE" in script
        return (
            "CODEX_SMARTWRITE_RENDER_CONTROLS_OK\n"
            "CODEX_SMARTWRITE_CHOICES_OK|12\n"
            "CODEX_SMARTWRITE_PERSISTED_STATE_OK\n"
            "CODEX_SMARTWRITE_OUTPUT_DIRECTORIES_OK\n"
            "CODEX_SMARTWRITE_VERSION_STABLE"
        )

    monkeypatch.setitem(
        verifier["verify_roundtrip"].__globals__,
        "_run_natron",
        fake_run_natron,
    )

    verifier["verify_roundtrip"](project, renderer, plugin_directory)

    assert calls[0][0] == project.resolve()
    assert calls[1][0].name == "TST_000_0001_comp_v001.ntp"


def test_natron_runner_can_only_target_the_nonexistent_sentinel_writer(
    monkeypatch, tmp_path: Path
) -> None:
    verifier = runpy.run_path(str(VERIFIER))
    renderer = tmp_path / "NatronRenderer.exe"
    project = tmp_path / "comp.ntp"
    plugin_directory = tmp_path / "natron_plugins"
    profile = tmp_path / "profile"
    onload_script = tmp_path / "verify.py"
    captured = {}

    class Result:
        stdout = ""
        stderr = "does not belong to the project file"

    def fake_subprocess_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return Result()

    monkeypatch.setattr(
        verifier["_run_natron"].__globals__["subprocess"],
        "run",
        fake_subprocess_run,
    )

    verifier["_run_natron"](
        renderer, project, plugin_directory, profile, onload_script
    )

    assert captured["command"] == [
        str(renderer),
        "--onload",
        str(onload_script),
        "--writer",
        verifier["WRITER_SENTINEL"],
        str(project),
    ]
    assert captured["kwargs"]["check"] is False


def test_natron_runner_accepts_a_bounded_exit_after_onload_completion(
    monkeypatch, tmp_path: Path
) -> None:
    verifier = runpy.run_path(str(VERIFIER))

    def fake_subprocess_run(command, **_kwargs):
        raise subprocess.TimeoutExpired(
            command,
            90,
            output=b"CODEX_SMARTWRITE_ROUNDTRIP_SAVED\n",
            stderr=b"Natron remained resident after onload\n",
        )

    monkeypatch.setattr(
        verifier["_run_natron"].__globals__["subprocess"],
        "run",
        fake_subprocess_run,
    )

    output = verifier["_run_natron"](
        tmp_path / "NatronRenderer.exe",
        tmp_path / "comp.ntp",
        tmp_path / "natron_plugins",
        tmp_path / "profile",
    )

    assert "CODEX_SMARTWRITE_ROUNDTRIP_SAVED" in output


def test_natron_runner_rejects_a_timeout_before_onload_completion(
    monkeypatch, tmp_path: Path
) -> None:
    verifier = runpy.run_path(str(VERIFIER))

    def fake_subprocess_run(command, **_kwargs):
        raise subprocess.TimeoutExpired(
            command,
            90,
            output=b"Loading project\n",
            stderr=b"still running\n",
        )

    monkeypatch.setattr(
        verifier["_run_natron"].__globals__["subprocess"],
        "run",
        fake_subprocess_run,
    )

    with pytest.raises(RuntimeError, match="timed out before onload completed"):
        verifier["_run_natron"](
            tmp_path / "NatronRenderer.exe",
            tmp_path / "comp.ntp",
            tmp_path / "natron_plugins",
            tmp_path / "profile",
        )
