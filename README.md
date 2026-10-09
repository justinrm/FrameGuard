# FrameGuard

Offline, evidence-first CLI for inspecting one local MP4 or MOV. A clean file
exits 0. Black or silence intervals warn. Coded-dimension or reported
frame-rate mismatches fail.

```console
python -m pip install -e '.[dev]'
frameguard --help
frameguard --version
frameguard scan video.mp4 --expect-width 1080 --expect-height 1920 --json report.json --html report.html
```

`--expect-width` and `--expect-height` compare coded dimensions. Warnings still exit 0. JSON is the authoritative report; see [docs/report-schema.md](docs/report-schema.md).

One selected video stream and one selected audio stream are inspected. Trailing black ends at the last picture PTS, so a short black tail at end of file can be missed.

Requires FFmpeg/FFprobe 9.0.2 on PATH. Validated locally on macOS arm64 with
Python 3.14.8. That is not a claim of 6.1+, Linux, or other-build support.

```console
python -m pytest -q
ruff check .
ruff format --check .
```
