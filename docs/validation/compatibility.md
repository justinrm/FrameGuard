# Claimed envelope and scenario coverage

Recorded from the existing local scan and [M0 decision](m0-decision.md). No new platform measurements.

## Claimed

macOS arm64, Python 3.14.8, exact FFmpeg/FFprobe 9.0.2. `discover_tools` accepts only that FFmpeg version. No 6.1 floor, Linux media run, or other-build support is claimed. GitHub Actions runs unit tests only and does not install FFmpeg.

## T01–T16

| Scenario | Where it is checked |
|---|---|
| T01 Valid expected MP4 | `test_real_baseline_scan_passes`; installed CLI pass exit |
| T02 Incorrect dimensions | `test_rotated_copy_still_mismatches_portrait_coded_size`; CLI `--expect-width` |
| T03 Incorrect FPS | `test_integer_fps_mismatches_rational_baseline` |
| T04 Required audio absent | `test_required_missing_audio_fails_and_skips_silence` |
| T05 Two-second black | `test_interior_black_warns_and_short_tail_does_not` |
| T06 Three-second silence | `test_pcm_silence_warns_and_one_active_channel_does_not` |
| T07 Missing input | CLI missing-file scan; `test_missing_input_is_controlled_incomplete` |
| T08 Invalid media bytes | CLI scan of non-media bytes |
| T09 Missing FFmpeg | `test_discovery_reports_missing_tools` (mocked lookup); `test_missing_tools_are_incomplete`; `test_installed_cli_reports_missing_ffmpeg` |
| T10 Spaces in path | Baseline fixture name `baseline ü space.mp4` is the pass-scan input. `test_installed_cli_writes_a_spaced_unicode_report` writes `out ü report.json`. |
| T11 Optional audio absent | `test_optional_absent_audio_passes` |
| T12 No qualifying intervals | Baseline pass, 0.5 s black tail, and one active channel produce no matching interval |
| T13 Missing optional metadata | `test_normalization_keeps_unknowns_and_rational_rates`. No generated unknown-duration file. |
| T14 Rational equivalence | `test_frame_rate_tolerance`; 30 vs `30000/1001` fails; CLI `--expect-fps 29.97` on the baseline passes |
| T15 Leading/trailing intervals | `test_leading_black_starts_at_zero` expects black 0–1. The 0.5 s black tail completes with no `BLACK_INTERVAL`. |
| T16 Failure after success | `test_detector_failure_keeps_other_results_incomplete`; `test_damaged_bitstream_stays_incomplete`; `test_changed_input_stays_incomplete` |

`test_clean_wheel_scans_outside_checkout` installs the built wheel into a clean virtual environment and scans the same baseline from outside the checkout. `test_clean_sdist_scans_outside_checkout` builds a wheel from the sdist and does the same scan. The clean install does not download a build backend.

## I24 restricted inputs

Recorded on macOS arm64, `.venv` Python 3.14.8, FFmpeg/FFprobe 9.0.2:

```text
$ .venv/bin/python -m pytest tests/integration/test_restricted_inputs.py -q
exit 0; 1 passed in 1.71s
```

`test_manifest_reference_and_url_do_not_connect` scans three inputs through `scan`, with a loopback TCP listener on an ephemeral `127.0.0.1` port:

- An HLS manifest named `manifest.mp4` whose only URL is that listener. Result: probe produces no metadata, status `incomplete`, exit 2.
- The same M0 `alis` patch as `tools/validate_media.py`, applied to the generated baseline, with the listener URL as the alias target. Result: status `incomplete`, exit 2.
- The listener URL passed as the scan path. `pathlib` treats it as a filesystem path, so the scan stops at `input_unavailable` and never starts FFmpeg. Result: status `incomplete`, exit 2.

The listener accepted 0 connections. SHA-256 of the manifest, the patched file, and the baseline was unchanged. Detector timeout for this test is 10 seconds. The accept count is loopback TCP only. It does not prove a packet never left the machine, and file-only protocols plus disabled data references are still not a filesystem sandbox.

## Added product scans

These use the same local 9.0.2 build. They are not a second-platform measurement.

- `test_edit_list_keeps_one_origin_and_av_offset`: two `elst` boxes, format origin 0, video start 0, audio start 0.5, black near 1–3, silence start near 1.502667. The audio/video offset is still present after one shared origin.
- `test_leading_black_starts_at_zero`: black 0–1.
- `test_aac_silence_matches_recorded_oracle`: silence within 0.05 s of 1.003792–4.009542.
- `test_short_and_vfr_scans_do_not_claim_pacing`: a clip under 0.5 s is scanned, and a variable-frame-rate clip is judged only by `avg_frame_rate`. The report does not claim uniform pacing.
- `test_multi_track_selects_default_real_streams`: selected video 1 and audio 3; indexes 0, 2, and attached picture 4 stay uninspected.
- `test_directory_and_fifo_are_not_regular_files`: directory and FIFO return `input_not_regular`, incomplete, exit 2.

`scan` follows a symlink input and reads the target. It does not reject a hardlink input. An existing output path, including a symlink or hardlink to the source, is refused.

## Residuals

- Trailing black ends at the final picture PTS. A true 15-frame/0.5-second end-of-file run can be missed.
- One real video stream and one audio stream are inspected. Other tracks are inventoried only.
- Info-log grammar is not a stable FFmpeg API.
- Output caps and process cleanup are not a CPU, memory, or filesystem sandbox.
- Loopback accept counts are not a proof that no packet left the machine.
- 14-frame and 16-frame black tails, silence edges at 1.99/2.00/2.01 seconds, and the atom-patched negative-CTS file stay Milestone 0 evidence.
- An unreadable file is not a product test. `chmod 000` on this Mac does not prove the owner cannot stat the file. A missing path still returns `input_unavailable`.
- No second FFmpeg build, Linux media run, owner footage, or GitHub Actions URL is recorded. Actions still runs unit tests only and does not install FFmpeg.
