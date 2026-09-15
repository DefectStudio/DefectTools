"""Validate an EXE copied outside its checkout. Real rendering requires explicit fixtures."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="New directory; must not exist")
    parser.add_argument("--bishop-settings", type=Path)
    parser.add_argument("--bishop-job", type=Path)
    args = parser.parse_args()
    if bool(args.bishop_settings) != bool(args.bishop_job):
        parser.error("Supply both Bishop fixtures to opt in to a real render")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    exe = output / "Portable App/RenderWorkerV2.exe"
    exe.parent.mkdir()
    shutil.copy2(args.exe, exe)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "DEFECT_"))}
    env.update(PATH=str(Path(os.environ["SystemRoot"]) / "System32"),
               LOCALAPPDATA=str(output / "fresh-user"))
    result = subprocess.run([str(exe), "--self-test", str(output / "self-test.json")],
                            cwd=os.environ["SystemRoot"], env=env, timeout=90)
    if result.returncode:
        raise RuntimeError(f"Copied EXE self-test failed; see {output / 'self-test.json'}")
    summary = dict(self_test=json.loads((output / "self-test.json").read_text()), second_machine=False)
    # Replace the binary and verify the same artifact still opens and tests successfully.
    shutil.copy2(args.exe, exe)
    result = subprocess.run([str(exe), "--self-test", str(output / "replacement-self-test.json")],
                            cwd=os.environ["SystemRoot"], env=env, timeout=90)
    if result.returncode:
        raise RuntimeError("Self-test after EXE replacement failed")
    summary["replacement_self_test"] = True
    if args.bishop_settings:
        original = json.loads(args.bishop_settings.read_text())
        registration = next(p for p in original["registered_projects"] if p["project_id"].casefold() == "s3bishop")
        show = output / "shows/s3bishop"
        farm = show / "renderFarm"
        farm.mkdir(parents=True)
        identifier = "bishop_exe_validation_" + uuid4().hex[:12]
        job = json.loads(args.bishop_job.read_text())
        render_output = show / "Validation" / identifier / "output"
        job.update(job_id=identifier, status="queued", project="s3bishop", project_id="s3bishop",
                   priority=50, submitted_utc=datetime.now(timezone.utc).isoformat(),
                   output_directory=str(render_output), output_relative_directory=f"Validation/{identifier}/output",
                   submitted_show_file_server_path=str(show), submitted_output_directory=str(render_output))
        for key in ("worker_output_directory", "worker_show_file_server_path", "prepared_git_commit", "git_commit_after_pull"):
            job.pop(key, None)
        for key, value in job["graph_variable_overrides"].items():
            if key.casefold() == "outputdirectory":
                value.update(enabled=True, serialized_value=str(render_output))
        settings = output / "render-settings.json"
        registration = dict(registration, render_farm_root=str(farm), allow_downloads=False)
        write_json(settings, dict(unreal_editor_cmd=original["unreal_editor_cmd"], registered_projects=[registration]))
        job_path = output / "bishop-job.json"
        write_json(job_path, job)
        direct_output = show / "DirectValidation"
        result = subprocess.run([str(exe), "render", "--settings", str(settings), "--project", "s3bishop",
                                 "--job", str(job_path), "--output-root", str(direct_output), "--timeout", "1800"],
                                cwd=os.environ["SystemRoot"], env=env, timeout=1860)
        receipts = list(direct_output.rglob("result.json"))
        if len(receipts) != 1:
            raise RuntimeError("Expected one direct-render receipt from the copied EXE")
        summary["render"] = json.loads(receipts[0].read_text())
        summary["render_mode"] = "explicit-job-file (SQL claiming tested separately)"
        render_output = Path(summary["render"]["run_root"]) / "output"
        summary["exr_count"] = sum(1 for p in render_output.rglob("*.exr") if p.stat().st_size > 0)
        summary["render_output"] = str(render_output)
        write_json(output / "validation-result.json", summary)
        if result.returncode or not summary["render"]["success"] or summary["exr_count"] != 40:
            raise RuntimeError(f"Bishop render validation failed; see {output / 'validation-result.json'}")
    write_json(output / "validation-result.json", summary)
    print(f"Validation passed: {output / 'validation-result.json'}")


if __name__ == "__main__":
    main()
