"""Prepare the current Unreal session for the supervised hosted Bishop test.

Run from Unreal's Cmd console with: py "<absolute path to this file>"
No jobs are submitted and no saved connection settings are changed.
Restart Unreal to discard this session's V2 submission settings.
"""

import json
import os
from pathlib import Path
from urllib.request import Request, urlopen


COMPANY_URL = "https://defect-farm-api-v2.twilight-tooth-7b7c.workers.dev"
TEST_SEQUENCE = "/Game/_S3Bishop/Sequences/ZZZ/ZZZ_000_0850.ZZZ_000_0850"


def read_json(url, token=None):
    headers = {"User-Agent": "DefectUnrealFarmSubmitter/1.0"}
    if token:
        headers["Authorization"] = "Bearer " + token
    with urlopen(Request(url, headers=headers), timeout=20) as response:
        return json.load(response)


def prepare_connection(environ=None, profile_path=None):
    environ = os.environ if environ is None else environ
    profile_path = profile_path or (
        Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        / "DefectStudio/RenderFarmV2/company-submit.json"
    )
    profile = json.loads(Path(profile_path).read_text(encoding="utf-8-sig"))
    url = str(profile.get("api_url", "")).strip().rstrip("/")
    token = str(profile.get("submit_token", "")).strip()
    if url != COMPANY_URL or not token:
        raise RuntimeError("A valid company V2 submitter profile is required.")
    health = read_json(url + "/health")
    if (health.get("ok") is not True
            or health.get("service") != "defect-farm-api-v2"
            or health.get("environment") != "v2-production"
            or health.get("database") != "connected"):
        raise RuntimeError("The hosted V2 database did not pass its health check.")
    auth = read_json(url + "/api/v1/auth/check", token)
    if auth.get("ok") is not True or auth.get("role") != "submit":
        raise RuntimeError("V2 submitter authentication failed.")
    environ["DEFECT_FARM_API_URL"] = url
    environ["DEFECT_FARM_SUBMIT_TOKEN"] = token
    return url


def main():
    import inspect
    import unreal
    import publish_render_queue_to_farm

    try:
        if "use_v2" in inspect.signature(publish_render_queue_to_farm.run).parameters:
            unreal.log("[V2 setup] Use the V1/V2 checkboxes beside Send Render Queue to Farm. Select V2 for the company V2 service. No session override was applied.")
            return
        queue = unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem).get_queue()
        jobs = list(queue.get_jobs() or [])
        sequence_paths = [
            job.get_editor_property("sequence").export_text()
            for job in jobs
        ]
        for sequence_path in sequence_paths:
            unreal.log("[V2 setup] Queued sequence: " + sequence_path)
        if len(jobs) != 1:
            raise RuntimeError("Keep only ZZZ_000_0850 in the queue for this first test.")
        sequence_path = sequence_paths[0]
        if sequence_path != TEST_SEQUENCE:
            raise RuntimeError("This test requires the Bishop ZZZ_000_0850 sequence.")
        url = prepare_connection()
        unreal.log("[V2 setup] V2 READY: submitter authenticated; database connected.")
        unreal.log("[V2 setup] Submission destination: " + url)
        unreal.log("[V2 setup] One Bishop shot queued. Nothing submitted yet.")
        unreal.log("[V2 setup] This editor session now submits to V2; restart Unreal to restore saved routing.")
    except Exception as error:
        unreal.log_error("[V2 setup] NOT READY — do not submit: " + str(error))
        raise


if __name__ == "__main__":
    main()
