"""Run selected sample packets through the configured LLM and print rule results."""
import re
import sys
from pathlib import Path

from app import llm, service


ROOT = Path(__file__).resolve().parent
VALID_PACKETS = {"A": "SUB-A", "B": "SUB-B", "C": "SUB-C"}


def parse_packets(raw: str) -> list[str]:
    normalized = re.sub(r"\bSUB\s*-?\s*([ABC])\b", r"SUB-\1", raw, flags=re.IGNORECASE)
    tokens = re.split(r"[\s,;]+|\band\b", normalized, flags=re.IGNORECASE)
    packets = []
    for token in tokens:
        if not token:
            continue
        candidate = token.upper().replace("-", "")
        letter = candidate.removeprefix("SUB")
        if letter not in VALID_PACKETS:
            raise ValueError(f"Unknown packet '{token}'. Choose SUB-A, SUB-B, or SUB-C.")
        packet = VALID_PACKETS[letter]
        if packet not in packets:
            packets.append(packet)
    if not packets:
        raise ValueError("Enter at least one packet: SUB-A, SUB-B, or SUB-C.")
    return packets


def main() -> int:
    print("Available packets: SUB-A, SUB-B, SUB-C")
    try:
        packets = parse_packets(input("Enter packet IDs: "))
    except (EOFError, ValueError) as error:
        print(error)
        return 1

    print(f"Provider/model: {llm.provider_info()['provider']} / {llm.provider_info()['model']}")
    for packet in packets:
        folder = ROOT / "samples" / packet
        files = [(path.name, path.read_bytes()) for path in sorted(folder.iterdir()) if path.is_file()]
        submission = service.process(files)
        result = service.view(submission)
        print(f"\n{packet}: {result['overall_status']}")
        for rule in result["rules"]:
            print(f"  {rule['id']} {rule['status']}: {rule['reason']}")
        issues = [field["name"] for field in result["fields"]
                  if field["extracted"].get("extraction_issue")]
        if issues:
            print(f"  Extraction issues: {', '.join(issues)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())