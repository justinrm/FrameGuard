# FrameGuard

Offline CLI that inspects one local MP4 or MOV and reports technical evidence. It does not judge creative quality, edit the file, or upload anything. The source is only read.

JSON is the authoritative report. Terminal text and static HTML render that same result. Field names and status rules are in [docs/report-schema.md](docs/report-schema.md). What this Mac has actually been shown to do is in [docs/validation/compatibility.md](docs/validation/compatibility.md).

## Install

Python 3.11 or newer, plus FFmpeg and FFprobe **9.0.2** on `PATH`. Any other FFmpeg version stops the scan. This tree was validated on macOS arm64 with Python 3.14.8. That is not a claim of Linux, Windows, or any other FFmpeg build.

```console
python -m pip install -e '.[dev]'
frameguard --help
frameguard --version
```

`frameguard --version` prints `frameguard 0.1.0`.

## Scan a file

Quote the whole path. Inside quotes, write the space as a space. A backslash stays in the name FrameGuard looks up, and a space before the closing quote does too.

```console
frameguard scan "/path/to/My Clip.mp4"
```

```console
frameguard scan "/path/to/My Clip.mp4" \
  --expect-width 1080 --expect-height 1920 --expect-fps 30 \
  --json report.json --html report.html
```

`1080`, `1920`, and `30` are example expectations. Use the coded size and average rate you actually want. The generated test baseline is 320×240 at `30000/1001`. `--expect-fps 29.97` matches that rate. `--expect-fps 30` does not.

JSON and HTML paths are created only when you pass `--json` and `--html`. If either file already exists, FrameGuard refuses it and leaves the existing bytes alone. The two output paths must differ, and neither may be the input file.

## What a scan checks

| Check | When it runs | Result |
|---|---|---|
| Resolution | `--expect-width` and/or `--expect-height` | Critical `RESOLUTION_MISMATCH` when coded pixels differ. Rotation does not change the coded size. |
| Frame rate | `--expect-fps` | Compared to the reported average only, within 0.001 fps. `29.97` matches `30000/1001`. A mismatch is critical `FPS_MISMATCH`. This is not a cadence or variable-frame-rate diagnosis. |
| Audio presence | Always | Missing audio is info `AUDIO_ABSENT`. With `--require-audio` it is critical `AUDIO_REQUIRED_MISSING`, and silence is skipped. |
| Black | A real video stream was selected | Warning `BLACK_INTERVAL` for runs of at least 0.5 seconds (`pic_th=0.98`, `pix_th=0.10`). |
| Silence | A real audio stream was selected | Warning `SILENCE_INTERVAL` for 2 seconds at -60 dB on the selected stream, across channels together. One active channel is not silence. |

Unconfigured resolution or frame-rate checks are skipped. A skipped check is not a failure.

One video stream and one audio stream are inspected. FrameGuard picks the default real stream of each type, then the lowest index. Attached pictures are not video. Other tracks are listed as uninspected.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | `pass`, or `warn` when the only findings are black, silence, or optional missing audio |
| 1 | `fail`: a coded-size or frame-rate mismatch |
| 2 | `incomplete`, a bad option, a missing tool, or an output error |

A warning does not change a mismatch into a pass, and a mismatch does not hide a warning. If a required check cannot finish, the status is `incomplete` even when other findings were already collected.

## Paths and files

- A missing path returns `input_unavailable`.
- A directory or FIFO returns `input_not_regular`.
- A symlink is followed and the target is scanned.
- A URL is treated as a filesystem path and is not opened over the network.
- The input must be a regular local file. Playlists and external media references are not scanned as movies.

## Limits

- Trailing black ends at the last picture timestamp. A black tail of about 0.5 seconds at end of file can be missed. That limitation is printed on a completed black check.
- Detector events come from FFmpeg info logs. Those lines are not a stable API.
- Only the selected video stream and selected audio stream are measured. A defect on another track is not reported.
- Frame timing is not a frame-pacing analysis. Uneven frame spacing is not diagnosed.
- Requires the exact FFmpeg/FFprobe 9.0.2 build. No broader platform support is claimed.

## Development

```console
python -m pytest -q
ruff check .
ruff format --check .
```

Tests generate small local clips. They do not download footage.
