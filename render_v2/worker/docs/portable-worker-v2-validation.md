# Portable V2 preview validation — September 15, 2026

Version: 2.0.0-preview.1. Current release location: `F:/Defect Tools/tools/RenderWorkerV2.exe` (approximately 12.2 MiB). The EXE and validation artifacts were relocated into Defect Tools on September 18. These September 15 results describe the build tested at that time; later hosted SQL acceptance is recorded in [the September 17 report](hosted-bishop-acceptance-20260917.md).

Verified:

- 206 worker unit/integration tests passed on Python 3.13, including connection setup, URL validation, setup diagnostics, GUI checks without claims, frozen settings paths and V2 cloud control-file isolation.
- A folder build copied outside the repository passed GUI/resource/settings diagnostics.
- The final single-file build was copied to a directory containing spaces outside the repository and launched from the Windows directory with a fresh Local AppData directory, no Python/Git on PATH, and no inherited Python/Defect configuration variables.
- The frozen self-test launched `RenderWorkerV2App`, loaded bundled animations/runtime scripts, exercised project registration and saved-preference reload, kept downloads off and started no automatic jobs. External process startup passed. A second invocation after replacing the EXE also passed. Preference reload is exercised inside the self-test; this is not a separate user's upgrade test.
- The exact final release artifact claimed Bishop `ZZZ_000_0850` from a newly created isolated filesystem queue, launched Unreal using the bundled runtime, produced 40 nonempty EXR files, and moved the job into `03_RenderComplete` with a successful completion receipt.
- Frozen build inventory contained no saved worker JSON, cloud connection JSON, projects.json, or LocalSaveFiles content.
- Git diff checks passed. Code changes are confined to Worker V2; V1 source and production services were not changed.

The first fixture attempt failed before Unreal startup because the older direct-render fixture lacked filesystem-queue priority and submission time. The validation utility now supplies those fields. The successful final run used the updated fixture preparation and the final EXE.

Local evidence, excluded from Git:

- `F:/Defect Tools/render_v2/worker/LocalSaveFiles/portable-validation/final-20260915/validation-result.json`
- `F:/Defect Tools/render_v2/worker/LocalSaveFiles/portable-validation/final-20260915/self-test.json`
- `F:/Defect Tools/render_v2/worker/LocalSaveFiles/portable-validation/final-20260915/render-result.json`
- Final render outputs and Unreal logs under that validation directory's `shows/s3bishop` tree.
- Build logs in the worker's `LocalSaveFiles/build-v2-single.log` and `build-v2-folder.log`.

Limits: these tests ran on the development computer with isolated process settings, not a second physical computer or a new Windows account. Python/Git remain installed on the computer, but neither was on the executable test process's PATH and the EXE reported Git unavailable. The real packaged render exercised filesystem claiming; packaged cloud claiming against a deployed V2 service still needs acceptance testing. This release is unsigned. Real target-machine security policy, user-profile replacement, GPU/driver compatibility and a reachable company V2 dispatcher still need verification before broad deployment.
