from pathlib import Path


def test_legacy_frontend_dead_files_are_removed():
    removed_paths = [
        "frontend/src/hooks/useWorkflowProject.js",
        "frontend/src/components/Keyframes/KeyframeStudio.jsx",
        "frontend/src/components/Merge/MergePanel.jsx",
        "frontend/src/services/merge.js",
        "frontend/src/hooks/useFileUpload.js",
        "frontend/src/components/Input/FilePreview.jsx",
    ]

    for path in removed_paths:
        assert not Path(path).exists(), f"expected dead frontend file to be removed: {path}"


def test_legacy_backend_dead_files_are_removed():
    removed_paths = [
        "backend/v1/app/generate/service/task_submission.py",
        "backend/v1/app/generate/dao/generation.py",
    ]

    for path in removed_paths:
        assert not Path(path).exists(), f"expected dead backend file to be removed: {path}"
