# Registering projects

The catalog is studio configuration. A machine selects its catalog location once; the worker reloads it before each job. Use a shared file or HTTPS URL so adding a project does not require editing each computer. The bundled `projects.json` is the local development catalog.

Each entry has a stable `project_id`, a `repository`, an explicit `branch`, and a checkout-relative `uproject` path. Increase `revision` when changing the definition. Enable `lfs` and `submodules` when required. Initial clones contain only the latest commit of the selected branch; later fast-forward pulls download changes since that tip. LFS fetches the current revision's assets, without a separate full hash scan. Submodules use their project-pinned revisions with shallow initialization.

Keep Git authentication in the computer's credential manager or SSH configuration. Repository URLs in the catalog must not contain passwords or HTTPS usernames/tokens. Changing a project's repository does not silently replace an existing managed checkout; use a new project ID or resolve the old workspace deliberately.

## Shot lookup

The `render` object describes Unreal asset paths. Templates support `{shot}` for the canonical shot name and `{prefix}` for its first underscore-delimited segment. `shot_aliases` maps convenient names such as `ZZZ850` to `ZZZ_000_0850`.

- `sequence`: the Level Sequence object path.
- `graph`: the Movie Render Graph object path.
- `level`: an optional explicit level object path or template.
- `shot_data`: a shot data asset path used when `level` is omitted.
- `level_property`: the shot data property holding the associated level; defaults to `AssociatedLevel`.

The pilot expects the graph to expose `OutputDirectory` and `FileNameFormat`, allowing the worker to redirect EXR output to an isolated run folder. It also sets `EXR`, `MP4`, `Hero`, and `MP4FileNameFormat` when those variables exist. Project graph script callbacks are disabled for these development renders. Projects with other rendering conventions need an adapter before they can use this direct-shot path.

## Machine settings

The UI saves `LocalSaveFiles/worker_v2.json`. The CLI accepts the same file with `--settings`; explicit command-line paths override saved values.

```json
{
  "catalog": "F:/StudioConfig/render-projects.json",
  "workspace_root": "F:/RenderWorkerWorkspace",
  "output_root": "F:/RenderWorkerWorkspace/renders",
  "preparation_timeout_seconds": 7200,
  "lfs_cache_roots": []
}
```

An optional cache root points to an existing Git LFS `objects` directory, not an artist project folder. Objects are reused by hardlink where possible, or copied when necessary. A machine with no cache downloads them through Git LFS. Enough free space is required for the project files and any missing cache objects.

Every preparation attempt rereads the current Windows user's Unreal and Epic metadata, including when a worker-owned checkout already exists. Discovery proceeds in this order:

1. Unreal Editor's recent `.uproject` files, newest first across engine versions. Nested project files are traced back to their Git repository root.
2. Project folders recorded by Unreal Editor and Epic Launcher.
3. The worker's previously remembered location and configured/common project folders.
4. The worker-owned checkout, or a new shallow clone if no suitable checkout exists.

Unreal's metadata is read from `%LOCALAPPDATA%/UnrealEngine/*/Saved/Config/*/EditorSettings.ini`, using `RecentlyOpenedProjectFiles` and `CreatedProjectPaths` in `[/Script/UnrealEd.EditorSettings]`. Epic Launcher's folder list comes from `%LOCALAPPDATA%/EpicGamesLauncher/Saved/Config/*/GameUserSettings.ini`, using `CreatedProjectPaths` in `[Launcher]`. Both Windows and WindowsEditor config folders are supported. These files are read only; stale or malformed entries are skipped. The Launcher records search folders, so those locations still need to be searched for repositories.

Folder searches cover up to four directory levels with a 5,000-directory bound per pass. Every candidate must match the catalog's origin, project file, and branch before reuse. A discovered path is remembered in `discovered-projects.json`. Supply `discovery_roots` for other fallback locations; an empty list disables the general folder scan while Unreal/Epic metadata and remembered paths remain active.

An existing checkout is pulled with `--ff-only` and used in place. Its tracked edits and local commits are preserved by stopping the job; untracked files are left alone. The worker installs its small runtime plugin beside the `.uproject` and adds it to Git's local exclude file. A lock in the Git metadata is held through preparation and rendering.

When no suitable repository is found, the worker prepares a shallow clone in a private staging folder and publishes it to `projects/<project_id>` once preparation succeeds. It holds that project's lock through rendering. An interrupted stage remains available for retry; local edits or an ownership mismatch produce an error instead of being overwritten.
