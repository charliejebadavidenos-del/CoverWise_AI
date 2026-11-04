import argparse
import json
from pathlib import Path

from src.clause_extractor import CLAUSE_NAMES


def consolidate_batches(folder: Path, document_name: str) -> dict:
    stem = Path(document_name).stem
    files = list(folder.glob(f"{stem}_pages_*.json"))

    if not files:
        raise ValueError(f"No saved batches found for {document_name}")

    grouped = {name: [] for name in CLAUSE_NAMES}
    analyzed_pages = set()
    seen = set()

    batches = [
        json.loads(file.read_text(encoding="utf-8"))
        for file in files
    ]
    batches.sort(key=lambda batch: min(batch["analyzed_pages"]))

    for batch in batches:
        if batch["document_name"] != document_name:
            raise ValueError("A batch belongs to a different document.")

        analyzed_pages.update(batch["analyzed_pages"])

        for clause in batch["clauses"]:
            name = clause["name"]

            if name not in grouped or clause["status"] != "found":
                continue

            key = (
                name,
                clause["page_number"],
                " ".join(clause["evidence"].split()),
            )

            if key not in seen:
                seen.add(key)
                grouped[name].append({
                    "page_number": clause["page_number"],
                    "evidence": clause["evidence"],
                    "explanation": clause["explanation"],
                })

    clauses = []

    for name, findings in grouped.items():
        clauses.append({
            "name": name,
            "status": "found" if findings else "unknown",
            "findings": findings,
            "review_required": True,
        })

    return {
        "document_name": document_name,
        "analyzed_pages": sorted(analyzed_pages),
        "batch_count": len(batches),
        "validation_scope": (
            "Source quote matching only. Interpretation, completeness "
            "and applicability still require review."
        ),
        "clauses": clauses,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("document_name")
    args = parser.parse_args()

    folder = Path("reports") / "extraction"
    result = consolidate_batches(folder, args.document_name)

    output = Path("reports") / (
        f"{Path(args.document_name).stem}_consolidated.json"
    )
    output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Batches combined: {result['batch_count']}")
    print(f"Distinct pages processed: {len(result['analyzed_pages'])}")

    for clause in result["clauses"]:
        pages = sorted({
            finding["page_number"]
            for finding in clause["findings"]
        })
        print(
            f"{clause['name']}: {clause['status']} "
            f"| evidence pages: {pages}"
        )

    print(f"\nSaved: {output}")