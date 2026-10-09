from __future__ import annotations

import html
import json
import math
import os
import re
from dataclasses import fields, is_dataclass, replace
from fractions import Fraction
from pathlib import Path

from .models import Finding, OutputError, ScanReport, ensure_finite_json

_SEVERITY = {"critical": 0, "warning": 1, "info": 2}
_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def report_to_dict(report: ScanReport) -> dict:
    ordered = replace(report, findings=sorted(report.findings, key=_finding_key))
    payload = _jsonable(ordered)
    ensure_finite_json(payload)
    return payload


def render_json(report: ScanReport) -> str:
    return json.dumps(report_to_dict(report), indent=2, allow_nan=False, ensure_ascii=False) + "\n"


def render_terminal(report: ScanReport) -> str:
    data = report_to_dict(report)
    lines = [
        f"FrameGuard {data['tool_version']}: {data['input']['display_name']}",
        f"Status: {data['overall_status']}",
    ]
    metadata = data["media_metadata"]
    if metadata is not None:
        lines.append(f"Format: {metadata['format_name'] or 'unknown'}")
        lines.append(f"Video stream: {metadata['selected_video_index']}")
        audio = metadata["selected_audio_index"]
        lines.append("Audio stream: " + ("none" if audio is None else str(audio)))
        video = next(
            (
                stream
                for stream in metadata["streams"]
                if stream["index"] == metadata["selected_video_index"]
            ),
            None,
        )
        if video is not None:
            width = video["width"] if video["width"] is not None else "unknown"
            height = video["height"] if video["height"] is not None else "unknown"
            lines.append(f"Coded dimensions: {width}x{height}")
            lines.append(f"Reported average FPS: {video['avg_frame_rate'] or 'unknown'}")
    for diagnostic in data["diagnostics"]:
        lines.append(f"{diagnostic['code']}: {diagnostic['message']}")
    for finding in data["findings"]:
        interval = finding["interval"]
        span = ""
        if interval is not None and interval["start_seconds"] is not None:
            end = interval["end_seconds"]
            span = f" {interval['start_seconds']}-{'' if end is None else end}"
        lines.append(f"{finding['severity']}: {finding['code']}{span}")
    for check in data["checks"]:
        if check["status"] != "completed":
            reason = check["reason_code"] or ""
            lines.append(f"{check['check_id']}: {check['status']} {reason}".rstrip())
        for limitation in check["limitations"]:
            lines.append(f"{check['check_id']}: {limitation}")
    lines.append("Intervals are technical evidence for human review, not a creative judgment.")
    return _plain("\n".join(lines)) + "\n"


def render_html(report: ScanReport) -> str:
    data = report_to_dict(report)
    metadata = data["media_metadata"]
    if metadata is None:
        streams = "<p>Selected streams: unavailable</p><p>Uninspected streams: unavailable</p>"
    else:
        uninspected = ", ".join(str(index) for index in metadata["uninspected_stream_indexes"])
        streams = (
            f"<p>Selected video stream: {_text(metadata['selected_video_index'])}</p>"
            f"<p>Selected audio stream: {_text(metadata['selected_audio_index'])}</p>"
            f"<p>Uninspected streams: {_text(uninspected or 'none')}</p>"
        )
    findings = "".join(
        "<section><h2>"
        + _text(severity)
        + "</h2><ul>"
        + "".join(
            "<li>" + _text(item["code"]) + _span(item) + " " + _text(item["explanation"]) + "</li>"
            for item in data["findings"]
            if item["severity"] == severity
        )
        + "</ul></section>"
        for severity in ("critical", "warning", "info")
        if any(item["severity"] == severity for item in data["findings"])
    )
    checks = "".join(
        "<tr><td>"
        + _text(check["check_id"])
        + "</td><td>"
        + _text(check["status"])
        + "</td><td>"
        + _text(check["reason_code"])
        + "</td><td>"
        + _text("; ".join(check["limitations"]))
        + "</td></tr>"
        for check in data["checks"]
    )
    configuration = "".join(
        "<li>" + _text(key) + ": " + ("null" if value is None else _text(value)) + "</li>"
        for key, value in data["configuration"].items()
    )
    limitations = "".join(
        "<li>" + _text(item) + "</li>" for item in data["timeline"]["limitations"]
    )
    return (
        '<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">'
        "<title>FrameGuard report</title><style>"
        "body{font:16px/1.45 sans-serif;margin:1rem;max-width:42rem}"
        "table{border-collapse:collapse;width:100%}"
        "td,th{border:1px solid #ccc;padding:.3rem;text-align:left;vertical-align:top}"
        "</style></head><body>"
        f"<h1>FrameGuard {_text(data['overall_status'])}</h1>"
        f"<p>{_text(data['input']['display_name'])}</p>"
        f"{streams}{findings}"
        f"<h2>Configuration</h2><ul>{configuration}</ul>"
        "<table><tr><th>Check</th><th>Status</th><th>Reason</th><th>Limitations</th></tr>"
        f"{checks}</table>"
        f"<h2>Timeline</h2><ul>{limitations}</ul>"
        "</body></html>\n"
    )


def check_outputs(source: Path, outputs: list[Path]) -> None:
    identities = [os.path.normcase(str(path.resolve())) for path in outputs]
    if len(identities) != len(set(identities)):
        raise OutputError("output paths must differ")
    source_id = os.path.normcase(str(source.resolve()))
    for path in outputs:
        parent = path.parent
        if not parent.is_dir():
            raise OutputError(f"output parent is missing: {path.name}")
        if not os.access(parent, os.W_OK):
            raise OutputError(f"output parent is not writable: {path.name}")
        if os.path.normcase(str(path.resolve())) == source_id:
            raise OutputError(f"output matches input: {path.name}")
        if path.is_symlink() or path.exists():
            raise OutputError(f"output already exists: {path.name}")


def publish_report(path: Path, content: str) -> None:
    parent = path.parent
    if not parent.is_dir():
        raise OutputError(f"output parent is missing: {path.name}")
    if path.is_symlink() or path.exists():
        raise OutputError(f"output already exists: {path.name}")
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    except FileExistsError as error:
        raise OutputError(f"output already exists: {path.name}") from error
    except OSError as error:
        path.unlink(missing_ok=True)
        raise OutputError(f"output could not be written: {path.name}") from error


def _finding_key(finding: Finding) -> tuple:
    start = math.inf if finding.interval is None else finding.interval.start_seconds
    stream = 2**31 if finding.stream_index is None else finding.stream_index
    return (_SEVERITY.get(finding.severity, 9), finding.check_id, start, stream, finding.code)


def _jsonable(value: object) -> object:
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("nonfinite JSON number")
        return round(value, 6)
    if isinstance(value, Fraction):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: _jsonable(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    raise TypeError(f"unsupported report value: {type(value).__name__}")


def _span(item: dict) -> str:
    interval = item["interval"]
    if interval is None or interval["start_seconds"] is None:
        return ""
    end = interval["end_seconds"]
    return f" {interval['start_seconds']}-{'' if end is None else end}"


def _text(value: object) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def _plain(text: str) -> str:
    text = _ANSI.sub("", text)
    return "".join(
        char if char in "\n\t" or (ord(char) >= 32 and char != "\x7f") else "" for char in text
    )
