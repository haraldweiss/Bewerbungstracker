"""In-memory Key Cache für Data Encryption Keys (DEKs).

Beim Login wird der DEK aus dem verschlüsselten User-Record entsperrt und hier
zwischengespeichert, damit Endpoints wie Backup-Erstellung den DEK ohne
Passwort verwenden können.

Multi-Worker-Hinweis: Jeder Worker hat seinen eigenen Cache. Bei Cache-Miss
müssen Endpoints, die den DEK benötigen, einen Re-Login erzwingen (401). Für
das aktuelle IONOS-Single-Worker-Setup ausreichend; bei Multi-Worker später
auf Redis umstellbar (Interface ist drop-in austauschbar).
"""

import threading
import time
from typing import Dict, Optional, Tuple

# TTL passt zur JWT-Token-TTL (auth_service.py) – kein längeres Memory-Halten.
DEFAULT_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 Tage


class KeyCache:
    """Thread-sicherer DEK-Cache mit TTL-basierter Eviction."""

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self._ttl = ttl_seconds
        self._store: Dict[str, Tuple[bytes, float]] = {}
        self._lock = threading.Lock()

    def put(self, user_id: str, dek: bytes) -> None:
        with self._lock:
            self._store[user_id] = (dek, time.time() + self._ttl)

    def get(self, user_id: str) -> Optional[bytes]:
        with self._lock:
            entry = self._store.get(user_id)
            if not entry:
                return None
            dek, expires_at = entry
            if time.time() > expires_at:
                del self._store[user_id]
                return None
            return dek

    def evict(self, user_id: str) -> None:
        with self._lock:
            self._store.pop(user_id, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def cleanup_expired(self) -> int:
        """Entfernt abgelaufene Einträge. Returns: Anzahl entfernter Einträge."""
        now = time.time()
        with self._lock:
            expired = [uid for uid, (_, exp) in self._store.items() if now > exp]
            for uid in expired:
                del self._store[uid]
            return len(expired)


# Modul-globaler Singleton – im Test-Setup über clear() resetbar.
_key_cache = KeyCache()


def get_key_cache() -> KeyCache:
    return _key_cache
