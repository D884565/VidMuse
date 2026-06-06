from pathlib import Path


def test_upload_bitmap_uses_redis_backed_bitmap_contract():
    source = Path("backend/v1/app/assets/core/upload_bitmap.py").read_text(encoding="utf-8")

    assert "Redis" in source or "redis" in source
    assert "setbit" in source.lower()
    assert "getbit" in source.lower() or "bitcount" in source.lower()
    assert "get_uploaded_indexes" in source
    assert "clear" in source

