# Render Worker V2: automatic project setup

Status: implementation started, September 9, 2026, on `codex/render-worker-v2`. Engine discovery and the isolated runtime validation harness are implemented. See `render-worker-v2-validation.md` for evidence and remaining dependency checks. Proposed defaults below remain open to revision.

## Outcome

Enroll a render computer once. When a job for a new project arrives, the worker discovers that project's configuration, obtains the repository, prepares a compatible checkout, renders, and reports its result without somebody selecting project paths or linking artist tools on that computer.

Adding a project requires one central registration by the studio. It must not require configuration on every worker. Workers continue to process one job at a time.

## Current baseline

- The desktop worker and farm manager live in `src/portable_pipe_tools/apps`. Worker execution, Git updates, path mapping, local spool handling, and API access live in `src/portable_pipe_tools/render_farm`.
- Machine settings currently contain `local_uproject`, `show_render_farm_root`, and `unreal_editor_cmd`. These bind a worker to a single local project and show.
- Cloudflare D1 owns job state and leases. Cloud jobs are materialized into a machine-local spool; Dropbox carries rendered outputs and copies of small logs.
- In the cloud path, the worker claims a job before Git preparation. Current Git preparation updates an existing checkout with `git pull --ff-only`; it does not provision new project checkouts.
- The worker launches Unreal with `DefectRenderFarmExecutor`. Its source and startup import are tracked in the current Unreal project's QuickWidgetTools plugin. The executor itself imports Unreal and standard Python modules. That supports, but does not prove, a checkout-only render setup.
- Project startup also imports render callbacks, including ClickUp reporting. Rendering requirements and optional reporting configuration must be established through a clean-checkout test.
- Existing worker self-update, lease reconciliation, stop controls, render validation, and failure reporting should be retained.

Relevant Unreal integration lives in `F:/Projects/Plugins/QuickWidgetTools/Content/Python`, particularly `publish_render_queue_to_farm.py`, `render_farm_runtime_executor.py`, and `init_unreal.py`. Dispatcher code lives in `cloudflare/defect-farm-api`.

## Scope of the first release

Include automatic project discovery, clone/update, local path resolution, installed-engine selection, preparation progress, recovery, and one-time machine setup. Make the minimum dispatcher and submitter changes required to support these features.

Keep the existing rendering pipeline and Dropbox output transport. Engine installation, arbitrary source builds, simultaneous renders, a farm-manager redesign, and a new output-storage service are separate work. Extracting the executor into its own plugin is optional follow-up work unless the dependency investigation proves it necessary.

## Configuration model

### Machine configuration: once per computer

- Farm enrollment and persistent worker identity, using the existing authentication mechanism initially.
- Credentials with access to the studio's approved project repositories.
- Workspace root and disk budget.
- Storage-root mappings: for example, the studio Dropbox root on this machine.
- Detected compatible Unreal installations, with a manual override when detection cannot identify one.
- Startup, render timeout, and worker update settings.

Target setup experience: run the installer/setup wizard, enroll, choose a workspace drive, and pass the access checks. Detect executable locations and storage roots where possible. A central project definition must never contain another computer's absolute path.

Unattended operation depends on repository credentials and shared-storage permissions covering newly registered projects. If access is granted separately per project today, that provisioning must be automated or performed centrally; the worker cannot infer permission.

### Project configuration: once for the studio

Store versioned project definitions centrally, preferably alongside the existing D1 dispatcher data, with a small administrative import/update interface first. A new management UI is not required for the initial rollout.

Each definition contains:

- Stable `project_id`, display name, and enabled state.
- Approved repository URL and render branch.
- `.uproject` path relative to the checkout root.
- Engine compatibility requirement, including build identity when a version number is insufficient.
- Required render-runtime version and declared plugin/dependency requirements.
- Git LFS/submodule requirements where applicable.
- Logical storage root plus relative show/output location.
- Configuration revision and preparation timeout.

Keep credentials in machine credential storage. Resolve repository locations from approved definitions, rather than accepting arbitrary repository URLs from jobs. Use explicit preparation steps instead of unrestricted project-provided shell commands.

A repository manifest can eventually supply most project metadata. Start with one authoritative central definition to avoid competing sources of configuration; add manifest import when its benefit is clear.

### Job and attempt data

Jobs reference `project_id` and a configuration revision. Preserve the existing descriptive project name for compatibility and display. Record the exact rendered commit, resolved engine, runtime version, and preparation timings on each attempt.

Proposed policy: fetch the latest commit from the configured render branch when preparing an attempt, then keep that commit fixed through the render. Record both the submitted commit, when available, and the rendered commit. Retries can therefore use a newer commit; pinning a whole batch to one revision is a separate policy choice to settle before rollout.

## Worker lifecycle

1. Start, perform the existing worker update check, load machine configuration, and report capabilities.
2. Discover enabled project definitions and determine which projects this machine can prepare. A project need not already be cloned to be eligible.
3. Claim the next eligible job using dispatcher-side filtering. Preserve queue ordering among eligible jobs, single-worker leases, and output-conflict protection.
4. Enter a visible preparation phase. Start renewing the lease immediately and continue throughout cloning, downloading, validation, rendering, and finalization.
5. Resolve a dedicated worker-owned workspace by stable project ID. Clone into a temporary location and promote it only after success. Existing checkouts fetch the configured branch and select the resolved commit without merging development changes.
6. Fetch required LFS objects and submodules, resolve the `.uproject` and engine, validate the render runtime, and map the output location. Check free space before expensive preparation. Never adopt or reset an artist's working checkout automatically.
7. Run Unreal with the resolved project and engine. Keep the existing result/output validation and cloud result reconciliation.
8. Retain the checkout for later jobs. Evict inactive worker-owned caches when required by the disk budget; never remove active checkouts, output folders, or pending result records.

Preparation and rendering need separate timeout budgets. Remote/local stop requests and lease-loss cancellation must work during preparation too. On restart, reconcile prior leases, pending results, and interrupted clone directories before claiming more work.

Classify preparation failures separately from render failures. Missing access, engine, or storage should produce an actionable status and a bounded per-project backoff on that worker, allowing other projects to proceed. Avoid repeated claims of a known incompatible project, avoid applying render-failure blacklists to ordinary setup failures, and re-evaluate after configuration changes or the backoff expires.

## Delivery milestones

### 1. Prove the minimal render environment

Use an isolated fresh checkout and a representative small job. Do not import artist tool links or saved artist settings. Inspect the existing project's engine/plugin availability, LFS content, external asset references, output access, and callbacks.

Run validation first, followed by a real render into an isolated test output directory. Prevent test callbacks from posting to production services. Verify generated files and final worker result, not merely Unreal's exit code.

Deliver a dependency inventory separating required render components, optional post-render integrations, and machine prerequisites. Decide explicitly whether missing optional integrations should warn or fail.

Acceptance: document precisely what a clean machine needs. A checkout-only claim is accepted only after an actual render succeeds.

### 2. Introduce project identity and central definitions

Add a versioned registry and project-definition API. Extend job submission with explicit project identity and dispatcher claims with eligibility filtering. Preserve current output ownership rules using the stable project identity.

Register the existing show as the first project. Restrict new multi-project jobs to V2-capable workers; old workers must not receive jobs for an unconfigured project. Support legacy jobs through an explicit mapping, never a guess based solely on similar names.

Acceptance: two registered projects resolve independently; a worker claims only supported work; old-worker behavior remains valid during rollout.

### 3. Build reusable project preparation

Introduce a project resolver/workspace manager rather than embedding clone logic in the GUI. Return a resolved execution context containing project path, checkout/commit, engine path, output roots, and configuration revision.

Implement clone/update, LFS/submodules as required, engine discovery, dependency checks, cancellation, disk checks, and interrupted-preparation recovery. Keep worker application self-update separate from project repository updates.

Acceptance: first use prepares project A; repeated use updates A; switching to B creates an independent workspace. Missing requirements produce useful errors without damaging other workspaces.

### 4. Connect preparation to leased execution

Refactor `worker.py` and `unreal_runner.py` to consume the resolved execution context. Move per-job path and engine selection out of global GUI settings. Extend lease maintenance and stop handling across the complete attempt lifecycle. Preserve pending result delivery and log publication.

Acceptance: A, B, then A render on one worker without changing settings. A clone taking longer than the normal lease interval retains ownership. Lease loss stops preparation/rendering, and the old attempt cannot finalize a new owner's job.

### 5. Simplify setup and enable unattended operation

Replace the single-project setup fields with enrollment, workspace/storage configuration, and engine detection. Show the current project, preparation stage, failure reason, and last successful check. Provide a setup readiness check and bounded local logs.

Automate startup and recovery under the intended Windows account. Determine whether the supported deployment uses automatic sign-in and a startup task or another execution model; verify GPU rendering and Dropbox access under that exact model before promising reboot-without-intervention behavior.

Acceptance: after reboot, the machine resumes polling and renders without opening settings. Expired credentials or unavailable storage are visible centrally and retried with backoff.

### 6. Pilot and roll out

Deploy to one worker with two projects. Add the second project centrally after machine setup to prove that no local configuration is needed. Test cold preparation, warm updates, project switching, cancellation, network interruption, restart, and disk pressure.

Roll out dispatcher compatibility first, then V2 worker support, then multi-project submission. Keep V1 jobs and existing settings available through the pilot. Rollback disables V2 claims/submission while allowing already leased work to finish or release safely; preserve job data and pending results.

Acceptance: a centrally added project renders end to end without touching the worker, and the existing project's renders still pass their output checks.

## Verification strategy

- Use temporary Git repositories for clone/update, branch selection, interrupted preparation, and workspace-isolation tests.
- Test registry/job compatibility, dispatcher filtering, lease ownership during preparation, preparation backoff, and stale-result rejection.
- Test project-specific path mapping on machines with different drive letters and engine locations.
- Extend existing worker, cloud queue, listener, and settings tests. Run dispatcher migration/API tests for protocol changes.
- Use two real project renders for the integration pilot. Unit tests cannot establish plugin, asset, GPU, or engine readiness.

## Decisions to settle during implementation planning

| Question | Proposed starting point |
|---|---|
| What exists outside each repository? | Establish through milestone 1; do not assume artist setup is required. |
| Which branch should workers render? | Explicit per-project render branch; fetch latest per attempt. |
| Must shots in a batch use the same revision? | Decide before production; retain commit records regardless. |
| How do new projects get repository/storage access? | Studio-managed access configured once per worker where possible. |
| How are engines and binary plugins supplied? | Preinstalled compatible builds for the first release. |
| Does reboot recovery require zero human login? | Treat it as a deployment acceptance test; choose a supported Windows execution model. |
| How much disk may project caches consume? | Machine-level budget, retain recently used projects, evict only inactive worker-owned caches. |

The first implementation task is the isolated clean-checkout render investigation. Its findings determine the preparation requirements before building onboarding or automatic cloning around unverified assumptions.
