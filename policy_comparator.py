import argparse
import json
from pathlib import Path


def compare_policies(current: dict, proposed: dict) -> dict:
    scenario = current.get("scenario")
    if not scenario or scenario != proposed.get("scenario"):
        raise ValueError("Both reports must use the same reviewed scenario.")

    current_values = current.get("reviewed_values", {})
    proposed_values = proposed.get("reviewed_values", {})
    rows = []

    for rule in sorted(current_values.keys() | proposed_values.keys()):
        left = current_values.get(rule)
        right = proposed_values.get(rule)

        if left is None or right is None:
            status = "Review needed"
        else:
            left_terms = {k: v for k, v in left.items() if k != "source_pages"}
            right_terms = {k: v for k, v in right.items() if k != "source_pages"}
            status = (
                "Same recorded terms"
                if left_terms == right_terms
                else "Recorded terms differ"
            )

        rows.append({
            "rule": rule,
            "current": left,
            "proposed": right,
            "status": status,
        })

    return {
        "scenario": scenario,
        "current_document": current["document_name"],
        "proposed_document": proposed["document_name"],
        "current_restriction_count": current.get("score"),
        "proposed_restriction_count": proposed.get("score"),
        "comparison": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("current_score_json", type=Path)
    parser.add_argument("proposed_score_json", type=Path)
    args = parser.parse_args()

    current = json.loads(args.current_score_json.read_text(encoding="utf-8"))
    proposed = json.loads(args.proposed_score_json.read_text(encoding="utf-8"))
    result = compare_policies(current, proposed)

    output = args.current_score_json.with_name("policy_comparison.json")
    output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    for row in result["comparison"]:
        print(f"{row['rule']} | {row['status']}")
    print(f"Saved: {output}")