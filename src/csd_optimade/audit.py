"""A single-process audit of the whole CSD → OPTIMADE mapping.

Runs every CSD entry through the same mapper and serialisation as `csd-ingest`,
one at a time, and writes one JSON line per entry recording its outcome
(ok/failed/read_error/skipped/interrupted), any error and traceback, any
warnings raised, which key fields are missing from the output, and timings
for each stage. The run can be stopped and resumed, and summarised afterwards.

Usage:

    csd-audit run [--output data/csd-audit.jsonl] [--start N] [--stop M] [--resume]
    csd-audit summarise data/csd-audit.jsonl

"""

from __future__ import annotations

import argparse
import datetime
import faulthandler
import json
import platform
import subprocess
import sys
import time
import traceback
import warnings
from collections import Counter
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import ccdc.io
import tqdm

from csd_optimade.ingest import BAD_IDENTIFIERS
from csd_optimade.mappers import from_csd_entry_directly

if TYPE_CHECKING:
    from typing import IO

KEY_FIELDS: tuple[str, ...] = (
    "chemical_formula_reduced",
    "chemical_formula_anonymous",
    "elements",
    "nsites",
    "species",
    "species_at_sites",
    "cartesian_site_positions",
    "space_group_int_number",
    "space_group_symbol_hermann_maugin",
    "_csd_smiles",
    "_csd_inchi",
    "_csd_crystal_system",
    "_csd_cell_volume",
)
"""Attributes whose absence from the serialised structure is recorded as `missing`."""

MAX_MESSAGE_LENGTH = 2000


def _safe(func: Callable[[], Any]) -> Any:
    """Return `func()`, or `None` if it raises (e.g., for flaky CSD API attributes)."""
    try:
        return func()
    except Exception:
        return None


def _package_version(name: str) -> str | None:
    try:
        return package_version(name)
    except PackageNotFoundError:
        return None


def _git_sha() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).parent,
        ).stdout.strip()
    except Exception:
        return None


def _error_fields(exc: BaseException, stage: str) -> dict[str, Any]:
    return {
        "stage": stage,
        "error_type": f"{type(exc).__module__}.{type(exc).__qualname__}",
        "error": str(exc)[:MAX_MESSAGE_LENGTH],
        "traceback": "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        ),
    }


def audit_entry(
    reader,
    index: int,
    skip_known_bad: bool = False,
    mapper: Callable | None = None,
) -> dict[str, Any]:
    """Run a single CSD entry through the mapper and serialisation, returning a
    record of the outcome and timings. Never raises (other than for interrupts)."""
    if mapper is None:
        mapper = from_csd_entry_directly
    record: dict[str, Any] = {"index": index, "identifier": None, "status": "ok"}

    t0 = time.perf_counter()
    try:
        entry = reader[index]
    except Exception as exc:
        record["t_read"] = time.perf_counter() - t0
        record.update(status="read_error", **_error_fields(exc, "read"))
        return record
    t_read = time.perf_counter() - t0
    record["t_read"] = t_read

    record["identifier"] = _safe(lambda: entry.identifier)
    record["has_3d"] = _safe(lambda: entry.has_3d_structure)
    record["disorder"] = _safe(lambda: entry.has_disorder)

    if skip_known_bad and record["identifier"] in BAD_IDENTIFIERS:
        record["status"] = "skipped"
        return record

    # Map, recording any warnings raised along the way
    t1 = time.perf_counter()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            structure, references = mapper(entry)
        except Exception as exc:
            record["t_map"] = time.perf_counter() - t1
            record.update(status="failed", **_error_fields(exc, "map"))
            structure = None
    if caught:
        record["warnings"] = [
            f"{w.category.__name__}: {str(w.message)[:MAX_MESSAGE_LENGTH]}"
            for w in caught
        ]
    if structure is None:
        return record
    record["t_map"] = time.perf_counter() - t1

    # Serialise exactly as `csd-ingest` does
    t2 = time.perf_counter()
    try:
        dumped = structure.model_dump_json(exclude_unset=True, exclude_none=True)
        dumped_refs = [
            ref.model_dump_json(exclude_unset=True, exclude_none=True)
            for ref in references or []
        ]
    except Exception as exc:
        record["t_dump"] = time.perf_counter() - t2
        record.update(status="failed", **_error_fields(exc, "dump"))
        return record
    record["t_dump"] = time.perf_counter() - t2

    # Inspect what actually made it into the output (not timed)
    attributes = json.loads(dumped).get("attributes", {})
    record["missing"] = [
        field for field in KEY_FIELDS if attributes.get(field) in (None, [], "")
    ]
    record["nsites"] = attributes.get("nsites")
    record["structure_features"] = attributes.get("structure_features") or []
    record["n_references"] = len(dumped_refs)
    record["bytes"] = len(dumped) + sum(len(r) for r in dumped_refs)
    return record


def _last_index(output: Path) -> int | None:
    """Return the highest entry index recorded in an existing audit file."""
    last = None
    with open(output) as f:
        for line in f:
            try:
                index = json.loads(line).get("index")
            except json.JSONDecodeError:
                # A partially written final line from a killed run
                continue
            if index is not None and (last is None or index > last):
                last = index
    return last


def _header(reader, args: argparse.Namespace, start: int, stop: int) -> dict:
    return {
        "header": {
            "started_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "start": start,
            "stop": stop,
            "csd_size": len(reader),
            "csd_version": _safe(lambda: ccdc.io.csd_version()),
            "skip_known_bad": args.skip_known_bad,
            "hang_timeout": args.hang_timeout,
            "git_sha": _git_sha(),
            "versions": {
                name: _package_version(name)
                for name in ("csd-optimade", "csd-python-api", "optimade", "pydantic")
            },
            "python": sys.version,
            "host": platform.node(),
        }
    }


def run(args: argparse.Namespace) -> None:
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    current_path = output.with_suffix(output.suffix + ".current")
    hangs_path = output.with_suffix(output.suffix + ".hangs.log")

    reader = ccdc.io.EntryReader("CSD")
    stop = min(args.stop, len(reader)) if args.stop is not None else len(reader)
    start = args.start

    resumed_record = None
    if args.resume and output.exists():
        last = _last_index(output)
        if last is not None:
            start = max(start, last + 1)
        # An entry still marked as current was being processed when the previous
        # run was killed (e.g., a hang): record it and move past it
        if current_path.exists():
            try:
                current = json.loads(current_path.read_text())
            except json.JSONDecodeError:
                current = None
            if current and current.get("index", -1) >= start:
                resumed_record = {
                    "index": current["index"],
                    "status": "interrupted",
                    "error": "Run was stopped while processing this entry (possible hang); "
                    f"see {hangs_path.name} for any stack trace",
                    "started_at": current.get("started_at"),
                }
                start = current["index"] + 1
    elif output.exists() and not args.overwrite:
        raise SystemExit(
            f"{output} already exists; pass --resume to continue it or --overwrite to replace it"
        )

    mode = "a" if args.resume else "w"
    counts: Counter[str] = Counter()
    with (
        open(output, mode, buffering=1) as out,
        open(hangs_path, "a", buffering=1) as hangs,
    ):
        out.write(json.dumps(_header(reader, args, start, stop)) + "\n")
        if resumed_record:
            out.write(json.dumps(resumed_record) + "\n")
            counts["interrupted"] += 1

        with tqdm.tqdm(
            total=max(stop - start, 0), desc="Auditing CSD", smoothing=0.01
        ) as pbar:
            try:
                for index in range(start, stop):
                    _mark_current(current_path, index, hangs, args.hang_timeout)
                    record = audit_entry(
                        reader, index, skip_known_bad=args.skip_known_bad
                    )
                    faulthandler.cancel_dump_traceback_later()
                    out.write(json.dumps(record) + "\n")
                    counts[record["status"]] += 1
                    pbar.update(1)
                    if index % 100 == 0:
                        pbar.set_postfix(counts, refresh=False)
            except KeyboardInterrupt:
                # A clean interrupt: the current entry is retried on --resume
                faulthandler.cancel_dump_traceback_later()
                current_path.unlink(missing_ok=True)
                print(f"\nInterrupted; resume with --resume. Counts: {dict(counts)}")
                return

    current_path.unlink(missing_ok=True)
    print(f"Audited entries {start}-{stop - 1} into {output}. Counts: {dict(counts)}")


def _mark_current(
    current_path: Path, index: int, hangs: IO[str], hang_timeout: float
) -> None:
    """Record which entry is in progress and arm the hang watchdog."""
    current_path.write_text(
        json.dumps(
            {
                "index": index,
                "started_at": datetime.datetime.now().isoformat(timespec="seconds"),
            }
        )
    )
    if hang_timeout > 0:
        hangs.write(f"# entry index {index}\n")
        faulthandler.dump_traceback_later(hang_timeout, repeat=False, file=hangs)


def summarise(args: argparse.Namespace) -> dict[str, Any]:
    """Summarise an audit file, keeping the latest record for each index."""
    path = Path(args.audit_file)
    headers = []
    records: dict[int, dict] = {}
    with open(path) as f:
        for line in f:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "header" in data:
                headers.append(data["header"])
            elif "index" in data:
                records[data["index"]] = data

    statuses = Counter(r["status"] for r in records.values())
    error_types = Counter(
        r.get("error_type") for r in records.values() if r.get("error_type")
    )
    messages = Counter(
        (r.get("error_type"), (r.get("error") or "").split("\n")[0][:200])
        for r in records.values()
        if r["status"] != "ok" and r.get("error")
    )
    missing = Counter(f for r in records.values() for f in r.get("missing", []))
    warning_counts = Counter(
        w.split("\n")[0][:200] for r in records.values() for w in r.get("warnings", [])
    )

    def _percentiles(key: str) -> dict[str, float] | None:
        values = sorted(r[key] for r in records.values() if r.get(key) is not None)
        if not values:
            return None
        return {
            f"p{p}": values[min(len(values) - 1, int(p / 100 * len(values)))]
            for p in (50, 90, 99)
        } | {"max": values[-1], "sum": sum(values)}

    ok_records = [r for r in records.values() if r["status"] == "ok"]
    slowest = sorted(
        records.values(),
        key=lambda r: (r.get("t_read") or 0)
        + (r.get("t_map") or 0)
        + (r.get("t_dump") or 0),
        reverse=True,
    )[: args.top]

    summary = {
        "audit_file": str(path),
        "runs": headers,
        "entries": len(records),
        "statuses": dict(statuses.most_common()),
        "ok_with_missing_fields": sum(1 for r in ok_records if r.get("missing")),
        "ok_with_warnings": sum(1 for r in ok_records if r.get("warnings")),
        "error_types": dict(error_types.most_common()),
        "top_errors": [
            {"error_type": t, "message": m, "count": c}
            for (t, m), c in messages.most_common(args.top)
        ],
        "missing_fields": dict(missing.most_common()),
        "top_warnings": dict(warning_counts.most_common(args.top)),
        "timings_s": {k: _percentiles(k) for k in ("t_read", "t_map", "t_dump")},
        "slowest": [
            {
                "index": r["index"],
                "identifier": r.get("identifier"),
                "status": r["status"],
                "nsites": r.get("nsites"),
                "t_map": r.get("t_map"),
                "t_dump": r.get("t_dump"),
            }
            for r in slowest
        ],
    }

    summary_path = path.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print(f"\nWritten to {summary_path}", file=sys.stderr)
    return summary


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="csd-audit",
        description="Audit the CSD → OPTIMADE mapping entry by entry, in a single process.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Audit CSD entries.")
    run_parser.add_argument(
        "--output",
        default=f"data/csd-audit-{datetime.date.today().isoformat()}.jsonl",
        help="Audit file to write (DEFAULT: data/csd-audit-<date>.jsonl).",
    )
    run_parser.add_argument("--start", type=int, default=0, help="First entry index.")
    run_parser.add_argument(
        "--stop", type=int, default=None, help="Stop before this index (DEFAULT: all)."
    )
    run_parser.add_argument(
        "--resume",
        action="store_true",
        help="Continue an existing audit file after its last recorded entry.",
    )
    run_parser.add_argument(
        "--overwrite", action="store_true", help="Replace an existing audit file."
    )
    run_parser.add_argument(
        "--skip-known-bad",
        action="store_true",
        help="Skip entries in BAD_IDENTIFIERS (e.g., known hangs) rather than auditing them.",
    )
    run_parser.add_argument(
        "--hang-timeout",
        type=float,
        default=300,
        help="Dump a stack trace if a single entry takes longer than this many seconds (0 to disable).",
    )
    run_parser.set_defaults(func=run)

    summarise_parser = subparsers.add_parser(
        "summarise", help="Summarise an audit file."
    )
    summarise_parser.add_argument("audit_file")
    summarise_parser.add_argument(
        "--top", type=int, default=20, help="Number of top errors/slowest to show."
    )
    summarise_parser.set_defaults(func=summarise)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    cli()
