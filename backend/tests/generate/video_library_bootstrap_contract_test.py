from pathlib import Path


def test_video_library_service_does_not_eagerly_create_storage_client_in_init():
    source = Path("backend/v1/app/admin/video_library/service/video_library_service.py").read_text(encoding="utf-8")

    assert "self._obj_store = None" in source
    assert "def obj_store(self):" in source
    assert "self._obj_store = get_storage_client()" in source

