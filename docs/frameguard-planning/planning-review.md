# FrameGuard — specification review and development planning

**Status:** Unapproved planning draft, 2026-10-08. **Target:** v0.1.0. **Baseline:** owner's supplied twenty-section MVP handoff. All recommendations preserve single-file, Python-first, offline, CLI-first operation. Implementation has not begun.

## 1. Executive assessment

FrameGuard is technically feasible and appropriately small if presented as an evidence-and-policy wrapper around FFmpeg, not an exhaustive media-integrity validator. Its value is composing native measurements into reproducible findings, clear completion states, explicit user expectations, and consistent reports. This is a plausible user benefit, not validated market demand; validate usability with a creator/editor before public release rather than expanding scope.

The specification's strongest features are evidence rather than creative judgment, explicit separation of processing failures from quality findings, nullable metadata, independently testable milestones, and honest platform/verification claims. The largest unresolved issues are EOF timing semantics, multi-stream selection, the meaning of unknown required metadata, safe output delivery, and the distinction between “probeable” and “fully analyzed.” These need contracts, not more features.

Recommend zero third-party Python runtime dependencies: argparse, dataclasses with explicit validation, subprocess, fractions, json, pathlib, and html. pytest and Ruff are development tools. FFmpeg/FFprobe remain external runtime dependencies. A small build backend is necessary for packaging but not for scanning.

## 2. Specification critique

### Required changes before the affected implementation

| ID | Gap or ambiguity | Proposed revision and reason |
|---|---|---|
| RC-01 | “Required checks” versus legitimate skips | A check without a supplied expectation is skipped/not configured. Silence without audio is skipped/not applicable. Applicable black/silence checks, probing, audio inventory, and supplied expectations must complete. Failure of any applicable required check makes overall status incomplete, even if critical findings already exist. |
| RC-02 | No usable video stream; attached artwork | A supported scan requires a real video stream, excluding attached pictures/cover art. Audio-only or artwork-only inputs are unsupported executions, exit 2, not a successful video scan or creative-quality finding. |
| RC-03 | Required facts absent | Missing optional metadata is null. Missing dimensions or avg_frame_rate needed by an explicit expectation fails that check as unavailable; it is neither a pass nor an invented mismatch. Do not silently substitute r_frame_rate for average frame rate. |
| RC-04 | Stream selection unspecified | Inventory all streams; select a default-disposition real video, otherwise lowest absolute index; select default-disposition audio, otherwise lowest index. Record selection/rationale and uninspected streams. Audio presence examines inventory; silence examines only selected audio, all its channels collectively. |
| RC-05 | Rotation and dimensions | Compare expected dimensions with coded width/height. Record rotation, sample/display aspect ratios when available, and explanatory display-orientation text. Do not interpret an arbitrary display matrix as a reliably swapped raster. Document coded semantics in help. |
| RC-06 | FPS equivalence/tolerance | Use positive finite Fraction values; compare selected avg_frame_rate with absolute tolerance 0.001 FPS inclusive. Accept integer, decimal, rational input. Preserve raw avg_frame_rate and r_frame_rate, label them reported metadata, and avoid CFR/VFR conclusions. |
| RC-07 | Boundary acceptance sounds frame-exact | Approve native-reported black EOF boundaries or require a proven alternative before coding detectors. Current source uses final frame PTS, omits its duration, and can suppress threshold-edge trailing intervals. Report this limitation explicitly; never infer the endpoint from container duration or average FPS. |
| RC-08 | Timestamp reference absent | Preserve source PTS/filter events, use one shared documented origin, never reset audio/video independently, and expose raw-timeline mode when origin is unknown. Negative/nonzero starts, edit lists, and offsets need M0 experiments. |
| RC-09 | Output and process failures blurred | Overall status describes analysis only. Output-delivery failure yields exit 2 and a separate diagnostic without converting a good video into a critical finding. Invalid configuration exits 2 before decoding. Complete warning-only scans exit 0. |
| RC-10 | Unsafe destinations and partial reports | Refuse existing reports, input aliases, identical JSON/HTML targets, nonregular destinations, and missing/unwritable parents; do not create parents implicitly. No overwrite flag in MVP. Use no-clobber publication and clean temporary files. Two outputs are not a transaction: disclose any successful output if the other fails. |
| RC-11 | Local-first does not imply network-safe subprocess | Restrict scanning to tested self-contained MP4/MOV; force the relevant demuxer after M0 validation, restrict protocols, and disable external-reference loading. Reject manifests/URLs, disable inherited FFREPORT, and test attempted network/reference access. This is defense in depth, not a media-parser sandbox. |
| RC-12 | No limits or completion contract | Bound time, captured output, diagnostic tails, and findings. Drain both pipes, terminate/kill/reap, and fail rather than silently truncate. Filter teardown logs are not proof of successful EOF. A zero return code, no timeout/cancellation/output-cap/decode failure, and valid parser/completion evidence must agree. |

### Recommended improvements

Use an initial support envelope of self-contained H.264/yuv420p MP4 and MOV with AAC audio when present, plus video-only variants; broaden only when tests justify it. This is a tested promise, not an extension whitelist or a claim that other files necessarily fail. Treat supported container plus unavailable decoder as controlled incomplete analysis. Prefer separate detector passes until correctness is established; a combined pass is optional later only if measured benefits justify coupling.

Use basename and size by default in shareable reports; avoid raw probe JSON, full commands, binary paths, and unsanitized diagnostics. Record schema version, selected indexes, effective parameters, report time basis, and exact binary version lines. Float times can be finite rounded values with provenance; rational FPS should serialize as strings/objects rather than binary floats. HTML must escape every user/metadata string and have no remote assets, scripts, or clickable untrusted URLs.

Keep a failure report available where configuration and destinations are valid, even for missing/invalid input; metadata may be null and downstream checks skipped due to failed prerequisites. For CLI parse errors, a diagnostic without a scan report is sufficient. Add explicit report-schema documentation and wheel-install smoke tests. Do not impose unsupported speed targets.

### Scope not needed now

A plugin registry, abstract check hierarchy, Pydantic, scene-detection stack, FFmpeg Python DSL, templating framework, thumbnails, progress percentages, user-selectable stream profiles, caches, strict-warning exit policy, extra output modes, or batch processing do not solve a demonstrated MVP need. A read-only report is enough. Full corruption certification, HDR perceptual interpretation, exact VFR cadence, channel-specific silence, and richer display-matrix interpretation remain future work.

## 3. Relevant open-source research

| Project/source | What it already supplies | FrameGuard decision |
|---|---|---|
| [FFmpeg filters](https://ffmpeg.org/ffmpeg-filters.html) and [FFprobe](https://ffmpeg.org/ffprobe.html) | Native black/silence detection, stream/container inventory, JSON writers | Reuse directly through controlled subprocesses; do not decode frames into Python or rewrite codecs. |
| [PySceneDetect](https://github.com/Breakthrough/PySceneDetect), [detector documentation](https://www.scenedetect.com/docs/latest/api/detectors.html) | Scene boundaries and fade/threshold detectors; frame-backend ecosystem | Adjacent problem, not equivalent black-interval QA. No dependency; average-RGB fade semantics differ from FFmpeg black-picture semantics. |
| [QCTools](https://github.com/bavc/qctools) / qcli | Preservation-focused audiovisual measurements, graphs, review, FFmpeg-derived statistics | Strong precedent for evidence plus human review; not a lightweight Python dependency or reason to add GUI/loudness scope. |
| [ffmpeg-quality-metrics](https://github.com/slhck/ffmpeg-quality-metrics) | Reference-versus-distorted fidelity metrics such as PSNR/SSIM/VMAF | Different problem requiring a reference; do not add objective “quality scores” to a single-file scan. |
| [ffmpeg-normalize](https://github.com/slhck/ffmpeg-normalize) | Stream-aware audio normalization and measurements | Learn stream/process conventions; transformation and loudness compliance are non-goals. |
| [ffmpeg-progress-yield](https://github.com/slhck/ffmpeg-progress-yield) | Process/progress/cancellation convenience | Study cleanup patterns, but not a dependency; progress is unnecessary and combined stdout/stderr behavior is unsuitable for authoritative event parsing. |

These are focused documentation/repository reviews, not exhaustive code audits or proof that FrameGuard is unique. FrameGuard's intended differentiation is a small single-file policy/report composition with clear status semantics.

[Python argparse](https://docs.python.org/3.14/library/argparse.html) meets this command surface without runtime dependencies. [Typer release notes](https://typer.tiangolo.com/release-notes/) and [its Python 3.14 CI change](https://github.com/fastapi/typer/pull/1372/files) establish upstream 3.14 support intent/test configuration, not FrameGuard compatibility. Current Typer vendors Click; outdated claims about mandatory external Click dependency should not drive this choice. Typer is reasonable if CLI breadth later warrants it.

[Dataclasses](https://docs.python.org/3/library/dataclasses.html) do not validate annotations; explicit boundary normalizers are required. Pydantic supplies useful validation/schema facilities but adds unnecessary runtime weight for this fixed model and still needs deliberate coercion rules. [pytest good practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html), [Ruff configuration](https://docs.astral.sh/ruff/configuration/), and [PyPA packaging guidance](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/) support src layout, pyproject configuration, importlib test mode, and installed-package verification.

## 4. Technical feasibility and evidence

| Capability | Verified evidence in this session | Still needs real execution |
|---|---|---|
| Metadata | FFprobe docs support show_format/show_streams/JSON; optional fields can be omitted | Pinned binary output, normalization fixtures, missing/invalid fields, rotated MOV, multi-stream selection. |
| Black thresholds | Current upstream source defaults d=2, pic_th=0.98, pix_th=0.10; luma threshold depends on range/bit depth | Explicit d=0.5 behavior, near-threshold and all-black EOF clips across supported releases. |
| Silence | Source default duration 2 s, amplitude 0.001 = -60 dB, collective channels by default | PCM oracle versus AAC artifacts, leading/trailing silence and channel activity. |
| Event source | Info logs include interval events; frame metadata also exists | Log grammar across supported builds, malformed records, process-failure teardown. |
| EOF | Current black source closes at last picture PTS; silence source closes at last audio frame PTS plus sample duration. Both use teardown paths | Exact installed-release behavior, successful EOF versus cancellation/decode failure; no endpoint-certainty claims yet. |
| Timestamps | Filters use incoming PTS/time base; metadata is not inherently zero-origin | copyts/null output invocation, common origin, negative starts, A/V offsets, edit lists and discontinuities. |
| Subprocess/packaging | Standard Python APIs and PyPA mechanisms are documented | Cleanup/output bounds, wheel install, actual Python 3.11–3.14 and macOS/Linux execution. |

[blackdetect source](https://raw.githubusercontent.com/FFmpeg/FFmpeg/master/libavfilter/vf_blackdetect.c) logs only intervals meeting d, whereas its frame start/end metadata is not duration-filtered. Its EOF source contains a FIXME for last-frame duration. [silencedetect source](https://raw.githubusercontent.com/FFmpeg/FFmpeg/master/libavfilter/af_silencedetect.c) measures sample amplitude, not RMS/EBU loudness, and metadata closure is not emitted during teardown. A metadata-only parser is therefore not automatically safer; it can miss EOF closure. Recommend a narrowly attributed info-log parser plus explicit completion checks, validated in M0.

No sample media probing, filter execution, benchmark, product test, or macOS check was performed. Read-only environment observations are Linux Python 3.10.12, FFmpeg/FFprobe 4.4.2, uv 0.12.13; these do not meet the proposed Python runtime or validate the proposed FFmpeg floor. Draft target is Python 3.11–3.14 and FFmpeg/FFprobe 6.1 or newer with actual 6.1 and a newer stable build tested. Version 6.1 is a proposed test-scope floor, not a minimum demanded by these longstanding filters. Exact release support is established by CI/manual evidence, not “or newer” marketing.

## 5. Recommended architecture

Choose a thin standard-library orchestration package. CLI validates configuration and destinations; a process module owns every subprocess; a probe adapter normalizes inventory; policy functions evaluate metadata; detector adapters produce timestamped events; the scanner aggregates completed/skipped/failed checks; reporting renders the same ScanReport. No inheritance framework or plugin loader is needed. See [architecture.md](architecture.md) for the diagram, exact interfaces, model fields, status precedence, stream selection, timestamp conventions, and command-validation gates.

Compared with a Typer/Pydantic version, this approach trades some handwritten validation for a smaller dependency surface. Compared with a combined FFmpeg filtergraph, separate passes trade additional demux/I/O for simpler parsing, attribution, and independent check failures. A Python frame-analysis stack is substantially heavier and unnecessary. Recommend the thin, separate-pass approach for v0.1.

## 6. Revised MVP scope

Keep FR-01–FR-12 and all three output forms. Retain the supplied CLI flags, detection defaults of black 0.5 seconds and silence 2 seconds at -60 dB, severity mappings, and exit codes 0/1/2. Fix black picture/pixel thresholds explicitly at 0.98/0.10 for reproducibility; do not add public tuning flags without a demonstrated need. Add a simple positive `--analysis-timeout` override if A3 is accepted; this is a resource-control knob, not a policy engine.

The initial report is schema 0.1.0, tool 0.1.0, with selected-stream and timestamp provenance, diagnostics separated from findings, and nullable unavailable values. HTML is static, accessible, escaped, and offline. No new scoring, repair, network service, cloud, AI, GUI, batch processing, or Rust. Frame pacing, complete corruption detection, channel-specific silence and HDR perceptual evaluation remain expressly excluded.

## 7. Implementation roadmap

[implementation-plan.md](implementation-plan.md) defines M0 technical validation, M1 installable metadata CLI, M2 quality checks, M3 full reporting, and M4 hardening/release. Each task names its files/interfaces, dependencies, complexity, tests, output, and completion conditions. The first honest end-to-end scan is M0 → M1 package/process/probe → M2 policies/detectors/aggregation → M3 terminal/JSON/exit behavior. HTML then completes the specified output workflow. CI starts in M1, not at the end.

M0 is a hard gate: baseline/filter capability, safe command behavior, timestamp interpretation, and approved black EOF semantics must be evidenced before detector implementation. M1 may begin only under explicit owner authorization after those gates pass. A functional M1 inspection command must identify analysis as incomplete because black/silence are not yet implemented; it must not masquerade as a released successful QA scan.

## 8. Testing strategy

[acceptance-tests.md](acceptance-tests.md) maps every FR and T01–T16 to unit versus real-FFmpeg tests and reproducible fixtures. Unit tests cover numeric normalization, selection, parsing, statuses, models, CLI/configuration, safe subprocess failure, and rendering. Real integrations verify native filter output and timing against controlled decoded media, not only mock stderr.

Start CI with Linux Python 3.11 and 3.14 plus macOS Python 3.14, each recording exact FFmpeg builds. Add a pinned 6.1 compatibility job and 3.12/3.13 unit/package checks if those Python versions will be claimed. Do not silently skip integration tests in release jobs. Short media fixtures are generated offline from lavfi; exact bytes can vary by encoder/build, so assert decoded properties/intervals rather than cross-version file hashes. Hash each input before/after scans to prove no content modification in tests. Runtime stat checks are race detection, not cryptographic guarantees.

## 9. Risks and mitigations

The dominant risks are native EOF limitations, timestamp offsets, parser drift, incomplete decode disguised as success, resource exhaustion, stream ambiguity, referenced media violating local-first expectations, and report clobbering/injection. [risk-register.md](risk-register.md) assigns impact, likelihood, owners, mitigation, evidence, and gate. The project-management risk is premature support claims: only claim platforms/codecs/builds actually verified. Release publication requires licensing and a recorded acceptance dossier, not feature presence.

## 10. Repository preparation

The selected folder is empty, including hidden project-local entries; it contains no .git, source, README, tests, packaging, CLAUDE.md, or AGENTS.md. Owner-side ancestor guidance and possible parent Git state outside the connected folder were not inspectable. Before coding, recheck project and parent guidance with authorized host access. Nothing existing was overwritten; only this draft documentation directory was created. No GitHub remote or repository was initialized.

Propose src/frameguard with cli.py, models.py, process.py, probe.py, scanner.py, checks/metadata.py, checks/black.py, checks/silence.py, and reporting.py. Consolidate three small renderers into reporting.py initially; split only if size warrants it. Keep explicit check adapters because their parser contracts differ. Add tests/unit, tests/integration, fixture generation helper, docs, pyproject.toml, README, .gitignore, and .github/workflows/ci.yml during authorized milestones. LICENSE is created only after owner selection.

Use Hatchling as one conventional build backend, pytest and Ruff as dev tools, requires-python >=3.11, Ruff target py311, and a console entry point frameguard = frameguard.cli:main. uv is optional convenience; document standard venv/pip commands. Do not bundle FFmpeg. A tested homebrew/apt installation path belongs in release documentation, and actual binary capabilities must still be checked.

Confirm GitHub owner/name, package-index name availability, and publication intentions when release work begins. Plan a minimal CI workflow, issue/PR templates only if helpful, concise contribution guidance, and a security-reporting route. Never push, upload footage, create a public repository, register a package, or tag/publish a release without authorization. Private fixture generation needs no network.

## 11. First coding-session handoff

[coding-session-handoff.md](coding-session-handoff.md) supplies a self-contained bounded prompt, exact planning files, authorized M0/M1 work, commands, evidence expectations, and stop conditions. It requires preserving input media, no publication, no M2 features in M1, verification before claims, and an approval record. The prompt is ready to copy after the owner fills in approval choices; it is not itself permission.

## 12. Decisions requiring approval

| Decision | Recommended choice | Why owner approval matters |
|---|---|---|
| A1 — Black EOF contract | v0.1 reports native detected intervals and explicitly documents last-frame-PTS understatement and near-threshold EOF misses; no fabricated correction. M0 verifies the exact bounds per supported build. | Materially narrows boundary acceptance relative to a reader expecting complete 0.5-second detection. If exact coverage is required, pause and design/test endpoint capture rather than proceeding silently. |
| A2 — Multi-stream coverage | Deterministic default-disposition/lowest-index selection; inventory all, decode one real video and one audio stream. No selection flags in v0.1. | Owners must agree that unselected tracks can contain unchecked defects and “pass” applies to selected tracks, not the entire asset. |
| A3 — Release/resource envelope | Initially verify self-contained H.264/yuv420p MP4/MOV ± AAC on macOS/Linux; design for Python 3.11–3.14 and FFmpeg/FFprobe 6.1+, claim only tested combinations. Add --analysis-timeout, default 600 seconds per detector. | Limits public compatibility claims and adds one operational option. The available workspace does not validate this baseline. |
| A4 — License/publication | MIT for FrameGuard-owned code, separately installed FFmpeg, original/generated fixtures, no copying upstream implementation bodies. | Owner grants the code license and authorizes distribution. FFmpeg licensing/build obligations are separate; do not treat MIT as licensing FFmpeg binaries. Publication/name checks occur before release. |

argparse, dataclasses, coded dimensions, avg-frame-rate tolerance, static HTML, and separate detector passes are engineering recommendations rather than product-scope expansions. Please correct them during design review if they conflict with the intended workflow; after acceptance, record them in the approved architecture. No user-market claim or performance claim is asserted.

## 13. Recommended next action

Approve or amend A1–A4 and authorize a bounded Milestone 0 validation session. That is the single best next step: establish native timing/completion behavior on the intended runtime before writing application code. Milestone 1 is conditional, not automatically approved by reading this draft.

## Sources and research provenance

Research date is 2026-10-08. Official manuals are current references, upstream master/main files are moving source evidence, and repository READMEs establish project scope rather than verified local execution. Primary references used are [FFmpeg documentation](https://ffmpeg.org/documentation.html), [filters](https://ffmpeg.org/ffmpeg-filters.html), [FFprobe](https://ffmpeg.org/ffprobe.html), [FFmpeg CLI](https://ffmpeg.org/ffmpeg.html), [protocols](https://ffmpeg.org/ffmpeg-protocols.html), [blackdetect source](https://raw.githubusercontent.com/FFmpeg/FFmpeg/master/libavfilter/vf_blackdetect.c), [silencedetect source](https://raw.githubusercontent.com/FFmpeg/FFmpeg/master/libavfilter/af_silencedetect.c), [FFprobe schema](https://raw.githubusercontent.com/FFmpeg/FFmpeg/master/doc/ffprobe.xsd), and [shared stream-specifier docs](https://raw.githubusercontent.com/FFmpeg/FFmpeg/master/doc/fftools-common-opts.texi). Additional ecosystem/tooling references are linked in section 3. No benchmark or local filter result is cited because none was executed.

