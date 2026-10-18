"""Submission lifecycle: process -> effective values (extracted + human overrides) -> rules -> view."""
import copy
import uuid
from datetime import datetime, timezone

from . import extract, ingest, llm as llm_mod, rules
from .normalize import ALL_FIELDS, KNOWN, normalize

STORE: dict = {}      # in-memory only; one entry per processed packet, never merged across packets
MAX_STORED = 20


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def process(files: list, email_text: str = "", llm=llm_mod) -> dict:
    docs = ingest.ingest(files, email_text)
    extracted = extract.extract_all(docs, llm)
    sub = {"id": uuid.uuid4().hex[:10], "created_at": _now(), "docs": docs,
           "inventory": [d.inventory() for d in docs], "extracted": extracted, "overrides": {},
           "narrative": None}
    STORE[sub["id"]] = sub
    while len(STORE) > MAX_STORED:
        STORE.pop(next(iter(STORE)))
    return sub


def effective_fields(sub: dict) -> dict:
    """Values the rules use: the human override if present, else the extracted value."""
    out = {}
    for name in ALL_FIELDS:
        ex, ov = sub["extracted"][name], sub["overrides"].get(name)
        if ov:
            out[name] = {"value": ov["value"], "state": KNOWN, "origin": "human_override", "extraction_issue": None}
        else:
            out[name] = {"value": ex["value"], "state": ex["state"], "origin": "extracted",
                         "extraction_issue": ex.get("extraction_issue")}
    return out


def set_override(sub: dict, field: str, raw_value, reason: str = "") -> None:
    if field not in ALL_FIELDS:
        raise ValueError(f"Unknown field '{field}'.")
    value, state, note = normalize(field, raw_value)
    if state != KNOWN:
        raise ValueError(f"Correction rejected: {note}.")
    orig = sub["extracted"][field]
    sub["overrides"][field] = {
        "value": value, "reason": reason.strip(), "at": _now(),
        "original": {"value": orig["value"], "state": orig["state"],
                     "evidence": copy.deepcopy(orig["evidence"]), "notes": orig["notes"]},
    }
    if sub.get("narrative"):
        sub["narrative"]["stale"] = True


def clear_override(sub: dict, field: str) -> None:
    sub["overrides"].pop(field, None)
    if sub.get("narrative"):
        sub["narrative"]["stale"] = True


def view(sub: dict) -> dict:
    eff = effective_fields(sub)
    result = rules.evaluate(eff)
    fields = []
    for name in ALL_FIELDS:
        fields.append({"name": name, "extracted": sub["extracted"][name], "override": sub["overrides"].get(name),
                       "effective": eff[name]})
    return {"id": sub["id"], "created_at": sub["created_at"], "inventory": sub["inventory"], "fields": fields,
            "rules": result["rules"], "overall_status": result["overall_status"], "disclaimer": result["disclaimer"],
            "customer_message": result["customer_message"], "narrative": sub.get("narrative"),
            "llm": llm_mod.provider_info()}
