import argparse
import json
from pathlib import Path


def score_restrictions(reviewed: dict[str, bool | None]) -> dict:
    """Count applicable restrictions after all four rules are reviewed."""
    rules = (
        "copayment",
        "room_or_icu_cap",
        "initial_waiting_period",
        "pre_existing_disease_waiting_period",
    )
    unresolved = [
        rule for rule in rules if type(reviewed.get(rule)) is not bool
    ]

    return {
        "score": None if unresolved else sum(reviewed[rule] for rule in rules),
        "maximum": len(rules),
        "applicable": [rule for rule in rules if reviewed.get(rule) is True],
        "unresolved": unresolved,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("reviewed_json")
    args = parser.parse_args()

    path = Path(args.reviewed_json)
    reviewed = json.loads(path.read_text(encoding="utf-8"))

    #print(json.dumps(score_restrictions(reviewed), indent=2))
    result = {
        "document_name": reviewed.get("document_name"),
        "scenario": reviewed.get("scenario"),
        "reviewed_values": reviewed.get("reviewed_values", {}),
        **score_restrictions(reviewed),
    }

    output = path.with_name(f"{path.stem}_score.json")
    output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Restriction count: {result['score']}/{result['maximum']}")
    print(f"Saved: {output}")    