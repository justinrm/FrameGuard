# FrameGuard

Offline, evidence-first CLI for inspecting one local MP4 or MOV. Milestone 1
is metadata inspection only: a valid file still exits 2 because black and
silence checks are not implemented.

```console
python -m pip install -e '.[dev]'
frameguard --help
frameguard --version
frameguard scan video.mp4
```

Requires FFmpeg/FFprobe 9.0.2 on PATH. Validated locally on macOS arm64 with
Python 3.14.8. That is not a claim of 6.1+, Linux, or other-build support.

```console
python -m pytest -m 'not detector' -q
ruff check .
ruff format --check .
```
