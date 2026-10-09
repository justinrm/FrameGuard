from __future__ import annotations

import hashlib
import importlib.util
import socket
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from frameguard.models import ScanConfig, exit_code
from frameguard.scanner import scan

ROOT = Path(__file__).resolve().parents[2]


def _make_external_reference():
    path = ROOT / "tools" / "validate_media.py"
    spec = importlib.util.spec_from_file_location("frameguard_m0_validate_media", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.make_external_reference


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@contextmanager
def _loopback_trap() -> Iterator[tuple[int, dict[str, int]]]:
    # ponytail: counts loopback TCP accepts only; use a capture if a build can leave this host
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    sock.settimeout(0.2)
    contacts = {"n": 0}
    stop = threading.Event()

    def accept() -> None:
        while not stop.is_set():
            try:
                conn, _addr = sock.accept()
            except TimeoutError:
                continue
            contacts["n"] += 1
            conn.close()

    thread = threading.Thread(target=accept, daemon=True)
    thread.start()
    try:
        yield sock.getsockname()[1], contacts
    finally:
        stop.set()
        thread.join(timeout=1)
        sock.close()


def test_manifest_reference_and_url_do_not_connect(
    tmp_path: Path, media_fixtures: dict[str, Path]
) -> None:
    make_external_reference = _make_external_reference()
    config = ScanConfig(analysis_timeout_seconds=10)
    with _loopback_trap() as (port, contacts):
        url = f"http://127.0.0.1:{port}/not-contacted.mp4"
        manifest = tmp_path / "manifest.mp4"
        manifest.write_text(f"#EXTM3U\n{url}\n", encoding="utf-8")
        manifest_before = _sha256(manifest)
        manifest_report = scan(manifest, config)

        reference = tmp_path / "external-reference.mp4"
        assert make_external_reference(media_fixtures["baseline"], reference, url)
        source_before = _sha256(media_fixtures["baseline"])
        reference_before = _sha256(reference)
        reference_report = scan(reference, config)

        missing = scan(Path(url), config)

    assert contacts["n"] == 0
    assert _sha256(manifest) == manifest_before
    assert _sha256(media_fixtures["baseline"]) == source_before
    assert _sha256(reference) == reference_before
    assert manifest_report.overall_status == "incomplete"
    assert manifest_report.media_metadata is None
    assert exit_code(manifest_report) == 2
    assert reference_report.overall_status == "incomplete"
    assert exit_code(reference_report) == 2
    assert missing.overall_status == "incomplete"
    assert any(item.code == "input_unavailable" for item in missing.diagnostics)
    assert exit_code(missing) == 2
