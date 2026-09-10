# Standalone repository extraction

Created September 9, 2026, at `F:/RenderWorker`. This is a new local Git repository with no remote configured.

## Source

- Existing repository: `F:/Defect Tools`.
- Source base commit: `227090396321ca24e29602251b774c70033be162`.
- Included uncommitted V2 work: engine discovery, runner integration, discovery tests, isolated Unreal validation scripts, and V2 documentation.
- The extraction copied files; it did not remove or rewrite the old repository's worker.

The worker GUI and cloud setup application's Python import dependencies were traced before copying. Only those modules, package initializers, corresponding tests, launchers, and five worker sprites were included. The farm manager UI, artist applications, unrelated tooling, cloud server source, machine settings, and credentials were excluded.

The internal Python package name remains `portable_pipe_tools` for now. The distributable project name is `defect-render-worker`. Renaming the package can happen separately after the extraction baseline is established.

## Validation boundaries

The earlier three-frame Unreal render was performed using the original V2 work in Defect Tools and a separate project checkout at `F:/RenderWorkerV2Validation`. That evidence remains useful for the copied code, but it is not evidence of automatic provisioning from this new repository.

The new repository's own tests must pass with `PYTHONPATH` pointing only at `F:/RenderWorker/src`. Worker/configuration imports must resolve inside this repository. No production worker, farm API mutation, or real render is required for extraction validation.

Extraction validation passed: 131 tests succeeded with the standalone source path. Worker UI, cloud setup, and engine discovery imports all resolved inside `F:/RenderWorker/src`, with no import from the old checkout.

The inherited self-update preflight requires an upstream. Keep that requirement intact while this repository is local-only; the automatic installation and project-provisioning flow is the next implementation work.
