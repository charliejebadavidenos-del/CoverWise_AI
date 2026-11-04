import json
from pathlib import Path

from src.pdf_reader import extract_pdf_pages


def normalize(text):
    return " ".join(text.split())


if __name__ == "__main__":
    pdf_path = Path("data/sample_policies/SBI_Insurance.pdf")
    base_path = Path("reports/SBI_Insurance_consolidated.json")

    policy = json.loads(base_path.read_text(encoding="utf-8"))
    pages = extract_pdf_pages(pdf_path.read_bytes(), pdf_path.name)
    source_pages = {p["page_number"]: p["text"] for p in pages}

    clauses_by_name = {
        clause["name"]: clause for clause in policy["clauses"]
    }

    # Remove reviewed classification errors from this SBI sample.
    # Correct replacements are loaded from targeted files below.
    for name in ("disease_sub_limits", "child_coverage"):
        clause = clauses_by_name.get(name)
        if clause is not None:
            clause["findings"] = []
            clause["status"] = "unknown"
            clause["review_required"] = True



    added = 0

    for file in sorted(Path("reports/targeted").glob("*.json")):
        record = json.loads(file.read_text(encoding="utf-8"))

        if record.get("document_name") != pdf_path.name:
            continue

        # Support both LLM results and direct source-section records.
        candidates = (
            record["clauses"]
            if "clauses" in record
            else [record]
        )

        for item in candidates:
            if (
                item.get("status") != "found"
                and item.get("extraction_method") != "source_section"
            ):
                continue

            name = item.get("name")
            page = item.get("page_number")
            evidence = item.get("evidence")

            if (
                not isinstance(name, str)
                or type(page) is not int
                or not isinstance(evidence, str)
                or not evidence.strip()
                or normalize(evidence)
                not in normalize(source_pages.get(page, ""))
            ):
                print(f"Skipped unverified evidence: {file.name}")
                continue

            clause = clauses_by_name.setdefault(name, {
                "name": name,
                "status": "unknown",
                "findings": [],
                "review_required": True,
            })

            duplicate = any(
                finding["page_number"] == page
                and normalize(finding["evidence"]) == normalize(evidence)
                for finding in clause["findings"]
            )

            if duplicate:
                continue

            clause["findings"].append({
                "page_number": page,
                "evidence": evidence,
                "explanation": item.get("explanation"),
                "extraction_method": item.get(
                    "extraction_method", "llm_targeted"
                ),
                "review_required": True,
            })
            clause["status"] = "found"
            clause["review_required"] = True
            added += 1

    policy["clauses"] = list(clauses_by_name.values())

    output = Path("reports/SBI_Insurance_enriched.json")
    output.write_text(
        json.dumps(policy, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Targeted findings added: {added}")
    print(f"Saved: {output}")