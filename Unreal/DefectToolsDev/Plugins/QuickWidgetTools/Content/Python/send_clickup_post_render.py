import importlib
import json
import mimetypes
import os
import re
import uuid
import urllib.error
import urllib.parse
import urllib.request

import unreal

try:
    import clickup_tasks_get_all_assignee
except Exception:
    clickup_tasks_get_all_assignee = None


@unreal.uclass()
class MRGSendClickUpPostRender(unreal.MovieGraphScriptBase):
    LOG_PREFIX = "[SendClickUpPostRender]"

    CLICKUP_DATA_FILE_NAME = "clickup_data.json"
    OUTPUT_DIRECTORY_VARIABLE_NAME = "OutputDirectory"
    FILE_NAME_VARIABLE_NAME = "FileNameFormat"
    MP4_FILE_NAME_VARIABLE_NAME = "MP4FileNameFormat"

    VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}
    IMAGE_EXTENSIONS = {".exr", ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
    MAX_TASK_PAGES = 25

    @unreal.ufunction(override=True)
    def on_job_finished(self, in_job_copy, in_output_data):
        super().on_job_finished(in_job_copy, in_output_data)
        return self.run_post_render(in_job_copy, in_output_data)

    def run_post_render(self, in_job_copy, in_output_data):
        self._log("on_job_finished")

        if not self._get_render_success(in_output_data):
            self._log_warning("Render was not successful. Skipping ClickUp post-render actions.")
            return False

        config = self._load_clickup_data()
        if not config:
            return False

        token = str(config.get("user_token", "")).strip()
        space_name = str(config.get("space_name", "")).strip()
        folder_name = str(config.get("folder_name", "")).strip()
        list_name = str(config.get("list_name", "")).strip()
        supervisors = config.get("supervisors", [])

        if not token:
            self._log_error("clickup_data.json is missing user_token.")
            return False
        if not space_name:
            self._log_error("clickup_data.json is missing space_name.")
            return False
        if not folder_name:
            self._log_error("clickup_data.json is missing folder_name.")
            return False

        output_directory = self._resolve_job_variable_string(in_job_copy, self.OUTPUT_DIRECTORY_VARIABLE_NAME)
        file_name_format = self._resolve_job_variable_string(in_job_copy, self.FILE_NAME_VARIABLE_NAME)
        mp4_file_name_format = self._resolve_job_variable_string(in_job_copy, self.MP4_FILE_NAME_VARIABLE_NAME)

        self._log(f"Resolved OutputDirectory: {output_directory!r}")
        self._log(f"Resolved FileNameFormat: {file_name_format!r}")
        self._log(f"Resolved MP4FileNameFormat: {mp4_file_name_format!r}")

        all_file_paths = self._collect_output_file_paths(in_output_data)
        video_files = self._filter_video_files(all_file_paths)
        image_files = self._filter_image_files(all_file_paths)

        self._log(f"Collected output file path count: {len(all_file_paths)}")
        self._log(f"Collected video file count: {len(video_files)}")
        self._log(f"Collected image file count: {len(image_files)}")

        shot_name = self._derive_shot_name(mp4_file_name_format, file_name_format, output_directory, video_files)
        if not shot_name:
            self._log_error("Could not derive shot_name from MRG variables or output files.")
            return False
        self._log(f"Resolved shot_name: {shot_name}")

        mp4_file_path = self._build_mp4_file_path(output_directory, mp4_file_name_format, shot_name, video_files)
        if not mp4_file_path:
            self._log_error("Could not build MP4 file path from MRG variables or output files.")
            return False
        self._log(f"Resolved MP4 path: {mp4_file_path}")

        if not os.path.isfile(mp4_file_path):
            self._log_error(f"MP4 file does not exist: {mp4_file_path}")
            return False

        exr_location_path = self._build_exr_location_path(output_directory, image_files)
        self._log(f"Resolved EXR location path: {exr_location_path}")

        team_id = self._find_first_team_id(token)
        if not team_id:
            self._log_error("Could not resolve ClickUp team/workspace ID.")
            return False
        self._log(f"Resolved team_id: {team_id}")

        space_id = self._find_space_id_by_name(token, team_id, space_name)
        if not space_id:
            self._log_error(f"Could not find space by name: {space_name}")
            return False
        self._log(f"Resolved space_id: {space_id}")

        folder_id = self._find_folder_id_by_name_with_fallbacks(token, space_id, folder_name)
        if not folder_id:
            self._log_error(f"Could not find folder by name: {folder_name}")
            return False
        self._log(f"Resolved folder_id: {folder_id}")

        task_id = self._resolve_task_id(token, folder_id, list_name, shot_name)
        if not task_id:
            self._log_error(f"Could not find task by name: {shot_name}")
            return False
        self._log(f"Resolved task_id: {task_id}")

        mention_user_ids = self._resolve_comment_mention_user_ids(token, task_id, supervisors)

        if not self._upload_attachment(token, task_id, mp4_file_path):
            self._log_error("Attachment upload failed.")
            return False

        if not self._post_render_complete_comment(
            api_token=token,
            task_id=task_id,
            shot_name=shot_name,
            mention_user_ids=mention_user_ids,
            exr_location_path=exr_location_path,
            mp4_file_path=mp4_file_path,
        ):
            self._log_error("Render-complete comment failed.")
            return False

        self._log("ClickUp post-render actions completed successfully.")
        return True

    # -------------------------------------------------------------------------
    # Config / render output
    # -------------------------------------------------------------------------

    def _get_clickup_data_file_path(self):
        module_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.normpath(os.path.join(module_dir, self.CLICKUP_DATA_FILE_NAME))

    def _load_clickup_data(self):
        path = self._get_clickup_data_file_path()
        self._log(f"clickup_data.json path: {path}")
        if not os.path.isfile(path):
            self._log_error(f"clickup_data.json does not exist: {path}")
            return None
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            self._log("Loaded clickup_data.json successfully.")
            return data
        except Exception as exc:
            self._log_error(f"Failed to read clickup_data.json: {exc}")
            return None

    def _get_render_success(self, in_output_data):
        for attr_name in ("success", "b_success"):
            try:
                return bool(getattr(in_output_data, attr_name))
            except Exception:
                pass
        return False

    def _collect_output_file_paths(self, in_output_data):
        collected = []
        try:
            graph_data = in_output_data.graph_data
        except Exception as exc:
            self._log_warning(f"Failed while reading graph_data: {exc}")
            return collected

        try:
            for render_output_data in graph_data:
                self._collect_from_render_output_data(render_output_data, collected)
        except Exception as exc:
            self._log_warning(f"Failed while collecting from graph_data: {exc}")

        return self._dedupe_paths(collected)

    def _collect_from_render_output_data(self, render_output_data, collected):
        try:
            render_layer_data = getattr(render_output_data, "render_layer_data", None)
            if render_layer_data is None:
                return

            if hasattr(render_layer_data, "items"):
                for _identifier_data, output_info in render_layer_data.items():
                    self._collect_from_output_info(output_info, collected)
                return

            for identifier_data in render_layer_data:
                output_info = render_layer_data[identifier_data]
                self._collect_from_output_info(output_info, collected)
        except Exception as exc:
            self._log_warning(f"Failed while collecting from render_layer_data: {exc}")

    def _collect_from_output_info(self, output_info, collected):
        try:
            for file_path in getattr(output_info, "file_paths", []) or []:
                collected.append(str(file_path))
        except Exception as exc:
            self._log_warning(f"Failed while collecting from output_info: {exc}")

    def _filter_video_files(self, all_file_paths):
        return self._filter_existing_files_by_extension(all_file_paths, self.VIDEO_EXTENSIONS)

    def _filter_image_files(self, all_file_paths):
        return self._filter_existing_files_by_extension(all_file_paths, self.IMAGE_EXTENSIONS)

    def _filter_existing_files_by_extension(self, all_file_paths, extensions):
        output = []
        for file_path in all_file_paths:
            normalized_path = os.path.normpath(str(file_path or ""))
            if not normalized_path:
                continue
            if os.path.splitext(normalized_path)[1].lower() not in extensions:
                continue
            if not os.path.isfile(normalized_path):
                continue
            output.append(normalized_path)
        output.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return self._dedupe_paths(output)

    def _dedupe_paths(self, paths):
        deduped = []
        seen = set()
        for path in paths:
            normalized = os.path.normpath(str(path))
            if normalized not in seen:
                seen.add(normalized)
                deduped.append(normalized)
        return deduped

    def _derive_shot_name(self, mp4_file_name_format, file_name_format, output_directory, video_files):
        candidates = [mp4_file_name_format, file_name_format, os.path.basename(str(output_directory or "").rstrip("/\\"))]
        for video_file in video_files:
            candidates.append(os.path.basename(video_file))
            candidates.append(os.path.splitext(os.path.basename(video_file))[0])

        for candidate in candidates:
            shot_name = self._extract_shot_name(candidate)
            if shot_name:
                return shot_name
        return ""

    def _extract_shot_name(self, text):
        match = re.search(r"([A-Za-z0-9]+_\d{3}_\d{4,})", str(text or ""))
        return match.group(1).upper() if match else ""

    def _build_mp4_file_path(self, output_directory, mp4_file_name_format, shot_name, video_files):
        clean_output_directory = self._normalize_folder_path(output_directory)
        clean_mp4_file_name_format = str(mp4_file_name_format or "").strip()

        if clean_output_directory and clean_mp4_file_name_format:
            mp4_root = os.path.dirname(clean_output_directory)
            candidate = os.path.normpath(os.path.join(mp4_root, f"{clean_mp4_file_name_format}.mp4"))
            if os.path.isfile(candidate):
                return candidate

        shot_name_upper = str(shot_name or "").upper()
        for video_file in video_files:
            if shot_name_upper and shot_name_upper in os.path.basename(video_file).upper():
                return video_file
        if video_files:
            return video_files[0]

        return ""

    def _build_exr_location_path(self, output_directory, image_files):
        clean_output_directory = self._normalize_folder_path(output_directory)
        if clean_output_directory:
            return os.path.normpath(clean_output_directory)
        if image_files:
            return os.path.normpath(os.path.dirname(image_files[0]))
        return ""

    # -------------------------------------------------------------------------
    # ClickUp lookup
    # -------------------------------------------------------------------------

    def _resolve_task_id(self, api_token, folder_id, list_name, task_name):
        clean_list_name = str(list_name or "").strip()
        clean_task_name = str(task_name or "").strip()
        if not clean_task_name:
            self._log_error("Cannot resolve task id because task_name is empty.")
            return ""

        if clean_list_name:
            self._log(f"clickup_data.json has list_name={clean_list_name!r}. Searching only that list.")
            list_id = self._find_list_id_by_name(api_token, folder_id, clean_list_name)
            if not list_id:
                self._log_error(f"Could not find ClickUp list by name: {clean_list_name}")
                return ""
            self._log(f"Resolved list_id: {list_id}")
            return self._find_task_id_by_name(api_token, list_id, clean_task_name)

        self._log(f"clickup_data.json has no list_name. Searching every list in folder for task: {clean_task_name}")
        return self._find_task_id_by_name_in_all_folder_lists(api_token, folder_id, clean_task_name)

    def _find_first_team_id(self, api_token):
        data = self._request_json("https://api.clickup.com/api/v2/team", api_token)
        teams = data.get("teams", [])
        return str(teams[0].get("id", "")).strip() if teams else ""

    def _find_space_id_by_name(self, api_token, team_id, target_name):
        data = self._request_json(f"https://api.clickup.com/api/v2/team/{team_id}/space", api_token)
        target = self._normalize_name(target_name)
        for space in data.get("spaces", []):
            name = str(space.get("name", "")).strip()
            space_id = str(space.get("id", "")).strip()
            self._log(f"Space Candidate: {name} | ID: {space_id}")
            if self._normalize_name(name) == target:
                return space_id
        return ""

    def _find_folder_id_by_name_with_fallbacks(self, api_token, space_id, target_name):
        target_text = str(target_name or "").strip()
        candidates = [target_text]
        lower_target = target_text.lower()
        if lower_target == "production" or lower_target.endswith(" production"):
            candidates.append(target_text + "s")
        elif lower_target == "productions" or lower_target.endswith(" productions"):
            candidates.append(target_text[:-1])

        seen = set()
        for candidate in candidates:
            normalized = self._normalize_name(candidate)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            folder_id = self._find_folder_id_by_name(api_token, space_id, candidate)
            if folder_id:
                return folder_id
        return ""

    def _find_folder_id_by_name(self, api_token, space_id, target_name):
        data = self._request_json(f"https://api.clickup.com/api/v2/space/{space_id}/folder", api_token)
        target = self._normalize_name(target_name)
        for folder in data.get("folders", []):
            name = str(folder.get("name", "")).strip()
            folder_id = str(folder.get("id", "")).strip()
            self._log(f"Folder Candidate: {name} | ID: {folder_id}")
            if self._normalize_name(name) == target:
                return folder_id
        return ""

    def _find_all_lists_in_folder(self, api_token, folder_id):
        data = self._request_json(f"https://api.clickup.com/api/v2/folder/{folder_id}/list", api_token)
        lists = []
        for item in data.get("lists", []):
            name = str(item.get("name", "")).strip()
            list_id = str(item.get("id", "")).strip()
            if not list_id:
                continue
            self._log(f"List Candidate: {name} | ID: {list_id}")
            lists.append({"name": name, "id": list_id})
        return lists

    def _find_list_id_by_name(self, api_token, folder_id, target_name):
        target = self._normalize_name(target_name)
        for item in self._find_all_lists_in_folder(api_token, folder_id):
            if self._normalize_name(item.get("name", "")) == target:
                return str(item.get("id", "")).strip()
        return ""

    def _find_task_id_by_name_in_all_folder_lists(self, api_token, folder_id, target_name):
        lists = self._find_all_lists_in_folder(api_token, folder_id)
        if not lists:
            self._log_error(f"No ClickUp lists found in folder_id={folder_id}")
            return ""

        self._log(f"Searching {len(lists)} ClickUp list(s) for parent task named exactly: {target_name}")

        for include_subtasks in (False, True):
            if include_subtasks:
                self._log_warning(f"Parent task not found in any list. Trying fallback search with subtasks=true for: {target_name}")
            for item in lists:
                list_name = str(item.get("name", "")).strip()
                list_id = str(item.get("id", "")).strip()
                task_id = self._find_task_id_by_name_paginated(api_token, list_id, target_name, include_subtasks)
                if task_id:
                    self._log(f"Matched task in list: {list_name} | list_id={list_id} | task_id={task_id}")
                    return task_id

        self._log_error(f"No ClickUp task matched target name in any folder list: {target_name}")
        return ""

    def _find_task_id_by_name(self, api_token, list_id, target_name):
        clean_target_name = str(target_name or "").strip()
        if not clean_target_name:
            self._log_error("Cannot find task because target_name is empty.")
            return ""

        self._log(f"Searching for ClickUp parent task named exactly: {clean_target_name} in list_id={list_id}")
        for include_subtasks in (False, True):
            task_id = self._find_task_id_by_name_paginated(api_token, list_id, clean_target_name, include_subtasks)
            if task_id:
                return task_id
            if not include_subtasks:
                self._log_warning(f"Parent task not found with subtasks=false. Trying fallback search with subtasks=true for: {clean_target_name}")
        self._log_error(f"No ClickUp task matched target name: {clean_target_name}")
        return ""

    def _find_task_id_by_name_paginated(self, api_token, list_id, target_name, include_subtasks):
        target = self._normalize_name(target_name)
        total_checked = 0

        for page in range(self.MAX_TASK_PAGES):
            query = urllib.parse.urlencode({
                "archived": "false",
                "subtasks": "true" if include_subtasks else "false",
                "page": str(page),
            })
            url = f"https://api.clickup.com/api/v2/list/{list_id}/task?{query}"
            self._log(f"Requesting ClickUp tasks page={page}, list_id={list_id}, subtasks={include_subtasks}")
            data = self._request_json(url, api_token)
            tasks = data.get("tasks", [])
            self._log(f"Task page returned count={len(tasks)}, page={page}, subtasks={include_subtasks}")

            if not tasks:
                break

            for task in tasks:
                name = str(task.get("name", "")).strip()
                task_id = str(task.get("id", "")).strip()
                total_checked += 1
                self._log(f"Task Candidate: {name} | ID: {task_id}")
                if self._normalize_name(name) == target:
                    self._log(f"Matched ClickUp task: {name} | ID: {task_id} | subtasks={include_subtasks} | page={page}")
                    return task_id

            if bool(data.get("last_page", False)):
                self._log("ClickUp reported last_page=true.")
                break

        self._log_warning(f"No match found after checking {total_checked} task candidate(s). target={target_name}, subtasks={include_subtasks}")
        return ""

    # -------------------------------------------------------------------------
    # Mention discovery
    # -------------------------------------------------------------------------

    def _resolve_comment_mention_user_ids(self, api_token, task_id, supervisors):
        if clickup_tasks_get_all_assignee is not None:
            try:
                importlib.reload(clickup_tasks_get_all_assignee)
                assignees = clickup_tasks_get_all_assignee.run(
                    api_token=api_token,
                    task_id=task_id,
                    include_subtasks=True,
                    fetch_subtask_details=True,
                )

                assignee_user_ids = []
                for assignee in assignees or []:
                    user_id = self._safe_int(assignee.get("id", ""))
                    if not user_id:
                        continue
                    assignee_user_ids.append(user_id)
                    self._log(f"Mention Assignee Candidate: {assignee.get('name', '')} | ID: {user_id}")

                assignee_user_ids = self._dedupe_user_ids(assignee_user_ids)
                if assignee_user_ids:
                    self._log(f"Using {len(assignee_user_ids)} task/subtask assignee(s) for ClickUp mentions.")
                    return assignee_user_ids

                self._log_warning("No task or subtask assignees found. Falling back to clickup_data.json supervisors.")
            except Exception as exc:
                self._log_warning(f"Failed while collecting task/subtask assignees: {exc}. Falling back to clickup_data.json supervisors.")
        else:
            self._log_warning("clickup_tasks_get_all_assignee.py could not be imported. Falling back to clickup_data.json supervisors.")

        supervisor_user_ids = self._extract_supervisor_user_ids(supervisors)
        if supervisor_user_ids:
            self._log(f"Using {len(supervisor_user_ids)} supervisor fallback user(s) for ClickUp mentions.")
            return supervisor_user_ids

        self._log_warning("No assignees or supervisor fallback user_ids found. Posting comment without mentions.")
        return []

    def _extract_supervisor_user_ids(self, supervisors):
        user_ids = []
        for supervisor in supervisors or []:
            if not isinstance(supervisor, dict):
                continue
            user_id = self._safe_int(supervisor.get("user_id", ""))
            if user_id:
                user_ids.append(user_id)
        return self._dedupe_user_ids(user_ids)

    def _safe_int(self, value):
        try:
            return int(str(value).strip())
        except Exception:
            return 0

    def _dedupe_user_ids(self, user_ids):
        output = []
        seen = set()
        for user_id in user_ids or []:
            clean = self._safe_int(user_id)
            if clean and clean not in seen:
                seen.add(clean)
                output.append(clean)
        return output

    # -------------------------------------------------------------------------
    # Attachment and comment
    # -------------------------------------------------------------------------

    def _upload_attachment(self, api_token, task_id, file_path):
        clean_file_path = os.path.normpath(str(file_path or "").strip().strip("\"'"))
        if not os.path.isfile(clean_file_path):
            self._log_error(f"Attachment file does not exist: {clean_file_path}")
            return False

        upload_url = f"https://api.clickup.com/api/v2/task/{task_id}/attachment"
        body_bytes, content_type_header, file_name = self._build_multipart_body(clean_file_path)
        self._log(f"Uploading attachment: {file_name}")
        self._log(f"Attachment path: {clean_file_path}")

        request = urllib.request.Request(
            upload_url,
            data=body_bytes,
            headers={
                "Authorization": api_token,
                "Content-Type": content_type_header,
                "Content-Length": str(len(body_bytes)),
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                response_text = response.read().decode("utf-8")
            data = json.loads(response_text) if response_text.strip() else {}
            self._log("Attachment uploaded successfully.")
            self._log(f"Attachment Response: {json.dumps(data, ensure_ascii=False)}")
            return True
        except urllib.error.HTTPError as exc:
            self._log_error(f"Attachment HTTPError: {exc.code} {exc.reason}")
            self._log_error(f"Attachment Response Body: {self._read_http_error_body(exc)}")
            return False
        except urllib.error.URLError as exc:
            self._log_error(f"Attachment URLError: {exc}")
            return False
        except Exception as exc:
            self._log_error(f"Attachment unexpected error: {exc}")
            return False

    def _build_multipart_body(self, file_path, field_name="attachment"):
        boundary = f"----ClickUpBoundary{uuid.uuid4().hex}"
        file_name = os.path.basename(file_path)
        content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

        with open(file_path, "rb") as handle:
            file_bytes = handle.read()

        boundary_bytes = boundary.encode("utf-8")
        parts = [
            b"--" + boundary_bytes + b"\r\n",
            (f'Content-Disposition: form-data; name="{field_name}"; filename="{file_name}"\r\n').encode("utf-8"),
            (f"Content-Type: {content_type}\r\n\r\n").encode("utf-8"),
            file_bytes,
            b"\r\n",
            b"--" + boundary_bytes + b"--\r\n",
        ]
        return b"".join(parts), f"multipart/form-data; boundary={boundary}", file_name

    def _post_render_complete_comment(self, api_token, task_id, shot_name, mention_user_ids, exr_location_path, mp4_file_path):
        mention_user_ids = self._dedupe_user_ids(mention_user_ids)
        exr_location_display = self._shorten_path_from_defect(exr_location_path)
        mp4_location_display = self._shorten_path_from_defect(mp4_file_path)

        comment_text = (
            f"\n{shot_name} render is complete."
            f"\nEXR Location: {exr_location_display}"
            f"\nMP4 Location: {mp4_location_display}"
        )

        comment_blocks = []
        for index, user_id in enumerate(mention_user_ids):
            comment_blocks.append({"type": "tag", "user": {"id": user_id}})
            if index < len(mention_user_ids) - 1:
                comment_blocks.append({"text": " "})
        comment_blocks.append({"text": comment_text})

        payload = {"comment": comment_blocks, "notify_all": False}
        request = urllib.request.Request(
            f"https://api.clickup.com/api/v2/task/{task_id}/comment",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": api_token, "Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                response_text = response.read().decode("utf-8")
            data = json.loads(response_text) if response_text.strip() else {}
            self._log("Render-complete comment created successfully.")
            self._log(f"Mention user id count: {len(mention_user_ids)}")
            self._log(f"Comment EXR Location: {exr_location_display}")
            self._log(f"Comment MP4 Location: {mp4_location_display}")
            self._log(f"Comment Response: {json.dumps(data, ensure_ascii=False)}")
            return True
        except urllib.error.HTTPError as exc:
            self._log_error(f"Comment HTTPError: {exc.code} {exc.reason}")
            self._log_error(f"Comment Response Body: {self._read_http_error_body(exc)}")
            return False
        except urllib.error.URLError as exc:
            self._log_error(f"Comment URLError: {exc}")
            return False
        except Exception as exc:
            self._log_error(f"Comment unexpected error: {exc}")
            return False

    # -------------------------------------------------------------------------
    # General helpers
    # -------------------------------------------------------------------------

    def _request_json(self, url, api_token):
        request = urllib.request.Request(
            url,
            headers={"Authorization": api_token, "Content-Type": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            response_text = response.read().decode("utf-8")
        return json.loads(response_text) if response_text.strip() else {}

    def _read_http_error_body(self, exc):
        try:
            return exc.read().decode("utf-8", errors="replace")
        except Exception:
            return "<could not read error body>"

    def _normalize_name(self, value):
        return " ".join(str(value or "").strip().lower().split())

    def _normalize_folder_path(self, folder_path):
        text = str(folder_path or "").strip().strip("\"'")
        return os.path.normpath(text) if text else ""

    def _shorten_path_from_defect(self, path_value):
        normalized = os.path.normpath(str(path_value or "").strip().strip("\"'"))
        if not normalized:
            return ""
        backslash_path = normalized.replace("/", "\\")
        lowered = backslash_path.lower()
        marker = "\\defect\\"
        index = lowered.find(marker)
        return backslash_path[index:] if index >= 0 else backslash_path

    def _resolve_job_variable_string(self, in_job_copy, variable_name):
        try:
            value = self._find_variable_value_anywhere(in_job_copy, variable_name, max_depth=4)
            return self._normalize_possible_variable_value(value)
        except Exception as exc:
            self._log_warning(f"Variable lookup failed for '{variable_name}': {exc}")
            return ""

    def _find_variable_value_anywhere(self, root_object, variable_name, max_depth=4):
        visited = set()
        return self._find_variable_value_recursive(root_object, variable_name, visited, 0, max_depth)

    def _find_variable_value_recursive(self, current_object, variable_name, visited, depth, max_depth):
        if current_object is None or depth > max_depth:
            return None
        object_id = id(current_object)
        if object_id in visited:
            return None
        visited.add(object_id)

        direct_match = self._extract_variable_from_container(current_object, variable_name)
        if direct_match is not None:
            return direct_match

        for child in self._collect_child_objects(current_object):
            value = self._find_variable_value_recursive(child, variable_name, visited, depth + 1, max_depth)
            if value is not None:
                return value
        return None

    def _collect_child_objects(self, obj):
        children = []
        attribute_names = (
            "graph_preset", "preset", "job", "job_copy", "graph_config", "configuration",
            "variable_assignments", "job_variable_assignments", "graph_variable_assignments", "variables",
        )
        method_names = (
            "get_graph_preset", "get_preset", "get_configuration", "get_config",
            "get_variable_assignments", "get_job_variable_assignments", "get_graph_variable_assignments",
        )
        for name in attribute_names:
            try:
                children.append(getattr(obj, name))
            except Exception:
                pass
        for name in method_names:
            try:
                method = getattr(obj, name, None)
                if callable(method):
                    children.append(method())
            except Exception:
                pass
        return children

    def _extract_variable_from_container(self, container, variable_name):
        normalized_target = str(variable_name or "").strip().lower()
        if not normalized_target:
            return None

        if hasattr(container, "items"):
            try:
                for key, value in container.items():
                    if str(key).strip().lower() == normalized_target:
                        return value
                    extracted = self._extract_assignment_value_if_named(key, value, normalized_target)
                    if extracted is not None:
                        return extracted
            except Exception:
                pass

        if not isinstance(container, (str, bytes)):
            try:
                for item in container:
                    extracted = self._extract_assignment_value_if_named(item, None, normalized_target)
                    if extracted is not None:
                        return extracted
            except Exception:
                pass

        return self._extract_assignment_value_if_named(container, None, normalized_target)

    def _extract_assignment_value_if_named(self, item, paired_value, normalized_target):
        candidate_names = []
        for attr_name in ("name", "variable_name", "member_name", "label"):
            try:
                candidate_names.append(str(getattr(item, attr_name)))
            except Exception:
                pass
        for method_name in ("get_name", "get_member_name", "get_variable_name"):
            try:
                method = getattr(item, method_name, None)
                if callable(method):
                    candidate_names.append(str(method()))
            except Exception:
                pass

        for candidate_name in candidate_names:
            if candidate_name.strip().lower() != normalized_target:
                continue
            if paired_value is not None:
                return paired_value
            for attr_name in ("value", "string_value", "resolved_value"):
                try:
                    return getattr(item, attr_name)
                except Exception:
                    pass
            for method_name in ("get_value", "get_resolved_value", "get_value_string"):
                try:
                    method = getattr(item, method_name, None)
                    if callable(method):
                        return method()
                except Exception:
                    pass
        return None

    def _normalize_possible_variable_value(self, value):
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        for method_name in ("to_string", "get_asset_path_name", "get_path_name"):
            try:
                method = getattr(value, method_name, None)
                if callable(method):
                    text = str(method()).strip()
                    if text and text.lower() not in ("none", "null"):
                        return text
            except Exception:
                pass
        try:
            text = str(value).strip()
            return "" if text.lower() in ("none", "null") else text
        except Exception:
            return ""

    def _log(self, message):
        unreal.log(f"{self.LOG_PREFIX} {message}")

    def _log_warning(self, message):
        unreal.log_warning(f"{self.LOG_PREFIX} Warning: {message}")

    def _log_error(self, message):
        unreal.log_error(f"{self.LOG_PREFIX} Error: {message}")
