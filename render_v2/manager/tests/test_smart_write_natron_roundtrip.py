from __future__ import annotations

import os
from pathlib import Path
import runpy

import pytest


PROJECT_ENVIRONMENT_VARIABLE = "SMARTWRITE_NATRON_ROUNDTRIP_PROJECT"
VERIFIER = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "verify_smart_write_roundtrip.py"
)


@pytest.mark.skipif(
    not os.environ.get(PROJECT_ENVIRONMENT_VARIABLE),
    reason=(
        "Set SMARTWRITE_NATRON_ROUNDTRIP_PROJECT to run the real Natron "
        "save/reload regression test."
    ),
)
def test_smart_write_survives_real_natron_save_reload() -> None:
    verifier = runpy.run_path(str(VERIFIER))
    repository = VERIFIER.parents[1]
    verifier["verify_roundtrip"](
        Path(os.environ[PROJECT_ENVIRONMENT_VARIABLE]),
        Path(os.environ.get("NATRON_RENDERER", r"F:\Natron\bin\NatronRenderer.exe")),
        repository / "natron_plugins",
    )
