from datetime import datetime

from backend.v1.app.generate.service.chat.chat_service import ChatService


class FakeFrame:
    def __init__(self, *, frame_id: int, sequence: int, last_edited_at: datetime | None):
        self.id = frame_id
        self.sequence = sequence
        self.last_edited_at = last_edited_at


def test_detect_external_edits_accepts_serialized_history_messages():
    frames = [
        FakeFrame(
            frame_id=51,
            sequence=2,
            last_edited_at=datetime.fromisoformat("2026-06-08T18:00:01"),
        )
    ]
    history = [
        {"role": "assistant", "content": "剧本已生成", "created_at": "2026-06-08T17:59:59"},
        {"role": "user", "content": "继续", "created_at": "2026-06-08T18:00:00"},
    ]

    edited = ChatService._detect_external_edits(frames, history)

    assert edited == [
        {
            "frame_id": 51,
            "sequence": 2,
            "edited_at": "2026-06-08T18:00:01",
        }
    ]
