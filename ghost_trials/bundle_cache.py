"""Memoized evidence-bundle verification.

Recomputing every SHA-256 on each read made list endpoints cost gigabytes of hashing. A result is reused
only while every file in the bundle keeps the same name, size and modification time; any change re-verifies.
"""
import copy
import threading
from collections import OrderedDict
from pathlib import Path

_MAX_ENTRIES = 4096
_cache: OrderedDict = OrderedDict()
_lock = threading.Lock()


def fingerprint(directory: Path) -> tuple:
    return tuple(sorted((path.name, stat.st_size, stat.st_mtime_ns)
                        for path in directory.iterdir() if path.is_file() for stat in [path.stat()]))


def cached_verification(kind: str, directory: Path, expected: str, verify):
    """Return verify(directory, expected), reusing the result while the bundle's files are unchanged.

    Failures are cached too and re-raised, so a corrupt bundle stays corrupt until its files change.
    """
    key = (kind, str(directory), expected, fingerprint(directory))
    with _lock:
        hit = _cache.get(key)
        if hit is not None:
            _cache.move_to_end(key)
    if hit is None:
        try:
            hit = ("ok", verify(directory, expected))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            # Store the type and arguments, not the instance: re-raising one instance keeps growing its
            # traceback and would pin every frame's locals in memory.
            hit = ("error", (type(exc), exc.args))
        with _lock:
            _cache[key] = hit
            while len(_cache) > _MAX_ENTRIES:
                _cache.popitem(last=False)
    if hit[0] == "error":
        kind, args = hit[1]
        raise kind(*args)
    return copy.deepcopy(hit[1])


def cpu_bundle(directory: Path, expected: str) -> dict:
    from .cpu_evidence import verify_cpu_bundle
    return cached_verification("cpu", directory, expected, verify_cpu_bundle)


def worker_bundle(directory: Path, expected: str) -> dict:
    from .independent_validation import verify_bundle
    return cached_verification("worker", directory, expected, verify_bundle)


def clear():
    with _lock:
        _cache.clear()
