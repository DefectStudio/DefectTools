"""Validate and render the isolated fixture using the worker's actual launcher."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import struct
import subprocess
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from portable_pipe_tools.render_farm.unreal_runner import (  # noqa: E402
    build_unreal_command,
    execute_unreal_job,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    if not (root / ".render-worker-v2-validation").is_file():
        raise RuntimeError("The requested root is not marked as an isolated validation workspace")
    folder = root / "job"
    job = json.loads((folder / "job.json").read_text(encoding="utf-8"))
    project = root / "runtime-smoke" / "s3bishop.uproject"
    if (
        job.get("job_id") != "render-worker-v2-runtime-smoke"
        or Path(job["uproject"]).resolve() != project
        or Path(job["output_directory"]).resolve() != root / "output"
        or job.get("output_relative_directory") != "output"
        or not all(str(job.get(key, "")).startswith("/Game/RenderWorkerV2Smoke/")
                   for key in ("level", "sequence", "render_config"))
    ):
        raise RuntimeError("Job does not match the isolated smoke fixture")
    if (root / "output").exists():
        raise RuntimeError("Output already exists; refusing to overwrite a previous smoke run")

    logging.basicConfig(filename=root / "worker.log", level=logging.INFO, encoding="utf-8")
    command = build_unreal_command(folder, job, validate_only=True, local_uproject=project)
    command = [part for part in command if not part.startswith("-abslog=")]
    command.append(f"-abslog={root / 'validate-unreal.log'}")
    result_path = folder / "unreal_result.json"
    if result_path.exists():
        result_path.rename(folder / f"unreal_result.previous_{uuid4().hex}.json")
    with (root / "validate-stdout.log").open("w", encoding="utf-8") as output:
        validation = subprocess.run(
            command, cwd=project.parent, stdout=output, stderr=subprocess.STDOUT,
            timeout=900, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {}
    if result.get("success") is not True or result.get("job_id") != job["job_id"]:
        print(json.dumps({"success": False, "stage": "validation", "exit_code": validation.returncode, "result": result}))
        return 1

    (root / "renderFarm").mkdir(exist_ok=True)
    execution = execute_unreal_job(
        folder, job, timeout_seconds=900, local_uproject=project,
        render_farm_root=root / "renderFarm",
    )
    files = sorted((root / "output").rglob("*.exr"))
    valid_headers = all(
        path.stat().st_size > 100 and _exr_magic(path) == 20000630 for path in files
    )
    summary = {
        "success": execution.success and len(files) == 3 and valid_headers,
        "engine": command[0],
        "project": str(project),
        "rendered_commit": job.get("rendered_git_commit"),
        "exr_count": len(files),
        "exr_headers_valid": valid_headers,
        "preview_files": [str(path) for path in sorted((root / "output").rglob("*.png"))],
        "worker_result": execution.terminal_result_details(),
        "reason": execution.reason,
    }
    (root / "smoke-result.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary))
    return 0 if summary["success"] else 1


def _exr_magic(path: Path) -> int:
    with path.open("rb") as file:
        return struct.unpack("<I", file.read(4))[0]


if __name__ == "__main__":
    raise SystemExit(main())
