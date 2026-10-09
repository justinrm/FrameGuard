from __future__ import annotations

import subprocess
from pathlib import Path


def _run(*argv: str) -> None:
    result = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", "replace"))


def generate_probe_fixtures(root: Path, ffmpeg: Path) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    baseline = root / "baseline ü space.mp4"
    _run(
        str(ffmpeg),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "color=c=blue:s=320x240:r=30000/1001:d=1",
        "-f",
        "lavfi",
        "-i",
        "sine=f=1000:r=48000:d=1",
        "-map",
        "0:v",
        "-map",
        "1:a",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        str(baseline),
    )
    video_only = root / "video-only.mov"
    _run(
        str(ffmpeg),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "color=c=blue:s=320x240:r=30:d=1",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(video_only),
    )
    rotated = root / "rotated.mov"
    _run(
        str(ffmpeg),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-display_rotation:v:0",
        "90",
        "-i",
        str(baseline),
        "-map",
        "0",
        "-c",
        "copy",
        str(rotated),
    )
    return {"baseline": baseline, "video_only": video_only, "rotated": rotated}
