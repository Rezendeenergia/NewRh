"""
Cache em memória thread-safe para o NewRH.
TTLs curtos garantem dados frescos sem sobrecarregar o Supabase.
"""
import time
import threading

_store: dict = {}
_lock = threading.Lock()


def get(key: str):
    with _lock:
        entry = _store.get(key)
        if entry and time.monotonic() < entry["exp"]:
            return entry["data"]
        if entry:
            del _store[key]
        return None


def set(key: str, data, ttl: int = 15):
    with _lock:
        _store[key] = {"data": data, "exp": time.monotonic() + ttl}


def invalidate(*prefixes: str):
    """Remove todas as chaves que começam com qualquer um dos prefixos."""
    with _lock:
        to_del = [k for k in _store for p in prefixes if k.startswith(p)]
        for k in to_del:
            del _store[k]


def invalidate_processo(processo_id: int):
    """Atalho para invalidar tudo relacionado a um processo específico."""
    invalidate(f"proc:{processo_id}", "lista:", "stats")
