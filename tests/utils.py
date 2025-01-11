"""Some testing utilities for environments without a valid CCDC/CSD license."""

import datetime
import warnings
from typing import NamedTuple


class Position(NamedTuple):
    x: float
    y: float
    z: float


class MockCSDAtom(NamedTuple):
    atomic_symbol: str
    coordinates: Position | None


class MockCSDMolecule:
    """A mock class for a CSD molecule."""

    formula: str = "C1 H1 O1"
    atoms: list[MockCSDAtom] = [
        MockCSDAtom("H", Position(0.0, 0.0, 0.0)),
        MockCSDAtom("C", Position(0.0, 0.0, 0.0)),
        MockCSDAtom("O", Position(0.0, 0.0, 0.0)),
    ]


class CellLengths(NamedTuple):
    a: float
    b: float
    c: float


class CellAngles(NamedTuple):
    alpha: float
    beta: float
    gamma: float


class MockCSDCrystal:
    """A mock class for a CSD crystal."""

    asymmetric_unit_molecule: MockCSDMolecule = MockCSDMolecule()
    formula: str = "C1 H1 O1"
    z_value: int = 1
    cell_lengths: CellLengths = CellLengths(a=1.0, b=1.0, c=1.0)
    cell_angles: CellAngles = CellAngles(alpha=90.0, beta=90.0, gamma=90.0)


class MockCSDEntry:
    """A mock class for a CSD entry."""

    identifier: str = "MOCK"
    deposition_date: datetime.date = datetime.date.today()
    ccdc_number: int = 100
    crystal: MockCSDCrystal = MockCSDCrystal()


def generate_same_random_csd_entries(csd_available=True):
    """Pick some random entries from the CSD, with a fixed seed."""

    num_entries: int = 1000
    if not csd_available:
        warnings.warn("CSD not available")
        yield zip(range(num_entries), num_entries * [MockCSDEntry()])

    else:
        import random

        from ccdc.io import EntryReader

        random.seed(0)
        entry_indices = set()
        entries = []
        max_n: int = int(1.29e6)

        with EntryReader("CSD") as reader:
            while len(entry_indices) < num_entries:
                i = random.randint(0, max_n)
                if i not in entry_indices:
                    try:
                        entry = reader[i]
                        if entry:
                            entries.append((i, entry))
                            entry_indices.add(i)
                    except Exception:
                        continue
            yield from entries
