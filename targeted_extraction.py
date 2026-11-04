import argparse
import json
from pathlib import Path

from src.clause_extractor import extract_clauses
from src.pdf_reader import extract_pdf_pages


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_path")
    parser.add_argument("clause")
    parser.add_argument("--page", type=int, required=True)
    parser.add_argument("--focus", default="")
    args = parser.parse_args()

    path = Path(args.pdf_path)
    pages = extract_pdf_pages(path.read_bytes(), path.name)

    if not 1 <= args.page <= len(pages):
        parser.error(f"--page must be between 1 and {len(pages)}")

    result = extract_clauses(
        pages[args.page - 1:args.page],
        [args.clause],
        focus=args.focus,
    )

    # Keep targeted results separate from the original batches.
    folder = Path("reports") / "targeted"
    folder.mkdir(parents=True, exist_ok=True)

    output = folder / (
        f"{path.stem}_{args.clause}_page_{args.page}.json"
    )

    output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\nSaved: {output}")