from backend.v1.app.generate.tasks import video_tasks


def test_should_inline_frame_video_tasks_when_worker_cli_uses_solo(monkeypatch):
    monkeypatch.setattr(video_tasks.celery_app.conf, "worker_pool", "prefork", raising=False)
    monkeypatch.delenv("CELERY_WORKER_POOL", raising=False)
    monkeypatch.delenv("CELERYD_POOL", raising=False)
    monkeypatch.delenv("WORKER_POOL", raising=False)
    monkeypatch.setattr(video_tasks.sys, "argv", ["celery", "worker", "--pool=solo"])

    assert video_tasks._should_run_frame_video_tasks_inline() is True


def test_should_not_inline_frame_video_tasks_for_prefork_runtime(monkeypatch):
    monkeypatch.setattr(video_tasks.celery_app.conf, "worker_pool", "prefork", raising=False)
    monkeypatch.delenv("CELERY_WORKER_POOL", raising=False)
    monkeypatch.delenv("CELERYD_POOL", raising=False)
    monkeypatch.delenv("WORKER_POOL", raising=False)
    monkeypatch.setattr(video_tasks.sys, "argv", ["celery", "worker", "--pool=prefork"])

    assert video_tasks._should_run_frame_video_tasks_inline() is False
