import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SAMPLES = ROOT / "samples"

LABELS = {
    "business name": "business_name", "requested effective date": "requested_effective_date",
    "garaging state": "garaging_state", "operations": "operations_description",
    "operations description": "operations_description", "declared vehicle count": "declared_vehicle_count",
    "operating radius miles": "operating_radius_miles", "hazardous materials": "hazardous_materials",
}


class StubModel:
    """TEST DOUBLE ONLY (never used by the app): stands in for the LLM so rule/pipeline tests need no network.
    It reads 'Label: value' / 'Label   value' lines out of the <source> block and replies in the model's JSON format."""

    def __init__(self, fail=False, hallucinate=None):
        self.fail, self.hallucinate, self.calls = fail, hallucinate or {}, 0

    def complete(self, system, user, max_tokens=1500):
        from app.llm import LLMError
        self.calls += 1
        if self.fail:
            raise LLMError("simulated outage")
        if "<facts>" in user:  # narrative call
            return json.dumps({"summary": "stub summary", "email_subject": "s", "email_body": "b"})
        out = {}
        for line in user.splitlines():
            low = line.strip().lower()
            for key in sorted(LABELS, key=len, reverse=True):      # longest label first
                if low.startswith(key) and (len(low) == len(key) or not low[len(key)].isalpha()):
                    val = line.strip()[len(key):].lstrip(" :\t").strip()
                    out.setdefault(LABELS[key], {"raw_value": None if val.lower() == "not provided" else val.rstrip("."),
                                                 "excerpt": line.strip()})
                    break
        out.update(self.hallucinate)
        return json.dumps({"fields": out})


def load_packet(name):
    folder = SAMPLES / name
    return [(p.name, p.read_bytes()) for p in sorted(folder.iterdir())]
