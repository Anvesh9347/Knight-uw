"""Rule logic only - no model, no files. Covers: missing info, source conflict, unequal counts, 150-mile threshold."""
import pytest

from app import rules


def F(**over):
    base = {
        "business_name": ("Acme", "KNOWN"), "requested_effective_date": ("2026-11-01", "KNOWN"),
        "garaging_state": ("CA", "KNOWN"), "operations_description": ("x", "KNOWN"),
        "declared_vehicle_count": (3, "KNOWN"), "schedule_vehicle_count": (3, "KNOWN"),
        "operating_radius_miles": (100.0, "KNOWN"), "hazardous_materials": (False, "KNOWN"),
        "loss_runs_present": (True, "KNOWN"),
    }
    base.update(over)
    return {k: {"value": v, "state": s, "origin": "extracted"} for k, (v, s) in base.items()}


def status(fields):
    return {r["id"]: r["status"] for r in rules.evaluate(fields)["rules"]}


def test_all_pass_is_ready_for_review():
    out = rules.evaluate(F())
    assert [r["status"] for r in out["rules"]] == ["PASS"] * 5
    assert out["overall_status"] == "READY_FOR_REVIEW"
    assert "all five preliminary checks passed" in out["customer_message"]
    assert "not a coverage, pricing or binding decision" in out["customer_message"]


def test_customer_message_lists_non_pass_rules_without_approval_language():
    out = rules.evaluate(F(
        requested_effective_date=(None, "MISSING"),
        operating_radius_miles=(180.0, "KNOWN"),
    ))
    assert out["overall_status"] == "NEEDS_REVIEW"
    assert "R1 · Required identity and effective date" in out["customer_message"]
    assert "requested effective date" in out["customer_message"]
    assert "R3 · Operating radius" in out["customer_message"]
    assert "R2 · Vehicle count reconciliation" not in out["customer_message"]
    assert "not a coverage, pricing or binding decision" in out["customer_message"]


# ---- missing information ----
def test_r1_missing_date_flags():
    s = status(F(requested_effective_date=(None, "MISSING")))
    assert s["R1"] == "FLAG"


def test_r1_absence_beats_conflict():
    s = status(F(requested_effective_date=(None, "MISSING"), business_name=(None, "CONFLICT")))
    assert s["R1"] == "FLAG"


def test_r1_conflict_or_invalid_alone_is_unknown():
    assert status(F(business_name=(None, "CONFLICT")))["R1"] == "UNKNOWN"
    assert status(F(requested_effective_date=(None, "INVALID")))["R1"] == "UNKNOWN"


def test_missing_hazmat_and_radius_are_unknown_not_pass():
    s = status(F(hazardous_materials=(None, "MISSING"), operating_radius_miles=(None, "MISSING")))
    assert s["R3"] == "UNKNOWN" and s["R4"] == "UNKNOWN"
    assert rules.evaluate(F(hazardous_materials=(None, "MISSING")))["overall_status"] == "NEEDS_REVIEW"


def test_model_failure_is_unknown_not_flag():
    f = F(business_name=(None, "MISSING"))
    f["business_name"]["extraction_issue"] = "model extraction failed"
    assert status(f)["R1"] == "UNKNOWN"


def test_missing_loss_runs_flags_unreadable_is_unknown():
    assert status(F(loss_runs_present=(False, "KNOWN")))["R5"] == "FLAG"
    assert status(F(loss_runs_present=(None, "INVALID")))["R5"] == "UNKNOWN"


# ---- source conflict ----
def test_conflict_is_unknown_before_threshold_or_yesno():
    s = status(F(operating_radius_miles=(None, "CONFLICT"), hazardous_materials=(None, "CONFLICT")))
    assert s["R3"] == "UNKNOWN" and s["R4"] == "UNKNOWN"


# ---- vehicle counts ----
def test_r2_unequal_counts_flag():
    r = rules.r2(F(declared_vehicle_count=(4, "KNOWN"), schedule_vehicle_count=(3, "KNOWN")))
    assert r["status"] == "FLAG" and "4" in r["reason"] and "3" in r["reason"]


def test_r2_zero_vehicles_is_valid():
    assert status(F(declared_vehicle_count=(0, "KNOWN"), schedule_vehicle_count=(0, "KNOWN")))["R2"] == "PASS"


@pytest.mark.parametrize("state", ["MISSING", "INVALID", "CONFLICT"])
def test_r2_unresolved_count_is_unknown(state):
    assert status(F(declared_vehicle_count=(None, state)))["R2"] == "UNKNOWN"
    assert status(F(schedule_vehicle_count=(None, state)))["R2"] == "UNKNOWN"


# ---- 150-mile threshold ----
@pytest.mark.parametrize("miles,expected", [(0.0, "PASS"), (149.9, "PASS"), (150, "PASS"), (150.0, "PASS"),
                                            (150.1, "FLAG"), (151, "FLAG"), (180.0, "FLAG")])
def test_r3_threshold(miles, expected):
    assert status(F(operating_radius_miles=(miles, "KNOWN")))["R3"] == expected


def test_r3_negative_or_nonnumeric_is_unknown():
    assert status(F(operating_radius_miles=(None, "INVALID")))["R3"] == "UNKNOWN"


def test_r4_yes_flags_no_passes():
    assert status(F(hazardous_materials=(True, "KNOWN")))["R4"] == "FLAG"
    assert status(F(hazardous_materials=(False, "KNOWN")))["R4"] == "PASS"
