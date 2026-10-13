from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_bytes():
    def _load(*parts: str) -> bytes:
        return FIXTURES.joinpath(*parts).read_bytes()

    return _load
