"""Route post-render actions from the MP4 and EXR files produced by this job."""

import os

import unreal

import mrg_callbacks_latestmp4
import mrg_callbacks_hero


@unreal.uclass()
class MRGAllRenderScripts(unreal.MovieGraphScriptBase):
    LOG_PREFIX = "[QuickWidgetToolsMRG_AllRenderScripts]"

    @unreal.ufunction(override=True)
    def on_job_finished(self, in_job_copy, in_output_data):
        super().on_job_finished(in_job_copy, in_output_data)
        collector = mrg_callbacks_latestmp4.MRGLatestMP4()
        if not collector._get_render_success(in_output_data):
            self._log("Render was not successful. Skipping post-render actions.")
            return

        output_types = self._collect_rendered_types(collector, in_output_data)
        if ".mp4" in output_types:
            self._run_callback(
                "latest MP4",
                mrg_callbacks_latestmp4.MRGLatestMP4,
                in_job_copy,
                in_output_data,
            )
        else:
            self._log("No MP4 was produced by this job. Skipping latest MP4 copy.")

        if ".exr" in output_types:
            self._run_callback(
                "EXR Hero copy",
                mrg_callbacks_hero.MRGHero,
                in_job_copy,
                in_output_data,
                image_extensions={".exr"},
            )
        else:
            self._log("No EXR was produced by this job. Skipping EXR Hero copy.")

    def _collect_rendered_types(self, collector, in_output_data):
        """Use completed-job outputs only; never scan for files from older renders."""
        output_types = set()
        for source_path in collector._collect_output_paths(in_output_data):
            extension = os.path.splitext(source_path)[1].casefold()
            if extension not in {".mp4", ".exr"}:
                continue
            try:
                if not os.path.isfile(source_path) or os.path.getsize(source_path) <= 0:
                    self._log_warning(f"Reported render output is missing or empty: {source_path}")
                    continue
            except OSError as exc:
                self._log_warning(f"Could not inspect render output '{source_path}': {exc}")
                continue
            output_types.add(extension)
        return output_types

    def _run_callback(self, label, callback_class, in_job_copy, in_output_data, image_extensions=None):
        try:
            callback = callback_class()
            if image_extensions is not None:
                callback.IMAGE_EXTENSIONS = image_extensions
            callback.on_job_finished(in_job_copy, in_output_data)
            return True
        except Exception as exc:
            self._log_warning(f"{label} callback failed: {exc}")
            return False

    def _log(self, message):
        unreal.log(f"{self.LOG_PREFIX} {message}")

    def _log_warning(self, message):
        unreal.log_warning(f"{self.LOG_PREFIX} Warning: {message}")

