import pytest


@pytest.fixture(scope="module")
def vcr_cassette_dir(request):
    return "fixtures/atlas/cassettes"


@pytest.fixture(scope="module")
def vcr_config():
    return {"record_mode": "none"}
