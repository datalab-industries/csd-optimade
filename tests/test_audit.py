"""Tests of the single-process `csd-audit` command, using a mocked CSD Python API."""

from __future__ import annotations

import importlib
import json
import sys
from typing import TYPE_CHECKING

import pytest

from .mock_ccdc import Entry, make_mock_ccdc_modules, make_mock_entries

if TYPE_CHECKING:
    from pathlib import Path

# A broken entry (no crystal) that makes the mapper raise
BROKEN_ENTRY = Entry(identifier="BROKEN", formula="C1 H4 O1", crystal=None)  # type: ignore[arg-type]
ENTRIES = make_mock_entries() + [BROKEN_ENTRY]
BROKEN_INDEX = len(ENTRIES) - 1


@pytest.fixture
def audit(monkeypatch):
    """Return the `csd_optimade.audit` module with the CSD Python API mocked out."""
    fake_modules = make_mock_ccdc_modules(ENTRIES)
    try:
        import csd_optimade.audit as audit
    except (ImportError, RuntimeError):
        for name, module in fake_modules.items():
            monkeypatch.setitem(sys.modules, name, module)
        for name in ("csd_optimade.audit", "csd_optimade.ingest"):
            monkeypatch.delitem(sys.modules, name, raising=False)
        audit = importlib.import_module("csd_optimade.audit")

    # Always use the mock reader, even if the real CSD is available
    monkeypatch.setattr(audit, "ccdc", fake_modules["ccdc"])
    return audit


def read_records(path: Path) -> tuple[list[dict], list[dict]]:
    lines = [json.loads(line) for line in path.read_text().splitlines()]
    headers = [line["header"] for line in lines if "header" in line]
    records = [line for line in lines if "index" in line]
    return headers, records


def test_audit_all_entries(audit, tmp_path):
    output = tmp_path / "audit.jsonl"
    audit.cli(["run", "--output", str(output), "--hang-timeout", "0"])

    headers, records = read_records(output)
    assert len(headers) == 1
    assert headers[0]["csd_size"] == len(ENTRIES)
    assert [r["index"] for r in records] == list(range(len(ENTRIES)))

    by_id = {r["identifier"]: r for r in records}
    for entry in ENTRIES[:-1]:
        record = by_id[entry.identifier]
        assert record["status"] == "ok"
        assert record["t_read"] >= 0 and record["t_map"] >= 0 and record["t_dump"] >= 0

    assert by_id["MOCK01"]["nsites"] == 6
    assert by_id["MOCK01"]["missing"] == []
    assert "cartesian_site_positions" in by_id["MOCK06"]["missing"]
    assert "space_group_int_number" in by_id["MOCK08"]["missing"]
    assert "disorder" in by_id["MOCK04"]["structure_features"]

    broken = by_id["BROKEN"]
    assert broken["status"] == "failed"
    assert broken["stage"] == "map"
    assert broken["error_type"].endswith("AttributeError")
    assert "Traceback" in broken["traceback"]

    # The current-entry marker is removed after a complete run
    assert not (tmp_path / "audit.jsonl.current").exists()


def test_audit_read_error(audit, tmp_path, monkeypatch):
    reader_cls = audit.ccdc.io.EntryReader
    original_getitem = reader_cls.__getitem__

    def flaky_getitem(self, index):
        if index == 2:
            raise RuntimeError("Unreadable entry")
        return original_getitem(self, index)

    monkeypatch.setattr(reader_cls, "__getitem__", flaky_getitem)

    output = tmp_path / "audit.jsonl"
    audit.cli(["run", "--output", str(output), "--hang-timeout", "0"])
    _, records = read_records(output)

    # The unreadable entry is recorded, and the rest are still audited
    assert len(records) == len(ENTRIES)
    assert records[2]["status"] == "read_error"
    assert records[2]["error"] == "Unreadable entry"
    assert records[3]["status"] == "ok"


def test_audit_refuses_to_overwrite(audit, tmp_path):
    output = tmp_path / "audit.jsonl"
    audit.cli(["run", "--output", str(output), "--stop", "1", "--hang-timeout", "0"])
    with pytest.raises(SystemExit):
        audit.cli(["run", "--output", str(output), "--hang-timeout", "0"])


def test_audit_resume(audit, tmp_path):
    output = tmp_path / "audit.jsonl"
    audit.cli(["run", "--output", str(output), "--stop", "3", "--hang-timeout", "0"])
    audit.cli(["run", "--output", str(output), "--resume", "--hang-timeout", "0"])

    headers, records = read_records(output)
    assert len(headers) == 2
    assert headers[1]["start"] == 3
    assert [r["index"] for r in records] == list(range(len(ENTRIES)))


def test_audit_resume_after_kill(audit, tmp_path):
    """An entry left marked as current (e.g., a hang that was killed) is recorded
    as interrupted and skipped on resume."""
    output = tmp_path / "audit.jsonl"
    audit.cli(["run", "--output", str(output), "--stop", "3", "--hang-timeout", "0"])
    (tmp_path / "audit.jsonl.current").write_text(
        json.dumps({"index": 3, "started_at": "2026-01-01T00:00:00"})
    )
    audit.cli(["run", "--output", str(output), "--resume", "--hang-timeout", "0"])

    _, records = read_records(output)
    assert [r["index"] for r in records] == list(range(len(ENTRIES)))
    assert records[3]["status"] == "interrupted"
    assert records[4]["status"] == "ok"


def test_audit_summarise(audit, tmp_path, capsys):
    output = tmp_path / "audit.jsonl"
    audit.cli(["run", "--output", str(output), "--hang-timeout", "0"])
    capsys.readouterr()

    audit.cli(["summarise", str(output)])
    summary = json.loads((tmp_path / "audit.summary.json").read_text())

    assert summary["entries"] == len(ENTRIES)
    assert summary["statuses"] == {"ok": len(ENTRIES) - 1, "failed": 1}
    assert summary["missing_fields"]["cartesian_site_positions"] >= 1
    assert summary["top_errors"][0]["count"] == 1
    assert summary["timings_s"]["t_map"]["max"] >= 0
    assert len(summary["slowest"]) == len(ENTRIES)


def test_audit_hang_watchdog(audit, tmp_path, monkeypatch):
    """A slow entry triggers a stack dump to the hangs log, but is still recorded."""
    import time

    mapper = audit.from_csd_entry_directly

    def slow_mapper(entry):
        if entry.identifier == "MOCK02":
            time.sleep(0.5)
        return mapper(entry)

    monkeypatch.setattr(audit, "from_csd_entry_directly", slow_mapper)

    output = tmp_path / "audit.jsonl"
    audit.cli(["run", "--output", str(output), "--stop", "3", "--hang-timeout", "0.1"])

    _, records = read_records(output)
    assert [r["status"] for r in records] == ["ok", "ok", "ok"]
    assert records[1]["t_map"] >= 0.5

    hangs = (tmp_path / "audit.jsonl.hangs.log").read_text()
    assert "# entry index 1" in hangs
    assert "slow_mapper" in hangs
