# Render Worker V2: first implementation and dependency investigation

Date: September 9, 2026. Branch: `codex/render-worker-v2`.

## Implemented

The worker can now discover Unreal installations through Epic Launcher's installation manifest and Windows engine registrations, as well as the original default installation folders. Explicit executable overrides remain supported. A named/custom engine association must match its registered build; it cannot silently select a generic launcher or PATH build.

Discovery skips missing executables, malformed launcher records, and registrations whose available `Build.version` identifies a different major/minor version. A PATH fallback must have matching build metadata when the project requests a known version. This is discovery of installed builds, not engine installation or full binary/plugin compatibility validation.

The existing runner uses this discovery directly. No project switching, dispatcher change, application update, or production deployment has been performed yet.

## Verified prerequisites

| Requirement | Evidence and V2 implication |
|---|---|
| Git LFS | The current project has 68,382 LFS entries, approximately 235 GiB of declared asset content. A Git checkout with pointer files is insufficient. Preparation must track asset download progress and disk requirements. |
| Unreal installation discovery | The project's `EngineAssociation` is `5.8`. The local compatible installation is registered in Epic Launcher's manifest at `D:/Unreal Engine/5.8/UE_5.8`, outside the original worker search locations. The new resolver finds it automatically. Its build metadata reports 5.8.2, changelist 56702186. |
| Farm runtime | `render_farm_runtime_executor.py`, its startup import, and the QuickWidgetTools plugin descriptor/binaries are tracked in the project. Artist tool links were not copied into the validation checkout. |
| Engine plugins | All explicitly enabled Windows-compatible plugin names in the current `.uproject` were found in the installed engine or working project during inventory. This is an availability check, not proof that every production asset/plugin combination renders. |
| First-start Python setup | The isolated checkout's first Unreal launch automatically downloaded and installed plugin-declared Python packages under its own `Intermediate/PipInstall`. Preparation needs to account for this time, disk use, and package-source access. |
| Optional callbacks | Project startup imports post-render callback classes, including ClickUp reporting. The fixture graph deliberately contains no script nodes; it does not test or invoke production reporting. Their optional/required failure policy remains to be decided. |
| Output transport | The fixture writes only to an isolated local output directory. Dropbox permissions and synchronization have not been validated by this test. |

## Isolated runtime test

Validation root: `F:/RenderWorkerV2Validation`.

The checkout is a detached sparse worktree at project commit `86ddd64234af41e9f586f831bdca2cfeaf728abc`. It includes tracked configuration, QuickWidgetTools, and the project's render-settings directory. It excludes artist `Saved` settings and external tool links. A full-show restoration was stopped in favor of this smaller runtime check, and that abandoned checkout was removed.

The fixture creates its own cube, camera, three-frame sequence, and basic EXR/PNG graph under a unique `/Game/RenderWorkerV2Smoke/Run_*` path. It uses engine assets and the project's unchanged farm executor. This tests the render runtime rather than the completeness of a production shot's dependencies.

Two checked-in scripts make the investigation repeatable:

- `tools/unreal/create_worker_v2_smoke_fixture.py`: runs inside Unreal to create the fixture. It requires an explicitly marked isolated workspace and refuses other project locations.
- `tools/unreal/run_worker_v2_smoke.py`: performs validate-only execution followed by the worker's real `execute_unreal_job` path. It checks worker-reported validation, three EXR outputs, and EXR file signatures. It refuses pre-existing output and preserves previous result files under unique names before starting another validation.

The setup commandlet logged an existing QuickWidgetTools early-Python-registration error and project GameFeatureData configuration errors, even after successfully creating the fixture. A commandlet exit code alone therefore does not establish whether fixture creation succeeded. These are recorded separately from the runtime render result.

Runtime result: **passed**. Validate-only execution loaded the tracked executor and built the graph job successfully. The actual worker render exited with code 0 and reported successful pipeline and output validation. It produced exactly three EXRs with valid EXR signatures and three 256 x 144 PNG previews. Visual inspection confirmed the test cube was present.

Evidence is preserved in:

- `F:/RenderWorkerV2Validation/smoke-result.json`
- `F:/RenderWorkerV2Validation/job/unreal_result.json`
- `F:/RenderWorkerV2Validation/job/unreal.log`
- `F:/RenderWorkerV2Validation/validate-unreal.log`
- `F:/RenderWorkerV2Validation/output/smoke.0001.png`

The original Unreal checkout retained exactly its pre-existing untracked research directory. The isolated checkout's only Git changes are the generated fixture assets. No cloud job was claimed or submitted and no production callback was invoked.

### Repeating the test

Use a new validation directory for each completed run. The following PowerShell example uses a separate root so existing evidence is preserved. Use forward slashes in the Unreal `-script` argument; backslash sequences can be interpreted by the Python commandlet.

```powershell
$validationRoot = 'F:/RenderWorkerV2Validation2'
git -C 'F:/Projects' worktree add --detach --no-checkout "$validationRoot/runtime-smoke" HEAD
git -C "$validationRoot/runtime-smoke" sparse-checkout set --cone Config Plugins/QuickWidgetTools Content/_S3Bishop/RenderSettings
git -C "$validationRoot/runtime-smoke" checkout HEAD
New-Item -ItemType File -Path "$validationRoot/.render-worker-v2-validation"
$env:RENDER_WORKER_V2_VALIDATION_ROOT = $validationRoot
& 'D:/Unreal Engine/5.8/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe' "$validationRoot/runtime-smoke/s3bishop.uproject" -run=pythonscript '-script=F:/Defect Tools/tools/unreal/create_worker_v2_smoke_fixture.py' -unattended -NullRHI -NoSplash -NoSound -NoP4
# Confirm WORKER_V2_FIXTURE success in the Unreal log and job/job.json exists.
python 'F:/Defect Tools/tools/unreal/run_worker_v2_smoke.py' --root $validationRoot
```

## Automated checks

135 distinct tests passed: 66 worker tests (including 13 new engine-discovery tests), 13 Unreal runner tests, 32 filesystem farm tests, and 24 cloud tests. These cover custom install paths, version preference, stale/malformed registrations, named builds, version-checked PATH fallback, existing explicit overrides, and regression behavior in the surrounding worker. `git diff --check` passed.

## Remaining milestone 1 acceptance

The small runtime test passed, but it does not prove a production show is self-contained. Before declaring the dependency investigation complete:

1. Choose a representative small production shot and identify its asset dependency closure.
2. Restore those assets and all required LFS/submodule content into an isolated checkout.
3. Render with the actual show graph and controlled callback behavior to a test destination.
4. Verify plugin/build compatibility, external asset references, output storage access, and the selected callback policy.

The next architecture milestone remains central project definitions and worker eligibility. Engine discovery is the first reusable piece of automatic project preparation.
