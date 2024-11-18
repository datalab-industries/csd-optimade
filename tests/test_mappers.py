import re
import warnings

import numpy as np
import pytest
from optimade.adapters.structures.utils import cellpar_to_cell


def check_entry(entry, resource, warn_only=False):
    try:
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

        assert (
            resource.attributes.nsites == total_num_atoms
        ), f"{resource.attributes.nsites} != {total_num_atoms} for {entry.identifier}"

        formula_dct = {}
        for e in (
            entry.crystal.asymmetric_unit_molecule.formula.strip("(")
            .strip(")n")
            .split(" ")
        ):
            matches = re.match(r"([a-zA-Z]+)([0-9]*)", e)
            if matches:
                species, count = matches.groups()
                formula_dct[species] = int(count) if count else 1

        formula_str: str = ""
        for e in sorted(formula_dct):
            formula_str += f"{e}{formula_dct[e] if formula_dct[e] > 1 else ''}"

        assert formula_str == resource.attributes.chemical_formula_reduced
    except AssertionError as exc:
        if warn_only:
            warnings.warn(f"{exc}", RuntimeWarning)
            return 0
        raise exc

    return 1


@pytest.mark.parametrize("bad_refcodes", [["ABEBUF", "ABAYIP"]])
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
        assert check_entry(entry, mapper(entry)), f"{entry.identifier} failed"


def test_mappers(mapper, same_random_csd_entries):
    from csd_optimade.mappers import from_csd_entry_directly

    mapper = from_csd_entry_directly
    failures = 0
    good = 0
    total = 0
    for index, entry in same_random_csd_entries:
        total += 1
        try:
            optimade = mapper(entry)
        except Exception as exc:
            print(f"⛔ {entry.identifier}")
            failures += 1
            warnings.warn(
                f"Failed for entry {index}: {entry.identifier}. {exc}",
                category=RuntimeWarning,
            )
            continue
        result = check_entry(entry, optimade, warn_only=True)
        good += result

    num_warnings = total - failures - good

    if num_warnings > 0 or failures > 0:
        warnings.warn(
            f"# warnings: {num_warnings}, # failures: {failures}, # success: {good}",
            RuntimeWarning,
        )

    assert good > failures
    assert good / (good + failures) > 0.95
