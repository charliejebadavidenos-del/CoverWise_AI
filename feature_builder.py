import argparse
import json
from pathlib import Path


def build_features(policy: dict) -> dict:
    """Build evidence features without inferring missing policy values."""
    features = {}

    for clause in policy["clauses"]:
        findings = clause.get("findings", [])

        evidence_present = any(
            isinstance(finding.get("evidence"), str)
            and bool(finding["evidence"].strip())
            for finding in findings
        )

        features[clause["name"]] = {
            "evidence_present": evidence_present,
            "source_pages": sorted({
                finding["page_number"]
                for finding in findings
                if type(finding.get("page_number")) is int
            }),
            # A matching quote does not validate its interpretation.
            "review_required": (
                clause.get("review_required", True)
                or any(
                    finding.get("review_required", True)
                    for finding in findings
                )
            ),
            # Numeric values require a separate validated extraction.
            "value": None,
            "unit": None,
            "conditions": None,
            "findings": findings,
        }

    evidenced = sum(
        feature["evidence_present"]
        for feature in features.values()
    )
    total = len(features)

    return {
        "document_name": policy["document_name"],
        "features": features,
        "evidenced_categories": evidenced,
        "total_categories": total,
        "evidence_availability_percent": (
            round(100 * evidenced / total, 1) if total else 0
        ),
        "risk_score": None,
        "scoring_status": "Withheld pending validated restriction values",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("policy_json")
    args = parser.parse_args()

    source = Path(args.policy_json)
    policy = json.loads(source.read_text(encoding="utf-8"))
    result = build_features(policy)

    output = source.with_name(f"{source.stem}_features.json")
    output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Document: {result['document_name']}")
    print(
        "Categories with evidence: "
        f"{result['evidenced_categories']}/{result['total_categories']}"
    )
    print(
        "Evidence availability: "
        f"{result['evidence_availability_percent']}%"
    )
    print(f"Risk score: {result['scoring_status']}")
    print(f"Saved: {output}")