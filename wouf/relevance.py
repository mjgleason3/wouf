"""BM25-lite lexical relevance scoring, pure stdlib.

This is the single seam where an embedding-based scorer would slot in:
anything with the same ``score(query, doc_id)`` shape works.
"""

from __future__ import annotations

import math
import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    "a an and are as at be but by for from has have how i in is it its me my of on or "
    "s t that the their them they this to was we what when where which who will with you your".split()
)

K1 = 1.5
B = 0.75


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


class Scorer:
    """BM25 over a small corpus of (id -> text). Rebuild is O(corpus); cheap at this scale."""

    def __init__(self, docs: dict[str, str]):
        self.doc_tokens = {doc_id: tokenize(text) for doc_id, text in docs.items()}
        self.n_docs = max(1, len(self.doc_tokens))
        self.avgdl = max(1.0, sum(len(t) for t in self.doc_tokens.values()) / self.n_docs)
        self.df: dict[str, int] = {}
        for tokens in self.doc_tokens.values():
            for term in set(tokens):
                self.df[term] = self.df.get(term, 0) + 1

    def idf(self, term: str) -> float:
        n = self.df.get(term, 0)
        return math.log(1.0 + (self.n_docs - n + 0.5) / (n + 0.5))

    def score(self, query: str, doc_id: str) -> float:
        tokens = self.doc_tokens.get(doc_id, [])
        if not tokens:
            return 0.0
        counts: dict[str, int] = {}
        for t in tokens:
            counts[t] = counts.get(t, 0) + 1
        norm = K1 * (1.0 - B + B * len(tokens) / self.avgdl)
        total = 0.0
        for term in tokenize(query):
            tf = counts.get(term, 0)
            if tf:
                total += self.idf(term) * tf * (K1 + 1.0) / (tf + norm)
        return total


def similarity(text_a: str, text_b: str) -> float:
    """Symmetric token overlap (Jaccard) — used for auto-linking, not recall."""
    a, b = set(tokenize(text_a)), set(tokenize(text_b))
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)
