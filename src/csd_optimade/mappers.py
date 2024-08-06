from __future__ import annotations
from collections.abc import Generator
from optimade.models import StructureResource
import os
import time
import itertools
from optimade.adapters.structures.ase import from_ase_atoms
import ase.io
import warnings
import json
import tqdm
import io
import ccdc.entry
import ccdc.crystal
import ccdc.io


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
) -> Generator[tuple[float, str | Exception]]:
    chunked_structures = [entry for entry in [reader[r] for r in range_]]
    for entry in chunked_structures:
        # elapsed = -1
        # start = time.monotonic_ns()
        try:
            optimade = from_csd_entry(entry)
            # elapsed = time.monotonic_ns() - start
        except Exception:
            # elapsed = time.monotonic_ns() - start
            yield RuntimeError(f"Bad entry: {entry.identifier!r}")

        dct = optimade.model_dump()  # type: ignore
        dct["attributes"].pop("_ase_spacegroup", None)
        yield json.dumps(dct)


# def handle_chunk(chunk_id: int, range_: Generator = None):
def handle_chunk(args):
    run_name = "test"
    chunk_id, range_ = args
    with open(f"{run_name}-optimade-{chunk_id}.jsonl", "w") as f:
        # with open(f"{run_name}-timings-{chunk_id}.csv", "w") as timings:
        desc_string = f"CSD -> OPTIMADE ({chunk_id:7d} (PID: {os.getpid()})"
        with tqdm.tqdm(
            iterable=None,
            total=100,
            delay=chunk_id,
            position=chunk_id,
            maxinterval=0.5,
            leave=False,
            desc=desc_string,
        ) as pbar:
            for entry in from_csd_database(ccdc.io.EntryReader("CSD"), range_):
                if isinstance(entry, Exception):
                    # pbar.set_description(
                    #     desc_string
                    #     + f"({bad_count} bad entries so far: {bad_count/total_count:.2%})"
                    # )
                    continue
                # timings.write(f"{json.loads(entry)['id']}, {timer:.2f}\n")
                else:
                    f.write(entry + "\n")
                pbar.update(1)


if __name__ == "__main__":
    from multiprocessing import Pool
    import sys

    run_name = sys.argv[1]
    pool_size = 8
    chunk_size = 100
    num_chunks = int(1.29e7) // chunk_size
    ranges = (range(i * chunk_size, (i + 1) * chunk_size) for i in range(num_chunks))

    with Pool(pool_size) as pool:
        results = pool.map(handle_chunk, enumerate(ranges), chunksize=1)
