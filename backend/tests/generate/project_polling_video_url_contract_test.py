from pathlib import Path


def test_project_polling_reads_video_output_url_from_project_detail():
    source = Path("frontend/src/hooks/useProjectPolling.js").read_text(encoding="utf-8")

    assert "setVideoUrl(data.video_output_url || data.video_url || null)" in source
    assert "data.video_output_url" in source
