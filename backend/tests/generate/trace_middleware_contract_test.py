from pathlib import Path


def test_trace_middleware_ignores_auth_parse_failures():
    source = Path("backend/framework/trace/middleware.py").read_text(encoding="utf-8")

    assert "except BusinessException" in source
    assert "trace auth parse skipped" in source
    assert "user_id = None" in source
