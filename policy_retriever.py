import argparse
from pathlib import Path

import faiss
from sentence_transformers import SentenceTransformer

from src.pdf_reader import extract_pdf_pages


def build_chunks(pages: list[dict]) -> list[dict]:
    """Split pages into overlapping passages while preserving citations."""
    chunk_size = 120
    overlap = 30
    chunks = []

    for page in pages:
        words = page["text"].split()

        for start in range(0, len(words), chunk_size - overlap):
            end = start + chunk_size
            chunks.append({
                "page_number": page["page_number"],
                "text": " ".join(words[start:end]),
                "start_word": start,
            })

            if end >= len(words):
                break

    return chunks


class PolicyRetriever:
    def __init__(self, pages: list[dict]):
        self.chunks = build_chunks(pages)

        self.page_words = {
            page["page_number"]: page["text"].split()
            for page in pages
        }

        if not self.chunks:
            raise ValueError("No readable policy text to index.")

        self.model = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2"
        )
        vectors = self.model.encode(
            [chunk["text"] for chunk in self.chunks],
            normalize_embeddings=True,
        ).astype("float32")

        self.index = faiss.IndexFlatIP(vectors.shape[1])
        self.index.add(vectors)

    def search(self, question: str, top_k: int = 4) -> list[dict]:
        if not question.strip() or top_k < 1:
            raise ValueError("Enter a question and request at least one result.")

        vector = self.model.encode(
            [question], normalize_embeddings=True
        ).astype("float32")

        scores, indices = self.index.search(
            vector, min(top_k, len(self.chunks))
        )

        passages = []

        for index, score in zip(indices[0], scores[0]):
            chunk = self.chunks[index]
            page_number = chunk["page_number"]
            start = chunk["start_word"]
            end = start + len(chunk["text"].split())
            words = self.page_words[page_number]

            passages.append({
                "page_number": page_number,
                "text": " ".join(words[max(0, start - 30):end + 30]),
                "similarity": float(score),
            })

        return passages


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("question")
    args = parser.parse_args()

    pages = extract_pdf_pages(args.pdf.read_bytes(), args.pdf.name)
    retriever = PolicyRetriever(pages)

    for passage in retriever.search(args.question):
        print(f"\nPage {passage['page_number']}")
        print(passage["text"])