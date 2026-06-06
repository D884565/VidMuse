from pathlib import Path
import importlib
import sys


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
        "backend/v1/app/taskTrace/task_service.py",
        "backend/v1/app/taskTrace/task_reconciliation.py",
    ]

    for path in removed_paths:
        assert not Path(path).exists(), f"expected dead backend file to be removed: {path}"


def test_legacy_backend_dead_directories_are_removed():
    removed_dirs = [
        "backend/v1/app/client",
    ]

    for path in removed_dirs:
        assert not Path(path).exists(), f"expected dead backend directory to be removed: {path}"


def test_search_package_import_stays_lightweight():
    prefixes = (
        "backend.v1.app.search",
        "backend.v1.app.search.agent",
        "backend.v1.app.search.processors",
        "backend.v1.app.search.tools",
    )
    for name in list(sys.modules):
        if name.startswith(prefixes):
            sys.modules.pop(name)

    module = importlib.import_module("backend.v1.app.search")

    assert hasattr(module, "RAGServiceAdapter")
    assert hasattr(module, "agent_trace_service")
    assert not any(name.startswith("backend.v1.app.search.agent") for name in sys.modules)
    assert not any(name.startswith("backend.v1.app.search.processors") for name in sys.modules)
    assert not any(name.startswith("backend.v1.app.search.tools") for name in sys.modules)


def test_asset_controller_import_path_is_valid():
    importlib.import_module("backend.v1.app.assets.controller.asset_controller")


def test_slice_service_import_path_is_valid():
    importlib.import_module("backend.v1.app.slice.service.slice_service")
