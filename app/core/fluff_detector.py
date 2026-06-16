import logging
import re

logger = logging.getLogger(__name__)

FLUFF_CATEGORIES: dict[str, list[str]] = {
    "overused_business": [
        "leverage", "synergy", "paradigm shift", "think outside the box",
        "circle back", "touch base", "deep dive", "low-hanging fruit",
        "actionable", "holistic", "scalable", "best-in-class",
    ],
    "hyperbolic_marketing": [
        "revolutionizing", "groundbreaking", "game-changer", "cutting-edge",
        "innovative", "disruptive", "industry-leading", "next-gen",
        "ultimate", "unprecedented", "one-of-a-kind", "world-class",
    ],
    "fluff_transitions": [
        "moreover", "furthermore", "in conclusion", "it is important to note",
        "in today's", "in the ever-evolving", "it goes without saying",
        "needless to say", "all in all",
    ],
    "academic_padding": [
        "delve", "testament to", "utilize", "optimize", "streamline",
        "elucidate", "delineate", "thus", "henceforth", "aforementioned",
    ],
}

SENTENCE_SPLITTER = re.compile(r"(?<=[.!?])\s+")


class SemanticFluffDetector:
    def __init__(self):
        self._use_embeddings = False
        self._embedder = None
        self._try_load_embeddings()

    def _try_load_embeddings(self):
        try:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
            self._use_embeddings = True
            logger.info("SemanticFluffDetector using sentence-transformers embeddings")
        except ImportError:
            logger.info(
                "sentence-transformers not available — "
                "SemanticFluffDetector using keyword fallback"
            )

    def detect(
        self, text: str, threshold: float = 0.75
    ) -> list[tuple[str, float, str]]:
        results: list[tuple[str, float, str]] = []
        lower = text.lower()

        for category, phrases in FLUFF_CATEGORIES.items():
            for phrase in phrases:
                if phrase in lower:
                    for sentence in SENTENCE_SPLITTER.split(text):
                        if phrase in sentence.lower():
                            results.append((category, 1.0, sentence.strip()))
                            break
                    else:
                        results.append((category, 1.0, phrase))

        if self._use_embeddings and self._embedder:
            results = self._score_with_embeddings(text, results, threshold)

        return results

    def _score_with_embeddings(
        self,
        text: str,
        keyword_results: list[tuple[str, float, str]],
        threshold: float,
    ) -> list[tuple[str, float, str]]:
        sentences = SENTENCE_SPLITTER.split(text)
        if not sentences:
            return keyword_results

        sentence_embeddings = self._embedder.encode(sentences)
        seen = set()
        enriched: list[tuple[str, float, str]] = []

        for category, phrases in FLUFF_CATEGORIES.items():
            phrase_embeddings = self._embedder.encode(phrases)
            for sent_emb, sent in zip(sentence_embeddings, sentences):
                sent_lower = sent.lower()
                scores = (phrase_embeddings @ sent_emb).tolist()
                if isinstance(scores, float):
                    scores = [scores]
                best_score = max(scores) if scores else 0.0
                if best_score >= threshold and sent_lower not in seen:
                    seen.add(sent_lower)
                    enriched.append((category, float(best_score), sent.strip()))

        seen_keywords = set()
        for cat, score, sent in keyword_results:
            if sent.lower() not in seen_keywords:
                seen_keywords.add(sent.lower())
                enriched.append((cat, score, sent))

        enriched.sort(key=lambda x: -x[1])
        return enriched
