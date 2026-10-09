# FrameGuard v0.1 — acceptance and verification matrix

**Status:** DRAFT. Tests are planned, not run. A1–A4 and M0 observations may require an owner-approved revision. U tests require no FFmpeg; I tests execute real FFmpeg/FFprobe unless explicitly noted as fake-child process tests; G gates combine CI/manual/package evidence. Test IDs are stable traceability identifiers, not promised pytest function names already present.

## Functional requirement coverage

| Requirement | Unit tests | Integration / acceptance | Fixture or dependency | Pass evidence and task owner |
|---|---|---|---|---|
| FR-01 Input validation | U06–U08/U10/U22/U23 | I01/I07/I08/I10/I13/I23/I24 | F01/F07/F11; OS permissions; fake runner | Valid MP4/MOV inspected; missing/nonregular/unreadable/invalid input controlled exit2; original hashes unchanged; M1.3–5/M4.1. |
| FR-02 Metadata | U09–U13 | I01/I13/I17/I18/I19 | F01/F02/F07/F08/F09/F10; missing-field payloads | Nullable typed inventory, both FPS fields/rotation/selected indexes correct, no invented fields; M1.4. |
| FR-03 Resolution | U13/U14 | I02/I17 | F01/F07 rotation | Explicit coded expectations mismatch critical with actual/expected; no requested fields unknown=>unavailable failure; M2.1. |
| FR-04 Reported FPS | U03/U15 | I03/I14/I19 | F01 rational variant/F10 | 29.97 equivalent pass, 30 vs30000/1001 fail; exact .001 inclusive tolerance; no cadence claims; M1.2/M2.2. |
| FR-05 Audio presence | U16/U21 | I04/I11/I17 | F02/F08 | Any inventory audio satisfies presence; required missing critical, optional missing info, silence skipped; M2.1/M2.5. |
| FR-06 Black intervals | U17–U20 | I05/I12/I15/I18/I20 | F03/F05/F09/F11 | Native warnings with index/timing/provenance; approved EOF limitation and threshold-edge behavior, never fabricated endpoint; M0.3/M2.3. |
| FR-07 Silence intervals | U17–U21 | I06/I11/I12/I15/I18/I20/I22 | F04/F05/F06/F09/F11 | Above-threshold collective audio not mislabeled; real silence intervals accurate within fixture tolerance; no-audio skip; M0.3/M2.4. |
| FR-08 Classification | U05/U16/U20/U21/U23 | I01–I06/I11/I16/I20 | Baselines, black/silence/mismatch, failed process | Objective expectations critical; detected creative intervals warning; failure separated and incomplete precedence; M1.2/M2.5. |
| FR-09 Reporting | U09/U24–U28 | I25/I26/I27 | Fixed model reports + E2E fixtures | All required fields, check states and consistent selected-stream findings across terminal/JSON/HTML; escaped offline HTML; M3.1–3. |
| FR-10 CLI | U01–U05/U23/U26–U28 | I01–I16/I25/I26/I27 | Installed CLI; invalid flags/options/outputs | Specified flags/help/version, paths with spaces, no traceback, exact 0/1/2 contract and optional approved timeout; M1.1/M3.3. |
| FR-11 Tool dependencies | U06–U08 | I09/I20/I21/I27 | PATH isolation, mocked builds, real baseline/newer binaries | Missing/incompatible tools/filters clear; bounded argv-only processes, versions captured; M0.1/M1.3/M4.2. |
| FR-12 Local-first | U07/U25/U26 | I23/I24/I27; G05 | Input hashes, reference/manifest attempts, network-denied process | No upload/network, no source modification, no remote HTML assets, self-contained inputs enforced; M0.4/M4.1/2. |

## Supplied scenarios T01–T16

| Scenario | Concrete test | Expected assertion | Owner |
|---|---|---|---|
| T01 Valid expected MP4 | I01 | Selected baseline properties match, applicable checks completed, no warning/critical, pass/exit0; M1 metadata-only path instead incomplete until M2 is delivered | M1.4/M2.5/M3.3 |
| T02 Incorrect dimensions | I02 | RESOLUTION_MISMATCH critical includes actual/expected coded dimensions; completed fail/exit1 | M2.1 |
| T03 Incorrect FPS | I03 | FPS_MISMATCH critical; reported average compared, fail/1 | M2.2 |
| T04 Required audio absent | I04 | AUDIO_REQUIRED_MISSING critical; silence skipped/no_audio, fail/1 not incomplete | M2.1/5 |
| T05 Two-second black | I05 | BLACK_INTERVAL warning around1–3s on decoded controlled fixture; warn/0 | M2.3 |
| T06 Three-second silence | I06 | SILENCE_INTERVAL warning around1–4s; warn/0 | M2.4 |
| T07 Missing input | I07 | Clear input diagnostic, incomplete if ScanReport exists, exit2; no traceback | M1.5 |
| T08 Invalid media bytes | I08 | Controlled probe failure; no-video checks not fabricated; exit2 | M1.4/5 |
| T09 Missing FFmpeg | I09 | Isolated PATH/mocked executable lookup gives dependency diagnostic, exit2 | M1.3/5 |
| T10 Spaces in path | I10 | Both scan and output paths with spaces/Unicode work, explicit argv retains whole filename | M1.4/M3.3 |
| T11 Optional audio absent | I11 | AUDIO_ABSENT info; silence skipped; other complete checks pass/0 | M2.1/4/5 |
| T12 No qualifying intervals | I12 | Constant nonblack/tone and subthreshold-short segments have no corresponding findings | M2.3/4 |
| T13 Missing optional metadata | U10, I13 | Pure payload omits optional fields=>null; actual unknown-duration case only if reproducibly generated, no crash. Mock does not establish FFmpeg behavior | M1.4 |
| T14 Rational equivalence | U15, I14 | avg30000/1001 expected29.97 no mismatch; expected30 does mismatch | M2.2 |
| T15 Leading/trailing intervals | I15 | Leading starts correct; trailing native-reported timestamps match build behavior and explicit A1 limitation; equal-threshold black EOF miss documented, not silently counted as success against an exact-coverage promise | M0.3/M2.3/4 |
| T16 Failure after success | U20, I16/I20 | Required detector failure makes incomplete/2 while successful checks/critical evidence remain; no false pass | M2.5 |

## Unit catalog (no native media tools)

| ID | Assertions / inputs | Intended test file and owner |
|---|---|---|
| U01 | CLI help/version/subcommand discovery; unknown command or missing input is2, help/version0 | test_cli.py; M1.1/M3.3 |
| U02 | Packaging metadata/console entry declaration; installed version does not import scan side effects | test_cli.py; M1.1 |
| U03 | Config dimensions/rates finite positive; integer/decimal/rational accepted; 0/0/NaN/Infinity rejected | test_config.py; M1.2 |
| U04 | Black/silence durations positive finite; silence<=86400; noise finite<=0; positive timeout; boundary options validated before runner invoked | test_config.py; M1.2 |
| U05 | Full status truth table including critical+failure=>incomplete, info-only pass, warning-only warn, unconfigured and no_audio skips allowed | test_status.py; M1.2 |
| U06 | Tool discovery: missing executable, too-old binary, missing filter/demuxer capability, malformed version, two version lines recorded | test_process.py; M1.3 |
| U07 | argv arrays/shellfalse/stdinDEVNULL; absolute safe input, no path-as-filter interpolation; FFREPORT removed and color disabled | test_process.py; M1.3 |
| U08 | Timeout, nonzero, cancellation, both pipes drained, event line cap and output cap fail closed; bounded tail is disclosed, not event truncation | test_process.py; M1.3 |
| U09 | Model optional fields null, enums stable, Fraction projection intentional, no nonfinite JSON, schema/tool versions distinct | test_models.py/test_reporting.py; M1.2/M3.1 |
| U10 | Probe numeric strings/N/A/0/0/missing fields=>null; malformed structural JSON/duplicate index fails; unexpected stream types inventoried | test_probe.py; M1.4 |
| U11 | Default-stream then lowest-index selection; attached picture excluded; multiple defaults deterministic; no fallback after failure | test_probe.py; M1.4 |
| U12 | Common origin and raw fallback, negative starts preserved, differing selected starts retain A/V offset; duration never used as end | test_probe.py; M1.4 |
| U13 | Matrix rotation preferred over legacy tag, conflicting metadata diagnostic; coded dimensions unchanged; SAR/DAR raw provenance | test_probe.py/test_metadata_checks.py; M1.4/M2.1 |
| U14 | Individual width/height expectations, match/mismatch values, unconfigured skip, requested unavailable dimension fails not invents | test_metadata_checks.py; M2.1 |
| U15 | Rational equivalence, .001 inclusive tolerance, above-bound fail, avg unavailable despite valid r unavailable-check; no VFR claim | test_fps.py; M2.2 |
| U16 | Required missing audio critical versus optional missing info; any inventoried audio satisfies presence | test_metadata_checks.py; M2.1 |
| U17 | Valid attributed native event grammar, multiple intervals, signed/scientific finite timestamps, correct selected index/provenance | test_black.py/test_silence.py; M2.3/4 |
| U18 | Nonfilter lookalikes ignored, malformed matching line/nonfinite/inconsistent duration/backwards times fail; duplicate start/unmatched end rejected | test_black.py/test_silence.py; M2.3/4 |
| U19 | Missing endpoint not invented; duration null; failed teardown events provisional; early attributable decode error followed by tail overflow, valid closing events and zero exit still failed via sticky state; accepted black native boundary precision caveat retained | test_black.py/test_silence.py; M2.3/4 |
| U20 | Injected check failure after completed checks preserves evidence but incomplete; prerequisite skips never conceal root failure | test_scanner.py; M2.5 |
| U21 | No-audio silence skip requiredfalse, independent of require_audio; existing audio requires silence completion | test_silence.py/test_scanner.py; M2.4/5 |
| U22 | Changed source stat/identity detected => incomplete; no chmod/write/delete operation on source; race guarantee not exaggerated | test_scanner.py; M2.5 |
| U23 | pass/warn0, completed critical1, incomplete/config/process/delivery2; cancellation2; output error not quality critical | test_status.py/test_cli.py; M1.2/M3.3 |
| U24 | Authoritative field contract, finite serialization, sort/order, nulls, no raw absolute paths, elapsed-runtime-only volatility | test_reporting.py; M3.1 |
| U25 | Hostile filenames/tags/text escaped in HTML; all check states/limitations displayed; no scripts/remote assets/untrusted links | test_html.py; M3.2 |
| U26 | Existing/input-alias/duplicate/missing-parent destinations refused; simulated race cannot replace; safe temp cleanup | test_outputs.py; M3.2/3 |
| U27 | Second requested output fails after first succeeds: exit2, truthful delivery message, no fictional transaction or changed media severity | test_outputs.py; M3.2 |
| U28 | Terminal strips/escapes ANSI/control injection and retains readable Unicode; concise incomplete diagnostic not hidden by findings | test_terminal.py; M3.3 |

## Fixture recipes and timing oracle

All fixtures are small, local, generated with argument-array FFmpeg jobs from lavfi. No download or copyrighted sample is needed. Store recipes/source and expected decoded properties, not large binaries; generate under a pytest temporary directory. Each generation step checks return code and probe/decode properties before using its output as an oracle. Different encoders/builds need not yield identical compressed bytes. Use input hashes before/after each scan only to check source nonmodification. For real footage, obtain consent and do not commit it or private absolute paths.

| Fixture | Deterministic recipe / purpose | Oracle and caveats |
|---|---|---|
| F01 Baseline | Six-second constant nonblack 320x240,30fps,yuv420p,H.264 MP4 +48kHz tone around -18dBFS,AAC; separate 60s1080x1920 variant for UX/benchmark | Explicitly probe dimensions/FPS/streams; decoded samples are above threshold. Baseline passes, benchmark has no acceptance speed target. |
| F02 Video only | F01 video with audio omitted; also very short <0.5s video | Inventory absence, no invented audio; very short video still analyzed, no minimum-length rejection. |
| F03 Interior black | Six-second same-geometry concatenation of1s nonblack,2s black,3s nonblack at30fps | Decoded-frame oracle black start1/end3; interior endpoints within one observed frame interval plus native printed-time precision. Avoid fades/near-black ambiguity. |
| F04 Interior silence | Tone1s, digital zero3s, tone2s at48kHz; PCM WAV/muxed MOV oracle, AAC MP4 support fixture separately | PCM onset/end within one sample plus printed precision; AAC controlled fixture <=0.05s onset/end error after accounting for decoded padding/start. If M0 fails this, fix recipe or escalate acceptance change; do not silently widen. |
| F05 Boundaries | Leading/trailing/all-black and silence; frame-count black tail below/equal/above0.5s (14/15/16 frames at30fps), audio2s edges | Check actual native EOF events. Under A1, black ends at last picture PTS and a15-frame trailing run may not emit; expected limitation must be visible. Audio EOF uses actual decoded sample end, not video/container end. |
| F06 Audio threshold/channels | Controlled low noise, audible tone, left-active/right-silent, both-silent stereo PCM; exact amplitude boundary synthetic samples | Silence is collective, not RMS/downmix. Threshold-equality unit/sample experiment verifies strict comparison on the chosen sample format; don't infer it from an encoded sine envelope. |
| F07 MOV/rotation | Self-contained H.264 MOV±AAC; second fixture coded landscape with right-angle rotation; optional anamorphic metadata | Probe rotation and coded dimensions. No display-dimension assertion from nominal rotation or SAR alone. |
| F08 Multiple streams | Two video/audio tracks with default dispositions/index order deliberately varied; attached artwork fixture if supported by generator | Probe all indexes/dispositions. Verify exact selected decode source; alternate defects stay uninspected and documented. Attachments never count as real video. |
| F09 Offsets | Remuxed/encoded controlled nonzero/negative common starts, unequal A/V starts, and explicit MOV/MP4 edit-list subcase; verify intended edit-list structure actually exists and preserve expected decoded packet/frame/sample PTS | Probe actual stored timestamps after muxing; generator requests alone are not oracle. Native filter output plus shared-origin model must preserve offsets. |
| F10 VFR/rational | Known selected-frame spacing VFR fixture; rational30000/1001CFR fixture | Assert raw reported rate fields and policy only; no FrameGuard claim that all frame intervals are uniform. Actual frame PTS establishes test ground truth. |
| F11 Invalid/truncated | Invalid byte file, audio-only media, attached-artwork-only, deliberately truncated/decode-damaged self-contained video | Where probe or decode fails, exit2/incomplete. A damaged file tolerated by FFmpeg is not guaranteed detected; use an observed failing corruption for regression and document non-goal. |
| F12 Operational/hostile | Controlled fake child programs for hangs/floods; hostile text/Unicode paths, directory/FIFO, preexisting reports and hardlinks; manifest/reference file | Fake children test runner independent of FFmpeg; adversarial reference attempts are rejected under safe demuxer/protocol options. No contact with real external services. |

For ordinary controlled black clips, timestamp tolerance is one actual frame duration plus native log-rounding error. Do not derive it from average FPS for VFR. Record printed precision on M0 builds; large PTS may have coarser string formatting than six fractional decimals. JSON rounding to six decimals is output formatting, not a promise of microsecond detection accuracy. For EOF under A1, assert native lower-bound endpoints/known misses, not fabricated exact coverage. If owner requires all >=0.5-second true trailing black intervals, A1 must be rejected and endpoint recovery designed before M2.

## Integration catalog

| ID | Concrete verification | Evidence / task |
|---|---|---|
| I01 | Real baseline MP4 scan with expected dimensions/FPS/audio, terminal and exports when available | F01, all applicable check states/pass0; M1/M2.5/M3.3 |
| I02 | Same file wrong width/height incl single supplied dimension | Critical actual/expected; M2.1 |
| I03 | Same file clearly wrong expected rate | FPS critical; M2.2 |
| I04 | Video-only with require-audio | Critical presence, silence skipped; M2.1/5 |
| I05 | Known interior black/native exact mapped video | F03 events/one-frame tolerance; M0.3/M2.3 |
| I06 | Known PCM/AAC interior silence/native exact mapped audio | F04/sample/AAC tolerance; M0.3/M2.4 |
| I07 | Missing file and directory/nonregular input | Controlled diagnostic2; M1.5 |
| I08 | Invalid bytes/audio-only/artwork-only input | Unsupported/probe diagnostic2; M1.4/5 |
| I09 | CLI executable lookup failure via PATH isolation; real runner not reached | ffmpeg/ffprobe missing cases; M1.3/5 |
| I10 | Space/Unicode input and output paths; basename is safe in all renderers | F12; M1.4/M3.3 |
| I11 | Video-only without require-audio | Info, silence skip, otherwise pass0; M2.1/4/5 |
| I12 | Nonblack/tone and sub-minimum intervals | No detector findings; M2.3/4 |
| I13 | Real available optional-metadata omissions and mocked omissions separately | U10 ensures general nullability; don't claim a fabricated native missing-field fixture; M1.4 |
| I14 | Real30000/1001 export expected29.97, then30 | Equivalent pass then mismatch; M2.2 |
| I15 | Leading/trailing/all-black/all-silent/below-equal-above minima | F05, native EOF contract and report caveat; M0.3/M2.3/4 |
| I16 | Scanner with one injected failed check after other successful checks | Hybrid orchestration test, not proof of native decoder failure; incomplete2; M2.5 |
| I17 | MOV, rotation, multiple streams/default changes/cover art | F07/F08 exact selected indexes and coded-dimension policy; M1.4/M2.1 |
| I18 | Nonzero/negative/unequal A/V starts, verified MOV/MP4 edit-list structure and decoded PTS, unknown duration where reproducible | F09 shared origin/raw provenance on floor/newer builds, no per-track reset; M0.3/M1.4/M2.3/4 |
| I19 | VFR/very short/rational media | F02/F10 metadata-only rate semantics, no pacing guarantee; M2.2/M4.1 |
| I20 | Native observed decode failure/truncation; cancellation teardown | F11 native errors/returncode, partial event evidence not complete; M0.3/M2.5 |
| I21 | Real Python child hangs/floods both pipes/long records; timeout/cancellation | Controlled process test no FFmpeg needed; bounded tail/events, reaped child; M1.3 |
| I22 | Collective multichannel silence and threshold above/below | F06, no downmix masking; M2.4 |
| I23 | Input hash preservation plus observed concurrent stat/identity change | All ordinary fixtures unchanged; simulated change incomplete; M2.5/M4.1 |
| I24 | Manifest/reference attempts under safe protocol/demuxer restrictions; denied-network scan | F12, reject unsupported sources before unsafe analysis; monitored/denied network no attempt/contact. File whitelist alone is not a filesystem sandbox; M0.4/M4.1 |
| I25 | Real filesystem clobber/input aliases/duplicate outputs/unwritable parent/collision and partial delivery | No bytes replaced; truthful exit2 on failure; M3.2/3 |
| I26 | One scan produces terminal/JSON/HTML with identical model facts; repeat semantics ignoring duration | Cross-renderer counts/codes/times/status/config/indexes; M3.1–3 |
| I27 | Wheel and sdist installed into fresh environment outside checkout; offline real scan both reports | Console script/resources/dependencies verified; M4.2 |

Unreadable file testing must run as a nonprivileged user or explicitly mock the open failure; a root process reading chmod000 does not prove the policy. Symlink/hardlink tests reflect tested OS behavior; Windows support is not inferred. Codecs unavailable in a custom build yield a documented incomplete/dependency diagnostic, not a hidden integration skip in a supported release job.

## CI and release gates

Start with Linux Python3.11 and3.14, macOS3.14, logging exact FFmpeg packages/builds; execute native integration for the declared formats. Add one reproducible FFmpeg6.1 floor job and a newer stable build; OS package availability alone does not establish these pins. Add Python3.12/3.13 pure-unit and wheel smoke if claiming the full interpreter range. Review Python3.14 behavior, including argparse keyword compatibility and subprocess handling. Keep features compatible with3.11; do not unconditionally use3.14-only parser constructor options.

| Gate | Evidence required | MVP completion criteria covered |
|---|---|---|
| G01 Test/lint | Actual `pytest`, `ruff check .`, `ruff format --check .` exit0; required integration jobs no skips; failures resolved | 3–14 |
| G02 Runtime/support | OS/interpreter/binary/codec compatibility record; actual macOS and Linux evidence for public claims | 1,3–8,11,17 |
| G03 Package install | Build wheel/sdist; clean installs outside checkout; help/version/scan returns expected exits and exports | 1,2,10 |
| G04 CI | Actual authorized GitHub Actions run URL/commit SHA with successful required jobs | 15 |
| G05 Privacy/safety | Offline/network-denied scan, unchanged media hashes, safe outputs, no remote report dependencies or secret/media artifacts | 12,13 |
| G06 New-user workflow | Reader follows README on clean tested system to generate/read terminal/JSON/HTML and explain warnings/incomplete | 16,17 |
| G07 Performance/limitations | Measured synthetic/real run parameters/timing/memory where observable; accurate documented EOF/streams/rates/codec limits | 11,17 |
| G08 Release | Owner-selected license, provenance/name ownership, reviewed acceptance dossier and explicit authorized tag/release | 18 |

Each test record captures command/argv, exit code, timestamp, OS/architecture, Python/tool versions, fixture recipe and expected/observed result. CI links supplement rather than replace tool/fixture provenance. Known unsupported cases have explicit safe-rejection/limitation evidence. No gate is passed in this planning session.

