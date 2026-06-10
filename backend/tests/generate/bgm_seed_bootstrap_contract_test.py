from pathlib import Path


def test_startup_bootstrap_invokes_bgm_seed_sync():
    source = Path("backend/v1/main.py").read_text(encoding="utf-8")

    assert "ensure_seed_bgm_assets" in source
    assert "ensure_seed_bgm_assets()" in source


def test_schema_bootstrap_reads_repo_seed_bgm_file():
    source = Path("backend/store/database/schema_bootstrap.py").read_text(encoding="utf-8")

    assert "seed_bgm_assets.json" in source
    assert "bgm_library" in source


def test_repo_contains_seed_bgm_asset_manifest():
    seed_path = Path("resources/seed_bgm_assets.json")

    assert seed_path.exists()
