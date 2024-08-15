from __future__ import annotations

import io
import itertools
import json
import os
import warnings
from collections.abc import Generator

import ase.io
import ccdc.crystal
import ccdc.entry
import ccdc.io
import tqdm
from optimade.adapters.structures.ase import from_ase_atoms
from optimade.models import StructureResource


def from_csd_entry(entry: ccdc.entry.Entry) -> StructureResource:
    cif = entry.crystal.to_string(format="cif")
    warnings.filterwarnings("ignore", category=UserWarning)
    ase_atoms = ase.io.read(io.StringIO(cif), format="cif")
    return StructureResource(
        **{
            "attributes": from_ase_atoms(ase_atoms),
            "id": entry.identifier,
            "type": "structures",
        }
    )


def from_csd_database(
    reader, range_=itertools.count()
) -> Generator[str | RuntimeError, None, None]:
    chunked_structures = [entry for entry in [reader[r] for r in range_]]
    for entry in chunked_structures:
        try:
            optimade = from_csd_entry(entry)
        except Exception:
            yield RuntimeError(f"Bad entry: {entry.identifier!r}")

        dct = optimade.model_dump()  # type: ignore
        dct["attributes"].pop("_ase_spacegroup", None)
        yield json.dumps(dct)


# def handle_chunk(chunk_id: int, range_: Generator = None):
def handle_chunk(args):
    run_name = "test"
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


def main():
    from multiprocessing import Pool

    pool_size = 4
    chunk_size = 100
    num_chunks = int(1.29e7) // chunk_size
    ranges = (range(i * chunk_size, (i + 1) * chunk_size) for i in range(num_chunks))

    with Pool(pool_size) as pool:
        pool.map(handle_chunk, enumerate(ranges), chunksize=1)
