# Project provisioning validation

Date: September 9, 2026. Repository: `F:/RenderWorker`, branch `codex/project-provisioning`. Extraction baseline was committed first as `bc174ee`.

## Automated coverage

The complete standalone suite passed **150 tests**. Coverage includes shallow initial history containing exactly one commit, fast-forward updates, existing-clone discovery, remembered paths, untracked-file preservation, refusal to overwrite tracked edits, and locking a discovered repository across different worker workspaces. Temporary Git repositories and a real LFS fixture cover independent projects, ownership, origin matching, cancellation, engine failure, interrupted-preparation recovery, and hydration without a preexisting cache. Runtime installation is checked for ownership and clean Git status, including nested `.uproject` locations. The V2 Tkinter window loads a catalog without preparing a project.

## Real Bishop acceptance run

Started with Bishop absent from `F:/RenderWorkerWorkspace/projects/bishop` using:

```bat
F:\RenderWorker\render_project.bat render --project bishop --shot ZZZ850
```

The worker cloned `https://github.com/DefectStudio/s3bishop.git`, fetched `main`, and selected commit `86ddd64234af41e9f586f831bdca2cfeaf728abc`. It automatically found Unreal 5.8.2 at `D:/Unreal Engine/5.8/UE_5.8`. It identified 68,382 LFS assets and reused 68,286 objects from the optional machine cache at `F:/Projects/.git/lfs/objects` before verifying them. The artist checkout was not used as the render workspace.

The initial hash scan was stopped at the user's request and removed from the implementation. The earlier interrupted checkout is preserved under `F:/RenderWorkerWorkspace/interrupted-pre-shallow`. A new attempt starts from an empty project workspace using a shallow clone, enables Git's Windows long-path support, and updates with `git pull --ff-only`. Its log is `F:/RenderWorker/LocalSaveFiles/bishop-v2-acceptance-shallow.log`.

The shallow clone and pull completed and reported `rev-list --count HEAD = 1` and `--is-shallow-repository = true`. The duplicate asset copy was then stopped when the user requested discovery and reuse of an existing checkout. This cold attempt is not evidence of a completed cold render; the fallback remains covered by the integration tests.

## Successful discovery and real render

The worker automatically found `F:/Projects`, matched its origin and `main` branch, ran `git pull --ff-only` and `git lfs pull`, found Unreal 5.8.2, installed the standalone runtime, resolved the shot, and rendered it. No project path was supplied to this command:

```bat
F:\RenderWorker\render_project.bat render --project bishop --shot ZZZ850
```

- Result: **success**, engine exit code 0, **40 validated EXR files**, frames **1001–1040**.
- Commit rendered: `86ddd64234af41e9f586f831bdca2cfeaf728abc`.
- Sequence: `/Game/_S3Bishop/Sequences/ZZZ/ZZZ_000_0850.ZZZ_000_0850`.
- Level: `/Game/LVL_Startup`, read from the shot data's `AssociatedLevelPathString`.
- Graph: `/Game/_S3Bishop/RenderSettings/beauty_HDsRGB.beauty_HDsRGB`. The similarly named per-shot beauty asset is a Level Sequence, not a graph.
- Output/run directory: `F:/RenderWorkerWorkspace/renders/bishop/ZZZ_000_0850/20260910T002909Z_2c9d656b`.
- Evidence: `result.json`, `preparation-result.json`, `job/unreal_result.json`, and `output/EXR/` in that directory. `preview.png` is a converted first-frame preview and was visually inspected.
- The standalone runtime disabled one graph script callback and redirected outputs. The final Git status of `F:/Projects` still contained only the preexisting untracked `defect-asset-infrastructure-research/` directory; tracked assets were unchanged.

The runtime uses Unreal's exposed branch traversal API to locate script nodes. Earlier failed attempts and their logs remain in adjacent run directories for diagnosis.

## Boundaries

Metadata discovery follow-up: all **155 tests pass** after adding Unreal Editor/Epic Launcher lookup. A read-only check with an empty worker history and the general folder scan disabled found `F:/Projects` from the actual machine metadata. No pull or additional render was performed for that check. Fixtures cover multiple engine versions, UTF-16 settings, repeated INI keys, removed/stale entries, nested projects, Launcher folders, and newly remembered projects taking priority on the next attempt.

This validates direct project jobs. Cloud leasing, service enrollment, automatic engine installation, and worker self-updates remain separate delivery milestones. Project render paths are registered in the catalog. The pilot uses the shot's real sequence and beauty graph, redirects outputs to an isolated directory, and disables graph script callbacks and MP4/hero output.
