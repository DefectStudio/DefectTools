"""Movie Render Graph callback for a stable latest MP4 for every rendered shot."""

import os

import unreal

import latest_mp4


@unreal.uclass()
class MRGLatestMP4(unreal.MovieGraphScriptBase):
    LOG_PREFIX = "[QuickWidgetToolsMRG_LatestMP4]"

    @unreal.ufunction(override=True)
    def on_job_finished(self, in_job_copy, in_output_data):
        super().on_job_finished(in_job_copy, in_output_data)
        if not self._get_render_success(in_output_data):
            self._log("Render was not successful. Skipping latest MP4 copy.")
            return

        job_name = str(getattr(in_job_copy, "job_name", "") or "").strip()
        destinations = {}
        for source_path in self._collect_output_paths(in_output_data):
            if os.path.splitext(source_path)[1].casefold() != ".mp4":
                continue
            try:
                if not os.path.isfile(source_path) or os.path.getsize(source_path) <= 0:
                    self._log_warning(f"Rendered MP4 is missing or empty: {source_path}")
                    continue
                destination_path = latest_mp4.destination_from_mp4(source_path, job_name)
            except (OSError, ValueError) as exc:
                self._log_warning(f"Skipping MP4 '{source_path}': {exc}")
                continue
            destination_key = os.path.normcase(destination_path).casefold()
            destinations.setdefault(destination_key, []).append((source_path, destination_path))

        copied_count = 0
        for candidates in destinations.values():
            if len(candidates) != 1:
                destination_path = candidates[0][1]
                sources = ", ".join(source_path for source_path, _destination in candidates)
                self._log_warning(
                    f"Multiple rendered MP4s target '{destination_path}'. Skipping ambiguous latest copy: {sources}"
                )
                continue
            source_path, destination_path = candidates[0]
            try:
                latest_mp4.copy_latest_mp4(source_path, job_name)
                copied_count += 1
                self._log(f"Copied '{source_path}' -> '{destination_path}'")
            except Exception as exc:
                self._log_warning(f"Latest MP4 copy failed for '{source_path}': {exc}")

        self._log(f"Latest MP4 copies completed: {copied_count}")

    def _get_render_success(self, output_data):
        for property_name in ("success", "b_success"):
            try:
                return bool(getattr(output_data, property_name))
            except Exception:
                continue
        return False

    def _collect_output_paths(self, output_data):
        """Collect only files reported by this completed graph job."""
        collected = []
        seen = set()
        try:
            graph_data = output_data.graph_data
        except Exception as exc:
            self._log_warning(f"Could not read graph output data: {exc}")
            return collected

        for render_output in graph_data or []:
            try:
                render_layers = getattr(render_output, "render_layer_data", None)
                if render_layers is None:
                    continue
                if hasattr(render_layers, "items"):
                    output_infos = (output_info for _identifier, output_info in render_layers.items())
                else:
                    output_infos = (render_layers[identifier] for identifier in render_layers)
                for output_info in output_infos:
                    for raw_path in getattr(output_info, "file_paths", []) or []:
                        path_text = str(raw_path or "").strip()
                        if not path_text:
                            continue
                        source_path = os.path.abspath(os.path.normpath(path_text))
                        source_key = os.path.normcase(source_path).casefold()
                        if source_key not in seen:
                            seen.add(source_key)
                            collected.append(source_path)
            except Exception as exc:
                self._log_warning(f"Could not read a graph render layer's output files: {exc}")
        return collected

    def _log(self, message):
        unreal.log(f"{self.LOG_PREFIX} {message}")

    def _log_warning(self, message):
        unreal.log_warning(f"{self.LOG_PREFIX} Warning: {message}")
