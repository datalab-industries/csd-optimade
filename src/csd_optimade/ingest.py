from __future__ import annotations

import glob
import itertools
import json
import os
import tempfile
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Callable

import ccdc.crystal
import ccdc.entry
import ccdc.io
import tqdm

if TYPE_CHECKING:
    from collections.abc import Generator

    from optimade.models import ReferenceResource, StructureResource

from optimade_maker.convert import _construct_entry_type_info

from csd_optimade.mappers import from_csd_entry_directly


def from_csd_database(
    reader: ccdc.io.EntryReader,
    range_: Generator = itertools.count(),  # type: ignore
    mapper: Callable[
        [ccdc.entry.Entry], tuple[StructureResource, list[ReferenceResource]]
    ] = from_csd_entry_directly,
) -> Generator[str | RuntimeError]:
    """Loop through a chunk of the entry reader and map the entries to OPTIMADE
    structures, plus a list of any linked resources.
    """
    chunked_structures = [entry for entry in [reader[r] for r in range_]]
    for entry in chunked_structures:
        try:
            data, included = mapper(entry)
            yield data.model_dump_json(exclude_unset=True, exclude_none=True)
            for resource in included or []:
                yield resource.model_dump_json(exclude_unset=True, exclude_none=True)
        except Exception:
            yield RuntimeError(f"Bad entry: {entry.identifier!r}")


def handle_chunk(args, run_name: str = "test", num_chunks: int | None = None):
    """Handle a chunk of the CSD database, logging bad entries and showing a progress bar."""
    chunk_id, range_ = args
    bad_count: int = 0
    total_count: int = 0
    str_chunk_id = f"{chunk_id:0{len(str(num_chunks))}d}"
    with open(f"data/{run_name}-optimade-{str_chunk_id}.jsonl", "w") as f:
        try:
            for entry in from_csd_database(ccdc.io.EntryReader("CSD"), range_):
                if isinstance(entry, Exception):
                    bad_count += 1
                    continue
                else:
                    f.write(entry + "\n")
                total_count += 1
        except RuntimeError:
            # The database iterator raises RuntimeError once we are out of bounds
            pass
    if total_count == 0 and bad_count != 0:
        raise RuntimeError("No good entries found in chunk; something went wrong.")

    return chunk_id, total_count, bad_count


def cli():
    import argparse
    from multiprocessing import Pool

    parser = argparse.ArgumentParser()
    parser.add_argument("--num-processes", type=int, default=4)
    parser.add_argument("--chunk-size", type=int, default=10_000)
    parser.add_argument(
        "--num-structures", type=int, nargs="?", const=int(1.29e7), default=int(1.29e7)
    )
    parser.add_argument("--run-name", type=str, default="csd")

    args = parser.parse_args()

    pool_size = args.num_processes
    chunk_size = args.chunk_size
    if chunk_size > int(args.num_structures):
        chunk_size = int(args.num_structures)
        num_chunks = 1
        pool_size = 1
    else:
        num_chunks = int(args.num_structures) // chunk_size

    run_name = args.run_name

    ranges = (range(i * chunk_size, (i + 1) * chunk_size) for i in range(num_chunks))

    total_bad = 0
    total = 0
    with Pool(pool_size) as pool:
        with tqdm.tqdm(
            total=num_chunks * chunk_size,
            desc=f"Processing CSD ({chunk_size=}, {pool_size=}",
        ) as pbar:
            for chunk_id, total_count, bad_count in pool.imap_unordered(
                partial(handle_chunk, run_name=run_name, num_chunks=num_chunks),
                enumerate(ranges),
                chunksize=1,
            ):
                total_bad += bad_count
                total += total_count
                pbar.update(total)
                try:
                    pbar.set_postfix({"% bad": 100 * (total_bad / total)})
                except ZeroDivisionError:
                    pbar.set_postfix({"% bad": "???"})

    # Combine all results into a single JSONL file, first temporary
    output_file = f"{run_name}-optimade.jsonl"
    tmp_dir = tempfile.TemporaryDirectory()
    tmp_jsonl_path = Path(tmp_dir.name) / output_file
    print(f"Collecting results into {output_file}")

    pattern = f"{run_name}-optimade-*.jsonl"
    input_files = sorted(
        glob.glob(os.path.join("data", pattern)),
        key=lambda x: int(x.split("-")[-1].split(".")[0]),
    )

    with open(tmp_jsonl_path, "w") as tmp_jsonl:
        # Write headers
        tmp_jsonl.write(
            json.dumps({"x-optimade": {"meta": {"api_version": "1.1.0"}}}) + "\n"
        )
        tmp_jsonl.write(
            _construct_entry_type_info(
                "structures", properties=[], provider_prefix=""
            ).model_dump_json()
            + "\n"
        )

        for filename in input_files:
            file = Path(filename)
            with open(file) as infile:
                tmp_jsonl.write(infile.read())
            tmp_jsonl.write("\n")
            file.unlink()

    with open(tmp_jsonl_path) as tmp_jsonl:
        ids_by_type: dict[str, set] = {}
        with open(output_file, "a") as final_jsonl:
            for line_entry in tmp_jsonl:
                if not line_entry.strip():
                    continue
                json_entry = json.loads(line_entry)
                if _type := json_entry.get("type"):
                    if _type not in ids_by_type:
                        ids_by_type[_type] = set()
                    if _id := json_entry.get("id") in ids_by_type[_type]:
                        continue
                    ids_by_type[_type].add(json_entry["id"])
                    final_jsonl.write(line_entry)

    tmp_dir.cleanup()

    # Final scan to remove duplicates an empty lines
    print(
        f"Combined {len(input_files)} files into {output_file} (total size of file: {os.path.getsize(output_file) / 1024**2:.1f} MB)"
    )
