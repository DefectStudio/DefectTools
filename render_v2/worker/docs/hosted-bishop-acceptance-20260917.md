# Hosted Bishop render acceptance — September 17, 2026

The supervised end-to-end test passed using the existing Bishop editor, the
released RenderWorkerV2.exe, and the separate hosted V2 service.

- Job: `ZZZ_000_0850_v004_20260917T172229.182Z_eb829c`.
- Project/shot: `s3bishop`, `ZZZ_000_0850`.
- Service: `https://defect-farm-api-v2.twilight-tooth-7b7c.workers.dev`.
- Submitted from the actual Unreal Movie Render Queue at 17:22:29 UTC.
- Worker: `ESCAPESHUTTLE3-V2`; its SQL attempt finished `complete` at
  17:24:34 UTC. Unreal exit code 0, reported success, no cancellation or simulation.
- Worker output validation succeeded for 41 files with no validation errors.
- Independent disk verification found exactly 40 nonempty v004 EXRs, frames
  1001–1040 inclusive, each with an EXR header. The v004 MP4 is nonempty
  (36,306 bytes) and has an MP4 file-type header. Files were written during
  this run, at 10:23:53–10:24:30 Pacific.
- Output folder:
  `F:/Defect DropBox2/Defect Dropbox/defect/s3bishop/sequences/ZZZ/ZZZ_000_0850/lite/unreal/_output`.
- EXR subfolder: `ZZZ_000_0850_beauty_v004`.
- MP4: `ZZZ_000_0850_beauty_v004.mp4`.

Submission used `manager/tools/prepare_unreal_v2_submission.py` to verify the
single Bishop queue entry and authenticate the private V2 submitter profile,
then set only this Unreal process's submission environment. The actual farm
publisher's resolved endpoint was verified remotely before the user submitted.
Saved V1 connection settings were not changed. Restarting the editor discards
the session routing, so permanent artist-side V2 submission setup remains work.

The preparation script was corrected and executed successfully through Epic's
Python remote execution connection to the already-running Bishop editor.
UE 5.8.2 exposes `SoftObjectPath.export_text()`; the attempted `to_string()` and
`SystemLibrary.break_soft_object_path()` calls are unavailable in its Python API.

This completes hosted submission, SQL claim, real Unreal rendering, output
validation, and SQL completion acceptance on the development computer. It does
not establish second-computer portability, Dropbox synchronization to another
machine, or visual quality of the rendered images/video.
