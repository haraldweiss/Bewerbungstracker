# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""Ollama-basierte Embedding-Helper (nomic-embed-text, 768-dim).

OLLAMA_HOST env (default: http://127.0.0.1:11434) zeigt auf den
autossh-Tunnel zum Mac. Bei Ausfall returnen alle Funktionen None
statt zu crashen — der Caller fällt auf reinen Prefilter-Score zurück.
"""

from __future__ import annotations
import os
import logging
import numpy as np
import requests

logger = logging.getLogger(__name__)

OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://127.0.0.1:11434')
EMBED_MODEL = os.getenv('OLLAMA_EMBED_MODEL', 'nomic-embed-text')
EMBED_DIM = 768
EMBED_TIMEOUT_S = 10


def vector_pack(vec) -> bytes:
    """Pack float-Liste/np.array zu float32-Bytes."""
    arr = np.asarray(vec, dtype=np.float32)
    return arr.tobytes()


def vector_unpack(blob: bytes) -> np.ndarray:
    """Restore float32-Array aus Bytes."""
    return np.frombuffer(blob, dtype=np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine-Similarity, safe gegen Zero-Vektoren."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def embed_text(text: str) -> bytes | None:
    """Embed text via Ollama. Returns packed float32-bytes or None on failure."""
    if not text or not text.strip():
        return None
    try:
        resp = requests.post(
            f'{OLLAMA_HOST}/api/embeddings',
            json={'model': EMBED_MODEL, 'prompt': text[:8000]},
            timeout=EMBED_TIMEOUT_S,
        )
        if not resp.ok:
            logger.warning('Ollama embed failed: HTTP %s', resp.status_code)
            return None
        data = resp.json()
        vec = data.get('embedding')
        if not vec or len(vec) != EMBED_DIM:
            logger.warning('Ollama returned unexpected embedding (len=%s)', len(vec) if vec else 0)
            return None
        return vector_pack(vec)
    except Exception as e:
        logger.warning('Ollama embed exception: %s', e)
        return None


def embed_raw_job(raw_job) -> bool:
    """Embed RawJob und persistiere als JobEmbedding. Idempotent."""
    from database import db
    from models import JobEmbedding

    existing = JobEmbedding.query.filter_by(raw_job_id=raw_job.id).first()
    if existing:
        return True

    text = f"{raw_job.title or ''}\n\n{raw_job.description or ''}"
    blob = embed_text(text)
    if blob is None:
        return False

    emb = JobEmbedding(raw_job_id=raw_job.id, vector=blob, model=EMBED_MODEL)
    db.session.add(emb)
    db.session.commit()
    return True
