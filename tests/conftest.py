import warnings

import pytest

from .utils import MockCSDEntry


@pytest.fixture(scope="session")
def csd_available():
    """Check if the CSD is available."""

    try:
        from ccdc import io

        io.EntryReader("CSD")
        return True
    except (ImportError, Exception):
        return False


@pytest.fixture(scope="session")
def same_random_csd_entries(csd_available):
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
            yield entries
