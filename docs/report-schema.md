# FrameGuard report schema 0.1.0

JSON is the authoritative report. Terminal text and static HTML are renderings of the same object. `analysis_duration_seconds` is elapsed runtime and may differ between equivalent scans. Unknown values are null. Rational frame rates are strings such as `30000/1001`. Times are finite decimal seconds. Absolute paths, argv, and tool paths are omitted.

Top-level fields: `schema_version`, `tool_version`, `input` (`display_name`, `size_bytes`), `media_metadata`, `configuration`, `timeline`, `checks`, `findings`, `diagnostics`, `overall_status` (`pass`, `warn`, `fail`, `incomplete`), `analysis_duration_seconds`, `tool_versions`.

`media_metadata` is null when probing did not produce an inventory. Otherwise it includes `streams`, `selected_video_index`, `selected_audio_index`, `selection_reason`, and `uninspected_stream_indexes`. Stream fields that do not apply are null.

`checks` use status `completed`, `skipped`, or `failed`, plus `reason_code`, `required`, and `limitations`. A completed check can still have findings. `findings` use severity `info`, `warning`, or `critical` and may include an `interval`. Findings are ordered by severity, check, start time, stream index, then code.

`overall_status` is `incomplete` when a required check did not complete, `fail` when a completed scan has a critical finding, `warn` when the strongest completed finding is a warning, and `pass` otherwise. Exit codes are 0 for pass or warn, 1 for fail, and 2 for incomplete analysis or a configuration or output error.
