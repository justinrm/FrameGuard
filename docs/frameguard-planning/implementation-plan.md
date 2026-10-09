# FrameGuard v0.1 Implementation Plan

> **For agentic workers:** After owner approval, use superpowers:subagent-driven-development or superpowers:executing-plans task-by-task. This is an unapproved draft, not authorization. Steps use checkboxes for future execution; none are completed by this planning session.

**Goal:** Build an installable offline Python CLI that inspects one exported video, applies technical expectations, detects native black/silence intervals, and renders consistent terminal/JSON/static-HTML evidence.

**Architecture:** Standard-library CLI and typed dataclasses, a single bounded subprocess layer, FFprobe normalization, pure metadata policies, two separate detector adapters, and scanner aggregation. One ScanReport drives all renderers; processing/delivery failures stay separate from media severity.

**Tech stack:** Python 3.11–3.14 target, FFmpeg/FFprobe proposed floor 6.1, argparse/dataclasses/subprocess/fractions/json/html/pathlib, pytest, Ruff, Hatchling build backend. No third-party Python runtime dependency. uv optional.

**Spec:** [planning-review.md](planning-review.md) and [architecture.md](architecture.md), reconciled with the owner's original supplied specification. Acceptance definitions: [acceptance-tests.md](acceptance-tests.md). A1–A4 are approval gates, not accepted assumptions.

## Global constraints

Single regular local input, no source modification, no network/telemetry/accounts, no remote assets in reports, no cloud/AI/Rust/editing/batch scope. Preserve supplied defaults: black minimum 0.5 s with explicit pic_th=0.98/pix_th=0.10; silence minimum 2 s/-60 dB collective channels. Coded-dimension policy, avg_frame_rate tolerance 0.001 FPS, deterministic selected streams, unknown=null, completed/skipped/failed check states, incomplete precedence, exit 0/1/2, no silent overwrite. Effective operational limits and timestamp model are exactly those in architecture.md, contingent on A3/M0. Only claim tested codecs/containers/platforms/tool versions. No install, Git initialization, public remote, commit, push, or release action is authorized in this planning session.

## File map and shared interfaces

Create src/frameguard/{__init__,cli,models,process,probe,scanner,reporting}.py; src/frameguard/checks/{__init__,metadata,black,silence}.py; pyproject.toml; README.md; .gitignore; .github/workflows/ci.yml. Tests live in tests/unit and tests/integration with tests/conftest.py and tests/fixtures/generate.py. M0 experiment helper is tools/validate_media.py, not production library code. Validation and release evidence goes in docs/validation/ and docs/release/. LICENSE awaits A4. No directories are scaffolding tasks by themselves: each file is created by the task needing its verified deliverable.

All functions/models are defined in architecture.md's contract. Runner = Callable[[ProcessSpec], ProcessResult]. M1.2 produces shared ScanConfig/InputInfo/StreamMetadata/MediaMetadata/Timeline/ToolVersions/Diagnostic/CheckResult/Interval/Finding/ScanReport/ProcessSpec/ProcessResult/Toolchain/ProbeResult and ConfigError/DependencyError/OutputError. M1.3 produces discover_tools/run_process; M1.4 produces normalize_probe/choose_streams/choose_timeline/probe_media; M2.1/2 produce metadata policies; M2.3/4 produce BlackParser/SilenceParser and detect functions; M1.5 creates scan as a deliberately incomplete metadata path, M2.5 completes it. M1.2 produces calculate_status/exit_code; M3.1 produces report_to_dict/render_json; M1.1 starts main and M3.3 finalizes CLI/render_terminal. M3.2 produces render_html/publish_report. Do not change a signature silently across task boundaries.

## Review focus

An existing/symlinked/hardlinked output or race must never overwrite source/report (M3.2/M3.3, U26/I25). Media resembling a playlist or containing external references must not cause network/reference loading (M0.4/M1.4/M4.1, I24). Successful teardown logs after decoding failure must not turn partial analysis into a pass (M0.3/M2.5, U20/I20). Offset/unknown timestamps must never be normalized per stream independently or guessed from duration (M0.3/M1.4/M2.3/4, U12/I18). Filenames/metadata with ANSI/HTML content or Unicode must remain safe and readable (M1.4/M3.2/3, U25/U28/I10). Each owner task below pins these behaviors.

## Milestones, gates, and effort

Complexity S means one focused implementation/review cycle; M means several tightly coupled cases; L means research-heavy uncertainty and should be split if experiments reveal a new design. These are relative estimates, not hour promises. Each task's output is independently reviewable. Execute a targeted red/green test cycle where implementation is involved; an observational experiment need not be forced into a failing-test ritual. Run broader regression at every milestone. Coherent commits happen only in an owner-authorized local Git repository; never git add the whole folder or media blindly.

| Milestone | Prerequisites | Expected output / acceptance | Verification and principal risk | Relative effort |
|---|---|---|---|---|
| M0 Technical validation | Owner approves experimental scope and A1–A3 or records alternatives | Exact builds/commands, fixture observations, EOF/timeline/completion decision, offline-safe input strategy, source references; every gate evidenced | Re-run saved bounded commands/observations; no product claim. Stop on unsupported environment or unresolved timing/safety contract | L; highest uncertainty |
| M1 Package/media inspection | M0 gates pass; explicit conditional M1 authorization | Wheel/install/help/version/scan metadata path, normalized nullable inventory, controlled failures; incomplete QA clearly labeled | Installed CLI smoke + unit/probe integration + first CI. Risk: workspace runtime mismatch, selection/probe drift | M |
| M2 Quality checks | Stable M1 interfaces and accepted M0 parser/timing behavior | All five check functions, findings, status/skips, complete internal report | Unit + real FFmpeg for policies/boundaries/failures. Risk: EOF limitations and false success | L |
| M3 Reporting | Stable report/check model | Consistent terminal/JSON/HTML, safe output handling, exact exit contract; first complete user workflow | CLI E2E, cross-renderer assertions, malicious text, report collisions. Risk: report clobber or conflicting semantics | M |
| M4 Release hardening | Complete workflow and A4 resolved before distribution | Acceptance evidence, CI/support envelope, wheel/docs/manual smoke, benchmarks, license and authorized release | Run all release gates; no skipped required integrations. Risk: premature support/publication claims | M–L |

## M0 — technical validation, no application scaffolding

### M0.1 Runtime and capability inventory

Dependencies: owner authorization; complexity S. Create docs/validation/m0-environment.md. Record OS/architecture, exact Python candidates, FFmpeg/FFprobe version lines, blackdetect/silencedetect/mov demuxer options and availability. Interfaces: consumes host-authorized command access, produces an environment/capability evidence record used by M0.2 and M1.3. Completion: an actual Python >=3.11 and approved FFmpeg floor are available in the environment chosen for coding, or a documented blocker stops M1. Linux observations do not establish macOS support. Tests/output: version/filter/demuxer commands with exit codes, redacted environment details, no media analysis yet.

- [ ] Record `python3 --version`, `ffmpeg -version`, `ffprobe -version`, and `uv --version` if used; locate executables without reading credentials.
- [ ] Run bounded `ffmpeg -hide_banner -filters`, `ffmpeg -hide_banner -h filter=blackdetect`, `-h filter=silencedetect`, and `-h demuxer=mov`; record relevant capabilities and restrictions.
- [ ] Compare observations to A3; do not install/replace host binaries without permission or claim a nonexistent runtime.
- [ ] Review evidence for reproducibility; commit later with M1 repository setup only if Git work is authorized.

### M0.2 Controlled baseline and probe experiments

Dependencies: M0.1; complexity M. Create tools/validate_media.py and docs/validation/m0-observations.md with only bounded experiments; generated clips go in an ignored temporary directory. Consumes approved executable paths; produces reproducible lavfi recipes and FFprobe observations, not production code. Fixtures: F01 baseline MP4, F02 video-only, F07 MOV, F08 multiple streams/attached picture. Completion: exact selection/optional-field examples and safe MP4/MOV command behavior recorded. Required experiments: I01/I04/I07/I08/I17, including space/Unicode filenames. No dependency installed solely to generate clips.

- [ ] Define generation recipes with constant nonblack video, tone clearly above -60 dB, explicit codecs/dimensions/FPS and stream mapping; check native exit codes.
- [ ] Probe show_format/show_streams JSON; verify rational rate strings, nullable values, actual absolute indexes, and no source modification.
- [ ] Record inputs/decoded expectations, selected streams, command argv and exact binary versions; keep fixture bytes out of public commits.
- [ ] Re-run recipes and observations; document which output values are build-dependent rather than hard-code a fabricated universal JSON snapshot.

### M0.3 Detector EOF, timestamp, and failure contract

Dependencies: M0.2 and A1; complexity L. Extend tools/validate_media.py and m0-observations.md. Produces accepted parser/event grammar, timeline convention and error-completion evidence for M2.3/4/5. Fixtures: F03/F04 known interior black/silence, F05 EOF/leading/all-black, F09 offsets, F10 VFR; truncated F11. Completion: native leading/trailing/equal-threshold behavior documented on the floor and newer tested build; shared-origin transformations and failure teardown verified. If A1 is rejected or experiments contradict contract, stop for a revised design.

- [ ] Execute separate mapped black/silence null-output jobs using candidate copyts/no-resampling commands; record raw event output and zero/nonzero return codes.
- [ ] Compare interior boundaries to decoded-frame/sample ground truth; test EOF just below/equal/above 0.5 s, silence 2 s edges, all-black/all-silent and unequal-channel activity.
- [ ] Test nonzero/negative A/V starts, unknown-origin mocks, and an explicit MOV/MP4 edit-list subcase: verify the intended edit list is actually stored, establish decoded frame/sample PTS, and compare raw detector/shared-origin times on floor/newer builds. Demonstrate no independent per-stream resets; unresolved edit-list behavior blocks the timing gate unless the owner approves a safe support restriction. Test decode error/cancellation teardown, not merely clean EOF.
- [ ] Save pass/fail/limitation evidence for I05/I06/I14/I15/I18/I19/I20; pin source/release references and record any owner-approved acceptance revisions.

### M0.4 Offline and operational safety gate

Dependencies: M0.1–3; complexity M. Create docs/validation/m0-decision.md. Consumes experimental command evidence; produces accepted argv/limits and go/no-go recommendation. Completion: no network/reference loading under approved MOV demuxer/protocol restrictions, no source writes, verified cancellation/timeout strategy, no silent event loss. Tests/output: I24 plus temporary fake child processes for timeout/output flooding. No need to build the production wrapper yet.

- [ ] Validate file-only protocols, forced MOV demuxing and disabled external data references; attempt a playlist/reference fixture using only controlled local test resources.
- [ ] Observe timeout/cancellation and bounded-output assumptions; define two-second terminate/kill grace and return-code/error policy without assuming log closure proves EOF.
- [ ] Record unresolved issues as blockers, not optimistic TODOs; list exact supported commands/builds and A1 boundary limitation.
- [ ] Present the M0 evidence and request permission to proceed unless the owner already explicitly authorized conditional M1 and every gate passed.

## M1 — installable package and inspection path

### M1.1 Installed CLI spine

Dependencies: successful M0 and M1 authorization; complexity S. Create pyproject.toml, src/frameguard/__init__.py, cli.py, tests/unit/test_cli.py, README.md, .gitignore. Produces main(argv)->int and installed `frameguard` entry point; main initially help/version only. Completion: `requires-python >=3.11`, Hatchling, pytest/Ruff dev extra, zero runtime dependencies, correct installed version, src layout. Tests: U01/U02 and wheel help/version smoke. Initialize Git only with permission and after checking owner-side parent guidance.

- [ ] Define `test_help_and_version`: installed `frameguard --help` exit 0 and scan command help is discoverable; `--version` includes 0.1.0. Establish console-script packaging failure before adding the entry point.
- [ ] Add minimal argparse/packaging behavior and dependency separation; configure pytest importlib mode and Ruff py311.
- [ ] Run `python -m pytest tests/unit/test_cli.py -q`, `ruff check .`, `ruff format --check .`, and a built-wheel help/version invocation outside the checkout; expected exit 0.
- [ ] Commit only package/CLI spine files with a coherent message after reviewing staged diff.

### M1.2 Models, validation, statuses, and finite serialization boundary

Dependencies: M1.1; complexity M. Create models.py, tests/unit/test_models.py, test_config.py, test_status.py. Produces every shared type, validate_config, calculate_status and exit_code, as defined in architecture.md. Completion: finite/nullable semantics, reason codes, stable finding/check IDs, exact status precedence, 0/1/2 behavior. Tests U03–U05/U09/U22/U23: unconfigured skips do not force incomplete; required failed check dominates critical findings; info-only is pass; warning-only exit0; delivery error exit2.

- [ ] Pin assertions: Fraction('29.97') accepted, zero denominators/NaN/Infinity/negative durations/zero dimensions rejected; supplied dimensions need only their individual expectations; silence duration >86400 rejected.
- [ ] Pin status truth table: completed+critical => fail/1; completed+warning => warn/0; required failure+critical => incomplete/2; optional no_audio skip+info => pass/0.
- [ ] Implement explicit validators/types without Pydantic/coercion magic. Keep output Paths out of ScanConfig.
- [ ] Run `python -m pytest tests/unit/test_models.py tests/unit/test_config.py tests/unit/test_status.py -q`; all assertions must pass. Commit a focused model/policy-boundary change.

### M1.3 Bounded process runner and toolchain discovery

Dependencies: M1.2 and accepted M0 commands; complexity M. Create process.py, tests/unit/test_process.py, tests/integration/test_process.py. Produces discover_tools and run_process; consumes ProcessSpec/Result/Toolchain. Completion: argv-only invocation, stdin closed, tool version/filter verification, concurrent pipe drain, exact limits, cancellation/timeout cleanup, safe diagnostics. Tests U06–U08/I21: missing ffprobe or filter, nonzero exit, flood, long line, hanging child, teardown after termination, no surviving child. Tool absence must not yield a traceback.

- [ ] Define fake-child tests for both-pipe flood and hang; assert timeout/output_limit flags, bounded diagnostic tail, child reaped, and no shell invocation. Assert FFREPORT is removed and color disabled.
- [ ] Define tool-discovery tests for absent ffmpeg/ffprobe, below-floor versions, unsupported filter/demuxer options and parseable exact version lines; executable lookup is via shutil.which.
- [ ] Implement the runner/discovery in the one process module; do not hide raw subprocess calls in checks. Grace is two seconds before kill; any authoritative-output loss becomes failure.
- [ ] Run `python -m pytest tests/unit/test_process.py tests/integration/test_process.py -q`; review resource behavior and staged diff, then commit.

### M1.4 Input/probe normalization and stream/timeline selection

Dependencies: M1.3; complexity M. Create probe.py, tests/unit/test_probe.py, tests/integration/test_probe.py, tests/conftest.py and tests/fixtures/generate.py by promoting only approved fixture recipes. Produces normalize_probe, choose_streams, choose_timeline, probe_media. Consumes Toolchain/Runner; outputs ProbeResult/MediaMetadata. Completion: supported real-video inventory, nullable fields, deterministic indexes, coded rotation metadata, common-origin provenance, regular readable input, forced safe demuxer. Tests U10–U12/I01/I07/I08/I10/I13/I17/I18/I24. Input validation is exercised through scanner in M1.5; do not depend on chmod to establish readability.

- [ ] Define payload tests: missing optional sample rate/duration => null; avg rate 0/0 => unknown; malformed/duplicate index => failed probe; attached picture excluded; multiple default flags resolve by lowest real-stream index.
- [ ] Assert common origin follows format start, else minimum starts only if every selected stream start known, else raw source_pts with origin=null; preserve A/V offset and negative timestamps.
- [ ] Implement explicit bounded FFprobe normalization/selection, using accepted M0 protocol/demuxer/reference restrictions; do not copy raw tags or leak absolute input path into report.
- [ ] Run `python -m pytest tests/unit/test_probe.py tests/integration/test_probe.py -q`; inspect actual supported MP4/MOV reports and original input hashes; commit.

### M1.5 Functional inspection scan and early CI

Dependencies: M1.1–4; complexity M. Create scanner.py, tests/unit/test_scanner.py, tests/integration/test_scan_metadata.py, .github/workflows/ci.yml; update cli.py/README.md. Produces scan as a metadata inspection path, not completed QA. Consumes models/probe/process; emits ScanReport with black/silence feature_not_implemented failures when applicable, overall incomplete and exit2. Completion: missing/invalid/unreadable/audio-only inputs controlled, metadata visibly useful, no false pass, initial CI and wheel install succeed. Tests I01/I07/I08/I09/I10/I16 and U20/U23; M1's fixture metadata may be valid while QA status remains incomplete.

- [ ] Define scanner/CLI tests for file with spaces, invalid data, absent file, dependency failure and no real video; assert useful diagnostic, stable checks, no uncaught traceback and expected exit2.
- [ ] Wire scan orchestration, monotonic duration and basic terminal inspection; black/silence remain explicitly unavailable rather than placeholder successes.
- [ ] Add Linux 3.11/3.14 and macOS 3.14 CI smoke/unit/probe jobs with exact tool-version logging; a required integration dependency missing fails CI instead of skip.
- [ ] Run `python -m pytest -m 'not detector' -q`, lint/format checks and isolated installed-wheel inspection. Record remote CI as unverified until its actual run succeeds; commit the working M1 increment.

## M2 — core quality checks

### M2.1 Resolution and required/optional audio policies

Dependencies: M1.4/5; complexity S. Create checks/__init__.py, checks/metadata.py, tests/unit/test_metadata_checks.py. Produces check_resolution/check_audio_presence. Completion: compare supplied coded dimensions only; rotation explained; inventory-based presence; exact critical/info codes; absent audio does not create silence. Tests U14/U16 and I02/I04/I11, with actual both values in findings.

- [ ] Assert expected width1080/height1920 versus coded1920x1080 yields RESOLUTION_MISMATCH even if rotation90; explanation names coded/display distinction. No expectation => skipped/not_configured. Missing requested dimensions => failed/unavailable.
- [ ] Assert absent audio+require_audio => AUDIO_REQUIRED_MISSING/critical; absent optional => AUDIO_ABSENT/info; any inventoried audio satisfies presence regardless of selected-track silence.
- [ ] Implement the two pure policy functions without process calls; run `python -m pytest tests/unit/test_metadata_checks.py -q`, then relevant integrations as wired in M2.5. Review/commit.

### M2.2 Rational reported-frame-rate policy

Dependencies: M2.1; complexity S. Update checks/metadata.py; create tests/unit/test_fps.py. Produces check_frame_rate using avg_frame_rate only. Completion: 0.001 FPS inclusive tolerance, exact rational handling and labeled metadata limitation. Tests U15/I03/I14/I19.

- [ ] Assert 29.97 vs30000/1001 passes; 23.976 vs24000/1001 passes; 30 vs30000/1001 produces FPS_MISMATCH/critical; boundary difference1/1000 passes and >1/1000 fails.
- [ ] Assert unknown average with requested FPS is failed/unavailable even if r_frame_rate=30/1; no expectation is skipped; conflicting rate fields never claim VFR/CFR diagnosis.
- [ ] Implement Fraction comparison; run `python -m pytest tests/unit/test_fps.py -q` and rational-FPS integration, review/commit.

### M2.3 Black parser and video-only detection adapter

Dependencies: M1.3/4, M0.3, A1; complexity M. Create checks/black.py, tests/unit/test_black.py, tests/integration/test_black.py. Produces BlackParser feed/finish and detect_black; consumes same selected stream/timeline across probe/scan. Completion: explicitly configured native filter, narrow attribution, finite events, warnings with provenance and accepted EOF limitations; no false full completion after failure. Tests U17–U19/I05/I12/I15/I18/I20.

- [ ] Pin accepted M0 log grammar with normal/leading/trailing intervals; exact test event start1/end3/duration2 produces BLACK_INTERVAL with stream index and shared-origin times. Nonfilter lookalikes ignored; malformed matching records fail.
- [ ] Pin negative/scientific timestamps, unknown end, duration inconsistency, line truncation, failure teardown and signed zero normalization; expected malformed/provisional results cannot become complete. Add an early attributable decode-error line followed by diagnostic-tail overflow, valid closing events and returncode0; assert sticky decode failure, provisional findings and incomplete/exit2.
- [ ] Implement parser/command builder and runner adaptation using d0.5/pic0.98/pix0.10. Include check-wide EOF caveat; do not correct with nominal FPS or file duration.
- [ ] Run `python -m pytest tests/unit/test_black.py tests/integration/test_black.py -q`; compare floor/newer native events to decoded-frame oracle. Commit only after assertions and limitations match approved A1.

### M2.4 Silence parser and audio-only detection adapter

Dependencies: M1.3/4, M0.3; complexity M. Create checks/silence.py, tests/unit/test_silence.py, tests/integration/test_silence.py. Produces SilenceParser feed/finish and detect_silence. Completion: paired events, collective channels, native sample-threshold semantics, skipped/no_audio versus failed decoding, safe EOF closure. Tests U17–U19/I06/I11/I12/I15/I18/I20/I22.

- [ ] Assert log start1/end4/duration3 creates one warning; delayed start notification retains earlier timestamp; no audio yields skipped/no_audio required=false, not completed/no findings.
- [ ] Assert duplicate start, unmatched end, reversed end, nonfinite value, corrupt event and incomplete process lead to failed/provisional evidence; include early decode error plus tail overflow/closing events/zero exit to pin sticky failure. At least one active channel prevents a collective silence finding.
- [ ] Implement separate explicitly mapped audio pass at -60dB/2s, with no downmix/resampling or per-channel mode. Gate teardown closure on process completion.
- [ ] Run `python -m pytest tests/unit/test_silence.py tests/integration/test_silence.py -q`; validate PCM oracle and AAC decoded tolerance. Review/commit.

### M2.5 Completed scan orchestration and partial-failure regression

Dependencies: M2.1–4/M1.5; complexity M. Update scanner.py and tests/unit/test_scanner.py; create tests/integration/test_scan.py. Consumes five policy/detector functions and calculate_status; produces complete ScanReport workflow. Completion: all required applicable checks run, absent expectation/audio skips are legitimate, independent failure retained, provisional evidence visible, input identity change detected. Tests T01–T16 with output delivery added M3; U20–U23/I16/I20/I23. No performance-pass optimization until correctness.

- [ ] Assert a valid expected baseline is pass, mismatch is fail, black/silence is warn; missing required audio is fail with skipped silence; optional absent audio is pass/info with skipped silence.
- [ ] Inject black failure after successful policies and silence; assert incomplete/exit2 and preserve other check results/critical evidence. Inject changed input stat/identity and assert incomplete.
- [ ] Implement sequential separate passes and dependency-aware check states; continue independent applicable checks when safe. Avoid substituting another stream on failure.
- [ ] Run `python -m pytest tests/unit tests/integration -q` on required FFmpeg environment; inspect selected indexes and timing caveats. Review/commit and record M2 verification.

## M3 — useful and safe reports

### M3.1 Authoritative JSON and documented schema

Dependencies: M2.5; complexity S–M. Create reporting.py, docs/report-schema.md, tests/unit/test_reporting.py. Produces report_to_dict/render_json. Completion: complete top-level fields from architecture, finite numbers, nullable unknowns, rational provenance, stable ordering, safe basename, schema0.1.0/tool0.1.0, explicit check states and timing caveats. Tests U24/I26.

- [ ] Assert every required top-level field and finding/check field exists on pass/warn/fail/incomplete reports; null unknowns are not 0; Fraction serializes as normalized text/object; NaN/Infinity rejected.
- [ ] Assert two equivalent scans have equal semantic projections excluding elapsed runtime, and raw absolute input paths/commands/tags are absent.
- [ ] Implement the explicit projection once; document units/versions/status precedence and forward-consumer guidance. Do not create independent JSON analysis logic.
- [ ] Run `python -m pytest tests/unit/test_reporting.py -q`; decode emitted JSON back and compare to report semantics. Review/commit.

### M3.2 Static HTML and no-clobber publication

Dependencies: M3.1; complexity M. Update reporting.py; create tests/unit/test_html.py, tests/unit/test_outputs.py, tests/integration/test_outputs.py. Produces render_html/publish_report. Completion: inline accessible styling, grouped findings/intervals/check states/configuration, no scripts/remote assets, escaped hostile text, safe destinations and no replacement races. Tests U25–U27/I25/I26.

- [ ] Assert script-like filename/metadata becomes escaped text; HTML includes incomplete/skipped reasons, selected/uninspected streams and timeline limitations; zero remote URLs/assets/executable JS in rendered output.
- [ ] Assert existing target, hardlink/symlink to input, duplicate outputs, missing/unwritable parent and simulated collision cannot overwrite a byte; simulate second export failure and retain truthful first-output diagnostic.
- [ ] Implement tested no-clobber publication/cleanup, not check-then-write; do not claim a two-file transaction. Document atomicity or fallback honestly.
- [ ] Run `python -m pytest tests/unit/test_html.py tests/unit/test_outputs.py tests/integration/test_outputs.py -q`; open representative static HTML locally and review readability/narrow layout. Review/commit.

### M3.3 Final CLI, terminal summary, configuration and exit behavior

Dependencies: M3.1/2; complexity M. Update cli.py/reporting.py/README.md; create tests/integration/test_cli.py, tests/unit/test_terminal.py. Produces render_terminal and final main. Completion: all specified scan flags plus approved timeout flag, early configuration/output preflight, terminal sanitized, exports from same ScanReport, exact 0/1/2 exits, concise controlled errors, failure-report delivery where possible. Tests U01–U05/U23/U28/I01–I16/I25/I26.

- [ ] Pin command cases for complete pass0, warning0, critical1, missing/invalid/dependency/incomplete2, output error2, negative/NaN config2 and KeyboardInterrupt cleanup2. Help must explain coded dimensions, selected streams and warning exit policy.
- [ ] Assert ANSI/control filename content cannot inject terminal commands/colors; Unicode/spaces remain readable. Export failure does not change a completed media report to a critical quality finding.
- [ ] Wire destinations/CLI options and summary; report primary status, failed/skipped checks, counts, intervals, and the human-review caveat without hiding criticals in incomplete runs.
- [ ] Run `python -m pytest tests/unit/test_cli.py tests/unit/test_terminal.py tests/integration/test_cli.py -q`; run owner example against generated portrait fixture with both reports. Review/commit and record first complete workflow evidence.

## M4 — hardening and release

### M4.1 Full acceptance/regression and compatibility evidence

Dependencies: M3.3; complexity M–L. Extend integrations/fixture generator and docs/validation/compatibility.md. Completion: FR-01–FR-12/T01–T16 and additional edge obligations have evidence; optional platform limitations explicit. Verify proposed floor/newer build, Python versions/platforms being claimed, malformed/truncated inputs, offline behavior, source hash preservation, boundaries, output races and install tests. Required tests are those in acceptance-tests.md; unsupported scenarios must be safely rejected with documented limits rather than silently removed from the matrix.

- [ ] Execute all unit/process/native/CLI/installed-wheel tests and inspect skipped reasons; no required release integration may skip.
- [ ] Run offset/VFR/multitrack/rotation/unreadable/truncated/reference fixtures and real creator media with consent, recording selected coverage and no unsupported integrity claims.
- [ ] Record exact builds/platforms and failures; fix in narrowly reviewed regression changes or reduce proposed support with owner approval.
- [ ] Commit compatibility evidence and regression tests only when their claims match recorded commands.

### M4.2 Packaging and CI release gates

Dependencies: M4.1; complexity M. Update pyproject.toml/ci.yml, create tests/integration/test_installed_package.py and docs/release/checklist.md. Completion: Linux3.11/3.14/macOS3.14 core CI, pinned floor build coverage, 3.12/3.13 unit+wheel checks if claimed; wheel/sdist installs outside checkout; actual CI succeeds. Tests: I27 and release gates G01–G05. Do not assume apt/homebrew provides the pinned floor or latest release; record exact packages.

- [ ] Build wheel/sdist with `python -m build`; install each in a clean >=3.11 virtual environment, from outside source tree, and run help/version/scan with both reports.
- [ ] Run `python -m pytest -q`, `ruff check .`, `ruff format --check .` and `python -m pip check`; record successful exit codes and CI URLs after authorized push.
- [ ] Verify runtime dependency list/resources, offline scan under network denial and no imports from checkout; report macOS support only after actual macOS verification.
- [ ] Review artifacts/staged changes and commit; no publication/tag yet.

### M4.3 Documentation, usability and measured performance

Dependencies: M3.3/M4.1; complexity M. Complete README.md, docs/limitations.md, docs/validation/benchmark.md and concise contribution instructions. Completion: installation/FFmpeg setup for tested OSes, exact quickstart, flags/severities/exit codes, stream/EOF/timing/codec limits, developer/test commands, privacy/local operation and report schema references. Tests: G06/G07, no invented speed claim.

- [ ] Have a clean-environment reader follow README to scan a generated video and open JSON/HTML; record steps, OS/tools, blockers and corrections.
- [ ] Benchmark synthetic 60-second vertical and consented representative real clips, warm/cold notes, selected codecs/resolution, elapsed time and peak process memory where measurable; separately note probe/black/silence costs.
- [ ] Confirm documentation describes passing selected checks rather than guaranteeing defect-free media; unknown timing and EOF limitations visible.
- [ ] Review/commit documentation and raw measurement summaries without private paths/media.

### M4.4 License, final review, and authorized release

Dependencies: M4.2/3 and A4; complexity S–M. Create LICENSE only after owner choice; finalize release checklist/changelog. Completion: G01–G08 evidence, project name/package-index checks, original code/generated-fixture provenance, release approval, reviewed v0.1.0 tag and release only in authorized repo. MIT applies to FrameGuard-owned code, not separately installed FFmpeg builds. No PyPI publication assumed.

- [ ] Review all FR/completion criteria against command output/CI/manual evidence, unresolved risks and known limitations; request independent final code review.
- [ ] Confirm license/copyright attribution, no bundled FFmpeg or copied upstream code, no private fixtures/secrets in artifacts, and GitHub/package ownership.
- [ ] Present release candidate evidence and obtain explicit publication/tag authorization; do not invent CI/OS results if blocked.
- [ ] Tag/release only after approval and successful gates; summarize exact support, artifact locations, verified commands, unresolved limitations and postrelease issues.

## Critical path and stop conditions

First complete scan path is M0.1→M0.2→M0.3→M0.4→M1.1→M1.2→M1.3→M1.4→M1.5→M2.1/2/3/4→M2.5→M3.1→M3.3. M3.2 adds required HTML and safe delivery, so full MVP workflow waits for M3.2 and M3.3. Model-dependent metadata policies, black parser and silence parser may be developed separately after M1/M0 contracts settle; they may not silently change shared model files concurrently. Hardening/release remains a gate, not optional cleanup.

Stop when owner approvals are missing, intended runtime is unavailable, safe offline demuxing cannot be shown, EOF/timestamp behavior violates the accepted contract, source media could be overwritten, output bounds cannot preserve honest completion, or required tests fail. Do not begin later milestones to conceal a blocker. At each milestone summarize changed files, commands/results, limitations, unresolved decisions and proposed next authorization. Commit only after evidence and review; no claim of completed release from feature code alone.

