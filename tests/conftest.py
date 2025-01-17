import pytest


@pytest.fixture(scope="session")
def csd_available():
    """Check if the CSD is available."""
    try:
        from ccdc import io

        io.EntryReader("CSD")
        return True
    except (ImportError, Exception):
        return False
