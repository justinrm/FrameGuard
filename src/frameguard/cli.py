from __future__ import annotations

import argparse
from fractions import Fraction
from pathlib import Path

from . import __version__
from .models import ConfigError, OutputError, ScanConfig, ScanReport, exit_code, validate_config
from .reporting import check_outputs, publish_report, render_html, render_json, render_terminal
from .scanner import scan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="frameguard")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command")
    scan_parser = commands.add_parser(
        "scan",
        help="inspect one local MP4 or MOV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Inspect one local MP4 or MOV.\n"
            "Expectations compare coded width and height, not display orientation.\n"
            "One selected video stream and one selected audio stream are inspected.\n"
            "A clean file exits 0. Warnings still exit 0.\n"
            "Dimension or frame-rate mismatches exit 1. Incomplete analysis exits 2."
        ),
    )
    scan_parser.add_argument("input", metavar="INPUT", help="path to a local MP4 or MOV file")
    scan_parser.add_argument("--expect-width", type=int, help="expected coded width")
    scan_parser.add_argument("--expect-height", type=int, help="expected coded height")
    scan_parser.add_argument("--expect-fps", help="expected average frame rate")
    scan_parser.add_argument(
        "--require-audio", action="store_true", help="fail when no audio stream is present"
    )
    scan_parser.add_argument(
        "--analysis-timeout",
        type=float,
        default=600.0,
        help="seconds allowed for each detector (default 600)",
    )
    scan_parser.add_argument("--json", type=Path, help="write the authoritative JSON report")
    scan_parser.add_argument("--html", type=Path, help="write a static HTML report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    source = Path(args.input)
    outputs = [path for path in (args.json, args.html) if path is not None]
    try:
        config = _config(args)
        validate_config(config)
        check_outputs(source, outputs)
        report = scan(source, config)
    except ConfigError as error:
        print(f"Configuration error: {error}")
        return 2
    except OutputError as error:
        print(f"Output error: {error}")
        return 2
    except KeyboardInterrupt:
        print("Inspection cancelled.")
        return 2
    try:
        _publish(args, report)
    except OutputError as error:
        print(f"Output error: {error}")
        print(render_terminal(report), end="")
        return 2
    print(render_terminal(report), end="")
    return exit_code(report)


def _config(args: argparse.Namespace) -> ScanConfig:
    fps = None
    if args.expect_fps is not None:
        try:
            fps = Fraction(args.expect_fps)
        except (ValueError, ZeroDivisionError) as error:
            raise ConfigError("expect_fps must be a positive rational") from error
    return ScanConfig(
        expect_width=args.expect_width,
        expect_height=args.expect_height,
        expect_fps=fps,
        expect_fps_input=args.expect_fps,
        require_audio=args.require_audio,
        analysis_timeout_seconds=args.analysis_timeout,
    )


def _publish(args: argparse.Namespace, report: ScanReport) -> None:
    if args.json is not None:
        publish_report(args.json, render_json(report))
    if args.html is not None:
        publish_report(args.html, render_html(report))


if __name__ == "__main__":
    raise SystemExit(main())
