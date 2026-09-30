Render Farm Manager V2

Launch tools\run_manager_v2.bat from the complete Defect Tools checkout.
Python 3.11+ with Tcl/Tk is required. No pip installation is needed.
The root run_manager_v2.bat remains an alias. All company launchers forward
arguments, return the Python exit code, and keep double-click failures visible.

Company connection is ready to use:
render_v2\manager\company-manager.json ships in the checkout with api_url and
manager_token for the separate hosted V2 service. No credential setup is needed.
Anyone with the checkout can perform V2 manager operations with this profile.
The worker and submitter credentials remain separate.

Optional connection overrides, in order of precedence:
1. --profile "path\company-manager.json" passed to the launcher.
2. An existing %LOCALAPPDATA%\DefectStudio\RenderFarmV2\company-manager.json.
3. The bundled render_v2\manager\company-manager.json.
An invalid override fails visibly rather than silently using another profile.

Select the Dropbox project root when prompted. The manager uses company V2 SQL.
Settings: %LOCALAPPDATA%\DefectStudio\RenderFarmManagerV2\manager.json
Log: %LOCALAPPDATA%\DefectStudio\RenderFarmManagerV2\logs\manager.log
Older source settings are copied on first GUI launch if no per-user settings exist.

Read-only startup check (from the Defect Tools root):
tools\run_manager_v2.bat --self-test "%TEMP%\manager-v2-check.json"
This verifies database health, manager authentication, reading jobs/workers, and
the actual GUI. It does not change jobs or start renders. The report includes
any startup failure. Missing Python/Tk is reported directly by the batch file.

On failure, send the console error or manager.log to the administrator. Do not
send the credential file along with diagnostic logs.

Validation, September 30, 2026:
330 manager tests passed, including bundled-profile startup, per-user profile
precedence, explicit overrides, missing profiles, and V1/worker-profile rejection.
The tools launcher passed from a fresh user environment with no per-user
credential file. The bundled profile authenticated as manager, passed hosted V2
database/jobs/workers read checks, and opened the actual GUI. No jobs were changed.
