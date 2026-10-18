"""Deterministic normalization of raw extracted strings into typed values (no AI)."""
import re
from datetime import datetime

KNOWN, MISSING, CONFLICT, INVALID = "KNOWN", "MISSING", "CONFLICT", "INVALID"

FIELD_TYPES = {
    "business_name": "string",
    "requested_effective_date": "date",
    "garaging_state": "state",
    "operations_description": "string",
    "declared_vehicle_count": "count",
    "operating_radius_miles": "radius",
    "hazardous_materials": "bool",
    "loss_runs_present": "bool",
    "schedule_vehicle_count": "count",
}
# fields the LLM extracts from text; the other two are derived from the attachments
LLM_FIELDS = [f for f in FIELD_TYPES if f not in ("loss_runs_present", "schedule_vehicle_count")]
ALL_FIELDS = list(FIELD_TYPES)

PLACEHOLDERS = {"", "not provided", "n/a", "na", "not stated", "not specified", "tbd", "unknown",
                "none provided", "blank", "-", "--", "—"}

STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO",
    "connecticut": "CT", "delaware": "DE", "district of columbia": "DC", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD", "massachusetts": "MA",
    "michigan": "MI", "minnesota": "MN", "mississippi": "MS", "missouri": "MO", "montana": "MT",
    "nebraska": "NE", "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM",
    "new york": "NY", "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}
STATE_CODES = set(STATES.values())
WORD_NUMBERS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
    "sixteen seventeen eighteen nineteen twenty".split())}


def norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().casefold()


def is_placeholder(raw) -> bool:
    return raw is None or norm_ws(str(raw)).rstrip(".") in PLACEHOLDERS


def normalize(field: str, raw) -> tuple:
    """Return (value, state, note). state is KNOWN or INVALID. Never raises."""
    kind = FIELD_TYPES[field]
    s = "" if raw is None else str(raw).strip()
    if kind == "string":
        s = re.sub(r"\s+", " ", s)
        return (s, KNOWN, None) if s else (None, INVALID, "empty text")
    if kind == "date":
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            try:
                return datetime.strptime(s, "%Y-%m-%d").date().isoformat(), KNOWN, None
            except ValueError:
                return None, INVALID, f"'{s}' is not a real calendar date"
        for fmt in ("%B %d, %Y", "%b %d, %Y", "%B %d %Y"):
            try:
                return datetime.strptime(s, fmt).date().isoformat(), KNOWN, f"normalized from '{s}'"
            except ValueError:
                pass
        return None, INVALID, f"'{s}' is not in YYYY-MM-DD form (ambiguous formats are not guessed)"
    if kind == "state":
        t = norm_ws(s).rstrip(".")
        if t.upper() in STATE_CODES:
            return t.upper(), KNOWN, None
        if t in STATES:
            return STATES[t], KNOWN, f"normalized from '{s}'"
        return None, INVALID, f"'{s}' is not a recognised US state"
    if kind == "count":
        t = norm_ws(s)
        t = re.sub(r"\s*(power units?|vehicles?|units?|autos?)$", "", t)
        if t in WORD_NUMBERS:
            return WORD_NUMBERS[t], KNOWN, f"normalized from '{s}'"
        m = re.fullmatch(r"(-?\d+)(?:\.0+)?", t)
        if not m:
            return None, INVALID, f"'{s}' is not a whole number"
        n = int(m.group(1))
        return (n, KNOWN, None) if n >= 0 else (None, INVALID, "count cannot be negative")
    if kind == "radius":
        t = norm_ws(s)
        t = re.sub(r"\s*(miles?|mi\.?)$", "", t).replace(",", "")
        if re.fullmatch(r"-?\d+(\.\d+)?", t):
            v = float(t)
            return (v, KNOWN, None) if v >= 0 else (None, INVALID, "radius cannot be negative")
        return None, INVALID, f"'{s}' is not numeric miles"
    if kind == "bool":
        t = norm_ws(s).rstrip(".")
        if t in ("yes", "y", "true"):
            return True, KNOWN, None
        if t in ("no", "n", "false"):
            return False, KNOWN, None
        return None, INVALID, f"'{s}' is not an explicit Yes/No"
    raise ValueError(kind)


def compare_key(field: str, value):
    """Key used to decide whether two normalized values 'agree'."""
    if FIELD_TYPES[field] == "string":
        return norm_ws(str(value)).rstrip(".,;:")
    return value
