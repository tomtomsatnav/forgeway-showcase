from collections.abc import Sequence

from forgeway_kit import Embedder, cosine_similarity


def top_k(embedder: Embedder, query: str, documents: Sequence[str], k: int = 3) -> list[str]:
    if not documents:
        return []
    query_vector, *document_vectors = embedder.embed([query, *documents])
    scored = [
        (cosine_similarity(query_vector, vector), document)
        for vector, document in zip(document_vectors, documents, strict=True)
    ]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [document for _, document in scored]
