"""End-to-end tests of ingestion and serving, using a mocked CSD Python API.

These run `csd-ingest` against a handful of mock CSD entries, then serve the
resulting JSONL file with `csd-serve` and query the running API.
They do not need a CSD licence or data.
"""

from __future__ import annotations

import importlib
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import TYPE_CHECKING

import pytest

from .mock_ccdc import make_mock_ccdc_modules, make_mock_entries

if TYPE_CHECKING:
    from pathlib import Path

MOCK_ENTRIES = make_mock_entries()
NUM_MOCK_ENTRIES = len(MOCK_ENTRIES)
NUM_MOCK_REFERENCES = sum(len(e.publications) for e in MOCK_ENTRIES)


@pytest.fixture
def mock_ingest(monkeypatch):
    """Return the `csd_optimade.ingest` module with the CSD Python API mocked out.

    If the real `ccdc` package cannot be imported (e.g., no licence), fake modules
    are installed in its place for the duration of the test.
    """
    fake_modules = make_mock_ccdc_modules(MOCK_ENTRIES)
    try:
        import csd_optimade.ingest as ingest
    except (ImportError, RuntimeError):
        for name, module in fake_modules.items():
            monkeypatch.setitem(sys.modules, name, module)
        monkeypatch.delitem(sys.modules, "csd_optimade.ingest", raising=False)
        ingest = importlib.import_module("csd_optimade.ingest")

    # Always use the mock reader, even if the real CSD is available
    monkeypatch.setattr(ingest, "ccdc", fake_modules["ccdc"])
    return ingest


def run_ingest(ingest, tmp_path: Path, monkeypatch, *extra_args: str) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TMPDIR", str(tmp_path / "tmp"))
    (tmp_path / "tmp").mkdir(exist_ok=True)
    monkeypatch.setattr(
        sys,
        "argv",
        ["csd-ingest", "--num-processes", "1", "--run-name", "mock", *extra_args],
    )
    # Make `tempfile` pick up the patched TMPDIR
    monkeypatch.setattr("tempfile.tempdir", None)
    ingest.cli()
    output = tmp_path / "data" / "mock-optimade.jsonl"
    assert output.exists()
    return output


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


@pytest.fixture
def ingested_jsonl(mock_ingest, tmp_path, monkeypatch) -> Path:
    # A chunk size that does not divide the number of entries, so the final chunk is partial
    return run_ingest(mock_ingest, tmp_path, monkeypatch, "--chunk-size", "3")


def test_ingest_all_mock_entries(ingested_jsonl):
    lines = read_jsonl(ingested_jsonl)

    assert "x-optimade" in lines[0]
    assert "available_endpoints" in lines[1]["data"]["attributes"]
    entry_infos = lines[2:4]
    assert {info["type"] for info in entry_infos} == {"info"}
    assert {info["id"] for info in entry_infos} == {"structures", "references"}

    structures = [line for line in lines if line.get("type") == "structures"]
    references = [line for line in lines if line.get("type") == "references"]

    assert sorted(s["id"] for s in structures) == sorted(
        e.identifier for e in MOCK_ENTRIES
    )
    assert len(references) == NUM_MOCK_REFERENCES

    by_id = {s["id"]: s["attributes"] for s in structures}
    assert by_id["MOCK01"]["chemical_formula_reduced"] == "CH4O"
    assert by_id["MOCK01"]["nsites"] == 6
    assert by_id["MOCK03"]["elements"] == ["C", "H", "O"]
    assert "disorder" in by_id["MOCK04"]["structure_features"]
    assert "cartesian_site_positions" not in by_id["MOCK06"]
    assert by_id["MOCK07"]["space_group_int_number"] == 225
    assert "space_group_int_number" not in by_id["MOCK08"]


def test_ingest_num_structures_cap(mock_ingest, tmp_path, monkeypatch):
    output = run_ingest(
        mock_ingest, tmp_path, monkeypatch, "--num-structures", "5", "--chunk-size", "5"
    )
    structures = [
        line for line in read_jsonl(output) if line.get("type") == "structures"
    ]
    assert len(structures) == 5


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _serve_env(tmp_path: Path) -> dict[str, str]:
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("OPTIMAKE_", "OPTIMADE_"))
    }
    # Avoid picking up any user-level optimade-python-tools config file
    env["OPTIMADE_CONFIG_FILE"] = str(tmp_path / "missing-optimade-config.json")
    # optimade-python-tools makes a HEAD request to validate any license URL at startup;
    # unset it (via the env, which takes precedence) to keep the test offline
    env["OPTIMAKE_LICENSE"] = ""
    return env


def _serve_cmd(jsonl: Path, port: int, *extra_args: str) -> list[str]:
    return [
        sys.executable,
        "-c",
        "from csd_optimade.serve import cli; cli()",
        str(jsonl),
        "--port",
        str(port),
        *extra_args,
    ]


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read())


@pytest.fixture
def served_api(ingested_jsonl, tmp_path):
    """Start `csd-serve` on the ingested mock data and yield its base URL."""
    port = _free_port()
    log_path = tmp_path / "serve.log"
    with open(log_path, "w") as log:
        proc = subprocess.Popen(
            _serve_cmd(ingested_jsonl, port),
            stdout=log,
            stderr=subprocess.STDOUT,
            env=_serve_env(tmp_path),
            cwd=tmp_path,
        )
    base_url = f"http://127.0.0.1:{port}/v1"
    try:
        deadline = time.monotonic() + 90
        while True:
            if proc.poll() is not None:
                pytest.fail(f"csd-serve exited early:\n{log_path.read_text()}")
            try:
                _get(f"{base_url}/info")
                break
            except (urllib.error.URLError, ConnectionError):
                if time.monotonic() > deadline:
                    pytest.fail(f"csd-serve did not start:\n{log_path.read_text()}")
                time.sleep(0.5)
        yield base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_serve_mock_entries(served_api):
    structures = _get(f"{served_api}/structures?page_limit=100")
    assert structures["meta"]["data_returned"] == NUM_MOCK_ENTRIES
    assert sorted(s["id"] for s in structures["data"]) == sorted(
        e.identifier for e in MOCK_ENTRIES
    )

    single = _get(f"{served_api}/structures/MOCK07")
    assert single["data"]["attributes"]["chemical_formula_reduced"] == "ClNa"
    assert (
        single["data"]["attributes"]["_csd_space_group_symbol_hermann_mauginn"]
        == "Fm-3m"
    )

    filtered = _get(
        f"{served_api}/structures?filter=" + urllib.parse.quote('elements HAS "Na"')
    )
    assert [s["id"] for s in filtered["data"]] == ["MOCK07"]

    references = _get(f"{served_api}/references")
    assert references["meta"]["data_returned"] == NUM_MOCK_REFERENCES

    info = _get(f"{served_api}/info/structures")
    assert "_csd_chemical_name" in info["data"]["properties"]


def test_serve_exit_after_insert(ingested_jsonl, tmp_path):
    """`--exit-after-insert` (used by the Docker entrypoint) should insert and then exit."""
    result = subprocess.run(
        _serve_cmd(ingested_jsonl, _free_port(), "--exit-after-insert"),
        capture_output=True,
        text=True,
        env=_serve_env(tmp_path),
        cwd=tmp_path,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
