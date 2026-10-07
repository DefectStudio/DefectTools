# Update Quick Widget Tools

Double-click `UpdateQuickWidgetTools.bat`, choose a project's `.uproject` with **Browse**, then click **INSTALL**. You can also paste a project folder or `.uproject` path into the address box. Close that project's Unreal editor first.

The launcher and `UpdateQuickWidgetTools.ps1` must stay together in the DefectTools checkout's `tools` folder. The source is always that checkout's local `Unreal/DefectToolsDev/Plugins/QuickWidgetTools` folder, including its packaged binaries. Update/download the source checkout first when you want a newer version; the tool does not fetch or build the development plugin.

The selected project can be on any drive. Its destination is the ordinary `Plugins/QuickWidgetTools` folder beside the selected `.uproject`, as in ChristmasFuneral, Spectrum, and IronWidow. The tool backs up the previous plugin, replaces it with the local source, and commits only the plugin update and any required plugin-specific Git attributes. It uploads Git LFS files and pushes to the selected project's current branch/upstream. **Green Done means the copied files and remote commit were verified.** An already-current installation verifies the remote without making another commit.

Requirements: Windows PowerShell 5.1, Git for Windows and Git LFS available on PATH, a configured Git identity and upstream branch, working remote credentials, and writable `I:\AICache`. The packaged plugin must support the destination project's Unreal engine version/build. This tool copies the package; it does not compile it or change engine settings.

Submit unrelated project edits and staged files in Anchorpoint before installing. Clean incoming commits are fast-forwarded automatically. Existing unpublished commits must be synchronized first, so the updater cannot accidentally publish other work. Local plugin edits are preserved in the backup before replacement.

Backups, logs, source snapshots, and recovery receipts are stored under `I:\AICache\QuickWidgetToolsUpdater`. The window remembers the last selected project there too. If installation fails before creating a commit, the tool restores its pre-install plugin and Git metadata. A failed incoming synchronization reports any remaining changed project files for review in Anchorpoint. If an upload/push fails, the local update commit is kept; retry **INSTALL** with the same source/project to push it. A changed source or unexpected commit requires review in Anchorpoint, and the log explains the problem.

Keep the window open until it finishes. Avoid simultaneous Git operations or plugin editing during installation.

## Developer checks

Run the isolated integration suite from the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\tests\Test-UpdateQuickWidgetTools.ps1
```

The suite creates disposable repositories and local bare remotes under `I:\AICache\QuickWidgetToolsUpdater-tests`; it does not install into production projects or contact GitHub. Do not run an installation at the same time, because the updater deliberately permits only one operation at a time.

To check the Browse dialog and empty-input handling:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\tests\Test-UpdateQuickWidgetToolsGui.ps1
```

This check opens and automatically cancels the test process's file picker, then verifies that empty INSTALL shows a clear message without starting a worker. Its files stay under `I:\AICache\QuickWidgetToolsUpdater-gui-tests`.
