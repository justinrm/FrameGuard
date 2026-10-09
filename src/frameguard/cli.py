from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from .models import ConfigError, ScanConfig, exit_code
from .scanner import scan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="frameguard")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command")
    scan = commands.add_parser(
        "scan",
        help="inspect one local MP4 or MOV",
        description=(
            "Inspect one local MP4 or MOV. Milestone 1 reports metadata only; "
            "black and silence checks fail as not implemented, so a valid file "
            "exits 2 (incomplete)."
        ),
    )
    scan.add_argument("input", metavar="INPUT", help="path to a local MP4 or MOV file")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        report = scan(Path(args.input), ScanConfig())
    except ConfigError as error:
        print(f"Configuration error: {error}")
        return 2
    except KeyboardInterrupt:
        print("Inspection cancelled.")
        return 2

    print(f"FrameGuard metadata inspection: {report.input.display_name}")
    print(f"Status: {report.overall_status}")
    if report.media_metadata is not None:
        metadata = report.media_metadata
        print(f"Format: {metadata.format_name or 'unknown'}")
        print(f"Video stream: {metadata.selected_video_index}")
        print(
            "Audio stream: "
            + (
                str(metadata.selected_audio_index)
                if metadata.selected_audio_index is not None
                else "none"
            )
        )
        video = next(
            (
                stream
                for stream in metadata.streams
                if stream.index == metadata.selected_video_index
            ),
            None,
        )
        if video is not None:
            print(f"Coded dimensions: {video.width or 'unknown'}x{video.height or 'unknown'}")
            print(f"Reported average FPS: {video.avg_frame_rate or 'unknown'}")
    for diagnostic in report.diagnostics:
        print(f"{diagnostic.code}: {diagnostic.message}")
    failed = {check.check_id for check in report.checks if check.status == "failed"}
    if "black" in failed:
        print("Black detection: not implemented in Milestone 1")
    if "silence" in failed:
        print("Silence detection: not implemented in Milestone 1")
    return exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
