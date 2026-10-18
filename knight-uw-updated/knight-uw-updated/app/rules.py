"""R1-R5 in ordinary, deterministic code. No AI and no I/O.

Input: dict field_name -> {"value", "state", "extraction_issue"(optional), ...} (the *effective* field values).
Output: list of rule results + overall status.
"""
from decimal import Decimal

from .normalize import KNOWN, MISSING

RADIUS_THRESHOLD_MILES = Decimal("150")


def _kind(f: dict) -> str:
    """ok | absent | unresolved"""
    if f["state"] == KNOWN:
        return "ok"
    if f["state"] == MISSING and not f.get("extraction_issue"):
        return "absent"
    return "unresolved"  # CONFLICT, INVALID, or an extraction failure (not the same as absent)


def _describe(f: dict) -> str:
    if f["state"] == KNOWN:
        return repr(f["value"])
    if f.get("extraction_issue"):
        return f"unresolved ({f['extraction_issue']})"
    return f["state"]


def _inputs(fields: dict, names: list) -> dict:
    return {n: {"value": fields[n]["value"], "state": fields[n]["state"],
                "origin": fields[n].get("origin", "extracted")} for n in names}


def _result(rid, name, status, reason, fields, names):
    return {"id": rid, "name": name, "status": status, "reason": reason, "inputs": _inputs(fields, names)}


def r1(fields):
    names = ["business_name", "requested_effective_date"]
    kinds = {n: _kind(fields[n]) for n in names}
    absent = [n for n in names if kinds[n] == "absent"]
    if absent:  # absence beats every other unresolved state
        return _result("R1", "Required identity and effective date", "FLAG",
                       f"Required field(s) absent: {', '.join(absent)}.", fields, names)
    bad = [n for n in names if kinds[n] == "unresolved"]
    if bad:
        return _result("R1", "Required identity and effective date", "UNKNOWN",
                       "Present but unresolved: " + "; ".join(f"{n} is {_describe(fields[n])}" for n in bad) + ".",
                       fields, names)
    return _result("R1", "Required identity and effective date", "PASS",
                   "Business name and requested effective date are present, valid and non-conflicting.", fields, names)


def r2(fields):
    names = ["declared_vehicle_count", "schedule_vehicle_count"]
    d, s = fields[names[0]], fields[names[1]]
    if _kind(d) != "ok" or _kind(s) != "ok":
        why = [f"{n} is {_describe(fields[n])}" for n in names if _kind(fields[n]) != "ok"]
        return _result("R2", "Vehicle count reconciliation", "UNKNOWN",
                       "Cannot compare: " + "; ".join(why) + ".", fields, names)
    if d["value"] == s["value"]:
        return _result("R2", "Vehicle count reconciliation", "PASS",
                       f"Declared count ({d['value']}) equals schedule count ({s['value']}).", fields, names)
    return _result("R2", "Vehicle count reconciliation", "FLAG",
                   f"Declared count ({d['value']}) differs from schedule count ({s['value']}).", fields, names)


def r3(fields):
    names = ["operating_radius_miles"]
    f = fields[names[0]]
    if _kind(f) != "ok":
        return _result("R3", "Operating radius", "UNKNOWN",
                       f"Radius is {_describe(f)}; cannot test the 150-mile threshold.", fields, names)
    miles = Decimal(str(f["value"]))
    if miles > RADIUS_THRESHOLD_MILES:
        return _result("R3", "Operating radius", "FLAG",
                       f"Radius {f['value']} miles is greater than 150.", fields, names)
    return _result("R3", "Operating radius", "PASS",
                   f"Radius {f['value']} miles is 150 or less.", fields, names)


def r4(fields):
    names = ["hazardous_materials"]
    f = fields[names[0]]
    if _kind(f) != "ok":
        return _result("R4", "Hazardous materials", "UNKNOWN",
                       f"Hazardous materials answer is {_describe(f)}; absence is not 'No'.", fields, names)
    if f["value"] is True:
        return _result("R4", "Hazardous materials", "FLAG", "Hazardous materials answered Yes.", fields, names)
    return _result("R4", "Hazardous materials", "PASS", "Hazardous materials answered No.", fields, names)


def r5(fields):
    names = ["loss_runs_present"]
    f = fields[names[0]]
    if _kind(f) != "ok":
        return _result("R5", "Loss runs attachment", "UNKNOWN",
                       f"Loss runs attachment is {_describe(f)}.", fields, names)
    if f["value"] is True:
        return _result("R5", "Loss runs attachment", "PASS",
                       "A readable loss runs / loss history report is attached.", fields, names)
    return _result("R5", "Loss runs attachment", "FLAG",
                   "No loss runs / loss history document is attached (a promise in the email does not count).",
                   fields, names)


def evaluate(fields: dict) -> dict:
    results = [r1(fields), r2(fields), r3(fields), r4(fields), r5(fields)]
    overall = "READY_FOR_REVIEW" if all(r["status"] == "PASS" for r in results) else "NEEDS_REVIEW"
    if overall == "READY_FOR_REVIEW":
        customer_message = (
            "Your submission is READY_FOR_REVIEW: all five preliminary checks passed. "
            "This status is for human review only; it is not a coverage, pricing or binding decision."
        )
    else:
        outstanding = "; ".join(
            f"{r['id']} · {r['name']}: {r['reason'].replace('_', ' ')}"
            for r in results if r["status"] != "PASS"
        )
        customer_message = (
            f"Your submission is NEEDS_REVIEW. The following checks need attention: {outstanding} "
            "This status is for human review only; it is not a coverage, pricing or binding decision."
        )
    return {"rules": results, "overall_status": overall,
            "disclaimer": "Readiness for human review only; not a coverage, pricing or binding decision.",
            "customer_message": customer_message}
