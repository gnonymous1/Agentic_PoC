import difflib

from app.models.content_models import MultiPlatformContent


def content_similarity(
    a: MultiPlatformContent,
    b: MultiPlatformContent,
    field_weights: dict[str, float] | None = None,
) -> float:
    if field_weights is None:
        field_weights = {
            "twitter": 0.25,
            "linkedin": 0.20,
            "facebook": 0.20,
            "blogspot": 0.35,
        }

    a_texts = _extract_texts(a)
    b_texts = _extract_texts(b)

    total = 0.0
    for key in field_weights:
        if key in a_texts and key in b_texts:
            ratio = difflib.SequenceMatcher(
                None, a_texts[key], b_texts[key]
            ).ratio()
            total += field_weights[key] * ratio

    return total


def _extract_texts(content: MultiPlatformContent) -> dict[str, str]:
    texts = {}
    texts["twitter"] = ". ".join(content.twitter.posts)
    texts["linkedin"] = content.linkedin.body
    texts["facebook"] = content.facebook.body
    texts["blogspot"] = content.blogspot.html_body
    return texts


def utd_similarity(utd_a: str, utd_b: str) -> float:
    if not utd_a and not utd_b:
        return 1.0
    if not utd_a or not utd_b:
        return 0.0
    return difflib.SequenceMatcher(None, utd_a, utd_b).ratio()
