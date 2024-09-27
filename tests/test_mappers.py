import re
import warnings

import numpy as np
from optimade.adapters.structures.utils import cellpar_to_cell


def check_entry(entry, resource):
    warn = False
    assert entry.identifier == resource.id, f"{entry.identifier} != {resource.id}"
    total_num_atoms = entry.crystal.z_value * len(entry.molecule.atoms)

    a, b, c = entry.crystal.cell_lengths
    alpha, beta, gamma = entry.crystal.cell_angles
    cell = cellpar_to_cell([a, b, c, alpha, beta, gamma])
    np.testing.assert_array_almost_equal(
        cell, resource.attributes.lattice_vectors, decimal=5
    )

    try:
        assert (
            resource.attributes.nsites == total_num_atoms
        ), f"{resource.attributes.nsites} != {total_num_atoms} for {entry.identifier}"
    except AssertionError:
        warnings.warn(f"nsites check failed for {resource.id}", category=RuntimeWarning)
        warn = True

    try:
        formula_dct = {}
        for e in entry.molecule.formula.strip("(").strip(")n").split(" "):
            matches = re.match(r"([a-zA-Z]+)([0-9]*)", e)
            if matches:
                species, count = matches.groups()
                formula_dct[species] = int(count) if count else 1
            else:
                warnings.warn(
                    f"Failed to parse formula for {resource.id}: {entry.molecule.formula}",
                    category=RuntimeWarning,
                )
                warn = True

        formula_str: str = ""
        for entry in sorted(formula_dct):
            formula_str += (
                f"{entry}{formula_dct[entry] if formula_dct[entry] > 1 else ''}"
            )

        assert formula_str == resource.attributes.chemical_formula_reduced
    except AssertionError:
        warnings.warn(
            f"Chemical formula check failed for {resource.id}", category=RuntimeWarning
        )
        warn = True

    if warn:
        print(f"⚠  {resource.id}")
        return 0
    # print emoji check box
    print(f"✅ {resource.id}")
    return 1


def test_via_cif_and_ase(same_random_csd_entries):
    from csd_optimade.mappers import from_csd_entry_via_cif_and_ase

    failures = 0
    good = 0
    total = 0
    for index, entry in same_random_csd_entries:
        total += 1
        try:
            optimade = from_csd_entry_via_cif_and_ase(entry)
        except Exception as exc:
            print(f"⛔ {entry.identifier}")
            failures += 1
            warnings.warn(
                f"Failed for entry {index}: {entry.identifier}. {exc}",
                category=RuntimeWarning,
            )
            continue
        result = check_entry(entry, optimade)
        good += result

    num_warnings = total - failures - good

    if num_warnings > 0 or failures > 0:
        warnings.warn(
            f"# warnings: {num_warnings}, # failures: {failures}, # success: {good}",
            RuntimeWarning,
        )

    assert good > failures
    assert good / (good + failures) > 0.95
