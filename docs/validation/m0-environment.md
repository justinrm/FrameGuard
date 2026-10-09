# FrameGuard M0 environment and capability record

Recorded: 2026-10-08  
Scope: M0.1  
Verdict: **M0.1 passed under the owner-amended exact-build contract**

## Approval and workspace

The owner's 2026-10-08 execution instruction authorizes Milestone 0 only and
accepts native black EOF evidence (A1) and deterministic selected-stream
coverage (A2). During M0.1, no FFmpeg 6.1 build was installed. The owner then
explicitly amended A3: validate only the installed FFmpeg/FFprobe 9.0.2 build,
make no 6.1+ or cross-build claim, and continue only if experiments reveal no
downstream blocker. M1 requires separate authorization.

No project-local `CLAUDE.md` or `AGENTS.md` was present. The folder is not a
Git repository:

```text
$ pwd
/Users/justin/Desktop/Projects/frameguard
$ git status --short --branch
fatal: not a git repository (or any of the parent directories): .git
```

No Git repository was initialized and no host runtime was installed or
changed.

## Host

```text
$ uname -a
Darwin Justins-MacBook.local 27.0.0 Darwin Kernel Version 27.0.0: Tue Aug 11 21:05:57 PDT 2026; root:xnu-13432.1.9~1/RELEASE_ARM64_T8140 arm64
$ uname -m
arm64
$ sw_vers
ProductName: macOS
ProductVersion: 27.0.1
BuildVersion: 26A434
```

All commands in this record ran locally in the selected folder. No external
service was contacted intentionally and no footage was uploaded.

## Runtime inventory

| Command | Exit | Observed |
|---|---:|---|
| `command -v python3` | 0 | `/opt/homebrew/bin/python3` |
| `python3 --version` | 0 | `Python 3.14.8` |
| `command -v ffmpeg` | 0 | `/opt/homebrew/bin/ffmpeg` |
| `ffmpeg -version` | 0 | `ffmpeg version 9.0.2`; Apple clang 21.0.0; libavformat 63.1.102; libavfilter 12.1.102 |
| `command -v ffprobe` | 0 | `/opt/homebrew/bin/ffprobe` |
| `ffprobe -version` | 0 | `ffprobe version 9.0.2`; same Homebrew `ffmpeg-full` build configuration |
| `uv --version` | 0 | `uv 0.12.21 (7af826859 2026-09-29 aarch64-apple-darwin)` |
| `docker --version` | 0 | `Docker version 29.8.2, build 7fc2dff9bc` |
| `docker image ls --format '{{.Repository}}:{{.Tag}}'` | 1 | Docker API socket absent; daemon not running |
| `podman --version` | 127 | `podman` not installed |

The Homebrew cellar contained only `ffmpeg-full/9.0.2`. A read-only
`brew list --versions ffmpeg ffmpeg-full ffmpeg@6` attempt could not complete
because Homebrew tried to refresh API metadata and the sandboxed request
received HTTP 403. Direct cellar inspection still found no installed 6.1
build.

Python 3.14.8 satisfies the experiment-helper requirement. FFmpeg 9.0.2 is a
newer stable build relative to the original draft. After the owner amendment,
9.0.2 became the sole M0 build under test. This record does not establish
compatibility with 6.1, other FFmpeg 9 builds, Linux, Intel macOS, or Windows.

## Required FFmpeg capability commands on 9.0.2

| Command | Exit | Relevant observation |
|---|---:|---|
| `ffmpeg -hide_banner -filters` | 0 | `blackdetect` video filter and `silencedetect` audio filter are present |
| `ffmpeg -hide_banner -h filter=blackdetect` | 0 | `d`/`black_min_duration` default 2; `pic_th` default 0.98; `pix_th` default 0.1 |
| `ffmpeg -hide_banner -h filter=silencedetect` | 0 | noise default 0.001 (-60 dB amplitude); duration default 2; `mono=false` |
| `ffmpeg -hide_banner -h demuxer=mov` | 0 | `use_absolute_path=false`, `enable_drefs=false`, edit-list controls present |

The MOV demuxer exposes:

```text
-use_absolute_path <boolean> allow using absolute path when opening alias,
                              this is a possible security issue (default false)
-ignore_editlist <boolean>    Ignore the edit list atom. (default false)
-advanced_editlist <boolean>  Modify the AVIndex according to the editlists.
                              (default true)
-enable_drefs <boolean>       Enable external track support. (default false)
```

Option presence alone was not treated as execution evidence. M0.4 subsequently
used a controlled QuickTime alias fixture and confirmed that
`-enable_drefs 0` logged `Skipped opening external track` and returned nonzero;
URL input was rejected by `-protocol_whitelist file`.

## Reproducibility notes

The exact FFmpeg configuration identifies Homebrew
`/opt/homebrew/Cellar/ffmpeg-full/9.0.2`, Apple clang 21.0.0, GPL and
`libx264` enabled; library versions include libavformat 63.1.102 and
libavfilter 12.1.102. Full filter output was 584 lines. The required version,
filter and demuxer help commands all completed with exit 0.

## Gate result

M0.1 passed for the exact macOS arm64 / Python 3.14.8 / FFmpeg and FFprobe
9.0.2 environment. No runtime was installed or changed. The accepted support
envelope is now narrower than the planning draft; broadening it requires new
owner-approved build coverage.
