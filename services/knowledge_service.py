"""Read-only loader and validator for the parallel Huimang Go knowledge base.

This module is intentionally not connected to ``/api/chat`` yet. It loads the
catalog, validates metadata, exposes published documents and creates natural
Markdown chunks for tests and future retrieval work.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG_PATH = PROJECT_ROOT / "knowledge" / "catalog.json"

ALLOWED_DOMAINS = {
    "student-aid",
    "education-growth",
    "agriculture",
    "community",
    "employment",
    "local",
    "shared",
    "youth",
}
ALLOWED_AUDIENCES = {
    "student",
    "parent",
    "rural-youth",
    "farmer",
    "villager",
}
ALLOWED_STATUSES = {"draft", "published", "archived"}
ALLOWED_RISK_LEVELS = {"normal", "verify-officially", "high"}

REQUIRED_FIELDS = {
    "id",
    "title",
    "file",
    "domain",
    "audiences",
    "region",
    "keywords",
    "source_title",
    "source_organization",
    "source_url",
    "source_date",
    "updated_at",
    "reviewed_at",
    "status",
    "risk_level",
    "suggested_questions",
}

MARKDOWN_HEADING = re.compile(r"^(#{1,3})\s+(.+?)\s*$")
PATH_PART = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class KnowledgeService:
    """Load, validate and cache a Markdown knowledge catalog.

    Validation errors are collected instead of raised so a broken parallel
    catalog cannot prevent the existing Flask site from starting.
    """

    def __init__(self, catalog_path: str | Path = DEFAULT_CATALOG_PATH) -> None:
        self.catalog_path = Path(catalog_path).resolve()
        self.knowledge_root = self.catalog_path.parent
        self._documents: list[dict[str, Any]] = []
        self._published_documents: list[dict[str, Any]] = []
        self._chunks: list[dict[str, Any]] = []
        self._errors: list[str] = []
        self._warnings: list[str] = []
        self._status_counts = {status: 0 for status in ALLOWED_STATUSES}
        self._total_documents = 0
        self.reload()

    @property
    def documents(self) -> tuple[dict[str, Any], ...]:
        """Return validated catalog documents of every status."""

        return tuple(deepcopy(self._documents))

    @property
    def published_documents(self) -> tuple[dict[str, Any], ...]:
        """Return only validated, published documents loaded into memory."""

        return tuple(deepcopy(self._published_documents))

    @property
    def chunks(self) -> tuple[dict[str, Any], ...]:
        """Return cached chunks from published documents only."""

        return tuple(deepcopy(self._chunks))

    def reload(self) -> None:
        """Clear the cache and load the catalog from disk again."""

        self._documents = []
        self._published_documents = []
        self._chunks = []
        self._errors = []
        self._warnings = []
        self._status_counts = {status: 0 for status in ALLOWED_STATUSES}
        self._total_documents = 0

        catalog = self._read_catalog()
        if catalog is None:
            return

        raw_documents = catalog.get("documents")
        if not isinstance(raw_documents, list):
            self._errors.append("catalog.json field 'documents' must be a list.")
            return

        self._total_documents = len(raw_documents)
        seen_ids: set[str] = set()

        for index, raw_document in enumerate(raw_documents):
            location = f"documents[{index}]"
            if not isinstance(raw_document, dict):
                self._errors.append(f"{location} must be an object.")
                continue

            status = raw_document.get("status")
            if status in ALLOWED_STATUSES:
                self._status_counts[status] += 1

            document_errors = self._validate_document(
                raw_document,
                location=location,
                seen_ids=seen_ids,
            )
            if document_errors:
                self._errors.extend(document_errors)
                continue

            document = deepcopy(raw_document)
            document_path = self.knowledge_root / PurePosixPath(document["file"])
            document["path"] = str(document_path)
            self._documents.append(document)

            if document["status"] != "published":
                continue

            try:
                body = document_path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                self._errors.append(
                    f"{location} could not read '{document['file']}': {exc}"
                )
                continue

            document["content"] = body
            self._published_documents.append(document)

            if not body.strip():
                self._warnings.append(
                    f"{location} published Markdown file '{document['file']}' is empty."
                )
                continue

            self._chunks.extend(self._split_document(document, body))

    def get_statistics(self) -> dict[str, Any]:
        """Return serializable read-only knowledge-base statistics."""

        return {
            "total_documents": self._total_documents,
            "published": self._status_counts["published"],
            "draft": self._status_counts["draft"],
            "archived": self._status_counts["archived"],
            "available_documents": len(self._published_documents),
            "available_chunks": len(self._chunks),
            "errors": list(self._errors),
            "warnings": list(self._warnings),
        }

    def _read_catalog(self) -> dict[str, Any] | None:
        try:
            raw_catalog = self.catalog_path.read_text(encoding="utf-8")
        except OSError as exc:
            self._errors.append(f"Could not read catalog '{self.catalog_path}': {exc}")
            return None

        try:
            catalog = json.loads(raw_catalog)
        except json.JSONDecodeError as exc:
            self._errors.append(
                f"Invalid JSON in catalog '{self.catalog_path}': "
                f"line {exc.lineno}, column {exc.colno}."
            )
            return None

        if not isinstance(catalog, dict):
            self._errors.append("catalog.json root must be an object.")
            return None
        return catalog

    def _validate_document(
        self,
        document: dict[str, Any],
        *,
        location: str,
        seen_ids: set[str],
    ) -> list[str]:
        errors: list[str] = []
        missing_fields = sorted(REQUIRED_FIELDS - set(document))
        if missing_fields:
            errors.append(
                f"{location} is missing required fields: {', '.join(missing_fields)}."
            )
            return errors

        document_id = document.get("id")
        if not isinstance(document_id, str) or not document_id.strip():
            errors.append(f"{location} field 'id' must be a non-empty string.")
        elif document_id in seen_ids:
            errors.append(f"{location} has duplicate id '{document_id}'.")
        else:
            seen_ids.add(document_id)

        domain = document.get("domain")
        if domain not in ALLOWED_DOMAINS:
            errors.append(f"{location} has invalid domain '{domain}'.")

        audiences = document.get("audiences")
        if not isinstance(audiences, list) or not audiences:
            errors.append(f"{location} field 'audiences' must be a non-empty list.")
        else:
            invalid_audiences = sorted(
                {audience for audience in audiences if audience not in ALLOWED_AUDIENCES}
            )
            if invalid_audiences:
                errors.append(
                    f"{location} has invalid audiences: {', '.join(invalid_audiences)}."
                )

        status = document.get("status")
        if status not in ALLOWED_STATUSES:
            errors.append(f"{location} has invalid status '{status}'.")

        risk_level = document.get("risk_level")
        if risk_level not in ALLOWED_RISK_LEVELS:
            errors.append(f"{location} has invalid risk_level '{risk_level}'.")

        for field in (
            "title",
            "region",
            "source_title",
            "source_organization",
            "source_url",
            "source_date",
            "updated_at",
            "reviewed_at",
        ):
            if not isinstance(document.get(field), str):
                errors.append(f"{location} field '{field}' must be a string.")

        for field in ("keywords", "suggested_questions"):
            value = document.get(field)
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                errors.append(f"{location} field '{field}' must be a list of strings.")

        file_value = document.get("file")
        if not self._is_valid_relative_markdown_path(file_value):
            errors.append(
                f"{location} field 'file' must be a lowercase relative Markdown path "
                "using English letters, numbers and hyphens."
            )
        else:
            document_path = self.knowledge_root / PurePosixPath(file_value)
            if not document_path.is_file():
                errors.append(f"{location} file does not exist: '{file_value}'.")

        source_url = document.get("source_url")
        if isinstance(source_url, str):
            if source_url:
                parsed = urlparse(source_url)
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    errors.append(f"{location} has invalid source_url '{source_url}'.")
            else:
                self._warnings.append(
                    f"{location} source_url is empty; no URL was generated automatically."
                )

        source_date = document.get("source_date")
        if source_date == "":
            self._warnings.append(
                f"{location} source_date is empty because the existing source did not "
                "provide a confirmed publication date."
            )

        return errors

    @staticmethod
    def _is_valid_relative_markdown_path(value: Any) -> bool:
        if not isinstance(value, str) or not value or "\\" in value:
            return False
        if value != value.lower():
            return False

        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or path.suffix != ".md":
            return False
        if len(path.parts) < 2:
            return False

        directory_parts = path.parts[:-1]
        file_stem = path.stem
        return all(PATH_PART.fullmatch(part) for part in directory_parts) and bool(
            PATH_PART.fullmatch(file_stem)
        )

    @staticmethod
    def _split_document(
        document: dict[str, Any], body: str
    ) -> list[dict[str, Any]]:
        body_lines = body.splitlines()
        if body_lines and body_lines[0].strip() == "---":
            try:
                frontmatter_end = next(
                    index
                    for index, line in enumerate(body_lines[1:], start=1)
                    if line.strip() == "---"
                )
            except StopIteration:
                frontmatter_end = -1
            if frontmatter_end >= 0:
                body_lines = body_lines[frontmatter_end + 1 :]

        sections: list[tuple[str, int | None, str]] = []
        current_title = document["title"]
        current_level: int | None = None
        current_lines: list[str] = []

        def flush() -> None:
            content = "\n".join(current_lines).strip()
            if content:
                sections.append((current_title, current_level, content))

        for line in body_lines:
            heading = MARKDOWN_HEADING.match(line)
            if heading:
                flush()
                current_title = heading.group(2).strip()
                current_level = len(heading.group(1))
                current_lines = []
            else:
                current_lines.append(line)
        flush()

        chunks: list[dict[str, Any]] = []
        for index, (section_title, heading_level, content) in enumerate(sections, start=1):
            chunks.append(
                {
                    "chunk_id": f"{document['id']}:{index}",
                    "document_id": document["id"],
                    "document_title": document["title"],
                    "section_title": section_title,
                    "heading_level": heading_level,
                    "domain": document["domain"],
                    "audiences": list(document["audiences"]),
                    "region": document["region"],
                    "keywords": list(document["keywords"]),
                    "source_title": document["source_title"],
                    "source_organization": document["source_organization"],
                    "source_url": document["source_url"],
                    "source_date": document["source_date"],
                    "updated_at": document["updated_at"],
                    "reviewed_at": document["reviewed_at"],
                    "risk_level": document["risk_level"],
                    "suggested_questions": list(document["suggested_questions"]),
                    "content": content,
                }
            )
        return chunks


_default_service: KnowledgeService | None = None


def get_default_knowledge_service(*, force_reload: bool = False) -> KnowledgeService:
    """Return the process-local cached service for the project catalog."""

    global _default_service
    if _default_service is None or force_reload:
        _default_service = KnowledgeService(DEFAULT_CATALOG_PATH)
    return _default_service


def get_default_knowledge_statistics(*, force_reload: bool = False) -> dict[str, Any]:
    """Return statistics for the project knowledge base without mutating files."""

    return get_default_knowledge_service(force_reload=force_reload).get_statistics()
