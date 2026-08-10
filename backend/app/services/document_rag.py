"""
Document RAG service.

MVP ini memakai chunk table + embedding lokal deterministic agar alur RAG sudah benar
tanpa menunggu vector database eksternal. Provider embedding/rerank dapat diganti
ke NeMo Retrieval/Qdrant pada fase berikutnya.
"""
import hashlib
import json
import logging
import math
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import Document, DocumentChunk
from app.services.ai_service import AIService

logger = logging.getLogger(__name__)


TOKEN_RE = re.compile(r"[a-zA-Z0-9_./-]+", re.UNICODE)


@dataclass
class RetrievedChunk:
    chunk: DocumentChunk
    score: float


def _tokens(text: str) -> List[str]:
    return [item.lower() for item in TOKEN_RE.findall(text or "") if len(item) > 1]


def _hash_embedding(text: str, dimensions: Optional[int] = None) -> List[float]:
    dimensions = dimensions or settings.RAG_EMBEDDING_DIMENSIONS
    vector = [0.0] * dimensions
    for token in _tokens(text):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[bucket] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / norm, 6) for value in vector]


def _cosine(left: Iterable[float], right: Iterable[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _chunk_text(text: str, chunk_size: Optional[int] = None, overlap: Optional[int] = None) -> List[str]:
    chunk_size = chunk_size or settings.RAG_CHUNK_SIZE
    overlap = overlap if overlap is not None else settings.RAG_CHUNK_OVERLAP
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []

    chunks = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + chunk_size, length)
        if end < length:
            boundary = max(text.rfind(". ", start, end), text.rfind("\n", start, end))
            if boundary > start + int(chunk_size * 0.55):
                end = boundary + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        start = max(0, end - overlap)
    return chunks


def extract_text(content: bytes, filename: str) -> str:
    return AIService._extract_document_text(content, filename)


def index_document(db: Session, document: Document, content: bytes, filename: str) -> int:
    if not settings.RAG_ENABLED:
        return 0

    try:
        text = extract_text(content, filename)
    except Exception as exc:
        logger.warning("Document RAG extraction skipped for %s: %s", filename, exc)
        return 0

    chunks = _chunk_text(text)
    if not chunks:
        return 0

    db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()
    for index, chunk_text in enumerate(chunks):
        db.add(DocumentChunk(
            document_id=document.id,
            project_id=document.project_id,
            chunk_index=index,
            text=chunk_text,
            embedding_json=json.dumps(_hash_embedding(chunk_text)),
            token_estimate=max(1, len(chunk_text) // 4),
        ))
    db.commit()
    return len(chunks)


def retrieve_chunks(
    db: Session,
    project_id: int,
    question: str,
    allowed_document_ids: Optional[List[int]] = None,
    top_k: Optional[int] = None,
) -> List[RetrievedChunk]:
    top_k = top_k or settings.RAG_TOP_K
    query = db.query(DocumentChunk).filter(DocumentChunk.project_id == project_id)
    if allowed_document_ids is not None:
        if not allowed_document_ids:
            return []
        query = query.filter(DocumentChunk.document_id.in_(allowed_document_ids))

    chunks = query.all()
    if not chunks:
        return []

    question_vector = _hash_embedding(question)
    question_terms = set(_tokens(question))
    scored = []
    for chunk in chunks:
        try:
            embedding = json.loads(chunk.embedding_json)
        except Exception:
            embedding = _hash_embedding(chunk.text)
        semantic = _cosine(question_vector, embedding)
        chunk_terms = set(_tokens(chunk.text))
        overlap = len(question_terms & chunk_terms) / max(1, len(question_terms))
        scored.append(RetrievedChunk(chunk=chunk, score=round((0.75 * semantic) + (0.25 * overlap), 6)))

    return sorted(scored, key=lambda item: item.score, reverse=True)[:top_k]
