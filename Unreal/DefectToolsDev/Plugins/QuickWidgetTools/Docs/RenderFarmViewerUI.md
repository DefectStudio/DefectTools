# Render Farm Viewer UI contract

The viewer reads jobs and workers from the company V2 service at
`https://defect-farm-api-v2.twilight-tooth-7b7c.workers.dev` using its bundled
read-only viewer credential. Artists do not need a local connection profile.
The rendering tool's V1/V2 submission selector does not change this viewer.
`/api/v1` in request paths is the API protocol version, not the farm generation.

Python owns API reads, data normalization, and refresh timing.
UMG owns every visual decision: hierarchy, anchors, sizing, spacing, fonts,
colors, brushes, wrapping, and visibility.

## Main widget

`WBP_09_Render_Farm_Viewer` may be redesigned freely, but keep these widgets
checked as **Is Variable**:

- `FarmViewerStatus` — TextBlock
- `FarmViewerSummary` — TextBlock
- `FarmViewerList` — VerticalBox inside a vertically oriented ScrollBox
- `FarmViewerRefreshButton` — Button
- `FarmViewerJobsButton` — Button
- `FarmViewerWorkersButton` — Button

Python never changes their layout properties.

For responsive sizing, `FarmViewerList` must use a ScrollBoxSlot with
**Horizontal Alignment = Fill**. Its ScrollBox and ancestor layout slots must
also use Fill sizing up to the main stretched CanvasPanel slot. The Unreal
viewer is deliberately list-only and must not contain a details panel.

## Designer-owned child widgets

The assets live in `EditorWidgets/RenderFarm`. Each asset contains Text variables
in the **Data** category. Build any UMG hierarchy you want and bind your TextBlock
Text properties to those variables.

### WBP_RenderFarmCellText

Reusable body-text cell for the Render Farm lists. Its root `CellText` TextBlock
uses Roboto, Regular at size 8, and Slate's inherited
foreground color. `Text` is instance-editable and exposed on spawn. Use the
public Blueprint `SetText` function when the value changes after construction.

### WBP_RenderFarmJobsTable

The jobs view creates exactly one instance of this widget. Its Data variables
are `JobName`, `Worker`, `User`, `Status`, `Time`, `Errors`, `Progress`,
`Submitted`, and `Completed`. Each variable contains that entire column as
newline-delimited text, with one line per job. Put static header labels and all
nine vertical body columns inside this one Designer hierarchy so their widths
can be adjusted together.

The visible body columns are RichTextBlocks named `JobNameRichText`,
`WorkerRichText`, `UserRichText`, `StatusRichText`, `TimeRichText`,
`ErrorsRichText`, `ProgressRichText`, `SubmittedRichText`, and
`CompletedRichText`. Python fills them with one tagged line per job using the
shared `DT_RenderFarmJobStatusStyles` table. The legacy `TextBlock` through
`TextBlock_8` controls remain collapsed to preserve their existing Blueprint
bindings and type compatibility.

Each visible body column now shares a `FieldColumn` VerticalBox with a
`FieldSortButton` header (for example, `JobNameColumn` contains
`JobNameSortButton` and `JobNameRichText`). Style those nine buttons and their
`FieldSortLabel` children directly in the Designer, but keep their names. Python
binds the click events and adds `▲` or `▼` to the active heading. Text columns
start ascending; Time, Errors, Progress, Submitted, and Completed start
descending; clicking the active heading toggles direction, and blank values
remain at the bottom. The viewer initially sorts by `Submitted ▼`, placing the
newest submitted jobs at the top.

The nine sorting buttons copy their button style and label typography from
`FarmViewerRefreshButton`, keeping the Jobs header visually consistent with the
Refresh, Jobs, and Workers toolbar controls. Their labels use 70% of the
Refresh label's font size so the table headings remain compact.

`WBP_RenderFarmJobHeader` and `WBP_RenderFarmJobRow` are retained as legacy
layout references but are no longer instantiated by the viewer.

### WBP_RenderFarmWorkersTable

The workers view creates exactly one instance of this widget. Its Data
variables are `WorkerName`, `Project`, `Status`, `CurrentJob`, `LastSeen`, and
`Commit`. Each variable contains that entire column as newline-delimited text,
with one line per worker. Put static header labels and all six vertical body
columns inside this one Designer hierarchy so their widths can be adjusted
together.

The visible body columns are RichTextBlocks named `WorkerNameRichText`,
`ProjectRichText`, `StatusRichText`, `CurrentJobRichText`, `LastSeenRichText`,
and `CommitRichText`. Python fills them with one tagged line per worker using
the shared `DT_RenderFarmWorkerStatusStyles` table. The legacy `TextBlock`
through `TextBlock_5` controls remain collapsed because their existing
Blueprint bindings must remain type-compatible; do not make those legacy
controls visible.

`WBP_RenderFarmWorkerHeader` and `WBP_RenderFarmWorkerRow` are retained as
legacy layout references but are no longer instantiated by the viewer.

## Safe redesign rules

- Keep `WBP_RenderFarmJobsTable`, `WBP_RenderFarmWorkersTable`, and their
  Data-variable names unchanged.
- Their internal visual hierarchies may be completely replaced.
- Keep `FarmViewerList` as the Fill-aligned list container described above.
- Job and worker rows do not require a `RowButton`.
