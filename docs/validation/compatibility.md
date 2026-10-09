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
| T09 Missing FFmpeg | `test_discovery_reports_missing_tools` (mocked lookup); `test_missing_tools_are_incomplete` |
| T10 Spaces in path | Baseline fixture name `baseline ü space.mp4` is the pass-scan input. CLI output paths in that test are plain names. |
| T11 Optional audio absent | `test_optional_absent_audio_passes` |
| T12 No qualifying intervals | Baseline pass, 0.5 s black tail, and one active channel produce no matching interval |
| T13 Missing optional metadata | `test_normalization_keeps_unknowns_and_rational_rates`. No generated unknown-duration file. |
| T14 Rational equivalence | `test_frame_rate_tolerance`; 30 vs `30000/1001` fails; CLI `--expect-fps 29.97` on the baseline passes |
| T15 Leading/trailing intervals | 0.5 s black tail is completed with no `BLACK_INTERVAL`. Leading-interval starts remain an M0 observation. |
| T16 Failure after success | `test_detector_failure_keeps_other_results_incomplete`; `test_damaged_bitstream_stays_incomplete`; `test_changed_input_stays_incomplete` |

`test_clean_wheel_scans_outside_checkout` installs the built wheel into a clean virtual environment and scans the same baseline from outside the checkout.

## Residuals

- Trailing black ends at the final picture PTS. A true 15-frame/0.5-second end-of-file run can be missed.
- One real video stream and one audio stream are inspected. Other tracks are inventoried only.
- Info-log grammar is not a stable FFmpeg API.
- Output caps and process cleanup are not a CPU, memory, or filesystem sandbox.
- File-only protocols and disabled data references are defense in depth, not filesystem isolation.
- Edit lists, variable frame rate, reference rejection, and network denial stay M0 observations. They are not product fixtures.
