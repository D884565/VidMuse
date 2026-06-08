from pathlib import Path


def test_concat_audio_clips_uses_mp3_compatible_codec_for_mp3_output():
    source = Path("backend/ffmpeg/pyutils.py").read_text(encoding="utf-8")
    section = source[source.index("def concat_audio_clips"):source.index("def append_tail_silence")]

    assert 'output_path = output_path or self._generate_temp_path(suffix=".mp3", prefix="concat")' in section
    assert '"-c:a", "libmp3lame"' in section
    assert '"-c:a", "aac"' not in section
