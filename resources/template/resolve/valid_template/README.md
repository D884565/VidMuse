# 校验模板更新说明

## 2026-06-04 第二次更新（全中文化）
- 所有字段名已统一为中文，移除英文key
- slice.json 字段翻译：
  - bgm_style → 背景音乐风格
  - bgm_speed → 背景音乐速度
  - voice_speed → 人声语速
  - has_sound_effect → 是否有音效
  - audio_mood → 音频情绪
  - scene → 场景
  - shot_type → 镜头类型
  - color_style → 色彩风格
  - subtitle_style → 字幕样式
  - creator_emotion → 创作者情绪
  - audience_emotion → 观众情绪
  - opening_style → 开场风格
  - speech_style → 话术风格
  - keywords → 关键词
  - category → 商品品类
  - promotion → 促销方式
- video.json 字段翻译：
  - strategy_skeleton → 策略框架
  - core_template → 核心模板
  - hook_strategy → 钩子策略
    - hook_type → 钩子类型
    - hook_emotion → 钩子情绪
    - hook_duration → 钩子时长
  - narrative_flow → 叙事流程
    - structure_type → 结构类型
    - step_sequence → 步骤序列
  - emotion_flow_curve → 情绪流动曲线
    - first_stage_emotion → 开篇阶段情绪
    - mid_stage_emotion → 中间阶段情绪
    - last_stage_emotion → 收尾阶段情绪
    - emotion_change_type → 情绪变化类型
  - rhythm_strategy → 节奏策略
    - overall_speed → 整体速度
    - clip_frequency → 剪辑频率
    - rhythm_change → 节奏变化
  - tension_strategy → 张力策略
    - tension_build_method → 张力构建方式
    - climax_position → 高潮位置
  - conversion_arrangement → 转化安排
    - selling_point_appear → 卖点出现方式
    - cta_strategy → 引导策略
  - BGM节奏匹配 → 背景音乐节奏匹配

## 2026-06-04 第一次更新
### slice_valid.json 更新
- 适配新的 slice.json 结构，将原有创作要素重构为五大域：
  1. 音频域（背景音乐风格、背景音乐速度、人声语速、是否有音效、音频情绪）
  2. 画面视觉域（场景、镜头类型、色彩风格、字幕样式）
  3. 情绪心理域（创作者情绪、观众情绪）
  4. 文案话术域（开场风格、话术风格、关键词）
  5. 商品营销域（商品品类、促销方式）
- 每个字段都添加了对应的枚举值校验，确保值在可选范围内
- 保留了原有可选字段：关键帧时间戳、一致性校验

### video_valid.json 更新
- 适配新的 video.json 结构，新增策略框架顶层对象，包含以下模块：
  1. 核心模板：核心模板类型校验
  2. 钩子策略：钩子策略校验（类型、情绪、时长）
  3. 叙事流程：叙事流程校验（结构类型、步骤序列）
  4. 情绪流动曲线：情绪曲线校验（三阶段情绪、变化类型）
  5. 节奏策略：节奏策略校验（整体速度、剪辑频率、节奏变化）
  6. 张力策略：张力策略校验（构建方式、高潮位置）
  7. 转化安排：转化安排校验（卖点出现方式、引导策略）
  8. 片段间关系：转场序列、情绪曲线、视觉节奏、背景音乐节奏匹配
- 保留了原有片段索引列表作为可选字段，兼容旧版本数据
- 所有枚举值都与新模板中的可选值保持一致

## 使用说明
1. 模板文件（slice.json、video.json）中的斜杠分隔值为示例展示所有可选选项，实际使用时应选择其中一个值
2. 校验规则会严格校验字段是否存在以及值是否在允许的枚举范围内
3. additionalProperties 设为 true，允许扩展额外字段