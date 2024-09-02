import pytest


@pytest.fixture(scope="session")
def csd_available():
    """Check if the CSD is available."""

    from ccdc import io

    try:
        io.EntryReader("CSD")
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def same_random_csd_entries():
    """Pick some random entries from the CSD, with a fixed seed."""

    import random

    from ccdc.io import EntryReader

    random.seed(0)
    entry_indices = []
    entries = []
    num_entries: int = 100
    max_n: int = int(1.29e6)

    with EntryReader("CSD") as reader:
        while len(entry_indices) < num_entries:
            i = random.randint(0, max_n)
            if i not in entry_indices:
                try:
                    entry = reader[i]
                    if entry:
                        entries.append((i, entry))
                        entry_indices.append(i)
                except Exception:
                    continue
        yield entries
