# Render Worker V2

- The user consolidated both V2 apps into Defect Tools on September 10. Worker V2 lives here in `render_v2/worker`; Manager V2 lives in sibling `../manager`. Preserve repository-root V1 source and launchers. V2 uses a separate local dispatcher/database; never deploy V2 migrations or code into V1 production resources. The known V1 dispatcher URL is rejected by this V2 client.

This directory is the home of Worker V2 development inside the shared repository. See `../README.md`. The old `F:/RenderWorker` checkout is a historical copy.

- The Python package temporarily retains the `portable_pipe_tools` namespace. Keep imports self-contained under this repository's `src` directory.
- Run `test_worker.bat --no-pause` for the standalone suite. The tests do not require a farm connection or a real render.
- Use context-mode tools for potentially large reads, searches, logs, and test output. Return concise derived findings rather than raw output.
- Keep credentials, machine settings, downloaded projects, outputs, and logs out of Git.
- The user's September 10 direction supersedes automatic project discovery: workers must use explicitly registered project locations. Do not scan Unreal Editor/Epic Launcher metadata, drive roots, or remembered discovery results. The existing implementation still needs migration; see `docs/manual-project-registration-plan.md`.
- Project downloading must be an explicit checkbox, off by default. The plan proposes a per-project setting. Whether downloads-off also disables Git pull is awaiting user clarification; do not silently allow network updates under that setting.
- For explicitly authorized downloads, use a shallow single-branch clone and `git pull --ff-only` for updates. Do not add separate asset hash scans. Preserve existing local changes and never switch an existing checkout's branch automatically.
- Test explicit local registration and optional empty-workspace downloading separately. The current real-shot acceptance target is Bishop `ZZZ_000_0850`; report which preparation path was actually exercised.
- The root V2 GUI supports worker-initiated filesystem/cloud claiming through registered local projects; `render_registered_job.bat` handles a selected job file. Neither path downloads or updates project repositories. See `docs/registered-queue-claiming.md`. The default EXE build now packages this GUI through `packaging/v2_entry.py`; see `docs/portable-worker-v2.md`. The old `worker_entry.py` and `RenderWorker.spec` are historical pilot artifacts. Startup recovery and unattended updates remain separate work.
- See `docs/render-worker-v2-plan.md` and `docs/repository-extraction.md` before changing the architecture.
