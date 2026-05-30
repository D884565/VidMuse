from pathlib import Path


def test_project_creation_persists_initial_conversation_message():
    source = Path("backend/v1/app/generate/controller/generation.py").read_text(encoding="utf-8")

    assert "project_initial_message_builder.build(" in source
    assert "Conversation(" in source
    assert "blocks=initial_message[\"blocks\"]" in source
    assert "metadata_=initial_message[\"metadata\"]" in source
