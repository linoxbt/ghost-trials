import os

import pytest

from ghost_trials import bundle_cache


def test_cache_reuses_result_until_bundle_files_change(tmp_path):
    (tmp_path / "telemetry.jsonl").write_text("a")
    calls = []

    def verify(directory, expected):
        calls.append(expected)
        if (directory / "telemetry.jsonl").read_text() != "a":
            raise ValueError("tampered")
        return {"status": "ok"}

    bundle_cache.clear()
    assert bundle_cache.cached_verification("t", tmp_path, "d", verify) == {"status": "ok"}
    assert bundle_cache.cached_verification("t", tmp_path, "d", verify) == {"status": "ok"}
    assert len(calls) == 1
    path = tmp_path / "telemetry.jsonl"
    path.write_text("b")
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    with pytest.raises(ValueError, match="tampered"):
        bundle_cache.cached_verification("t", tmp_path, "d", verify)
    # Returned results are copies; callers cannot poison the cache.
    path.write_text("a")
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000))
    result = bundle_cache.cached_verification("t", tmp_path, "d", verify)
    result["status"] = "mutated"
    assert bundle_cache.cached_verification("t", tmp_path, "d", verify) == {"status": "ok"}


def test_cached_failure_does_not_grow_tracebacks(tmp_path):
    (tmp_path / "telemetry.jsonl").write_text("x")

    def verify(directory, expected):
        raise ValueError("corrupt")

    bundle_cache.clear()
    depths = []
    for _ in range(3):
        try:
            bundle_cache.cached_verification("t", tmp_path, "d", verify)
        except ValueError as exc:
            depth, tb = 0, exc.__traceback__
            while tb:
                depth, tb = depth + 1, tb.tb_next
            depths.append(depth)
    assert len(set(depths)) == 1
