"""Deterministic, provider-neutral packaging of retrieval evidence for future RAG."""

from app.retrieval.models import ContextEvidence, RetrievalContextPackage, RetrievalResponse


class RetrievalContextPackager:
    """Apply explicit evidence and character budgets without generating prompts or prose."""

    def package(
        self,
        response: RetrievalResponse,
        *,
        max_characters: int = 12_000,
        max_items: int = 20,
        max_excerpt_characters: int = 1_000,
    ) -> RetrievalContextPackage:
        if not 1 <= max_characters <= 100_000:
            raise ValueError("max_characters must be between 1 and 100000")
        if not 1 <= max_items <= 100:
            raise ValueError("max_items must be between 1 and 100")
        if not 1 <= max_excerpt_characters <= 4_000:
            raise ValueError("max_excerpt_characters must be between 1 and 4000")

        remaining = max_characters
        evidence: list[ContextEvidence] = []
        truncated = len(response.results) > max_items
        for hit in response.results[:max_items]:
            if remaining <= 0:
                truncated = True
                break
            excerpt = hit.snippet[:max_excerpt_characters]
            if len(excerpt) > remaining:
                excerpt = excerpt[:remaining]
                truncated = True
            if len(hit.snippet) > len(excerpt):
                truncated = True
            evidence.append(
                ContextEvidence(
                    evidence=hit.evidence,
                    excerpt=excerpt,
                    retrieval_signals=hit.signals,
                )
            )
            remaining -= len(excerpt)

        return RetrievalContextPackage(
            query=response.query,
            mode=response.mode,
            semantic_status=response.semantic_status,
            evidence=tuple(evidence),
            max_characters=max_characters,
            characters_used=max_characters - remaining,
            truncated=truncated,
            no_evidence=not evidence,
        )
