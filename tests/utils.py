"""Some testing utilities for environments without a valid CCDC/CSD license."""

import datetime
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
