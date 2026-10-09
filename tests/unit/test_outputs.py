import os
from pathlib import Path

import pytest

from frameguard.models import OutputError
from frameguard.reporting import check_outputs, publish_report


def test_publish_is_exclusive_and_refuses_existing_or_linked_files(tmp_path: Path) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"source-bytes")
    created = tmp_path / "report.json"
    publish_report(created, "{}\n")
    assert created.read_text() == "{}\n"
    with pytest.raises(OutputError):
        publish_report(created, "other\n")
    assert created.read_text() == "{}\n"

    existing = tmp_path / "kept.json"
    existing.write_bytes(b"keep")
    with pytest.raises(OutputError):
        publish_report(existing, "new")
    assert existing.read_bytes() == b"keep"

    linked = tmp_path / "linked.json"
    linked.symlink_to(source)
    with pytest.raises(OutputError):
        publish_report(linked, "new")
    hard = tmp_path / "hard.json"
    os.link(source, hard)
    with pytest.raises(OutputError):
        publish_report(hard, "new")
    assert source.read_bytes() == b"source-bytes"


def test_check_outputs_rejects_missing_parent_duplicates_and_input(tmp_path: Path) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"source-bytes")
    missing = tmp_path / "missing" / "out.json"
    with pytest.raises(OutputError):
        check_outputs(source, [missing])
    assert not missing.exists()

    same = tmp_path / "out.json"
    with pytest.raises(OutputError):
        check_outputs(source, [same, same])

    with pytest.raises(OutputError):
        check_outputs(source, [source])
    assert source.read_bytes() == b"source-bytes"

    parent = tmp_path / "locked"
    parent.mkdir()
    parent.chmod(0o500)
    try:
        with pytest.raises(OutputError):
            check_outputs(source, [parent / "out.json"])
    finally:
        parent.chmod(0o700)
