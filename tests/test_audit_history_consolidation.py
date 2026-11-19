"""Regression for bounded, correctly filtered, concurrent audit history."""
import concurrent.futures
from backend.security.audit_log import AuditLogger


def test_bounded_history_with_filter_and_no_full_snapshot(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    logger = AuditLogger(max_history=3)
    for i in range(5):
        logger.record("owner", f"operation-{i}", "compute",
                      "DENIED" if i % 2 else "ALLOWED", "bounded")
    assert len(logger._records) == 3
    assert [r["operation"] for r in logger.history(limit=2)] == ["operation-4", "operation-3"]
    assert [r["operation"] for r in logger.history(limit=5, decision="DENIED")] == ["operation-3"]
    assert logger.history(limit=0) == []


def test_concurrent_append_and_eviction_remain_bounded(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    logger = AuditLogger(max_history=10)
    def write(i):
        return logger.record("owner", f"work-{i}", "compute", "ALLOWED", "test")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(write, range(50)))
    assert len(logger._records) == 10
    assert len(logger.history(limit=100)) == 10
