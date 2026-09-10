# Dropbox projects in V2

Project identity is the exact folder name in `<Dropbox root>/<show>/renderFarm`.
For example, `s3bishop` stays `s3bishop`; `Development` keeps its capital D.
No slug, Unreal filename, or SQL-created identifier replaces it.

Both V2 GUIs list all immediate folders under the selected Dropbox root,
including shows without jobs or a renderFarm directory. Existing renderFarm
directory names preserve their casing; otherwise the expected path is
`<show>/renderFarm`. Listing a show does not mean it is ready to render:
the worker still checks its registered local project and renderFarm folder.
This is a read-only directory listing:
it creates no folders, downloads nothing, and never searches for local Unreal
checkouts. New show folders become available on refresh.

## Manager

Run `F:/Defect Tools/run_manager_v2.bat`. Select the Dropbox root on first
startup, or use **File > Change Dropbox Folder...**. Its saved root supplies the
project filter; **All Projects** continues to show jobs outside the current
folder list. The create/edit project registry UI has been removed. Existing
jobs and their IDs are not rewritten.

The local SQL registry prototype and its migration remain for historical
compatibility with the already-created local database. Neither V2 GUI reads or
writes that registry. No production database change is required.

## Worker

Run `F:/Defect Tools/run_worker_v2.bat`. Under **Projects on this worker**,
browse once to the Dropbox root containing the show folders. This root persists
in V2 settings. **Refresh** updates the available names; opening Add/Edit also
refreshes them.

Click **+**, select the Dropbox project, then browse to its local `.uproject`.
The exact project name and renderFarm path fill automatically. **Allow project
downloads** remains unchecked by default. Click **OK** to save the registration;
double-click to edit, or **−** to remove only the registration.

An unavailable Dropbox root displays an error and does not erase registrations.
Existing entries can still be edited offline. Older IDs are preserved until a
person explicitly selects a Dropbox show in the editor; nothing silently remaps
existing jobs or registrations.

The V2 worker can claim jobs for ready registered projects or render a selected
job file. Updating the packaged EXE remains separate work. V1 and the live
service remain independently usable.
