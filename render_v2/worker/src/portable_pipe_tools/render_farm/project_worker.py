"""Direct V2 project jobs: fetch a project before preparing or rendering a shot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from portable_pipe_tools.app_runtime import default_catalog_path, default_settings_path

from portable_pipe_tools.render_farm.project_catalog import load_catalog
from portable_pipe_tools.render_farm.project_workspace import ProjectWorkspace


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["list", "prepare", "render"])
    parser.add_argument("--settings", type=Path, default=default_settings_path())
    parser.add_argument("--catalog")
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--project")
    parser.add_argument("--shot")
    args = parser.parse_args(argv)
    try:
        settings = json.loads(args.settings.read_text(encoding="utf-8-sig")) if args.settings.exists() else {}
        catalog_path = args.catalog or settings.get("catalog") or str(default_catalog_path())
        projects = load_catalog(catalog_path)
        if args.command == "list":
            for project in projects.values():
                print(f"{project.project_id}: {project.branch}, {project.uproject}")
            return 0
        if args.project not in projects:
            raise ValueError(f"Choose a registered project: {', '.join(projects)}")
        if args.command == "render":
            if not args.shot:
                raise ValueError("A shot is required for rendering")
            projects[args.project].canonical_shot(args.shot)
        workspace_root = args.workspace or settings.get("workspace_root")
        if not workspace_root:
            raise ValueError(f"Choose a workspace once with --workspace or {args.settings}")
        workspace = ProjectWorkspace(Path(workspace_root), progress=lambda message: print(message, flush=True),
                                     cache_roots=tuple(Path(p) for p in settings.get("lfs_cache_roots", [])),
                                     discovery_roots=tuple(Path(p) for p in settings["discovery_roots"]) if "discovery_roots" in settings else None,
                                     timeout_seconds=settings.get("preparation_timeout_seconds", 7200))
        with workspace.acquire(projects[args.project]) as prepared:
            if args.command == "prepare":
                print(json.dumps({"project": prepared.project.project_id, "checkout": str(prepared.checkout),
                                  "commit": prepared.commit, "engine": str(prepared.engine)}))
            else:
                from portable_pipe_tools.render_farm.project_render import render_project_shot
                output_root = args.output_root or settings.get("output_root") or Path(workspace_root) / "renders"
                result = render_project_shot(prepared, args.shot, Path(output_root), progress=workspace.progress)
                print(json.dumps(result, indent=2))
                return 0 if result["success"] else 1
        return 0
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
        return 130
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Render Worker: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
