from search import top_k

from forgeway_kit import HashingEmbedder, cosine_similarity

DOCS = [
    "Resetting your password requires access to your registered email address.",
    "Our refund policy allows returns within thirty days of purchase.",
    "The office kitchen is cleaned every Friday afternoon.",
    "Shipping to Europe usually takes five to seven working days.",
    "Two-factor authentication adds a second step when you sign in.",
]

QUESTIONS = [
    ("How do I reset my password?", 0),
    ("What is the refund policy for returns?", 1),
    ("When is the kitchen cleaned?", 2),
    ("How long does shipping to Europe take?", 3),
]


def plain(result):
    """Check a returned list of documents and turn it into plain built-ins."""
    assert type(result) is list, f"top_k should return a list, got {type(result).__name__}."
    for item in result:
        assert type(item) is str, f"Each result should be a plain str, got {type(item).__name__}."
    return list(result)


def test_best_match_is_first():
    embedder = HashingEmbedder()
    for question, index in QUESTIONS:
        result = plain(top_k(embedder, question, DOCS, k=1))
        assert result == [DOCS[index]], (
            f"For {question!r} the best match is {DOCS[index]!r}, but top_k returned {result!r}. "
            "Rank by cosine similarity, highest first."
        )
    shuffled = DOCS[::-1]
    result = plain(top_k(embedder, QUESTIONS[0][0], shuffled, k=1))
    assert result == [DOCS[0]], "The order of the input documents should not change the winner."


def test_ranking_and_k():
    embedder = HashingEmbedder()
    query = "What is the refund policy for returns?"
    query_vector = embedder.embed([query])[0]
    scores = {d: cosine_similarity(query_vector, embedder.embed([d])[0]) for d in DOCS}
    expected = sorted(DOCS, key=lambda d: scores[d], reverse=True)
    for k in (1, 2, 3, 5):
        result = plain(top_k(embedder, query, DOCS, k=k))
        assert len(result) == k, f"With k={k} top_k should return {k} documents, got {len(result)}."
        assert result == expected[:k], (
            f"With k={k} expected the documents ranked from most to least similar: "
            f"{[e[:25] for e in expected[:k]]}, but got {[r[:25] for r in result]}."
        )
    assert len(plain(top_k(embedder, query, DOCS))) == 3, "k should default to 3."


def test_edge_cases():
    embedder = HashingEmbedder()
    result = plain(top_k(embedder, "refund returns", DOCS[:2], k=10))
    assert len(result) == 2 and set(result) == set(DOCS[:2]), (
        f"With 2 documents and k=10 all 2 should be returned, got {len(result)}."
    )
    assert result[0] == DOCS[1], "Even when k exceeds the collection, the result must be ranked."
    assert plain(top_k(embedder, "anything", [], k=3)) == [], (
        "No documents should give an empty list."
    )
    docs = list(DOCS)
    top_k(embedder, "password", docs, k=2)
    assert docs == DOCS, "top_k must not reorder or modify the list it was given."
