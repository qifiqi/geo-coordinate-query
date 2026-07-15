"""Address and place-name matching utilities."""

from __future__ import annotations

from typing import Any, Mapping


def address_similarity(input_addr: str, api_result: Mapping[str, Any]) -> float:
    """Score a returned place against the input address or place name.

    POI results commonly carry both a descriptive name and a street address.
    A named scenic area should match its name even when its street address has
    no text in common with the query, so the higher score is used.
    """
    if not input_addr or not api_result:
        return 0.0

    input_clean = _clean(input_addr)
    candidates = (api_result.get("name", ""), api_result.get("address", ""))
    score = max((_text_similarity(input_clean, _clean(value)) for value in candidates), default=0.0)

    for key, weight in (("province", 0.08), ("city", 0.08), ("district", 0.14)):
        value = str(api_result.get(key, ""))
        if value and value != "[]" and value in input_addr:
            score += weight
    return round(min(1.0, score), 2)


def _clean(value: Any) -> str:
    return (
        str(value)
        .replace(" ", "")
        .replace("(", "")
        .replace(")", "")
        .replace("（", "")
        .replace("）", "")
        .replace("[", "")
        .replace("]", "")
    )


def _text_similarity(input_text: str, candidate_text: str) -> float:
    if not input_text or not candidate_text:
        return 0.0

    shorter, longer = sorted((input_text, candidate_text), key=len)
    if shorter in longer:
        return 0.85 + 0.15 * len(shorter) / len(longer)

    previous = [0] * (len(candidate_text) + 1)
    for input_char in input_text:
        current = [0]
        for index, candidate_char in enumerate(candidate_text, start=1):
            if input_char == candidate_char:
                current.append(previous[index - 1] + 1)
            else:
                current.append(max(previous[index], current[-1]))
        previous = current

    shorter_length = min(len(input_text), len(candidate_text))
    longer_length = max(len(input_text), len(candidate_text))
    lcs_ratio = previous[-1] / shorter_length
    length_factor = shorter_length / longer_length
    sequence_score = lcs_ratio * (0.7 + 0.3 * length_factor)
    return sequence_score * (0.7 + 0.3 * sequence_score)
