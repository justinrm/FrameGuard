# First FrameGuard coding-session handoff

**Status:** DRAFT prompt, not execution authorization. The owner must approve the planning contracts and scope before using it. Read the approval record rather than assuming these proposed choices were accepted.

## Approval record to supply with the prompt

Owner states whether A1 native black EOF limitations and A2 selected-stream coverage are accepted or supplies amended contracts. Owner states A3 tested runtime/format/timeout envelope and whether M0 only or M0→conditional M1 is authorized. A4 MIT/publication may remain undecided during private work but blocks LICENSE/public distribution. If no such approval record exists, stop and request it. Do not infer approval from this file's presence.

## Copyable prompt for the subsequent session

You are implementing the first bounded development increment of FrameGuard v0.1, an offline, Python-first single-video CLI. The product reports measurable technical evidence, not creative quality judgments. You may execute **Milestone 0 only**, and begin **Milestone 1 only if the accompanying owner approval explicitly authorizes conditional M1 and every M0 gate passes**. Do not implement M2 quality-check product code, M3 exports, M4 release, or any non-goal in this session. Throwaway M0 native detector experiments are authorized within M0; retaining production detector code is not.

The working folder is the owner's selected `frameguard` folder. Read these approved/revised files before acting: docs/frameguard-planning/README.md, planning-review.md, architecture.md, implementation-plan.md, acceptance-tests.md, risk-register.md, and this handoff. Read applicable CLAUDE.md/AGENTS.md and Git status/history if they now exist. These files were unapproved drafts when created; use the owner's approval record and accepted revisions as the source of authority. Reconcile contradictions before writing code. The original supplied MVP remains the baseline; do not silently revise FR/T acceptance criteria.

Prior session observations: the selected folder was empty and not a project-local Git repository before the planning documents were added. Linux workspace Python was3.10.12, FFmpeg/FFprobe4.4.2, uv0.12.13. These are not the owner's macOS versions, not a valid assumed development runtime, and not proof of support. No native media experiment, product test, packaging/install check, CI, or performance measurement was run. Obtain actual intended >=3.11 Python and approved FFmpeg builds with permission; never claim validation from these old observations.

### Authorized M0 objectives

Execute M0.1–M0.4 in implementation-plan.md. Create tools/validate_media.py only as a bounded experiment helper, plus docs/validation/m0-environment.md, m0-observations.md, and m0-decision.md. Generate tiny local lavfi fixtures in an ignored temporary directory, never download footage. Record command argv, exit codes, exact tool/build/OS/Python versions, probe output relevant to the contract, source references, raw native event lines, and expected/observed decoded timing. Do not introduce project runtime dependencies or application scaffolding during M0.

Verify self-contained H.264/yuv420p MP4/MOV±AAC baseline and video-only clips; exact selected-stream indexes/default/cover-art behavior; rational FPS; known interior black/silence; leading/trailing/all-black/all-silent; just-below/equal/above minimum black tail; differing/negative/nonzero A/V starts plus a verified MOV/MP4 edit-list fixture with decoded frame/sample PTS oracle on floor/newer builds; native EOF versus cancellation/failing decode (including an early decode error followed by diagnostic-tail overflow and zero exit); and safe protocol/demuxer/reference restrictions. Require actual floor and newer release evidence before compatibility claims; if only one is available, record the missing evidence and stop conditional M1 unless owner narrows its gate explicitly.

Important upstream-source fact to validate: blackdetect defaults to2s, not proposed0.5s; explicit pic_th0.98/pix_th0.10 are proposed. Its current source closes trailing black at last frame PTS, not PTS+duration, so near-minimum EOF intervals can be missed. Silencedetect defaults2s/-60dB and collectively checks channels; current source closes trailing detected silence at last audio-frame end. Both teardown closures can occur after failure. Info logs are the proposed event source; frame metadata alone lacks teardown closure. Do not fabricate black endpoints or use successful log parsing as proof of completed decoding.

Candidate native calls must be argv arrays, no shell, no stdin interaction, bounded time/output, selected absolute stream mapping, no -shortest/truncation/seeking/CFR override/downmix. Validate copyts/common origin, noautorotate and no-resampling/null output behavior. Validate forced MOV demuxer, file-only protocols and disabled data references on approved binaries. Preserve source PTS provenance, use one common origin, never reset A/V independently, never substitute duration for absolute end. If a restriction or timestamp convention is unproven, record a blocker and stop, not a passing observation.

### Conditional M1 objectives and files

Only after authorized successful M0, execute M1.1–M1.5. Create an installable src-layout package with minimal main/help/version and functional metadata inspection: pyproject.toml, README.md, .gitignore, src/frameguard/__init__.py, cli.py, models.py, process.py, probe.py, scanner.py, tests/unit and tests/integration files named in the roadmap, tests/conftest.py, tests/fixtures/generate.py, and initial .github/workflows/ci.yml. Do not create LICENSE until A4 is accepted. Do not create production black/silence adapters or full JSON/HTML reporting prematurely.

Use architecture.md interfaces exactly: shared models/config/status functions, Runner/ProcessSpec/Result, discover_tools/run_process, normalize_probe/choose_streams/choose_timeline/probe_media, scan, main. Dataclasses are not runtime validation; implement explicit finite/positive checks and nullable normalizers. argparse is recommended, no third-party runtime packages. Build/dev tools are Hatchling, pytest, Ruff; uv optional. Keep all subprocess execution in process.py. Tools and outputs expose safe diagnostics, not private absolute paths or raw unbounded logs.

M1 must be honestly functional as inspection, not claim finished QA: applicable black/silence are failed/feature_not_implemented and overall incomplete/exit2 until M2. Help/version are0. Missing/invalid/unreadable/no-real-video/dependency input errors are controlled diagnostics, never uncontrolled tracebacks. Optional probe fields unknown=>null; unknown required fields must not become fabricated0. Select real video default-disposition then lowest index; select audio similarly; inventory and disclose uninspected streams. Source file is never written, chmodded, deleted or overwritten.

Implement small test-first increments using the roadmap's exact assertions. Unit mocks do not verify FFmpeg behavior; run native integrations with generated fixtures. Inspect staged diff before each coherent local commit if Git setup/commits are authorized. Do not initialize Git, configure remotes, push, create GitHub repository, register a package, tag or publish unless explicitly permitted. Never add private footage or large generated binaries to Git.

### Verification commands and interpretation

Run environment commands before selecting Python: `python3 --version`, `ffmpeg -version`, `ffprobe -version`, `ffmpeg -hide_banner -filters`, `ffmpeg -hide_banner -h filter=blackdetect`, `ffmpeg -hide_banner -h filter=silencedetect`, and `ffmpeg -hide_banner -h demuxer=mov`. Enforce reasonable timeouts and retain relevant output/exit codes. Use selected Python >=3.11, not an unqualified python command if it resolves to3.10.

For authorized M1 after packaging: create a project venv with approved interpreter, then `python -m pip install -e '.[dev]'` (or equivalent `uv sync --extra dev`), `python -m pytest -m 'not detector' -q`, `ruff check .`, and `ruff format --check .`. Define/register the detector marker consistently; M1 contains no production-detector test yet. All expected M1 tests pass. Missing required native tools fails validation, not a quiet skip.

Build with `python -m pip install build` only with dependency-install permission, then `python -m build`. Install the built wheel into another clean approved-interpreter venv, run `python -m pip check`, and invoke `frameguard --help`, `frameguard --version`, and `frameguard scan <generated-baseline.mp4>` from outside the source directory. Help/version0, metadata inspection useful but incomplete2. Native fixture generation/probe and safety observations must have recorded successful/expected-failure return codes. Actual GitHub CI is unverified unless an authorized remote run can be linked; local checks are not remote CI evidence.

Commands are prospective; do not report them as run without actual results. If the execution environment requires sandbox-specific install flags, comply with that environment and keep host/project environments separate. Do not install dependencies or change the owner's host setup just because a suggested command appears here.

### Stop conditions

Stop for missing approval, unavailable >=3.11/approved native runtime, failed M0 timing/completion/offline gate, unsafe source/destination identity, unbounded authoritative output or orphan-process cleanup, contradictory contracts, failing required tests, unsupported parent guidance/Git permissions, or need for scope beyond M0/M1. Do not begin later milestones or weaken a test to bypass a blocker. If A1 native EOF semantics are not accepted, propose and obtain approval for an endpoint strategy rather than padding with avgFPS.

### Required completion summary

Report which authorized tasks completed, changed files and local commits, exact command outputs/exit codes, actual tool versions/platforms, fixture oracles and timing/EOF observations, source hash/nonmodification evidence, tests actually passed/failed/skipped and why, CI status, unverified claims, unresolved decisions/risks and next approval needed. Link M0 validation artifacts. State clearly whether M0 gates passed and whether M1 began under explicit authorization. Do not equate code presence with validation or label FrameGuard MVP complete at M1.

## Owner-facing next action

Approve/amend A1–A4 and authorize M0. Recommended execution is a single bounded implementer for M0/M1 with independent review of process/timestamp contracts after validation, rather than several concurrent implementers changing unproven shared interfaces. This is a recommendation, not a selected execution method.
