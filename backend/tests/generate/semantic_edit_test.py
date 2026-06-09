"""语义编辑测试：验证 apply_frame_modifications 支持 replace 指令格式"""
from types import SimpleNamespace
from backend.v1.app.generate.service.chat.chat_service import apply_frame_modifications


def _make_frame(description="", narration="", image_prompt="", video_prompt=""):
    return SimpleNamespace(
        description=description,
        narration=narration,
        image_prompt=image_prompt,
        video_prompt=video_prompt,
        duration=5.0,
        ai_params=None,
    )


# ── replace 指令 ─────────────────────────────────────────────

def test_replace_single_field():
    """replace 指令替换单个字段"""
    frame = _make_frame(description="一个男生手持产品展示")
    apply_frame_modifications(frame, {
        "description": {"replace": ["男生", "女生"]},
    })
    assert frame.description == "一个女生手持产品展示"


def test_replace_multiple_fields():
    """replace 指令同时替换多个字段"""
    frame = _make_frame(
        description="男生展示89元产品",
        image_prompt="男生站在白色背景前",
        narration="男生说这个产品很好",
    )
    apply_frame_modifications(frame, {
        "description": {"replace": ["男生", "女生"]},
        "image_prompt": {"replace": ["男生", "女生"]},
        "narration": {"replace": ["男生", "女生"]},
    })
    assert "女生" in frame.description
    assert "女生" in frame.image_prompt
    assert "女生" in frame.narration
    assert "男生" not in frame.description
    assert "男生" not in frame.image_prompt
    assert "男生" not in frame.narration


def test_replace_price():
    """replace 指令替换价格"""
    frame = _make_frame(description="这款产品只要89元，非常划算")
    apply_frame_modifications(frame, {
        "description": {"replace": ["89元", "109元"]},
    })
    assert frame.description == "这款产品只要109元，非常划算"
    assert "89元" not in frame.description


def test_replace_old_text_not_found():
    """旧文本不存在时跳过该字段"""
    frame = _make_frame(description="一个女生手持产品")
    apply_frame_modifications(frame, {
        "description": {"replace": ["男生", "女生"]},
    })
    # 没有"男生"，不做修改
    assert frame.description == "一个女生手持产品"


def test_replace_multiple_occurrences():
    """替换所有出现的旧文本"""
    frame = _make_frame(description="男生和男生一起看产品")
    apply_frame_modifications(frame, {
        "description": {"replace": ["男生", "女生"]},
    })
    assert frame.description == "女生和女生一起看产品"


# ── 整段覆写（兼容旧格式）─────────────────────────────────────

def test_string_overwrite():
    """字符串格式整段覆写"""
    frame = _make_frame(narration="原来的旁白内容")
    apply_frame_modifications(frame, {
        "narration": "新的旁白内容，语气更活泼",
    })
    assert frame.narration == "新的旁白内容，语气更活泼"


def test_mixed_format():
    """混合使用 replace 和整段覆写"""
    frame = _make_frame(
        description="男生展示产品，只要89元",
        narration="原来的旁白",
    )
    apply_frame_modifications(frame, {
        "description": {"replace": ["男生", "女生"]},
        "narration": "全新旁白，语气活泼",
    })
    assert frame.description == "女生展示产品，只要89元"
    assert frame.narration == "全新旁白，语气活泼"


# ── description → image_prompt 同步 ───────────────────────────

def test_replace_description_syncs_image_prompt():
    """replace 修改 description 时，image_prompt 也做同样的 replace（保留自己的内容）"""
    frame = _make_frame(
        description="男生展示产品",
        image_prompt="男生站在白色背景前",
    )
    apply_frame_modifications(frame, {
        "description": {"replace": ["男生", "女生"]},
    })
    assert frame.description == "女生展示产品"
    assert frame.image_prompt == "女生站在白色背景前"  # 保留自己的内容，只替换匹配的文本


def test_replace_description_does_not_override_explicit_image_prompt():
    """显式修改 image_prompt 时不同步"""
    frame = _make_frame(
        description="男生展示产品",
        image_prompt="男生站在白色背景前",
    )
    apply_frame_modifications(frame, {
        "description": {"replace": ["男生", "女生"]},
        "image_prompt": {"replace": ["白色", "蓝色"]},
    })
    assert frame.description == "女生展示产品"
    assert frame.image_prompt == "男生站在蓝色背景前"


def test_replace_description_does_not_overwrite_unrelated_image_prompt():
    """description replace 不覆盖不含旧文本的 image_prompt"""
    frame = _make_frame(
        description="男生展示产品",
        image_prompt="产品特写，白色背景，柔光",
    )
    apply_frame_modifications(frame, {
        "description": {"replace": ["男生", "女生"]},
    })
    assert frame.description == "女生展示产品"
    assert frame.image_prompt == "产品特写，白色背景，柔光"  # 不含"男生"，不被覆盖


# ── 边界情况 ─────────────────────────────────────────────────

def test_empty_modifications():
    """空 modifications 不做任何修改"""
    frame = _make_frame(description="原始内容")
    apply_frame_modifications(frame, {})
    assert frame.description == "原始内容"


def test_none_modifications():
    """None modifications 不做任何修改"""
    frame = _make_frame(description="原始内容")
    apply_frame_modifications(frame, None)
    assert frame.description == "原始内容"


def test_unknown_field_ignored():
    """未知字段名被忽略"""
    frame = _make_frame(description="原始内容")
    apply_frame_modifications(frame, {
        "unknown_field": {"replace": ["旧", "新"]},
    })
    assert frame.description == "原始内容"


def test_non_editable_field_ignored():
    """非可编辑字段被忽略（如 status）"""
    frame = _make_frame(description="原始内容")
    frame.status = 2
    apply_frame_modifications(frame, {
        "status": {"replace": ["2", "3"]},
    })
    assert frame.status == 2


# ── contract test ─────────────────────────────────────────────

def test_apply_frame_modifications_supports_replace_format():
    """合约测试：apply_frame_modifications 支持 replace 指令格式"""
    import inspect
    source = inspect.getsource(apply_frame_modifications)
    assert 'replace' in source, "apply_frame_modifications 应支持 replace 指令格式"
    assert 'isinstance(value, dict)' in source, "应检查 dict 类型的 value"
