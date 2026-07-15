"""Standard-library lightweight retrieval over published knowledge chunks."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .knowledge_keywords import analyze_question, normalize_text
from .knowledge_service import KnowledgeService, get_default_knowledge_service


TITLE_WEIGHT = 14
SECTION_WEIGHT = 12
KEYWORD_WEIGHT = 10
DOMAIN_WEIGHT = 8
CONTENT_WEIGHT = 4
MINIMUM_SCORE = 8
DEFAULT_TOP_K = 4
DEFAULT_ANSWER_GUIDANCE_PATH = (
    Path(__file__).resolve().parents[1] / "prompts" / "student-aid-answer-guidelines.md"
)


class RetrievalService:
    """Rank audited knowledge chunks using deterministic keyword scoring."""

    def __init__(
        self,
        knowledge_service: KnowledgeService | None = None,
        *,
        answer_guidance_path: str | Path = DEFAULT_ANSWER_GUIDANCE_PATH,
    ) -> None:
        self.knowledge_service = knowledge_service or get_default_knowledge_service()
        self.answer_guidance = self._load_answer_guidance(Path(answer_guidance_path))

    def retrieve(self, question: str, *, top_k: int = DEFAULT_TOP_K) -> list[dict[str, Any]]:
        """Return up to three-to-five relevant chunks for a user question."""

        question = str(question).strip()
        if not question:
            return []

        chunks = self.knowledge_service.chunks
        all_metadata_keywords = {
            keyword
            for chunk in chunks
            for keyword in chunk.get("keywords", [])
            if isinstance(keyword, str)
        }
        analysis = analyze_question(
            question,
            metadata_keywords=all_metadata_keywords,
        )
        if not analysis.terms and not analysis.domains:
            return []

        requested_limit = max(3, min(int(top_k), 5))
        ranked: list[tuple[int, str, dict[str, Any]]] = []

        for chunk in chunks:
            score = self._score_chunk(chunk, analysis)
            if score < MINIMUM_SCORE:
                continue
            ranked.append((score, chunk["chunk_id"], chunk))

        ranked.sort(key=lambda item: (-item[0], item[1]))
        results = [
            self._to_result(chunk, score)
            for score, _chunk_id, chunk in ranked[:requested_limit]
        ]
        if (
            results
            and results[0].get("domain") == "student-aid"
            and self.answer_guidance
        ):
            results[0]["content"] = (
                f"{results[0]['content']}\n\n"
                f"【回答规范】\n{self.answer_guidance}"
            )
        return results

    @staticmethod
    def _load_answer_guidance(path: Path) -> str:
        """Load optional prompt guidance without making retrieval unavailable."""

        try:
            return path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError):
            return ""

    @staticmethod
    def _score_chunk(chunk: dict[str, Any], analysis: Any) -> int:
        title = normalize_text(chunk.get("document_title", ""))
        section = normalize_text(chunk.get("section_title", ""))
        content = normalize_text(chunk.get("content", ""))
        metadata_keywords = {
            normalize_text(keyword)
            for keyword in chunk.get("keywords", [])
            if normalize_text(keyword)
        }
        score = 0

        for term in analysis.terms:
            normalized_term = normalize_text(term)
            if not normalized_term:
                continue
            if normalized_term in title:
                score += TITLE_WEIGHT
            if normalized_term in section:
                score += SECTION_WEIGHT
            if any(
                normalized_term in keyword or keyword in normalized_term
                for keyword in metadata_keywords
            ):
                score += KEYWORD_WEIGHT
            if normalized_term in content:
                score += CONTENT_WEIGHT

        if chunk.get("domain") in analysis.domains:
            score += DOMAIN_WEIGHT
        return score

    @staticmethod
    def _to_result(chunk: dict[str, Any], score: int) -> dict[str, Any]:
        return {
            "content": chunk["content"],
            "title": chunk["document_title"],
            "section": chunk["section_title"],
            "domain": chunk["domain"],
            "source": {
                "title": chunk["source_title"],
                "organization": chunk["source_organization"],
            },
            "url": chunk["source_url"],
            "updated_at": chunk["updated_at"],
            "score": score,
            "document_id": chunk["document_id"],
            "suggested_questions": deepcopy(chunk["suggested_questions"]),
        }


_default_retrieval_service: RetrievalService | None = None


def get_default_retrieval_service(*, force_reload: bool = False) -> RetrievalService:
    """Return the process-local retriever backed by the cached catalog."""

    global _default_retrieval_service
    if _default_retrieval_service is None or force_reload:
        knowledge_service = get_default_knowledge_service(force_reload=force_reload)
        _default_retrieval_service = RetrievalService(knowledge_service)
    return _default_retrieval_service
