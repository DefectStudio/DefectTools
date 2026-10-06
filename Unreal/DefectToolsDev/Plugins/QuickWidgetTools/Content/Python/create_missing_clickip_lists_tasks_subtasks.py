"""
Create missing ClickUp sequence lists, shot tasks, and subtasks from Unreal shot folders.

Uses create_missing_shot_and_shot_sequence_folders.py as the Unreal shot scanner.
Returns "true" on success, or "" on failure.
"""

import importlib
import json
import os
import traceback
import urllib.error
import urllib.parse
import urllib.request

import unreal

import create_missing_shot_and_shot_sequence_folders


LOG_PREFIX = "[CreateMissingClickUpListsTasksSubtasks]"
DEFAULT_SHOW_NAME = "S3Bishop"
DEFAULT_SEQUENCES_ROOT = "/Game/_S3Bishop/Sequences"
DEFAULT_LIST_NAME_TEMPLATE = "{sequence_name} Shots"
DEFAULT_SUBTASK_NAMES = ("anim", "fx", "env", "lite")
MAX_TASK_PAGES = 25


def _log(message):
    unreal.log(f"{LOG_PREFIX} {message}")


def _warn(message):
    unreal.log_warning(f"{LOG_PREFIX} Warning: {message}")


def _error(message):
    unreal.log_error(f"{LOG_PREFIX} Error: {message}")


def _as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in ("", "0", "false", "no", "off")


def _norm(value):
    return " ".join(str(value or "").strip().lower().split())


def _upper_filter(values):
    if values is None:
        return set()
    if isinstance(values, str):
        values = values.split(",")
    return set(str(value).strip().upper() for value in values if str(value).strip())


def _request_json(method, url, token, payload=None, timeout=60):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Authorization": token, "Content-Type": "application/json"},
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8")
        return json.loads(text) if text.strip() else {}
    except urllib.error.HTTPError as exc:
        try:
            error_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            error_body = "<could not read error body>"
        raise RuntimeError(
            f"ClickUp HTTPError: {method} {url} | {exc.code} {exc.reason} | {error_body}"
        )
    except urllib.error.URLError as exc:
        raise RuntimeError(f"ClickUp URLError: {method} {url} | {exc}")


def _clickup_data_path():
    return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "clickup_data.json"))


def _load_clickup_data():
    path = _clickup_data_path()
    _log(f"clickup_data.json path: {path}")

    if not os.path.isfile(path):
        raise RuntimeError(f"clickup_data.json does not exist: {path}")

    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    for key in ("user_token", "space_name", "folder_name"):
        if not str(data.get(key, "")).strip():
            raise RuntimeError(f"clickup_data.json is missing {key}.")

    return data


def _folder_name_candidates(folder_name):
    clean = str(folder_name or "").strip()
    if not clean:
        return []

    candidates = [clean]
    lower = clean.lower()
    if lower == "production" or lower.endswith(" production"):
        candidates.append(clean + "s")
    elif lower == "productions" or lower.endswith(" productions"):
        candidates.append(clean[:-1])

    output = []
    seen = set()
    for candidate in candidates:
        key = _norm(candidate)
        if key and key not in seen:
            seen.add(key)
            output.append(candidate)
    return output


def _first_team_id(token):
    data = _request_json("GET", "https://api.clickup.com/api/v2/team", token)
    teams = data.get("teams", [])
    return str(teams[0].get("id", "")).strip() if teams else ""


def _space_id(token, team_id, space_name):
    data = _request_json("GET", f"https://api.clickup.com/api/v2/team/{team_id}/space", token)
    target = _norm(space_name)

    for space in data.get("spaces", []):
        name = str(space.get("name", "")).strip()
        space_id = str(space.get("id", "")).strip()
        _log(f"Space Candidate: {name} | ID: {space_id}")
        if _norm(name) == target:
            return space_id

    return ""


def _folder_id(token, space_id, folder_name):
    data = _request_json("GET", f"https://api.clickup.com/api/v2/space/{space_id}/folder", token)
    targets = set(_norm(name) for name in _folder_name_candidates(folder_name))

    for folder in data.get("folders", []):
        name = str(folder.get("name", "")).strip()
        folder_id = str(folder.get("id", "")).strip()
        _log(f"Folder Candidate: {name} | ID: {folder_id}")
        if _norm(name) in targets:
            return folder_id

    return ""


def _lists_in_folder(token, folder_id):
    data = _request_json("GET", f"https://api.clickup.com/api/v2/folder/{folder_id}/list", token)
    lists = data.get("lists", [])

    for item in lists:
        _log(f"List Candidate: {item.get('name', '')} | ID: {item.get('id', '')}")

    return lists


def _find_list(lists, list_name):
    target = _norm(list_name)
    for item in lists:
        if _norm(item.get("name", "")) == target:
            return {
                "name": str(item.get("name", "")).strip(),
                "id": str(item.get("id", "")).strip(),
            }
    return None


def _ensure_list(token, folder_id, lists, list_name, dry_run):
    existing = _find_list(lists, list_name)
    if existing:
        _log(f"List already exists: {list_name} | ID: {existing['id']}")
        return existing, "exists"

    if dry_run:
        _log(f"DRY RUN: Would create list: {list_name}")
        return None, "would_create"

    payload = {"name": list_name, "content": f"Auto-created shot list for {list_name}."}
    data = _request_json("POST", f"https://api.clickup.com/api/v2/folder/{folder_id}/list", token, payload)
    created = {
        "name": str(data.get("name", list_name)).strip(),
        "id": str(data.get("id", "")).strip(),
    }

    if not created["id"]:
        raise RuntimeError(f"ClickUp created list but no list id was returned: {list_name}")

    lists.append(created)
    _log(f"Created list: {created['name']} | ID: {created['id']}")
    return created, "created"


def _tasks(token, list_id, include_subtasks=False):
    all_tasks = []
    page = 0

    while page < MAX_TASK_PAGES:
        query = urllib.parse.urlencode({
            "archived": "false",
            "subtasks": "true" if include_subtasks else "false",
            "page": str(page),
        })
        url = f"https://api.clickup.com/api/v2/list/{list_id}/task?{query}"
        data = _request_json("GET", url, token)
        tasks = data.get("tasks", [])
        _log(
            f"Task page returned count={len(tasks)}, "
            f"list_id={list_id}, page={page}, subtasks={include_subtasks}"
        )
        all_tasks.extend(tasks)

        if not tasks or bool(data.get("last_page", False)):
            break
        page += 1

    return all_tasks


def _task_parent_id(task):
    parent = task.get("parent")
    if parent is None:
        return ""
    if isinstance(parent, dict):
        return str(parent.get("id", "")).strip()
    return str(parent).strip()


def _find_task(tasks, task_name, parent_id=""):
    target = _norm(task_name)
    parent_id = str(parent_id or "").strip()

    for task in tasks:
        if _norm(task.get("name", "")) != target:
            continue
        if parent_id and _task_parent_id(task) != parent_id:
            continue
        return {
            "name": str(task.get("name", "")).strip(),
            "id": str(task.get("id", "")).strip(),
        }

    return None


def _create_task(token, list_id, task_name, parent_id=""):
    payload = {"name": task_name, "notify_all": False}
    if parent_id:
        payload["parent"] = str(parent_id)

    data = _request_json("POST", f"https://api.clickup.com/api/v2/list/{list_id}/task", token, payload)
    created = {
        "name": str(data.get("name", task_name)).strip(),
        "id": str(data.get("id", "")).strip(),
    }

    if not created["id"]:
        raise RuntimeError(f"ClickUp created task but no task id was returned: {task_name}")

    return created


def _ensure_shot_task(token, list_id, parent_tasks, shot_name, dry_run):
    existing = _find_task(parent_tasks, shot_name)
    if existing:
        _log(f"Shot task already exists: {shot_name} | ID: {existing['id']}")
        return existing, "exists"

    if dry_run:
        _log(f"DRY RUN: Would create shot task: {shot_name}")
        return None, "would_create"

    created = _create_task(token, list_id, shot_name)
    parent_tasks.append(created)
    _log(f"Created shot task: {created['name']} | ID: {created['id']}")
    return created, "created"


def _ensure_subtasks(token, list_id, all_tasks, parent_task, subtask_names, dry_run):
    parent_id = parent_task["id"]
    created = existing = would_create = 0

    for subtask_name in subtask_names:
        found = _find_task(all_tasks, subtask_name, parent_id)
        if found:
            existing += 1
            _log(f"Subtask already exists: {parent_task['name']} -> {subtask_name} | ID: {found['id']}")
            continue

        if dry_run:
            would_create += 1
            _log(f"DRY RUN: Would create subtask: {parent_task['name']} -> {subtask_name}")
            continue

        new_task = _create_task(token, list_id, subtask_name, parent_id)
        all_tasks.append({"name": new_task["name"], "id": new_task["id"], "parent": parent_id})
        created += 1
        _log(f"Created subtask: {parent_task['name']} -> {new_task['name']} | ID: {new_task['id']}")

    return created, existing, would_create


def _collect_shots(sequences_root, only_sequences=None, only_shots=None):
    sequence_filter = _upper_filter(only_sequences)
    shot_filter = _upper_filter(only_shots)

    raw = create_missing_shot_and_shot_sequence_folders._collect_unreal_sequences_and_shots(sequences_root)
    filtered = {}

    for sequence_name, shot_names in sorted(raw.items()):
        sequence_name = str(sequence_name).strip().upper()
        if sequence_filter and sequence_name not in sequence_filter:
            _log(f"Skipping sequence not in only_sequences: {sequence_name}")
            continue

        clean_shots = []
        for shot_name in sorted(shot_names):
            shot_name = str(shot_name).strip().upper()
            if shot_filter and shot_name not in shot_filter:
                continue
            clean_shots.append(shot_name)

        filtered[sequence_name] = clean_shots

    return raw, filtered


def run(
    show_name=DEFAULT_SHOW_NAME,
    dry_run=True,
    sequences_root=DEFAULT_SEQUENCES_ROOT,
    create_file_server_folders_first=False,
    only_sequences=None,
    only_shots=None,
    subtask_names=DEFAULT_SUBTASK_NAMES,
    list_name_template=DEFAULT_LIST_NAME_TEMPLATE,
):
    """Create or preview missing ClickUp shot lists, shot tasks, and subtasks."""
    try:
        importlib.reload(create_missing_shot_and_shot_sequence_folders)

        show_name = str(show_name or DEFAULT_SHOW_NAME).strip()
        dry_run = _as_bool(dry_run)
        sequences_root = str(sequences_root or DEFAULT_SEQUENCES_ROOT).rstrip("/")
        create_file_server_folders_first = _as_bool(create_file_server_folders_first)
        subtask_names = tuple(str(name).strip() for name in (subtask_names or ()) if str(name).strip())

        if not show_name:
            _error("show_name was empty.")
            return ""
        if not subtask_names:
            _error("subtask_names was empty.")
            return ""

        _log("=" * 80)
        _log(f"DRY_RUN: {dry_run}")
        _log(f"SHOW_NAME: {show_name}")
        _log(f"SEQUENCES_ROOT: {sequences_root}")
        _log(f"CREATE_FILE_SERVER_FOLDERS_FIRST: {create_file_server_folders_first}")
        _log(f"ONLY_SEQUENCES: {only_sequences}")
        _log(f"ONLY_SHOTS: {only_shots}")
        _log(f"LIST_NAME_TEMPLATE: {list_name_template}")
        _log(f"SUBTASK_NAMES: {subtask_names}")
        _log("=" * 80)

        if create_file_server_folders_first:
            result = create_missing_shot_and_shot_sequence_folders.run(show_name, dry_run, sequences_root)
            if result != "true":
                _error("File-server folder repair failed. Aborting ClickUp repair.")
                return ""

        data = _load_clickup_data()
        token = str(data.get("user_token", "")).strip()
        space_name = str(data.get("space_name", "")).strip()
        folder_name = str(data.get("folder_name", "")).strip()

        _log("Collecting sequence and shot folders from Unreal.")
        raw_shots, sequence_to_shots = _collect_shots(sequences_root, only_sequences, only_shots)

        if not raw_shots:
            _error(f"No valid sequence folders found under: {sequences_root}")
            return ""
        if not sequence_to_shots:
            _error("No sequences remained after filtering.")
            return ""

        summary = {
            "sequences_found": len(raw_shots),
            "shots_found": sum(len(shots) for shots in raw_shots.values()),
            "sequences_processed": len(sequence_to_shots),
            "shots_processed": sum(len(shots) for shots in sequence_to_shots.values()),
            "lists_existing": 0,
            "lists_created": 0,
            "lists_would_create": 0,
            "tasks_existing": 0,
            "tasks_created": 0,
            "tasks_would_create": 0,
            "subtasks_existing": 0,
            "subtasks_created": 0,
            "subtasks_would_create": 0,
            "failures": 0,
        }

        _log(f"Found sequences: {summary['sequences_found']}")
        _log(f"Found shots: {summary['shots_found']}")
        _log(f"Sequences to process: {summary['sequences_processed']}")
        _log(f"Shots to process: {summary['shots_processed']}")

        team_id = _first_team_id(token)
        if not team_id:
            _error("Could not resolve ClickUp team/workspace id.")
            return ""
        _log(f"Resolved team_id: {team_id}")

        clickup_space_id = _space_id(token, team_id, space_name)
        if not clickup_space_id:
            _error(f"Could not find ClickUp space: {space_name}")
            return ""
        _log(f"Resolved space_id: {clickup_space_id}")

        clickup_folder_id = _folder_id(token, clickup_space_id, folder_name)
        if not clickup_folder_id:
            _error(f"Could not find ClickUp folder: {folder_name}")
            return ""
        _log(f"Resolved folder_id: {clickup_folder_id}")

        lists = _lists_in_folder(token, clickup_folder_id)

        for sequence_name in sorted(sequence_to_shots.keys()):
            shot_names = sorted(sequence_to_shots[sequence_name])
            if not shot_names:
                _warn(f"Skipping sequence with no valid shot folders: {sequence_name}")
                continue

            list_name = str(list_name_template or DEFAULT_LIST_NAME_TEMPLATE).format(sequence_name=sequence_name)
            _log("-" * 80)
            _log(f"Processing sequence: {sequence_name}")
            _log(f"Target ClickUp list: {list_name}")
            _log(f"Shot count: {len(shot_names)}")

            clickup_list, list_status = _ensure_list(token, clickup_folder_id, lists, list_name, dry_run)
            if list_status == "exists":
                summary["lists_existing"] += 1
            elif list_status == "created":
                summary["lists_created"] += 1
            else:
                summary["lists_would_create"] += 1

            if clickup_list is None:
                for shot_name in shot_names:
                    summary["tasks_would_create"] += 1
                    _log(f"DRY RUN: Would create shot task in new list: {shot_name}")
                    for subtask_name in subtask_names:
                        summary["subtasks_would_create"] += 1
                        _log(f"DRY RUN: Would create subtask: {shot_name} -> {subtask_name}")
                continue

            list_id = clickup_list["id"]
            parent_tasks = _tasks(token, list_id, include_subtasks=False)
            all_tasks = _tasks(token, list_id, include_subtasks=True)

            for shot_name in shot_names:
                try:
                    shot_task, task_status = _ensure_shot_task(token, list_id, parent_tasks, shot_name, dry_run)
                    if task_status == "exists":
                        summary["tasks_existing"] += 1
                    elif task_status == "created":
                        summary["tasks_created"] += 1
                    else:
                        summary["tasks_would_create"] += 1

                    if shot_task is None:
                        for subtask_name in subtask_names:
                            summary["subtasks_would_create"] += 1
                            _log(f"DRY RUN: Would create subtask: {shot_name} -> {subtask_name}")
                        continue

                    created, existing, would_create = _ensure_subtasks(
                        token, list_id, all_tasks, shot_task, subtask_names, dry_run
                    )
                    summary["subtasks_created"] += created
                    summary["subtasks_existing"] += existing
                    summary["subtasks_would_create"] += would_create

                except Exception as exc:
                    summary["failures"] += 1
                    _error(f"Failed processing shot: {sequence_name}/{shot_name} | {exc}")
                    _error(traceback.format_exc())

        _log("=" * 80)
        _log("SUMMARY")
        for key in (
            "sequences_found", "shots_found", "sequences_processed", "shots_processed",
            "lists_existing", "lists_created", "lists_would_create",
            "tasks_existing", "tasks_created", "tasks_would_create",
            "subtasks_existing", "subtasks_created", "subtasks_would_create", "failures",
        ):
            _log(f"{key}: {summary[key]}")
        _log("=" * 80)

        if summary["failures"]:
            _error("ClickUp repair completed with failures.")
            return ""

        if dry_run:
            _log("Dry run complete. Run again with dry_run=False to create missing ClickUp items.")
        else:
            _log("ClickUp repair complete. Failures: 0")

        return "true"

    except Exception as exc:
        _error(str(exc))
        _error(traceback.format_exc())
        return ""
