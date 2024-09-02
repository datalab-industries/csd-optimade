import re
import warnings

import numpy as np
import tqdm
from optimade.adapters.structures.utils import cellpar_to_cell


def check_entry(entry, resource):
    assert entry.identifier == resource.id, f"{entry.identifier} != {resource.id}"
    total_num_atoms = entry.crystal.z_value * sum(
        len(comp.atoms) for comp in entry.molecule.components
    )
    assert (
        resource.attributes.nsites == total_num_atoms
    ), f"{resource.attributes.nsites} != {total_num_atoms} for {entry.identifier}"

    a, b, c = entry.crystal.cell_lengths
    alpha, beta, gamma = entry.crystal.cell_angles
    cell = cellpar_to_cell([a, b, c, alpha, beta, gamma])
    np.testing.assert_array_almost_equal(
        cell, resource.attributes.lattice_vectors, decimal=5
    )

    formula_dct = {}
    for entry in entry.molecule.formula.split(" "):
        species, count = re.match(r"([a-zA-Z]+)([0-9]*)", entry).groups()
        formula_dct[species] = int(count) if count else 1

    formula_str: str = ""
    for entry in sorted(formula_dct):
        formula_str += f"{entry}{formula_dct[entry] if formula_dct[entry] > 1 else ''}"

    assert formula_str == resource.attributes.chemical_formula_reduced


def test_via_cif_and_ase(same_random_csd_entries):
    from csd_optimade.mappers import from_csd_entry_via_cif_and_ase

    failures = 0
    good = 0
    for index, entry in tqdm.tqdm(same_random_csd_entries):
        try:
            optimade = from_csd_entry_via_cif_and_ase(entry)
        except Exception:
            failures += 1
            warnings.warn(
                f"Failed for entry {index}: {entry.identifier}", category=RuntimeWarning
            )
            continue
        assert check_entry(entry, optimade)
        good += 1

    assert good > failures
    assert good / (good + failures) > 0.95
