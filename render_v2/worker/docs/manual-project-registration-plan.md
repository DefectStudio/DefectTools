# Manual project registration for Render Worker V2

**Naming update:** [Dropbox projects](dropbox-projects.md) is the source of project
names for both V2 GUIs. Listing Dropbox show names does not register local Unreal
checkouts automatically or enable downloads.

September 10, 2026. Proposed strategy following supervisor feedback. This documents the next implementation; the current EXE still performs automatic discovery and clone fallback.

## Confirmed direction

- Remove automatic project discovery, including Unreal Editor metadata, Epic Launcher metadata, drive scans, and remembered discovery locations.
- Make project downloading optional through a checkbox, off by default.
- Let a person explicitly add the projects a particular worker can render.

## Recommended setup experience

Keep the shared project catalog as the studio's definitions of projects and render settings. Add a separate **Projects on this worker** list containing only projects a person has registered on this computer. A catalog entry alone does not authorize the worker to use or download a project.

**Add project** has three controls:

1. **Project:** select the studio project, such as Bishop.
2. **Local project:** browse directly to its `.uproject` file. Record that exact location; do not search its parent directories or other disks for alternatives.
3. **Allow project downloads:** unchecked initially for every project. When checked, also allow choosing a destination for a new download.

On save, validate the selected project and show a useful status: **Ready**, **Needs download**, **Missing engine**, or **Needs attention**, with a reason. Registering a project does not start a render. Downloading is a separate action, or happens before a job when explicitly enabled for that registered project.

For Bishop on this computer, the initial setup would simply be: select Bishop, browse to `F:\Projects\s3bishop.uproject`, and leave downloading off. Repeat once for each project this worker should support.

## Local copies and Git checkouts

Support two ways of supplying a project through the same registration flow:

- An existing Git checkout, selected explicitly by the operator.
- A complete project folder copied onto the machine, containing the required assets and plugins. This local-copy mode must work without a `.git` directory or Git installation when downloading is disabled.

The worker checks the registered `.uproject`, engine compatibility, required runtime dependencies, and job inputs. Validation is limited to the selected project. Installed-engine detection can remain; it does not discover project folders.

A copied folder must contain real assets, not Git LFS pointer placeholders. Validation should report missing inputs and render failures clearly without introducing a full asset hash scan. The worker's minimal Unreal runtime still needs a writable installation location for the selected project.

For a local copy, report the render source as a local snapshot; do not invent a Git revision. A Git checkout can report its local revision without fetching. Copy/update project files while the worker is idle; external copy tools cannot be made to honor the worker's lock automatically.

## Download policy to confirm

The outstanding question is whether downloading-off also disables updates to an existing Git checkout.

**Recommendation:** unchecked means no clone, fetch, pull, or LFS download. Render the supplied local files. Checked permits downloads and Git updates for that specific registered project. If this recommendation is accepted, label the checkbox **Allow project downloads and updates** so its effect is explicit.

The alternative is to disable only new clones while retaining Git pull for existing checkouts. That behavior needs explicit agreement because it still downloads files and modifies the local checkout.

When downloading is permitted, validate the configured remote and branch, preserve tracked edits, and fail on conflicts. Clone shallowly into a worker-owned destination. Never replace or repurpose a nonempty arbitrary folder. A copied project without Git metadata needs a separate empty clone destination to use Git downloading.

## Job eligibility

Before a direct render, look up the job's project ID in this worker's registrations. If it is absent, return **Project is not configured on this worker**. If its path is missing and downloads are disabled, return **Local project is missing**. Neither condition triggers a scan or clone.

When cloud leasing is connected later, report registered project IDs and readiness to the dispatcher. A worker should claim jobs only for projects it can render or is explicitly permitted to prepare. Jobs for unregistered projects remain available to other workers. Recheck eligibility before execution because folders, engine installations, and permissions can change after registration.

## Implementation sequence

1. Add persistent per-project machine registrations: project ID, explicit `.uproject` location or download destination, and a download flag defaulting to false. Keep credentials out of these records. Do not convert discovered-project caches into registrations automatically.
2. Replace discovery in project acquisition with registration lookup. Enforce the download policy in the common preparation layer so GUI and CLI obey the same rules. Support local folders without Git in local-only mode.
3. Add the worker's project list, Add/Edit/Remove controls, status validation, and the download checkbox. Removing a registration leaves its project files on disk. Separate the studio catalog from this worker's eligible projects.
4. Adapt runtime installation, locking, and result receipts for copied projects without Git. Keep existing protection against simultaneous worker use of the same project.
5. Test explicit local registration, unregistered/missing project rejection, zero discovery calls, zero project network operations when disabled, deliberate download opt-in, and copied-project rendering. Repeat Bishop ZZZ850 through the EXE with downloads off and document that path.
6. Rebuild the EXE and update setup instructions. Cloud capability reporting and leasing follow as their own integration step.

The smallest first delivery is the local project list with **Add project → choose `.uproject` → validate → render**, plus the explicit download gate. A fleet-wide installer or project-copying system is not required for that delivery.
