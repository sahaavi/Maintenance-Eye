"""
Shared text-matching helpers for asset/work-order search.
"""

from __future__ import annotations

import re

_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")

_NUMBER_WORD_ALIASES: dict[str, str] = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
}

_QUERY_NOISE_TOKENS = frozenset(
    {
        "the",
        "a",
        "an",
        "for",
        "in",
        "at",
        "on",
        "about",
        "of",
        "to",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "with",
        "and",
        "or",
        "not",
        "it",
        "show",
        "find",
        "get",
        "search",
        "look",
        "up",
        "lookup",
        "me",
        "my",
        "all",
        "list",
        "display",
        "what",
        "where",
        "which",
        "how",
        "please",
        "can",
        "you",
        "i",
        "need",
        "want",
        "there",
        "any",
        "anything",
        "this",
        "that",
        "these",
        "those",
        "do",
        "does",
        "did",
        "have",
        "has",
        "had",
        "we",
        "our",
        "us",
        "if",
        "whether",
        "currently",
        "right",
        "now",
        "still",
        "system",
        "subsystem",
        "work",
        "order",
        "orders",
        "wo",
        "wos",
        "ticket",
        "tickets",
        "asset",
        "assets",
        "equipment",
        "report",
        "reports",
        "record",
        "records",
        "inspection",
        "inspections",
        "dash",
        "hyphen",
        "minus",
        "number",
        "id",
        "identifier",
        "code",
    }
)


_DOMAIN_CORRECTIONS: dict[str, str] = {
    "ovc": "vobc",
    "bobc": "vobc",
    "vopc": "vobc",
}


def _normalize_token(token: str) -> str:
    t = _NUMBER_WORD_ALIASES.get(token.lower(), token.lower())
    return _DOMAIN_CORRECTIONS.get(t, t)


def _tokenize(text: str, *, drop_noise: bool = False) -> list[str]:
    tokens: list[str] = []
    for raw in _TOKEN_PATTERN.findall(text.lower()):
        token = _normalize_token(raw)
        if drop_noise and token in _QUERY_NOISE_TOKENS:
            continue
        if drop_noise and len(token) <= 1 and not token.isdigit():
            continue
        tokens.append(token)
    return tokens


def _numeric_variants(token: str) -> set[str]:
    if not token.isdigit():
        return set()
    raw = str(int(token))
    return {raw, raw.zfill(3), raw.zfill(4)}


def _build_searchable_tokens(text: str) -> set[str]:
    tokens = _tokenize(text, drop_noise=False)
    searchable = set(tokens)
    for token in tokens:
        searchable.update(_numeric_variants(token))
    return searchable


def query_matches_text(query: str, searchable_text: str) -> bool:
    """
    Return True when all normalized query tokens are represented in searchable text.

    Matching rules:
    - number words normalize to digits ("three" -> "3")
    - numeric tokens accept zero-padded equivalents ("3" == "003" == "0003")
    - alphabetic tokens prefer exact token match, with prefix fallback for partial input
    - consecutive unmatched alpha tokens are tried as a compound word
      ("metro" + "town" -> "metrotown")
    """
    query_tokens = _tokenize(query, drop_noise=True)
    if not query_tokens:
        return True

    searchable_tokens = _build_searchable_tokens(searchable_text)

    # First pass: mark which tokens are matched
    matched = [False] * len(query_tokens)
    for i, token in enumerate(query_tokens):
        if token.isdigit():
            if _numeric_variants(token) & searchable_tokens:
                matched[i] = True
            continue

        if token in searchable_tokens:
            matched[i] = True
            continue
        if len(token) >= 3 and any(st.startswith(token) for st in searchable_tokens):
            matched[i] = True

    if all(matched):
        return True

    # Second pass: try compound-word matching for unmatched alpha tokens.
    # e.g., "metro" + "town" -> "metrotown" matches against searchable tokens.
    # Also handles cases where the previous token was prefix-matched (e.g., "metro"
    # matched "metrotown" via prefix, but "town" was left unmatched).
    i = 0
    while i < len(query_tokens):
        if matched[i]:
            i += 1
            continue
        token = query_tokens[i]
        if not token.isalpha():
            i += 1
            continue

        # Try combining with previous alpha token (even if already matched)
        if i > 0 and query_tokens[i - 1].isalpha():
            compound = query_tokens[i - 1] + token
            if compound in searchable_tokens or (
                len(compound) >= 3 and any(st.startswith(compound) for st in searchable_tokens)
            ):
                matched[i] = True
                matched[i - 1] = True
                i += 1
                continue

        # Try combining with next unmatched alpha token
        if i + 1 < len(query_tokens) and not matched[i + 1] and query_tokens[i + 1].isalpha():
            compound = token + query_tokens[i + 1]
            if compound in searchable_tokens or (
                len(compound) >= 3 and any(st.startswith(compound) for st in searchable_tokens)
            ):
                matched[i] = True
                matched[i + 1] = True
                i += 2
                continue
        i += 1

    if all(matched):
        return True

    # Third pass: fuzzy bigram matching for remaining unmatched alpha tokens.
    # Handles ASR errors like "downtrex" ≈ "downtown" via Dice coefficient.
    for i, token in enumerate(query_tokens):
        if matched[i] or not token.isalpha() or len(token) < 5:
            continue
        for st in searchable_tokens:
            if not st.isalpha() or len(st) < 5:
                continue
            if _bigram_similarity(token, st) >= 0.6:
                matched[i] = True
                break

    return all(matched)


def _bigram_similarity(a: str, b: str) -> float:
    """Dice coefficient on character bigrams."""
    if len(a) < 2 or len(b) < 2:
        return 0.0
    bigrams_a = {a[i : i + 2] for i in range(len(a) - 1)}
    bigrams_b = {b[i : i + 2] for i in range(len(b) - 1)}
    overlap = len(bigrams_a & bigrams_b)
    return (2.0 * overlap) / (len(bigrams_a) + len(bigrams_b))
