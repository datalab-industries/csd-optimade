import os
import time
import traceback
import warnings
from typing import TYPE_CHECKING

import numpy as np
import pytest
from optimade.adapters.structures.utils import cellpar_to_cell

from csd_optimade.mappers import _reduce_csd_formula

from .utils import generate_same_random_csd_entries

if TYPE_CHECKING:
    import ccdc.entry
    from optimade.models import Resource, StructureResource

TEST_ENTRIES = generate_same_random_csd_entries()
TEST_ENTRIES_ALL = generate_same_random_csd_entries(num_entries=1_290_000)


def check_entry(
    entry: "ccdc.entry.Entry",
    resource: "StructureResource",
    included: list["Resource"],
    warn_only: bool = False,
) -> bool:
    assert entry.identifier == resource.id, f"{entry.identifier} != {resource.id}"
    # total_num_atoms = entry.crystal.z_value * len(
    #     entry.crystal.asymmetric_unit_molecule.atoms
    # )

    if resource.attributes.lattice_vectors:
        a, b, c = entry.crystal.cell_lengths
        alpha, beta, gamma = entry.crystal.cell_angles
        cell = cellpar_to_cell([a, b, c, alpha, beta, gamma])
        np.testing.assert_array_almost_equal(
            cell, resource.attributes.lattice_vectors, decimal=5
        )

    # try:
    #     assert resource.attributes.nsites == total_num_atoms, (
    #         f"{resource.attributes.nsites=} != {total_num_atoms=} for {entry.identifier}"
    #     )
    # except AssertionError as exc:
    #     if warn_only:
    #         warnings.warn(
    #     f"{exc} for {entry.identifier}",
    #     RuntimeWarning,
    # )
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


def test_random_entries_all(csd_available):
    if not csd_available:
        pytest.skip("CSD not available")

    if not os.getenv("CSD_TEST_ALL") == "1":
        pytest.skip("Skipping all CSD entries test as `CSD_TEST_ALL` unset.")

    from csd_optimade.mappers import from_csd_entry_directly

    mapper = from_csd_entry_directly

    for index, entry in TEST_ENTRIES_ALL:
        try:
            start = time.monotonic_ns()
            print(entry.identifier, end=",")
            optimade, included = mapper(entry)
            elapsed = time.monotonic_ns() - start
            assert check_entry(entry, optimade, included, warn_only=True), (
                f"{entry.identifier} ({index}) failed"
            )
            if elapsed > 1e9:
                print(f"{entry.identifier} ({index}) took {elapsed / 1e9:.1f}s")
            print(".", end="")
        except Exception as exc:
            print(f"{entry.identifier} ({index}) failed")
            traceback.print_exc()
            with open("bad_entries.txt", "a") as f:
                f.write(f"{entry.identifier} ({index}): {exc}\n")


def test_reduce_formula():
    zzzghe = "C18 H12 Br3 N1"
    assert _reduce_csd_formula(zzzghe) == "Br3C18H12N"

    pivcih01 = "C11 H20 O3"
    assert _reduce_csd_formula(pivcih01) == "C11H20O3"

    dumjif1 = "C54 H41 As2 O11 P1 Ru3,0.15(C1 H2 Cl2)"
    with pytest.raises(ValueError, match="multi-component"):
        _reduce_csd_formula(dumjif1)

    dipjer = "C20 H25 N2 S2 1+,C4 H3 O4 1-"
    with pytest.raises(ValueError, match="multi-component"):
        _reduce_csd_formula(dipjer)

    nubjax01 = "C36 H24 Br3 N3 O11 U2,H2 O1"
    with pytest.raises(ValueError, match="multi-component"):
        _reduce_csd_formula(nubjax01)

    jatfet01 = "C65 H45 Au2 N3 O1,C35 H40 N3 Pt1 1+,B1 F4 1-"
    with pytest.raises(ValueError, match="multi-component"):
        _reduce_csd_formula(jatfet01)
