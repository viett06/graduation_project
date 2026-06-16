import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


DEFAULT_KNOWLEDGE_DIR = Path(__file__).resolve().parents[3] / "knowledge"
MAX_CHUNK_CHARS = 1400


@dataclass(frozen=True)
class KnowledgeChunk:
    id: str
    title: str
    content: str
    source: str
    category: str | None = None
    bank_code: str | None = None


class KnowledgeBaseService:
    """
    Local RAG retriever for product/FAQ knowledge.

    This deliberately keeps retrieval behind a service boundary. The chatbot only
    calls `search`; later you can replace this local markdown retriever with
    pgvector, Qdrant, Pinecone, or OpenAI embeddings without changing agent flow.
    """

    def __init__(self, knowledge_dir: Path | str = DEFAULT_KNOWLEDGE_DIR):
        self.knowledge_dir = Path(knowledge_dir)
        self._chunks: list[KnowledgeChunk] | None = None

    def search(self, query: str, top_k: int = 4) -> dict[str, Any]:
        chunks = self._load_chunks()
        if not query.strip():
            return {
                "query": query,
                "results": [],
                "message": "Query rỗng, không thể tìm trong kho kiến thức.",
            }

        ranked = self._rank(query, chunks)
        results = [
            {
                "title": chunk.title,
                "content": chunk.content,
                "source": chunk.source,
                "category": chunk.category,
                "bank_code": chunk.bank_code,
                "score": round(score, 4),
            }
            for chunk, score in ranked[:max(1, min(top_k, 8))]
            if score > 0
        ]

        return {
            "query": query,
            "results": results,
            "message": None if results else "Không tìm thấy tài liệu phù hợp trong kho kiến thức.",
        }

    def _load_chunks(self) -> list[KnowledgeChunk]:
        if self._chunks is not None:
            return self._chunks

        if not self.knowledge_dir.exists():
            self._chunks = []
            return self._chunks

        chunks: list[KnowledgeChunk] = []
        for path in sorted(self.knowledge_dir.rglob("*.md")):
            chunks.extend(self._parse_markdown_file(path))

        self._chunks = chunks
        return chunks

    def _parse_markdown_file(self, path: Path) -> list[KnowledgeChunk]:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return []

        metadata, body = self._split_frontmatter(text)
        sections = self._split_sections(body)
        relative_source = str(path.relative_to(self.knowledge_dir))

        chunks = []
        for index, (title, content) in enumerate(sections):
            for part_index, part in enumerate(self._split_large_section(content)):
                chunks.append(
                    KnowledgeChunk(
                        id=f"{relative_source}:{index}:{part_index}",
                        title=title or metadata.get("title") or path.stem,
                        content=part,
                        source=relative_source,
                        category=metadata.get("category"),
                        bank_code=metadata.get("bank_code"),
                    )
                )
        return chunks

    @staticmethod
    def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
        if not text.startswith("---"):
            return {}, text

        parts = text.split("---", 2)
        if len(parts) < 3:
            return {}, text

        metadata = {}
        for line in parts[1].splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            value = value.strip().strip('"').strip("'")
            metadata[key.strip()] = value or None

        return metadata, parts[2].strip()

    @staticmethod
    def _split_sections(text: str) -> list[tuple[str, str]]:
        sections = []
        current_title = ""
        current_lines = []

        for line in text.splitlines():
            heading = re.match(r"^(#{1,3})\s+(.+)$", line.strip())
            if heading and current_lines:
                content = "\n".join(current_lines).strip()
                if content:
                    sections.append((current_title, content))
                current_title = heading.group(2).strip()
                current_lines = []
                continue
            if heading:
                current_title = heading.group(2).strip()
                continue
            current_lines.append(line)

        content = "\n".join(current_lines).strip()
        if content:
            sections.append((current_title, content))
        return sections or [("", text)]

    @staticmethod
    def _split_large_section(content: str) -> list[str]:
        if len(content) <= MAX_CHUNK_CHARS:
            return [content]

        paragraphs = [paragraph.strip() for paragraph in content.split("\n\n") if paragraph.strip()]
        chunks = []
        current = ""
        for paragraph in paragraphs:
            if len(current) + len(paragraph) + 2 <= MAX_CHUNK_CHARS:
                current = f"{current}\n\n{paragraph}".strip()
            else:
                if current:
                    chunks.append(current)
                current = paragraph
        if current:
            chunks.append(current)
        return chunks

    def _rank(self, query: str, chunks: list[KnowledgeChunk]) -> list[tuple[KnowledgeChunk, float]]:
        query_terms = self._tokenize(query)
        if not query_terms:
            return []

        query_vector = self._term_vector(query_terms)
        ranked = []
        for chunk in chunks:
            chunk_terms = self._tokenize(f"{chunk.title} {chunk.content} {chunk.source}")
            chunk_vector = self._term_vector(chunk_terms)
            lexical_overlap = len(set(query_terms) & set(chunk_terms)) / max(1, len(set(query_terms)))
            cosine = self._cosine_similarity(query_vector, chunk_vector)
            score = (0.65 * cosine) + (0.35 * lexical_overlap)
            ranked.append((chunk, score))

        return sorted(ranked, key=lambda item: item[1], reverse=True)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        normalized = text.lower()
        tokens = re.findall(r"[\wÀ-ỹ]+", normalized, flags=re.UNICODE)
        stop_words = {
            "là", "và", "của", "cho", "thì", "khi", "nào", "như", "nào",
            "the", "a", "an", "of", "to", "in", "on", "is", "are",
        }
        return [token for token in tokens if len(token) > 1 and token not in stop_words]

    @staticmethod
    def _term_vector(tokens: list[str]) -> dict[str, float]:
        vector: dict[str, float] = {}
        for token in tokens:
            vector[token] = vector.get(token, 0.0) + 1.0

        length = max(1.0, math.sqrt(sum(value * value for value in vector.values())))
        return {key: value / length for key, value in vector.items()}

    @staticmethod
    def _cosine_similarity(left: dict[str, float], right: dict[str, float]) -> float:
        common_keys = set(left) & set(right)
        if not common_keys:
            return 0.0
        left_values = np.array([left[key] for key in common_keys])
        right_values = np.array([right[key] for key in common_keys])
        return float(np.dot(left_values, right_values))
