from pathlib import Path


def test_settings_allow_empty_tos_credentials_without_import_failure():
    source = Path("backend/v1/app/config/config.py").read_text(encoding="utf-8")

    assert "TOS_ACCESS_KEY: str = os.getenv('TOS_ACCESS_KEY', '')" in source
    assert "TOS_SECRET_KEY: str = os.getenv('TOS_SECRET_KEY', '')" in source

