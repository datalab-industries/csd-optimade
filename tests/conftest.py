import pytest

from .utils import is_csd_available


@pytest.fixture(scope="session")
def csd_available():
    """Check if the CSD is available."""
    return is_csd_available()
