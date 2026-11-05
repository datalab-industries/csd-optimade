"""A minimal mock of the parts of the CSD Python API (`ccdc`) used by
csd-optimade, so that the ingestion pipeline can be run end-to-end
without a CSD licence or data.

Only the attributes accessed by `csd_optimade.mappers` and
`csd_optimade.ingest` are implemented.
"""

from __future__ import annotations

import datetime
import types
from dataclasses import dataclass, field


@dataclass
class Coordinates:
    x: float
    y: float
    z: float


@dataclass
class Atom:
    atomic_symbol: str
    coordinates: Coordinates | None


@dataclass
class Molecule:
    atoms: list[Atom]
    formula: str = ""
    smiles: str | None = None


@dataclass
class CellLengths:
    a: float
    b: float
    c: float


@dataclass
class CellAngles:
    alpha: float
    beta: float
    gamma: float


@dataclass
class Crystal:
    packed_atoms: list[Atom]
    cell_lengths: CellLengths = field(default_factory=lambda: CellLengths(5, 6, 7))
    cell_angles: CellAngles = field(default_factory=lambda: CellAngles(90, 90, 90))
    cell_volume: float = 210.0
    spacegroup_number_and_setting: tuple[int, int] = (14, 1)
    spacegroup_symbol: str = "P21/c"
    crystal_system: str = "monoclinic"
    z_value: int = 4
    z_prime: float = 1.0
    smiles: str | None = "CO"

    @property
    def asymmetric_unit_molecule(self) -> Molecule:
        return Molecule(atoms=self.packed_atoms)

    @property
    def molecule(self) -> Molecule:
        return Molecule(atoms=self.packed_atoms, smiles=self.smiles)

    def packing(self) -> Molecule:
        return Molecule(atoms=self.packed_atoms)


@dataclass
class Journal:
    full_name: str


@dataclass
class Citation:
    authors: str
    year: int
    journal: Journal
    volume: str
    first_page: str
    doi: str | None


@dataclass
class Inchi:
    inchi: str
    key: str


@dataclass
class Entry:
    identifier: str
    formula: str
    crystal: Crystal
    has_3d_structure: bool = True
    has_disorder: bool = False
    disorder_details: str | None = None
    chemical_name: str | None = None
    ccdc_number: int = 100000
    deposition_date: datetime.date | None = datetime.date(2020, 1, 1)
    remarks: str | None = None
    publications: list[Citation] = field(default_factory=list)
    component_inchis: list[Inchi] = field(default_factory=list)


def _methanol_atoms(*extra: str) -> list[Atom]:
    symbols = ["C", "O", "H", "H", "H", "H", *extra]
    return [
        Atom(s, Coordinates(0.1 * i, 0.2 * i, 0.3 * i)) for i, s in enumerate(symbols)
    ]


def make_mock_entries() -> list[Entry]:
    """Return a small, varied set of mock CSD entries covering the main mapper branches."""
    journal = Journal("Journal of Mock Crystallography")
    return [
        Entry(
            identifier="MOCK01",
            formula="C1 H4 O1",
            chemical_name="methanol",
            crystal=Crystal(_methanol_atoms()),
            publications=[
                Citation(
                    "A.Author, B.Author", 2020, journal, "1", "10", "10.1234/mock.1"
                )
            ],
            component_inchis=[
                Inchi("InChI=1S/CH4O/c1-2/h2H,1H3", "OKKJLVBELUTLKV-UHFFFAOYSA-N")
            ],
        ),
        Entry(
            identifier="MOCK02",
            formula="C1 H4 O1",
            crystal=Crystal(_methanol_atoms()),
            # Citation without a DOI, so an ID is generated
            publications=[Citation("C.Author", 2021, journal, "2", "20", None)],
        ),
        Entry(
            identifier="MOCK03",
            formula="C1 D4 O1",
            chemical_name="methanol-d4",
            crystal=Crystal(
                [Atom(s, Coordinates(0, 0, i)) for i, s in enumerate("CODDDD")]
            ),
        ),
        Entry(
            identifier="MOCK04",
            formula="C1 H4 O1",
            has_disorder=True,
            disorder_details="Disordered over two sites",
            crystal=Crystal(_methanol_atoms()),
        ),
        Entry(
            # Multi-component formula: elements taken from the asymmetric unit
            identifier="MOCK05",
            formula="C1 H4 O1,H2 O1",
            crystal=Crystal(_methanol_atoms("O", "H", "H")),
        ),
        Entry(
            # No 3D coordinates
            identifier="MOCK06",
            formula="C2 H6 O1",
            has_3d_structure=False,
            crystal=Crystal([]),
        ),
        Entry(
            identifier="MOCK07",
            formula="Na1 Cl1",
            crystal=Crystal(
                [
                    Atom("Na", Coordinates(0, 0, 0)),
                    Atom("Cl", Coordinates(2.8, 2.8, 2.8)),
                ],
                cell_lengths=CellLengths(5.64, 5.64, 5.64),
                spacegroup_number_and_setting=(225, 1),
                spacegroup_symbol="Fm-3m",
                crystal_system="cubic",
                smiles="[Na+].[Cl-]",
            ),
            publications=[
                Citation("D.Author", 2019, journal, "3", "30", "10.1234/mock.7")
            ],
        ),
        Entry(
            # Non-standard space group number, which should be dropped
            identifier="MOCK08",
            formula="C1 H4 O1",
            crystal=Crystal(_methanol_atoms(), spacegroup_number_and_setting=(231, 0)),
            remarks="A mock remark",
        ),
    ]


class EntryReader:
    """Mock of `ccdc.io.EntryReader`, indexable by position like the real reader."""

    entries: list[Entry] = []

    def __init__(self, database: str = "CSD"):
        self.database = database

    def __len__(self) -> int:
        return len(self.entries)

    def __getitem__(self, index: int) -> Entry:
        if index >= len(self.entries):
            # The real reader raises a RuntimeError when out of bounds
            raise RuntimeError(f"Index {index} out of range")
        return self.entries[index]

    def entry(self, identifier: str) -> Entry | None:
        return next((e for e in self.entries if e.identifier == identifier), None)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def make_mock_ccdc_modules(entries: list[Entry]) -> dict[str, types.ModuleType]:
    """Return fake `ccdc` modules, keyed by module name, serving the given entries."""
    reader_cls = type("EntryReader", (EntryReader,), {"entries": entries})

    ccdc = types.ModuleType("ccdc")
    io = types.ModuleType("ccdc.io")
    entry = types.ModuleType("ccdc.entry")
    crystal = types.ModuleType("ccdc.crystal")

    io.EntryReader = reader_cls  # type: ignore[attr-defined]
    entry.Entry = Entry  # type: ignore[attr-defined]
    crystal.Crystal = Crystal  # type: ignore[attr-defined]
    ccdc.io = io  # type: ignore[attr-defined]
    ccdc.entry = entry  # type: ignore[attr-defined]
    ccdc.crystal = crystal  # type: ignore[attr-defined]

    return {"ccdc": ccdc, "ccdc.io": io, "ccdc.entry": entry, "ccdc.crystal": crystal}
