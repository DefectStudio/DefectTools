"""
Collect ClickUp assignees from a parent task and its subtasks.

Used by send_clickup_post_render.py to decide who should be @mentioned when a render completes.
Returns a list of dictionaries with stable user ids and source task context.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

try:
    import unreal
except Exception:
    unreal = None


LOG_PREFIX = "[ClickUpTasksGetAllAssignee]"
CLICKUP_API_ROOT = "https://api.clickup.com/api/v2"


def _log(message):
    if unreal:
        unreal.log(f"{LOG_PREFIX} {message}")
    else:
        print(f"{LOG_PREFIX} {message}")


def _warn(message):
    if unreal:
        unreal.log_warning(f"{LOG_PREFIX} Warning: {message}")
    else:
        print(f"{LOG_PREFIX} Warning: {message}")


def _error(message):
    if unreal:
        unreal.log_error(f"{LOG_PREFIX} Error: {message}")
    else:
        print(f"{LOG_PREFIX} Error: {message}")


def _request_json(url, api_token, timeout=30):
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": api_token,
            "Content-Type": "application/json",
        },
        method="GET",
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
        raise RuntimeError(f"ClickUp HTTPError: GET {url} | {exc.code} {exc.reason} | {error_body}")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"ClickUp URLError: GET {url} | {exc}")


def _get_task(api_token, task_id, include_subtasks=False):
    clean_task_id = str(task_id or "").strip()
    if not clean_task_id:
        return {}

    query = urllib.parse.urlencode({
        "include_subtasks": "true" if include_subtasks else "false",
    })
    url = f"{CLICKUP_API_ROOT}/task/{clean_task_id}?{query}"
    return _request_json(url, api_token)


def _task_id(task):
    if isinstance(task, dict):
        return str(task.get("id", "")).strip()
    return str(task or "").strip()


def _task_name(task):
    if isinstance(task, dict):
        return str(task.get("name", "")).strip()
    return ""


def _user_id(user):
    if not isinstance(user, dict):
        return ""

    for key in ("id", "user_id", "userid", "member_id"):
        value = str(user.get(key, "")).strip()
        if value:
            return value

    return ""


def _user_display_name(user):
    if not isinstance(user, dict):
        return ""

    for key in ("username", "name", "display_name", "email"):
        value = str(user.get(key, "")).strip()
        if value:
            return value

    return ""


def _add_assignee(result_by_id, user, source_task):
    user_id = _user_id(user)
    if not user_id:
        return

    task_id = _task_id(source_task)
    task_name = _task_name(source_task)

    if user_id not in result_by_id:
        result_by_id[user_id] = {
            "id": user_id,
            "name": _user_display_name(user),
            "email": str(user.get("email", "")).strip() if isinstance(user, dict) else "",
            "source_tasks": [],
        }

    source_info = {
        "task_id": task_id,
        "task_name": task_name,
    }

    if source_info not in result_by_id[user_id]["source_tasks"]:
        result_by_id[user_id]["source_tasks"].append(source_info)


def _collect_assignees_from_task(result_by_id, task):
    if not isinstance(task, dict):
        return

    for user in task.get("assignees", []) or []:
        _add_assignee(result_by_id, user, task)


def _subtasks_from_task(task):
    if not isinstance(task, dict):
        return []

    subtasks = task.get("subtasks", []) or []
    if not isinstance(subtasks, (list, tuple)):
        return []

    return list(subtasks)


def get_all_assignees(api_token, task_id, include_subtasks=True, fetch_subtask_details=True):
    """
    Return unique ClickUp assignees from the parent task and, optionally, its subtasks.

    Args:
        api_token (str): ClickUp API token.
        task_id (str): Parent task id.
        include_subtasks (bool): Include direct subtasks in the scan.
        fetch_subtask_details (bool): Fetch each subtask detail page for complete assignee data.

    Returns:
        list[dict]: [{"id": "94424693", "name": "...", "email": "...", "source_tasks": [...]}]
    """
    clean_token = str(api_token or "").strip()
    clean_task_id = str(task_id or "").strip()

    if not clean_token:
        _error("api_token was empty.")
        return []

    if not clean_task_id:
        _error("task_id was empty.")
        return []

    result_by_id = {}
    fetched_task_ids = set()

    _log(f"Fetching parent task assignees: task_id={clean_task_id}")
    parent_task = _get_task(clean_token, clean_task_id, include_subtasks=include_subtasks)
    fetched_task_ids.add(clean_task_id)

    _collect_assignees_from_task(result_by_id, parent_task)

    if include_subtasks:
        subtasks = _subtasks_from_task(parent_task)
        _log(f"Found subtask reference count: {len(subtasks)}")

        for subtask in subtasks:
            _collect_assignees_from_task(result_by_id, subtask)

        if fetch_subtask_details:
            for subtask in subtasks:
                subtask_id = _task_id(subtask)
                if not subtask_id or subtask_id in fetched_task_ids:
                    continue

                fetched_task_ids.add(subtask_id)
                try:
                    _log(f"Fetching subtask assignees: task_id={subtask_id}")
                    subtask_detail = _get_task(clean_token, subtask_id, include_subtasks=False)
                    _collect_assignees_from_task(result_by_id, subtask_detail)
                except Exception as exc:
                    _warn(f"Could not fetch subtask detail for {subtask_id}: {exc}")

    results = list(result_by_id.values())
    results.sort(key=lambda item: str(item.get("name") or item.get("id") or "").lower())

    _log(f"Unique assignee count: {len(results)}")
    for item in results:
        _log(f"Assignee Candidate: {item.get('name', '')} | ID: {item.get('id', '')}")

    return results


def run(api_token, task_id, include_subtasks=True, fetch_subtask_details=True):
    return get_all_assignees(
        api_token=api_token,
        task_id=task_id,
        include_subtasks=include_subtasks,
        fetch_subtask_details=fetch_subtask_details,
    )
