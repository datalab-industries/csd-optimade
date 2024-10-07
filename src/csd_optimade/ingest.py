from __future__ import annotations

import glob
import itertools
import os
from collections.abc import Generator
from functools import partial
from typing import Callable

import ccdc.crystal
import ccdc.entry
import ccdc.io
import tqdm
from optimade.models import StructureResource

from csd_optimade.mappers import from_csd_entry_directly


def from_csd_database(
    reader: ccdc.io.EntryReader,
    range_: Generator = itertools.count(),  # type: ignore
    mapper: Callable[[ccdc.entry.Entry], StructureResource] = from_csd_entry_directly,
) -> Generator[str | RuntimeError, None, None]:
    """Loop through a chunk of the entry reader and map the entries to OPTIMADE structures."""
    chunked_structures = [entry for entry in [reader[r] for r in range_]]
    for entry in chunked_structures:
        try:
            yield mapper(entry).model_dump_json()
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
    return chunk_id, total_count, bad_count


def cli():
    import argparse
    from multiprocessing import Pool

    parser = argparse.ArgumentParser()
    parser.add_argument("--num-processes", type=int, default=4)
    parser.add_argument("--chunk-size", type=int, default=10000)
    parser.add_argument("--total-num", type=int, default=int(1.29e7))
    parser.add_argument("--run-name", type=str)

    args = parser.parse_args()

    pool_size = args.num_processes
    chunk_size = args.chunk_size
    num_chunks = int(args.total_num) // chunk_size
    run_name = args.run_name

    if run_name is None:
        run_name = "csd-"

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
                pbar.set_postfix({"% bad": 100 * (total_bad / total)})

    # Combine all results into a single JSONL file
    output_file = f"{run_name}-optimade.jsonl"
    print(f"Collecting results into {output_file}")

    pattern = f"{run_name}-optimade-*.jsonl"
    input_files = sorted(
        glob.glob(os.path.join("data", pattern)),
        key=lambda x: int(x.split("-")[-1].split(".")[0]),
    )

    with open(output_file, "w") as outfile:
        for filename in input_files:
            with open(filename, "r") as infile:
                outfile.write(infile.read())
            outfile.write("\n")

            print(f"Combined {len(input_files)} files into {output_file} (total size of file: {os.path.getsize(output_file) / 1024 ** 2:.1f} MB)")
