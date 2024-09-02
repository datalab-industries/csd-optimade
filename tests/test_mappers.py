import warnings

import pytest
import tqdm


def test_via_cif_and_ase(csd_available, same_random_csd_entries):
    if not csd_available:
        pytest.skip("CSD not available")

    from csd_optimade.mappers import from_csd_entry_via_cif_and_ase

    optimades = []
    failures = 0
    good = 0
    for index, entry in tqdm.tqdm(same_random_csd_entries):
        try:
            optimade = from_csd_entry_via_cif_and_ase(entry)
            assert optimade
            optimades += [optimade]
            good += 1
        except Exception:
            failures += 1
            warnings.warn(
                f"Failed for entry {index}: {entry.identifier}", category=RuntimeWarning
            )

    assert good > failures
    assert good / (good + failures) > 0.95
