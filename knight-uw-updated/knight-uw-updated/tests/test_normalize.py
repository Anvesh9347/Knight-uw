import pytest

from app.normalize import INVALID, KNOWN, normalize


@pytest.mark.parametrize("field,raw,value", [
    ("garaging_state", "California", "CA"), ("garaging_state", "ca", "CA"),
    ("requested_effective_date", "2026-11-01", "2026-11-01"),
    ("operating_radius_miles", "150.0", 150.0), ("operating_radius_miles", "150 miles", 150.0),
    ("declared_vehicle_count", "3", 3), ("declared_vehicle_count", "0", 0),
    ("hazardous_materials", "No", False), ("hazardous_materials", "Yes", True),
])
def test_known(field, raw, value):
    v, state, _ = normalize(field, raw)
    assert state == KNOWN and v == value


@pytest.mark.parametrize("field,raw", [
    ("requested_effective_date", "2026-02-30"), ("requested_effective_date", "11/01/2026"),
    ("operating_radius_miles", "-5"), ("operating_radius_miles", "about 150"),
    ("declared_vehicle_count", "-1"), ("declared_vehicle_count", "2.5"),
    ("hazardous_materials", "sometimes"), ("garaging_state", "Narnia"),
])
def test_invalid(field, raw):
    assert normalize(field, raw)[1] == INVALID
