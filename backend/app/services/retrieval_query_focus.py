"""Derive a short lexical query from a natural-language student question."""

import re

TOKEN = re.compile(r"[\w'-]+", re.UNICODE)

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "is",
        "are",
        "any",
        "not",
        "no",
        "our",
        "this",
        "that",
        "with",
        "from",
        "how",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "do",
        "does",
        "did",
        "be",
        "by",
        "or",
        "and",
        "as",
        "it",
        "its",
        "use",
        "course",
        "materials",
        "cite",
        "everything",
        "need",
        "teach",
        "me",
        "about",
        "per",
        "using",
    }
)


# Words that describe the *kind* of material or the requested task rather than its
# subject. A document that merely contains "lecture" is not evidence about a topic.
GENERIC_RETRIEVAL_TERMS = frozenset(
    {
        "lecture",
        "lectures",
        "slide",
        "slides",
        "note",
        "notes",
        "professor",
        "professors",
        "summarize",
        "summarise",
        "summary",
        "explain",
        "reading",
        "readings",
        "class",
        "document",
        "documents",
        "pdf",
        "file",
        "files",
        "please",
        "tell",
        "show",
        "give",
        "find",
        "recording",
    }
)


def focused_retrieval_query(query: str, *, max_terms: int = 6) -> str:
    """Keep discriminative tokens (e.g. lecture number, topic) for lexical retrieval."""
    terms = [
        term
        for term in TOKEN.findall(" ".join(query.casefold().split()))
        if term not in _STOPWORDS and (len(term) > 1 or term.isdigit())
    ]
    if not terms:
        return query.strip()
    focus: list[str] = []
    for index, term in enumerate(terms):
        if (
            term == "lecture"
            and index + 1 < len(terms)
            and re.fullmatch(r"\d+|[ivxl]+", terms[index + 1])
        ):
            focus.append(f"lecture {terms[index + 1]}")
            break
    subject_terms = [term for term in terms if term not in GENERIC_RETRIEVAL_TERMS]
    if subject_terms:
        terms = subject_terms
    for topic in ("robot", "kinematics", "quiz", "exam", "sensor", "neural"):
        if topic in terms and topic not in focus:
            focus.append(topic)
    if focus:
        return " ".join(focus[:max_terms])
    return " ".join(terms[:max_terms])
