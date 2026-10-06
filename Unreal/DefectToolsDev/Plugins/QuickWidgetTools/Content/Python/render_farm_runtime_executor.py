"""UE 5.8 command-line Movie Render Graph executor for Defect Render Farm.

This module is imported by ``init_unreal.py`` so Unreal registers the Python
UClass before Movie Render Pipeline parses the command line.  The external
worker launches it with::

    -MoviePipelineLocalExecutorClass=/Script/MovieRenderPipelineCore.MoviePipelinePythonHostExecutor
    -ExecutorPythonClass=/Engine/PythonTypes.DefectRenderFarmExecutor
    -MoviePipelineClass=/Script/MovieRenderPipelineCore.MoviePipeline
    -RenderFarmJob=<absolute path to job.json>

The executor never changes ``job.json``.  It writes ``unreal_result.json`` next
to it, and the external worker remains responsible for the farm state change.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import time
import traceback
from typing import Any, Callable, TypeVar
from uuid import uuid4

import unreal


LOG_PREFIX = "[DefectRenderFarmExecutor]"
JOB_SCHEMA_VERSION = 1
UNREAL_RESULT_SCHEMA_VERSION = 2
UNREAL_RESULT_FILENAME = "unreal_result.json"

# Work around UE-392456: slow image-sequence output can let Niagara GPU ticks
# accumulate while Movie Graph finalizes. Keep these outside the graph so its
# console-variable restoration does not undo them before finalization finishes.
NIAGARA_TICK_FLUSH_WORKAROUND_COMMANDS = (
    "fx.Niagara.Batcher.TickFlush.MaxQueuedFrames 100000",
    "fx.Niagara.Batcher.TickFlush.MaxPendingTicks 100000",
)

LOCK_RETRY_TIMEOUT_SECONDS = 15.0
LOCK_RETRY_INITIAL_DELAY_SECONDS = 0.1
LOCK_RETRY_MAX_DELAY_SECONDS = 1.0
TRANSIENT_WINDOWS_LOCK_ERRORS = frozenset((32, 33))
_OperationResult = TypeVar("_OperationResult")


def _log(message: str) -> None:
    unreal.log(f"{LOG_PREFIX} {message}")


def _log_warning(message: str) -> None:
    unreal.log_warning(f"{LOG_PREFIX} Warning: {message}")


def _log_error(message: str) -> None:
    unreal.log_error(f"{LOG_PREFIX} Error: {message}")


def _apply_render_workarounds(world: Any) -> None:
    for command in NIAGARA_TICK_FLUSH_WORKAROUND_COMMANDS:
        unreal.SystemLibrary.execute_console_command(world, command)
        _log(f"Applied render workaround: {command}")


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _retry_transient_windows_lock(
    operation: Callable[[], _OperationResult],
    description: str,
) -> _OperationResult:
    deadline = time.monotonic() + LOCK_RETRY_TIMEOUT_SECONDS
    delay_seconds = LOCK_RETRY_INITIAL_DELAY_SECONDS

    while True:
        try:
            return operation()
        except OSError as error:
            winerror = getattr(error, "winerror", None)
            if winerror not in TRANSIENT_WINDOWS_LOCK_ERRORS:
                raise

            remaining_seconds = deadline - time.monotonic()
            if remaining_seconds <= 0:
                raise
            wait_seconds = min(delay_seconds, remaining_seconds)
            _log_warning(
                f"{description} is temporarily locked (WinError {winerror}); "
                f"retrying in {wait_seconds:.1f} seconds."
            )
            time.sleep(wait_seconds)
            delay_seconds = min(
                delay_seconds * 2,
                LOCK_RETRY_MAX_DELAY_SECONDS,
            )


def _read_json_object(path: str) -> dict[str, Any]:
    def read() -> dict[str, Any]:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"Expected a JSON object in {path}")
        return data

    return _retry_transient_windows_lock(read, f"Read JSON {path}")


def _write_json_atomic(path: str, data: dict[str, Any]) -> None:
    temporary_paths: list[str] = []

    def write_temporary() -> str:
        temporary_path = os.path.join(
            os.path.dirname(path),
            f".{os.path.basename(path)}.{uuid4().hex}.tmp",
        )
        temporary_paths.append(temporary_path)
        with open(temporary_path, "x", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, indent=4, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        return temporary_path

    try:
        temporary_path = _retry_transient_windows_lock(
            write_temporary,
            f"Write temporary JSON for {path}",
        )
        _retry_transient_windows_lock(
            lambda: os.replace(temporary_path, path),
            f"Publish JSON {path}",
        )
    finally:
        for temporary_path in temporary_paths:
            try:
                _retry_transient_windows_lock(
                    lambda target=temporary_path: (
                        os.remove(target) if os.path.exists(target) else None
                    ),
                    f"Remove temporary JSON {temporary_path}",
                )
            except OSError as cleanup_error:
                _log_warning(
                    f"Could not remove temporary JSON '{temporary_path}': "
                    f"{cleanup_error}"
                )


def _command_line_parameters() -> dict[str, str]:
    _, _, parameters = unreal.SystemLibrary.parse_command_line(
        unreal.SystemLibrary.get_command_line()
    )
    return {str(key).casefold(): str(value) for key, value in parameters.items()}


def _parameter(parameters: dict[str, str], name: str) -> str:
    return parameters.get(name.casefold(), "").strip().strip('"')


def _parameter_is_true(parameters: dict[str, str], name: str) -> bool:
    return _parameter(parameters, name).casefold() in ("1", "true", "yes", "on")


def _validate_job(job: dict[str, Any], job_path: str) -> None:
    if job.get("schema_version") != JOB_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported schema_version in {job_path}; expected {JOB_SCHEMA_VERSION}."
        )
    if job.get("job_type") != "unreal_movie_render_graph":
        raise ValueError(
            "Real Unreal execution requires job_type='unreal_movie_render_graph'."
        )
    if job.get("status") != "rendering":
        raise ValueError(
            f"Expected claimed job status 'rendering', got {job.get('status')!r}."
        )
    for key in ("job_id", "level", "sequence", "render_config"):
        if not isinstance(job.get(key), str) or not job[key].strip():
            raise ValueError(f"Missing or invalid '{key}' in {job_path}.")
    if not isinstance(job.get("graph_variable_overrides"), dict):
        raise ValueError("graph_variable_overrides must be a JSON object.")


def _load_unreal_object(object_path: str, label: str) -> Any:
    loaded = unreal.load_object(None, object_path)
    if loaded is None:
        raise FileNotFoundError(f"Could not load {label}: {object_path}")
    return loaded


def _graph_variables_by_name(graph: Any) -> dict[str, Any]:
    variables: dict[str, Any] = {}
    for variable in list(graph.get_variables() or []):
        name = str(variable.get_member_name())
        variables[name.casefold()] = variable
    return variables


def _apply_graph_overrides(new_job: Any, graph: Any, job: dict[str, Any]) -> None:
    variables = _graph_variables_by_name(graph)
    override_container = new_job.get_or_create_variable_overrides(graph)
    if override_container is None:
        raise RuntimeError("Movie Render Graph variable override container was unavailable.")

    applied_names: list[str] = []
    for requested_name, payload in job["graph_variable_overrides"].items():
        if not isinstance(payload, dict) or payload.get("enabled") is not True:
            continue
        variable = variables.get(str(requested_name).casefold())
        if variable is None:
            raise ValueError(
                f"Graph variable '{requested_name}' does not exist in "
                f"{job['render_config']}."
            )
        serialized_value = str(payload.get("serialized_value", ""))
        if str(requested_name).casefold() == "outputdirectory":
            worker_output_directory = str(
                job.get("worker_output_directory") or ""
            ).strip()
            if worker_output_directory:
                serialized_value = unreal.DirectoryPath(
                    worker_output_directory
                ).export_text()
                _log(
                    "Using worker-local OutputDirectory graph override: "
                    f"{worker_output_directory}"
                )
        set_result = override_container.set_value_serialized_string(
            variable,
            serialized_value,
        )
        if set_result is False:
            raise ValueError(
                f"Unreal rejected serialized value for graph variable "
                f"'{requested_name}': {serialized_value!r}"
            )
        override_container.set_variable_assignment_enable_state(variable, True)
        applied_names.append(str(requested_name))

    if not applied_names:
        raise ValueError("The job did not contain any enabled graph variable overrides.")
    _log("Applied graph overrides: " + ", ".join(sorted(applied_names)))


def _build_pipeline_job(executor: Any, job: dict[str, Any]) -> Any:
    executor.farm_job_queue = unreal.new_object(
        unreal.MoviePipelineQueue,
        outer=executor,
    )
    new_job = executor.farm_job_queue.allocate_new_job(
        unreal.MoviePipelineExecutorJob
    )
    new_job.set_editor_property("job_name", str(job["shot_name"]))
    new_job.set_editor_property("author", str(job.get("submitted_user") or "DefectRenderFarm"))
    new_job.set_editor_property("comment", f"Farm job {job['job_id']}")
    new_job.set_editor_property("user_data", str(job["job_id"]))
    new_job.set_editor_property("sequence", unreal.SoftObjectPath(job["sequence"]))
    new_job.set_editor_property("map", unreal.SoftObjectPath(job["level"]))

    graph = _load_unreal_object(job["render_config"], "Movie Render Graph")
    new_job.set_graph_preset(graph)
    if new_job.get_graph_preset() is None:
        raise RuntimeError("Movie Render Graph assignment did not stick to the job.")

    _apply_graph_overrides(new_job, graph, job)
    _log(
        f"Built MRG job '{job['shot_name']}' with sequence '{job['sequence']}', "
        f"level '{job['level']}', graph '{job['render_config']}'."
    )
    return new_job


def _append_output_file(output_files: list[str], file_path: Any) -> None:
    clean_path = os.path.normpath(str(file_path or "").strip())
    if clean_path and clean_path not in output_files:
        output_files.append(clean_path)


def _append_output_info_files(output_files: list[str], output_info: Any) -> None:
    for file_path in list(getattr(output_info, "file_paths", []) or []):
        _append_output_file(output_files, file_path)


def _collect_output_files(results: Any) -> list[str]:
    """Collect UE 5.8 Movie Graph outputs, with legacy MRQ compatibility."""
    output_files: list[str] = []

    # Movie Render Graph reports outputs through graph_data. Each graph entry
    # contains a render_layer_data map whose values expose file_paths.
    for graph_output_data in list(getattr(results, "graph_data", []) or []):
        render_layer_data = getattr(graph_output_data, "render_layer_data", None)
        if render_layer_data is None:
            continue
        if hasattr(render_layer_data, "items"):
            for _identifier, output_info in render_layer_data.items():
                _append_output_info_files(output_files, output_info)
        else:
            for identifier in render_layer_data:
                _append_output_info_files(
                    output_files,
                    render_layer_data[identifier],
                )

    # Retain support for legacy Movie Render Pipeline output data.
    for shot_data in list(getattr(results, "shot_data", []) or []):
        render_pass_data = getattr(shot_data, "render_pass_data", None)
        if render_pass_data is None:
            continue
        for render_identifier in render_pass_data:
            pass_data = render_pass_data[render_identifier]
            _append_output_info_files(output_files, pass_data)
    return output_files


def _safe_output_child(output_root: str, portable_path: str) -> str:
    relative_text = str(portable_path or "").strip().replace("\\", "/")
    relative_parts = [
        part for part in relative_text.split("/") if part not in ("", ".")
    ]
    if not relative_parts or any(part == ".." for part in relative_parts):
        raise ValueError(f"Unsafe or empty output-relative path: {portable_path!r}")

    output_root = os.path.abspath(os.path.normpath(output_root))
    target_path = os.path.abspath(
        os.path.normpath(os.path.join(output_root, *relative_parts))
    )
    try:
        common_path = os.path.commonpath((output_root, target_path))
    except ValueError as exc:
        raise ValueError(
            f"Output path is not on the worker output drive: {target_path}"
        ) from exc
    if os.path.normcase(common_path) != os.path.normcase(output_root):
        raise ValueError(f"Output path escapes the worker output root: {target_path}")
    return target_path


def _scan_render_files(
    folder_path: str,
    extension: str,
    file_name_prefix: str = "",
) -> list[str]:
    normalized_extension = extension.casefold()
    normalized_prefix = file_name_prefix.casefold()

    def scan() -> list[str]:
        if not os.path.isdir(folder_path):
            return []
        matches: list[str] = []
        for current_root, _folder_names, file_names in os.walk(folder_path):
            for file_name in file_names:
                if os.path.splitext(file_name)[1].casefold() != normalized_extension:
                    continue
                if normalized_prefix and not file_name.casefold().startswith(
                    normalized_prefix
                ):
                    continue
                matches.append(os.path.normpath(os.path.join(current_root, file_name)))
        return sorted(matches, key=str.casefold)

    return _retry_transient_windows_lock(
        scan,
        f"Scan render outputs in {folder_path}",
    )


def _validate_render_outputs(
    job: dict[str, Any],
    reported_output_files: list[str],
) -> tuple[list[str], dict[str, Any]]:
    raw_output_root = str(
        job.get("worker_output_directory")
        or job.get("output_directory")
        or ""
    ).strip()
    validation_errors: list[str] = []
    if not raw_output_root:
        raise ValueError("The farm job has no worker output directory.")
    output_root = os.path.abspath(os.path.normpath(raw_output_root))

    outputs = job.get("outputs") or {}
    if not isinstance(outputs, dict):
        outputs = {}
    mp4_enabled = bool(outputs.get("mp4"))
    exr_enabled = bool(outputs.get("exr"))

    validated_files: list[str] = []
    for file_path in reported_output_files:
        normalized_path = os.path.normpath(str(file_path))
        if _retry_transient_windows_lock(
            lambda path=normalized_path: os.path.isfile(path),
            f"Validate reported render output {normalized_path}",
        ):
            _append_output_file(validated_files, normalized_path)

    mp4_path = ""
    mp4_exists = False
    if mp4_enabled:
        mp4_format = str(job.get("mp4_file_name_format") or "").strip()
        if not mp4_format:
            validation_errors.append("MP4 output is enabled but its filename is empty.")
        else:
            mp4_path = _safe_output_child(output_root, mp4_format)
            if os.path.splitext(mp4_path)[1].casefold() != ".mp4":
                mp4_path += ".mp4"
            mp4_exists = _retry_transient_windows_lock(
                lambda: os.path.isfile(mp4_path),
                f"Validate MP4 output {mp4_path}",
            )
            if mp4_exists:
                _append_output_file(validated_files, mp4_path)
            else:
                validation_errors.append(f"Expected MP4 was not created: {mp4_path}")

    expected_frame_count = job.get("frame_count", 0)
    if not isinstance(expected_frame_count, int) or isinstance(
        expected_frame_count,
        bool,
    ):
        expected_frame_count = 0

    exr_folder = ""
    exr_files: list[str] = []
    required_exr_count = 0
    if exr_enabled:
        exr_format = str(job.get("output_file_name_format") or "").strip()
        if not exr_format:
            validation_errors.append("EXR output is enabled but its filename is empty.")
        else:
            exr_template = _safe_output_child(output_root, exr_format)
            exr_folder = os.path.dirname(exr_template)
            frame_token = "{frame_number}"
            template_file_name = os.path.basename(exr_template)
            prefix = template_file_name.split(frame_token, 1)[0]
            prefix = prefix.rstrip("._- ")
            exr_files = _scan_render_files(exr_folder, ".exr", prefix)
            for exr_file in exr_files:
                _append_output_file(validated_files, exr_file)

            required_exr_count = max(expected_frame_count, 1)
            if len(exr_files) < required_exr_count:
                validation_errors.append(
                    "Expected at least "
                    f"{required_exr_count} EXR file(s), found {len(exr_files)} "
                    f"in {exr_folder}."
                )

    validation = {
        "success": not validation_errors,
        "worker_output_directory": output_root,
        "reported_output_file_count": len(reported_output_files),
        "validated_output_file_count": len(validated_files),
        "mp4_enabled": mp4_enabled,
        "mp4_path": mp4_path,
        "mp4_exists": mp4_exists,
        "exr_enabled": exr_enabled,
        "exr_folder": exr_folder,
        "expected_exr_file_count": required_exr_count,
        "exr_file_count": len(exr_files),
        "errors": validation_errors,
    }
    return sorted(validated_files, key=str.casefold), validation


@unreal.uclass()
class DefectRenderFarmExecutor(unreal.MoviePipelinePythonHostExecutor):
    active_pipeline = unreal.uproperty(unreal.MoviePipelineBase)
    farm_job_queue = unreal.uproperty(unreal.MoviePipelineQueue)
    job_json_path = unreal.uproperty(str)
    job_identifier = unreal.uproperty(str)
    completion_sent = unreal.uproperty(bool)

    def _post_init(self) -> None:
        self.active_pipeline = None
        self.farm_job_queue = None
        self.job_json_path = ""
        self.job_identifier = ""
        self.completion_sent = False

    def _write_result(
        self,
        success: bool,
        reason: str,
        stage: str,
        output_files: list[str] | None = None,
        output_validation: dict[str, Any] | None = None,
        error_traceback: str = "",
    ) -> None:
        result_path = os.path.join(
            os.path.dirname(self.job_json_path),
            UNREAL_RESULT_FILENAME,
        )
        result = {
            "schema_version": UNREAL_RESULT_SCHEMA_VERSION,
            "job_id": self.job_identifier,
            "success": bool(success),
            "stage": stage,
            "reason": reason,
            "finished_utc": _utc_now(),
            "output_files": list(output_files or []),
            "output_file_count": len(output_files or []),
            "output_validation": output_validation,
            "error_traceback": error_traceback,
        }
        _write_json_atomic(result_path, result)
        _log(f"Wrote Unreal result: {result_path}")

    def _finish_executor(self) -> None:
        if self.completion_sent:
            return
        self.completion_sent = True
        self.active_pipeline = None
        self.on_executor_finished_impl()

    def _fail_setup(self, reason: str) -> None:
        _log_error(reason)
        try:
            result_directory = os.path.dirname(self.job_json_path)
            if self.job_json_path and os.path.isdir(result_directory):
                self._write_result(
                    success=False,
                    reason=reason,
                    stage="setup",
                    error_traceback=traceback.format_exc(),
                )
            else:
                _log_error(
                    "Cannot write unreal_result.json because the job path was not resolved."
                )
        finally:
            self._finish_executor()

    @unreal.ufunction(override=True)
    def execute_delayed(self, in_pipeline_queue: Any) -> None:
        del in_pipeline_queue
        try:
            parameters = _command_line_parameters()
            raw_job_path = _parameter(parameters, "RenderFarmJob")
            if not raw_job_path:
                raise ValueError("Missing -RenderFarmJob=<absolute job.json path>.")
            self.job_json_path = os.path.abspath(
                os.path.expandvars(
                    os.path.expanduser(raw_job_path)
                )
            )

            job = _read_json_object(self.job_json_path)
            self.job_identifier = str(job.get("job_id") or "")
            _validate_job(job, self.job_json_path)
            _log(f"Loaded farm job: {self.job_identifier}")

            new_job = _build_pipeline_job(self, job)
            if _parameter_is_true(parameters, "RenderFarmValidateOnly"):
                reason = "Unreal command-line farm job validation succeeded."
                self._write_result(True, reason, "validation")
                _log(reason)
                self._finish_executor()
                return

            world = self.get_last_loaded_world()
            if world is None:
                raise RuntimeError("The command-line render world was not loaded.")

            # UE 5.8's command-line parser requires -MoviePipelineClass to be
            # derived from the legacy MoviePipeline type. MovieGraphPipeline is
            # a sibling under MoviePipelineBase, so create it explicitly here.
            self.active_pipeline = unreal.new_object(
                unreal.MovieGraphPipeline,
                outer=world,
                base_type=unreal.MoviePipelineBase,
            )
            if not isinstance(self.active_pipeline, unreal.MovieGraphPipeline):
                raise TypeError(
                    "Could not create the MovieGraphPipeline runtime instance."
                )

            self.active_pipeline.on_movie_pipeline_work_finished_delegate.add_function_unique(
                self,
                "on_movie_pipeline_finished",
            )
            _apply_render_workarounds(world)
            _log("Starting Movie Graph render...")
            self.active_pipeline.initialize(new_job, unreal.MovieGraphInitConfig())
        except Exception as exc:
            self._fail_setup(f"{type(exc).__name__}: {exc}")

    @unreal.ufunction(override=True)
    def is_rendering(self) -> bool:
        return self.active_pipeline is not None

    @unreal.ufunction(ret=None, params=[unreal.MoviePipelineOutputData])
    def on_movie_pipeline_finished(self, results: Any) -> None:
        pipeline_success = bool(results.success)
        reported_output_files: list[str] = []
        collection_warning = ""
        try:
            reported_output_files = _collect_output_files(results)
        except Exception as exc:
            collection_warning = (
                f" Output-file reporting warning: {type(exc).__name__}: {exc}"
            )
            _log_warning(collection_warning.strip())

        output_files: list[str] = []
        output_validation: dict[str, Any] = {
            "success": False,
            "errors": ["Output validation did not run."],
        }
        try:
            job = _read_json_object(self.job_json_path)
            output_files, output_validation = _validate_render_outputs(
                job,
                reported_output_files,
            )
        except Exception as exc:
            output_validation = {
                "success": False,
                "errors": [
                    f"Output validation error: {type(exc).__name__}: {exc}"
                ],
            }
            _log_error(output_validation["errors"][0])

        validation_success = output_validation.get("success") is True
        success = pipeline_success and validation_success
        if not pipeline_success:
            reason = "Movie Graph render reported failure."
        elif not validation_success:
            reason = (
                "Movie Graph render finished, but output validation failed: "
                + " | ".join(output_validation.get("errors") or [])
            )
        else:
            reason = (
                "Movie Graph render completed successfully and output validation "
                f"passed for {len(output_files)} file(s)."
            )
        reason += collection_warning
        _log(
            "Render finished. "
            f"pipeline_success={pipeline_success}, validation_success={validation_success}, "
            f"reported output files={len(reported_output_files)}, "
            f"validated output files={len(output_files)}"
        )
        try:
            self._write_result(
                success=success,
                reason=reason,
                stage="render",
                output_files=output_files,
                output_validation=output_validation,
            )
        finally:
            self._finish_executor()


_log("Registered /Engine/PythonTypes.DefectRenderFarmExecutor")
