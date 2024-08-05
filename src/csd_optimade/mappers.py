from optimade.models import StructureResource
from optimade.adapters.structures.ase import from_ase_atoms
import ase.io
import time
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


def from_csd_database(reader):
    for entry in reader:
        try:
            start = time.monotonic_ns()
            optimade = from_csd_entry(entry)
            elapsed = time.monotonic_ns() - start
        except Exception:
            yield elapsed / 1e9, RuntimeError(f"Bad entry: {entry.identifier!r}")

        dct = optimade.model_dump()
        dct["attributes"].pop("_ase_spacegroup", None)
        yield elapsed / 1e9, json.dumps(dct)


if __name__ == "__main__":
    bad_count = 0
    total_count = 0
    with open("optimade.jsonl", "w") as f:
        with open("timings.csv", "w") as timings:
            for timer, entry in (
                pbar := tqdm.tqdm(
                    from_csd_database(ccdc.io.EntryReader("CSD")),
                    ncols=120,
                    total=int(1.29e7),
                    desc="CSD -> OPTIMADE",
                )
            ):
                total_count += 1
                if isinstance(entry, Exception):
                    bad_count += 1
                    pbar.set_description(
                        f"CSD -> OPTIMADE ({bad_count} bad entries so far: {bad_count/total_count:.2%})"
                    )
                    continue
                timings.write(f"{json.loads(entry)['id']}, {timer:.2f}\n")
                f.write(entry + "\n")
