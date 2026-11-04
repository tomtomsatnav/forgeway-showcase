"""Embedding interface plus a deterministic, dependency-free implementation."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from typing import Protocol

Vector = list[float]


class Embedder(Protocol):
    """Turns texts into fixed-length vectors."""

    @property
    def dimensions(self) -> int: ...

    def embed(self, texts: Sequence[str]) -> list[Vector]: ...


class HashingEmbedder:
    """Feature-hashing embedder over lower-cased word unigrams and character trigrams.

    Deterministic across machines and Python versions (it uses BLAKE2, not `hash()`), and
    L2-normalised so dot product equals cosine similarity. It captures lexical overlap, not
    meaning: "car" and "automobile" are unrelated to it. Exercises that need real semantics use
    precomputed model vectors instead.
    """

    def __init__(self, dimensions: int = 256) -> None:
        if dimensions < 8:
            raise ValueError("dimensions must be at least 8")
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, texts: Sequence[str]) -> list[Vector]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> Vector:
        vector = [0.0] * self._dimensions
        for feature, weight in _features(text):
            digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "little") % self._dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign * weight
        norm = math.sqrt(sum(v * v for v in vector))
        return [v / norm for v in vector] if norm else vector


def _features(text: str) -> list[tuple[str, float]]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    features = [(f"w:{w}", 1.0) for w in words]
    for word in words:
        padded = f"#{word}#"
        features.extend((f"c:{padded[i : i + 3]}", 0.5) for i in range(len(padded) - 2))
    return features


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity of two equal-length vectors; 0.0 if either is all zeros."""
    if len(a) != len(b):
        raise ValueError("vectors must have the same length")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0
