from datetime import datetime
import json
import os
import shutil
import time

import unreal


@unreal.uclass()
class MRGRenderInfo(unreal.MovieGraphScriptBase):

    IMAGE_EXTENSIONS = {
        ".exr",
        ".png",
        ".jpg",
        ".jpeg",
        ".bmp",
        ".tif",
        ".tiff",
    }

    VIDEO_EXTENSIONS = {
        ".mp4",
        ".mov",
        ".avi",
        ".mkv",
    }

    LOG_PREFIX = "[QuickWidgetToolsMRG]"
    OUTPUT_DIRECTORY_VARIABLE_NAME = "OutputDirectory"
    MP4_FILE_NAME_VARIABLE_NAME = "MP4FileNameFormat"
    RENDER_LOG_FOLDER_NAME = "RenderLog"
    SHOW_RENDER_LOG_FOLDER_SUFFIX = "_RenderLog"
    FARM_JOB_PARAMETER_NAME = "RenderFarmJob"
    LOCK_RETRY_TIMEOUT_SECONDS = 15.0
    TRANSIENT_WINDOWS_LOCK_ERRORS = {32, 33}

    @unreal.ufunction(override=True)
    def on_job_finished(self, in_job_copy, in_output_data):
        super().on_job_finished(in_job_copy, in_output_data)

        all_file_paths = self._collect_output_file_paths(in_output_data)
        farm_job = self._load_active_farm_job()
        frame_files = self._filter_image_files(all_file_paths)

        if not frame_files:
            unreal.log_warning(f"{self.LOG_PREFIX} No rendered image sequence files found")
            return

        frame_records = self._build_frame_records(frame_files)

        if not frame_records:
            unreal.log_warning(f"{self.LOG_PREFIX} No valid frame timestamps found")
            return

        frame_records.sort(key=lambda item: item[1])

        first_frame_path, first_time = frame_records[0]
        last_frame_path, last_time = frame_records[-1]

        frame_count = len(frame_records)
        total_render_seconds = max(0.0, last_time - first_time)
        per_frame_seconds = total_render_seconds / max(frame_count - 1, 1)

        derived_render_output_folder = os.path.dirname(first_frame_path)

        output_directory_value = self._resolve_job_variable_string(
            in_job_copy,
            self.OUTPUT_DIRECTORY_VARIABLE_NAME,
        )
        render_output_folder = self._normalize_folder_path(output_directory_value)

        if not render_output_folder:
            render_output_folder = derived_render_output_folder
            if farm_job:
                unreal.log(
                    f"{self.LOG_PREFIX} Using Movie Graph's rendered-file location "
                    f"for farm output: {render_output_folder}"
                )
            else:
                unreal.log_warning(
                    f"{self.LOG_PREFIX} Could not resolve "
                    f"'{self.OUTPUT_DIRECTORY_VARIABLE_NAME}' from job. Falling "
                    f"back to derived output folder: {render_output_folder}"
                )
        else:
            unreal.log(f"{self.LOG_PREFIX} Resolved job variable OutputDirectory: {render_output_folder}")

        mp4_file_name_value = self._resolve_job_variable_string(
            in_job_copy,
            self.MP4_FILE_NAME_VARIABLE_NAME,
        )
        log_file_stem = self._sanitize_file_stem(mp4_file_name_value)

        if not log_file_stem:
            log_file_stem = self._derive_file_stem_from_video_outputs(all_file_paths)

        if not log_file_stem:
            log_file_stem = self._derive_file_stem_from_frame_path(first_frame_path)

        if not log_file_stem:
            log_file_stem = "RenderInfo"

        unreal.log(f"{self.LOG_PREFIX} Render log file stem: {log_file_stem}")

        summary_lines = [
            "==================================================",
            f"{self.LOG_PREFIX} Render Output Folder: {render_output_folder}",
            f"{self.LOG_PREFIX} Rendered Frame Count: {frame_count}",
            f"{self.LOG_PREFIX} Total Render Time: {total_render_seconds:.2f} sec",
            f"{self.LOG_PREFIX} Render Time Per Frame: {per_frame_seconds:.2f} sec",
            "==================================================",
        ]

        for line in summary_lines:
            unreal.log(line)

        self._write_summary_log(
            render_output_folder=render_output_folder,
            log_file_stem=log_file_stem,
            summary_lines=summary_lines,
            farm_job=farm_job,
        )

    def _collect_output_file_paths(self, in_output_data):
        collected = []

        try:
            graph_data = in_output_data.graph_data

            for render_output_data in graph_data:
                self._collect_from_render_output_data(render_output_data, collected)

        except Exception as exc:
            unreal.log_warning(
                f"{self.LOG_PREFIX} Failed while collecting from graph_data: {exc}"
            )

        return self._dedupe_paths(collected)

    def _collect_from_render_output_data(self, render_output_data, collected):
        try:
            if not hasattr(render_output_data, "render_layer_data"):
                return

            render_layer_data = render_output_data.render_layer_data

            if hasattr(render_layer_data, "items"):
                for identifier_data, output_info in render_layer_data.items():
                    self._collect_from_output_info(output_info, collected)

        except Exception as exc:
            unreal.log_warning(
                f"{self.LOG_PREFIX} Failed while collecting from render_output_data: {exc}"
            )

    def _collect_from_output_info(self, output_info, collected):
        try:
            if hasattr(output_info, "file_paths"):
                for file_path in output_info.file_paths:
                    collected.append(str(file_path))
        except Exception as exc:
            unreal.log_warning(
                f"{self.LOG_PREFIX} Failed while collecting from output_info: {exc}"
            )

    def _filter_image_files(self, all_file_paths):
        frame_files = []

        for file_path in all_file_paths:
            if not file_path:
                continue

            normalized_path = os.path.normpath(str(file_path))
            ext = os.path.splitext(normalized_path)[1].lower()

            if ext not in self.IMAGE_EXTENSIONS:
                continue

            if not os.path.isfile(normalized_path):
                continue

            frame_files.append(normalized_path)

        return self._dedupe_paths(sorted(frame_files))

    def _build_frame_records(self, frame_files):
        frame_records = []

        for frame_path in frame_files:
            try:
                modified_time = os.path.getmtime(frame_path)
                frame_records.append((frame_path, modified_time))
            except OSError as exc:
                unreal.log_warning(
                    f"{self.LOG_PREFIX} Could not read timestamp for: {frame_path} | {exc}"
                )

        return frame_records

    def _dedupe_paths(self, paths):
        deduped = []
        seen = set()

        for path in paths:
            norm = os.path.normpath(str(path))
            if norm not in seen:
                seen.add(norm)
                deduped.append(norm)

        return deduped

    def _normalize_folder_path(self, folder_path):
        text = str(folder_path or "").strip().strip("\"'")
        if not text:
            return ""

        normalized = os.path.normpath(text)
        return normalized

    def _sanitize_file_stem(self, value):
        raw = str(value or "").strip().strip("\"'")
        if not raw:
            return ""

        invalid_chars = '<>:"/\\|?*'
        cleaned = "".join("_" if ch in invalid_chars else ch for ch in raw).strip()
        cleaned = cleaned.rstrip(". ")

        return cleaned

    def _derive_file_stem_from_video_outputs(self, all_file_paths):
        for file_path in all_file_paths:
            if not file_path:
                continue

            normalized_path = os.path.normpath(str(file_path))
            ext = os.path.splitext(normalized_path)[1].lower()

            if ext not in self.VIDEO_EXTENSIONS:
                continue

            return os.path.splitext(os.path.basename(normalized_path))[0]

        return ""

    def _derive_file_stem_from_frame_path(self, frame_path):
        if not frame_path:
            return ""

        base_name = os.path.basename(str(frame_path))
        stem, _ext = os.path.splitext(base_name)

        if "." in stem:
            stem = stem.rsplit(".", 1)[0]

        return self._sanitize_file_stem(stem)

    def _write_summary_log(
        self,
        render_output_folder,
        log_file_stem,
        summary_lines,
        farm_job=None,
    ):
        if not render_output_folder:
            unreal.log_warning(
                f"{self.LOG_PREFIX} Could not write render log because render_output_folder was empty."
            )
            return

        render_log_root = os.path.dirname(render_output_folder)
        render_log_folder = os.path.join(render_log_root, self.RENDER_LOG_FOLDER_NAME)
        log_file_path = os.path.join(render_log_folder, f"{log_file_stem}.txt")

        unreal.log(f"{self.LOG_PREFIX} Render log root: {render_log_root}")
        unreal.log(f"{self.LOG_PREFIX} RenderLog folder: {render_log_folder}")
        unreal.log(f"{self.LOG_PREFIX} RenderLog file: {log_file_path}")

        try:
            os.makedirs(render_log_folder, exist_ok=True)
            unreal.log(f"{self.LOG_PREFIX} Ensured RenderLog folder exists: {render_log_folder}")
        except Exception as exc:
            unreal.log_error(
                f"{self.LOG_PREFIX} Failed to create RenderLog folder '{render_log_folder}': {exc}"
            )
            return

        try:
            with open(log_file_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("\n".join(summary_lines) + "\n")
            unreal.log(f"{self.LOG_PREFIX} Wrote render info log: {log_file_path}")
        except Exception as exc:
            unreal.log_error(
                f"{self.LOG_PREFIX} Failed to write render info log '{log_file_path}': {exc}"
            )
            return

        self._copy_summary_log_to_show_output(
            log_file_path,
            render_output_folder,
            farm_job,
        )

    def _copy_summary_log_to_show_output(
        self,
        log_file_path,
        render_output_folder,
        farm_job=None,
    ):
        if not log_file_path or not os.path.isfile(log_file_path):
            unreal.log_warning(
                f"{self.LOG_PREFIX} Could not copy render log because source log was missing: {log_file_path}"
            )
            return

        show_render_log_folder = self._get_show_render_log_folder(
            render_output_folder,
            farm_job,
        )
        if not show_render_log_folder:
            return

        try:
            os.makedirs(show_render_log_folder, exist_ok=True)
            unreal.log(f"{self.LOG_PREFIX} Ensured show RenderLog folder exists: {show_render_log_folder}")
        except Exception as exc:
            unreal.log_error(
                f"{self.LOG_PREFIX} Failed to create show RenderLog folder '{show_render_log_folder}': {exc}"
            )
            return

        dest_path = self._build_unique_file_path(
            show_render_log_folder,
            os.path.basename(log_file_path),
        )

        try:
            shutil.copy2(log_file_path, dest_path)
            unreal.log(f"{self.LOG_PREFIX} Copied render info log to show output: {dest_path}")
        except Exception as exc:
            unreal.log_error(
                f"{self.LOG_PREFIX} Failed to copy render info log '{log_file_path}' -> '{dest_path}': {exc}"
            )

    def _get_show_render_log_folder(self, render_output_folder, farm_job=None):
        output_path = self._get_farm_show_output_path(farm_job)
        if not output_path:
            output_path = self._infer_show_output_path(render_output_folder)
        if not output_path:
            unreal.log_warning(
                f"{self.LOG_PREFIX} Could not derive the show-level output path. "
                "Skipping the optional show RenderLog copy."
            )
            return ""

        date_stamp = datetime.now().strftime("%Y%m%d")
        show_render_log_folder_name = f"{date_stamp}{self.SHOW_RENDER_LOG_FOLDER_SUFFIX}"
        return os.path.normpath(
            os.path.join(output_path, "_output", show_render_log_folder_name)
        )

    def _get_farm_show_output_path(self, farm_job):
        if not isinstance(farm_job, dict):
            return ""

        show_root = self._normalize_folder_path(
            farm_job.get("worker_show_file_server_path")
        )
        if not show_root:
            return ""

        relative_output = str(
            farm_job.get("output_relative_directory") or ""
        ).replace("\\", "/")
        relative_parts = [
            part for part in relative_output.split("/") if part not in ("", ".")
        ]
        top_level_folder = (
            relative_parts[0]
            if relative_parts and relative_parts[0] != ".."
            else "sequences"
        )
        output_path = os.path.normpath(
            os.path.join(show_root, top_level_folder)
        )
        unreal.log(
            f"{self.LOG_PREFIX} Resolved worker-local show output path from "
            f"farm job: {output_path}"
        )
        return output_path

    def _infer_show_output_path(self, render_output_folder):
        normalized = os.path.abspath(
            self._normalize_folder_path(render_output_folder)
        )
        drive, tail = os.path.splitdrive(normalized)
        parts = [part for part in tail.split(os.sep) if part]
        for index, part in enumerate(parts):
            if part.casefold() != "sequences":
                continue
            anchor = drive + os.sep if drive else os.sep
            output_path = os.path.normpath(
                os.path.join(anchor, *parts[: index + 1])
            )
            unreal.log(
                f"{self.LOG_PREFIX} Inferred show output path from rendered "
                f"files: {output_path}"
            )
            return output_path
        return ""

    def _load_active_farm_job(self):
        try:
            _tokens, _switches, parameters = unreal.SystemLibrary.parse_command_line(
                unreal.SystemLibrary.get_command_line()
            )
            job_path = ""
            for key, value in parameters.items():
                if str(key).casefold() == self.FARM_JOB_PARAMETER_NAME.casefold():
                    job_path = str(value).strip().strip('"')
                    break
            if not job_path:
                return None

            job_path = os.path.abspath(os.path.normpath(job_path))
            deadline = time.monotonic() + self.LOCK_RETRY_TIMEOUT_SECONDS
            delay_seconds = 0.1
            while True:
                try:
                    with open(job_path, "r", encoding="utf-8") as handle:
                        job = json.load(handle)
                    if not isinstance(job, dict):
                        raise ValueError(f"Expected a JSON object in {job_path}")
                    unreal.log(
                        f"{self.LOG_PREFIX} Loaded worker-local farm paths from: "
                        f"{job_path}"
                    )
                    return job
                except OSError as exc:
                    if (
                        getattr(exc, "winerror", None)
                        not in self.TRANSIENT_WINDOWS_LOCK_ERRORS
                        or time.monotonic() >= deadline
                    ):
                        raise
                    time.sleep(delay_seconds)
                    delay_seconds = min(delay_seconds * 2, 1.0)
        except Exception as exc:
            unreal.log_warning(
                f"{self.LOG_PREFIX} Could not load active farm job paths: {exc}"
            )
            return None

    def _build_unique_file_path(self, folder_path, file_name):
        dest_path = os.path.join(folder_path, file_name)
        if not os.path.exists(dest_path):
            return dest_path

        stem, ext = os.path.splitext(file_name)
        index = 2
        while True:
            numbered_path = os.path.join(folder_path, f"{stem}_{index}{ext}")
            if not os.path.exists(numbered_path):
                return numbered_path
            index += 1

    def _resolve_job_variable_string(self, in_job_copy, variable_name):
        try:
            value = self._find_variable_value_anywhere(in_job_copy, variable_name, max_depth=4)
            normalized = self._normalize_possible_variable_value(value)
            if normalized:
                return normalized
        except Exception as exc:
            unreal.log_warning(
                f"{self.LOG_PREFIX} Variable lookup failed for '{variable_name}': {exc}"
            )

        return ""

    def _find_variable_value_anywhere(self, root_object, variable_name, max_depth=4):
        visited = set()
        return self._find_variable_value_recursive(
            current_object=root_object,
            variable_name=variable_name,
            visited=visited,
            depth=0,
            max_depth=max_depth,
        )

    def _find_variable_value_recursive(self, current_object, variable_name, visited, depth, max_depth):
        if current_object is None:
            return None

        if depth > max_depth:
            return None

        object_id = id(current_object)
        if object_id in visited:
            return None
        visited.add(object_id)

        direct_match = self._extract_variable_from_container(current_object, variable_name)
        if direct_match is not None:
            return direct_match

        next_objects = self._collect_child_objects(current_object)

        for child in next_objects:
            value = self._find_variable_value_recursive(
                current_object=child,
                variable_name=variable_name,
                visited=visited,
                depth=depth + 1,
                max_depth=max_depth,
            )
            if value is not None:
                return value

        return None

    def _collect_child_objects(self, obj):
        children = []

        attribute_names = [
            "graph_preset",
            "preset",
            "job",
            "job_copy",
            "graph_config",
            "configuration",
            "variable_assignments",
            "job_variable_assignments",
            "graph_variable_assignments",
            "variables",
        ]

        method_names = [
            "get_graph_preset",
            "get_preset",
            "get_configuration",
            "get_config",
            "get_variable_assignments",
            "get_job_variable_assignments",
            "get_graph_variable_assignments",
        ]

        for name in attribute_names:
            try:
                value = getattr(obj, name)
                children.append(value)
            except Exception:
                continue

        for name in method_names:
            try:
                method = getattr(obj, name, None)
                if callable(method):
                    children.append(method())
            except Exception:
                continue

        return children

    def _extract_variable_from_container(self, container, variable_name):
        normalized_target = str(variable_name or "").strip().lower()
        if not normalized_target:
            return None

        if hasattr(container, "items"):
            try:
                for key, value in container.items():
                    key_text = str(key).strip().lower()
                    if key_text == normalized_target:
                        return value
                    extracted = self._extract_assignment_value_if_named(key, value, normalized_target)
                    if extracted is not None:
                        return extracted
            except Exception:
                pass

        iterable = None
        if isinstance(container, (list, tuple, set)):
            iterable = container
        else:
            try:
                iter(container)
                iterable = container
            except Exception:
                iterable = None

        if iterable is not None and not isinstance(container, (str, bytes)):
            try:
                for item in iterable:
                    extracted = self._extract_assignment_value_if_named(item, None, normalized_target)
                    if extracted is not None:
                        return extracted
            except Exception:
                pass

        extracted = self._extract_assignment_value_if_named(container, None, normalized_target)
        if extracted is not None:
            return extracted

        return None

    def _extract_assignment_value_if_named(self, item, paired_value, normalized_target):
        candidate_names = []

        for attr_name in ("name", "variable_name", "member_name", "label"):
            try:
                value = getattr(item, attr_name)
                candidate_names.append(str(value))
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
                    result = method()
                    if result is not None:
                        text = str(result).strip()
                        if text and text.lower() not in ("none", "null"):
                            return text
            except Exception:
                pass

        try:
            text = str(value).strip()
            if text and text.lower() not in ("none", "null"):
                return text
        except Exception:
            pass

        return ""
