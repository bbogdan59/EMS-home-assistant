import pytest

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def mapping():
    return {
        "entity_id": "sensor.house_power",
        "kind": "power",
        "unit": "W",
        "device_class": "power",
        "state_class": "measurement",
        "max_age_seconds": 180,
        "source_validated": True,
        "quality": "estimated",
        "registry_id": None,
    }


@pytest.fixture
def entry_data(mapping):
    return {
        "url": "https://ems.example",
        "token": "x" * 43,
        "station_id": "station-one",
        "station_name": "Home",
        "instance_id": "instance-one",
        "mapping_version": 2,
        "mappings": [mapping],
        "occupancy_consent": False,
        "insights_consent": False,
    }
