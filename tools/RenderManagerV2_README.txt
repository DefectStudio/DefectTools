Render Farm Manager V2

Launch tools\run_manager_v2.bat from the complete Defect Tools checkout.
Python 3.11+ with Tcl/Tk is required. No pip installation is needed.
The root run_manager_v2.bat remains an alias. All company launchers forward
arguments, return the Python exit code, and keep double-click failures visible.

First-time setup on a supervisor's computer:
The administrator supplies the private company-manager.json file, containing
api_url and manager_token for the separate hosted V2 service. Place it at:
%LOCALAPPDATA%\DefectStudio\RenderFarmV2\company-manager.json
Or pass --profile "path\company-manager.json" to the launcher.
The worker and submitter credentials cannot perform manager operations.
Keep this manager profile private; it is not included in the shared repository.

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

Validation, September 21, 2026:
327 manager tests passed. The tools launcher and compatibility aliases opened
the actual GUI and passed hosted V2 database, manager-role, jobs and workers
read checks. A fresh user environment passed when supplied the manager profile.
Missing-profile and missing-Python cases returned clear errors and exit code 1.
No jobs were changed. The supervisor's original error was not available, so its
exact cause has not been confirmed on their computer.
