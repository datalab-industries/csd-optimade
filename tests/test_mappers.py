import re
import warnings
from typing import TYPE_CHECKING

import numpy as np
import pytest
from optimade.adapters.structures.utils import cellpar_to_cell

from .utils import generate_same_random_csd_entries

if TYPE_CHECKING:
    import ccdc.entry
    from optimade.models import Resource, StructureResource

TEST_ENTRIES = generate_same_random_csd_entries()


def check_entry(
    entry: "ccdc.entry.Entry",
    resource: "StructureResource",
    included: list["Resource"],
    warn_only: bool = False,
) -> bool:
    assert entry.identifier == resource.id, f"{entry.identifier} != {resource.id}"
    total_num_atoms = entry.crystal.z_value * len(
        entry.crystal.asymmetric_unit_molecule.atoms
    )

    a, b, c = entry.crystal.cell_lengths
    alpha, beta, gamma = entry.crystal.cell_angles
    cell = cellpar_to_cell([a, b, c, alpha, beta, gamma])
    if resource.attributes.lattice_vectors:
        np.testing.assert_array_almost_equal(
            cell, resource.attributes.lattice_vectors, decimal=5
        )

    try:
        assert resource.attributes.nsites == total_num_atoms, (
            f"{resource.attributes.nsites=} != {total_num_atoms=} for {entry.identifier}"
        )
    except AssertionError as exc:
        if warn_only:
            warnings.warn(
                f"{exc} for {entry.identifier}",
                RuntimeWarning,
            )

    formula_dct = {}
    for e in (
        entry.crystal.asymmetric_unit_molecule.formula.strip("(").strip(")n").split(" ")
    ):
        matches = re.match(r"([a-zA-Z]+)([0-9]*)", e)
        if matches:
            species, count = matches.groups()
            formula_dct[species] = int(count) if count else 1

    formula_str: str = ""
    for e in sorted(formula_dct):
        formula_str += f"{e}{formula_dct[e] if formula_dct[e] > 1 else ''}"

    try:
        assert formula_str == resource.attributes.chemical_formula_reduced
    except AssertionError as exc:
        if warn_only:
            warnings.warn(
                f"{exc} for {entry.identifier}",
                RuntimeWarning,
            )

    try:
        if entry.publications:
            assert resource.relationships.references is not None
            if entry.publications[0].doi:
                assert (
                    resource.relationships.references.data[0].id
                    == entry.publications[0].doi
                )
            assert len(included) == len(entry.publications)

    except AssertionError as exc:
        if warn_only:
            warnings.warn(
                f"{exc} for {entry.identifier}",
                RuntimeWarning,
            )

    return True


@pytest.mark.parametrize("bad_refcodes", [["ABEBUF", "ABAYIP", "ADALEZ"]])
def test_problematic_entries(bad_refcodes, csd_available):
    if not csd_available:
        pytest.skip("CSD not available")

    from ccdc.io import EntryReader

    from csd_optimade.mappers import from_csd_entry_directly

    mapper = from_csd_entry_directly
    reader = EntryReader("CSD")
    for refcode in bad_refcodes:
        entry = reader.entry(refcode)
        if not entry:
            raise ValueError(f"Entry {refcode} not found in CSD")
        assert check_entry(entry, *mapper(entry)), f"{entry.identifier} failed"


@pytest.mark.parametrize("index,entry", TEST_ENTRIES)
def test_random_entries(index: int, entry: "ccdc.entry.Entry", csd_available):
    if not csd_available:
        pytest.skip("CSD not available")
    from csd_optimade.mappers import from_csd_entry_directly

    mapper = from_csd_entry_directly
    optimade, included = mapper(entry)
    assert check_entry(entry, optimade, included, warn_only=True), (
        f"{entry.identifier} ({index}) failed"
    )
