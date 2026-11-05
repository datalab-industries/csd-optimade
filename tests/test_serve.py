"""Unit tests for the config passed by `csd-serve` to optimade-maker."""

import os
import sys
from pathlib import Path

import pytest

from csd_optimade import serve


@pytest.fixture(autouse=True)
def clean_optimake_env(monkeypatch):
    """Make sure no `OPTIMAKE_*` variables from the test environment leak in."""
    for var in list(os.environ):
        if var.startswith("OPTIMAKE_"):
            monkeypatch.delenv(var)


@pytest.fixture
def jsonl_file(tmp_path) -> Path:
    path = tmp_path / "csd-optimade.jsonl"
    path.touch()
    return path


@pytest.fixture
def run_cli(monkeypatch, jsonl_file):
    """Run `csd-serve` with the given flags, returning the `override_config`
    passed to optimade-maker, without starting the API or connecting to MongoDB.
    """
    import pymongo

    captured: dict = {}

    class FakeServer:
        def __init__(self, path, host, port, override_config):
            captured.update(override_config)

        def start_api(self):
            pass

    class FakeMongoClient:
        def __init__(self, *args, **kwargs):
            pass

        def server_info(self):
            return {"ok": 1}

        def drop_database(self, name):
            pass

    monkeypatch.setattr(serve, "OptimakeServer", FakeServer)
    monkeypatch.setattr(pymongo, "MongoClient", FakeMongoClient)

    def _run(*args: str, path: str | None = None) -> dict:
        captured.clear()
        monkeypatch.setattr(sys, "argv", ["csd-serve", path or str(jsonl_file), *args])
        serve.cli()
        return dict(captured)

    return _run


def test_defaults(run_cli, jsonl_file):
    config = run_cli()

    insert_path = Path(config["insert_from_jsonl"])
    assert insert_path.is_absolute()
    assert insert_path == jsonl_file.resolve()
    assert config["create_default_index"] is True
    assert config["database_backend"] == "mongomock"
    assert config["mongo_uri"] is None
    assert "exit_after_insert" not in config
    assert config["provider"]["prefix"] == "csd"
    assert config["provider_fields"]["structures"]
    assert config["implementation"]
    assert config["license"]


def test_relative_jsonl_path_is_made_absolute(run_cli, jsonl_file, monkeypatch):
    monkeypatch.chdir(jsonl_file.parent)
    config = run_cli(path=jsonl_file.name)
    assert Path(config["insert_from_jsonl"]) == jsonl_file.resolve()


def test_cli_flags(run_cli):
    config = run_cli("--no-insert", "--exit-after-insert")
    assert config["insert_from_jsonl"] is None
    assert config["exit_after_insert"] is True


def test_explicit_mongo_uri(run_cli):
    config = run_cli("--mongo-uri", "mongodb://db:27017/optimade")
    assert config["mongo_uri"] == "mongodb://db:27017/optimade"
    assert config["database_backend"] == "mongodb"


def test_mongo_uri_from_env(run_cli, monkeypatch):
    monkeypatch.setenv("OPTIMAKE_MONGO_URI", "mongodb://env:27017/optimade")
    config = run_cli()
    assert config["mongo_uri"] == "mongodb://env:27017/optimade"
    assert config["database_backend"] == "mongodb"


def test_explicit_mongo_uri_beats_env(run_cli, monkeypatch):
    monkeypatch.setenv("OPTIMAKE_MONGO_URI", "mongodb://env:27017/optimade")
    config = run_cli("--mongo-uri", "mongodb://cli:27017/optimade")
    assert config["mongo_uri"] == "mongodb://cli:27017/optimade"


def test_no_insert_beats_env(run_cli, monkeypatch):
    monkeypatch.setenv("OPTIMAKE_INSERT_FROM_JSONL", "/some/other.jsonl")
    config = run_cli("--no-insert")
    assert config["insert_from_jsonl"] is None


@pytest.mark.parametrize(
    "env_var,key",
    [
        ("OPTIMAKE_DATABASE_BACKEND", "database_backend"),
        ("OPTIMAKE_PROVIDER", "provider"),
        ("OPTIMAKE_INSERT_FROM_JSONL", "insert_from_jsonl"),
        ("OPTIMAKE_CREATE_DEFAULT_INDEX", "create_default_index"),
        ("OPTIMAKE_LICENSE", "license"),
    ],
)
def test_env_vars_take_precedence_over_defaults(run_cli, monkeypatch, env_var, key):
    """As in csd-optimade 0.1.x, `OPTIMAKE_*` variables should win over our defaults,
    so they must not be set in the override config (which optimade-maker>=0.6 applies last).
    """
    monkeypatch.setenv(env_var, "set-by-env")
    config = run_cli()
    assert key not in config
