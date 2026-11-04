from pathlib import Path

import pymupdf

import re

def clean_page_text(text: str) -> str:
    """Remove the noisy insurer heading and normalize whitespace."""
    cleaned_lines = []

    for line in text.splitlines():
        line = line.strip()

        # Remove this document's repeated insurer heading.
        if (
            line.startswith("SBISBISBISBI")
            and "InsuranceInsurance" in line
        ):
            continue

        line = re.sub(r"[ \t]+", " ", line)
        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()

def extract_pdf_pages(pdf_bytes: bytes, document_name: str) -> list[dict]:
    """Extract text while preserving document name and PDF page numbers."""
    pages = []

    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as document:
        if document.needs_pass:
            raise ValueError("The PDF is password-protected. Upload an unlocked copy.")

        for page_number, page in enumerate(document, start=1):
            text = clean_page_text(page.get_text("text", sort=True))

            pages.append({
                "document_name": document_name,
                "page_number": page_number,
                "text": text,
            })

    if not any(page["text"] for page in pages):
        raise ValueError(
            "No readable text found. This PDF may need OCR."
        )

    return pages


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Check PDF text extraction.")
    parser.add_argument("pdf_path", help="Path to a sample policy PDF")
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)
    pages = extract_pdf_pages(pdf_path.read_bytes(), pdf_path.name)

    print(f"Total pages: {len(pages)}")

    empty_pages = [
        page["page_number"] for page in pages if not page["text"]
    ]
    if empty_pages:
        print(f"Pages without extracted text (may need OCR): {empty_pages}")

    for page in pages[:2]:
        print(f"\n--- Page {page['page_number']} ---")
        print(page["text"][:1000])