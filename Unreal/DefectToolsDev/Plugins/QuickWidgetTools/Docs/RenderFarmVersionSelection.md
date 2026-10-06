# V2-only render farm submission

The Rendering Tool's Send Render Queue to Farm button always submits to V2.
Both version checkboxes are removed; artists do not need to select a farm version.

The button explicitly calls the publisher with `use_v2=True`. The confirmation
dialog identifies V2. It never falls back to V1 if V2 is unavailable or lacks
credentials. Compatibility code also forces older widget assets to use V2.

V2 works immediately with the company submit credential bundled in
`Content/Python/render_farm_v2_submit.json`. Artists only update the complete
plugin; no credential installation or environment setup is needed.
The file is intentionally distributed and tracked with the plugin, as authorized
by the company. It contains only the V2 submit credential, with no worker or
manager credential. Anyone who can read the plugin can read this shared submit
credential; rotating it requires updating the bundled file and redistributing.

Optional administrator-provisioned local profiles (take priority over the bundle):

- V1: `%LOCALAPPDATA%/DefectStudio/RenderFarm/cloud_connection.json`.
- V2: `%LOCALAPPDATA%/DefectStudio/RenderFarmV2/company-submit.json`.

Each profile contains the corresponding company's `api_url` and `submit_token`.
Machine-local profiles remain outside Git; the bundled V2 submit profile is the
explicit exception. Separate environment overrides
are supported as `DEFECT_FARM_V1_API_URL` / `DEFECT_FARM_V1_SUBMIT_TOKEN` and
`DEFECT_FARM_V2_API_URL` / `DEFECT_FARM_V2_SUBMIT_TOKEN`.
Each profile's URL must match its company's V1 or V2 endpoint. The Rendering Tool
uses the V2 profile only; V1 profiles remain supported by the lower-level API.

Legacy `DEFECT_FARM_SUBMIT_TOKEN` is accepted only when its corresponding
`DEFECT_FARM_API_URL` matches the selected service. A legacy token without a URL
is treated as V1 and is not used by the Rendering Tool's V2 submission.

Both submission from the Rendering Tool and the embedded Render Farm Viewer use
V2. The viewer uses the company V2 read-only viewer credential.

Routing regression tests cover a fresh account with no profiles or environment
credentials, administrator overrides, invalid bundles, and V1/V2 isolation.
V2-only regression tests also prevent legacy widget state from routing to V1.
The bundled connection was also verified
against the hosted V2 service with no local profile or credential environment:
the database was connected and authentication returned the `submit` role.
The saved widget can be updated with `Tests/Unreal/apply_render_farm_v2_only.py`
and checked in Unreal with `Tests/Unreal/verify_render_farm_v2_only.py`. The live
verification intercepts submission, so it does not publish test jobs.
Run the migration in the full editor so it regenerates and saves the widget's
Blueprint metadata along with the layout.
