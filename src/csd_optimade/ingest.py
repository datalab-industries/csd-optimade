from __future__ import annotations

import itertools
import json
import os
from collections.abc import Generator
from functools import partial
from typing import Callable

import ccdc.crystal
import ccdc.entry
import ccdc.io
import tqdm
from optimade.models import StructureResource

from csd_optimade.mappers import from_csd_entry_via_cif_and_ase


def from_csd_database(
    reader: ccdc.io.EntryReader,
    range_: Generator = itertools.count(),  # type: ignore
    mapper: Callable[
        [ccdc.entry.Entry], StructureResource
    ] = from_csd_entry_via_cif_and_ase,
) -> Generator[str | RuntimeError, None, None]:
    """Loop through a chunk of the entry reader and map the entries to OPTIMADE structures."""
    chunked_structures = [entry for entry in [reader[r] for r in range_]]
    for entry in chunked_structures:
        try:
            optimade = mapper(entry)
        except Exception:
            yield RuntimeError(f"Bad entry: {entry.identifier!r}")

        dct = optimade.model_dump()  # type: ignore
        dct["attributes"].pop("_ase_spacegroup", None)
        yield json.dumps(dct)


def handle_chunk(args, run_name: str = "test"):
    """Handle a chunk of the CSD database, logging bad entries and showing a progress bar."""
    chunk_id, range_ = args
    bad_count: int = 0
    total_count: int = 0
    with open(f"{run_name}-optimade-{chunk_id}.jsonl", "w") as f:
        desc_string = f"CSD -> OPTIMADE ({chunk_id:7d} (PID: {os.getpid()})"
        with tqdm.tqdm(
            iterable=None,
            total=100,
            delay=chunk_id,
            position=chunk_id,
            maxinterval=0.5,
            leave=True,
            desc=desc_string,
        ) as pbar:
            for entry in from_csd_database(ccdc.io.EntryReader("CSD"), range_):
                if isinstance(entry, Exception):
                    bad_count += 1
                    pbar.set_description(
                        desc_string
                        + f"({bad_count} bad entries so far: {bad_count/total_count:.2%})"
                    )
                    continue
                else:
                    f.write(entry + "\n")
                pbar.update(1)
                total_count += 1


def cli():
    import argparse
    from multiprocessing import Pool

    parser = argparse.ArgumentParser()
    parser.add_argument("--num-processes", type=int, default=4)
    parser.add_argument("--chunk-size", type=int, default=100)
    parser.add_argument("--total-num", type=int, default=int(1.29e7))
    parser.add_argument("--run-name", type=str)

    args = parser.parse_args()

    pool_size = args.num_processes
    chunk_size = args.chunk_size
    num_chunks = int(args.total_num) // chunk_size
    run_name = args.run_name

    if run_name is None:
        run_name = "test"

    ranges = (range(i * chunk_size, (i + 1) * chunk_size) for i in range(num_chunks))

    with Pool(pool_size) as pool:
        pool.map(
            partial(handle_chunk, run_name=run_name), enumerate(ranges), chunksize=1
        )
