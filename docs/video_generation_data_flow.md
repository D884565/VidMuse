# VidMuse 鍚庣瑙嗛鐢熸垚鏁版嵁娴佽浆鏂囨。

## 2026-05-30 workflow contract

- Render submission is policy-based: manual renders validate existing images first, while `auto_render` queues the full chain with `trigger_source="auto_render"`.
- `generate_video_task` records `trigger_source` in step snapshots so task history can distinguish manual and automatic runs.
- TTS uses bounded HTTP retry and returns `TtsResult` with `provider`, `fallback_used`, and `warning`. A silent fallback is not considered success unless degraded audio is explicitly allowed.
- Frame video composition is strict by default; failed Seedance segments raise and fail the task rather than silently inserting placeholders.
- Existing clean `frame.video_url` assets are downloaded and validated for reuse. Dirty or stale assets are regenerated.
- Duration validation is centralized in `generation_limits.py`; script generation and storyboard edits share the same normalized target-duration rule.
- The frontend should disable busy controls from `workflow_stage` and `stage_status`, not only legacy `project.status`.

## 涓€銆佽棰戠敓鎴愬畬鏁存祦绋?
鏁翠釜瑙嗛鐢熸垚鍒嗕负涓ゅぇ闃舵锛?*鍓ф湰鐢熸垚锛堝悓姝ワ級** 鍜?**瑙嗛鐢熶骇锛圕elery 寮傛浠诲姟锛?*銆?
### 闃舵 1锛氶」鐩垱寤?+ 鍓ф湰鐢熸垚锛堝悓姝ワ級

鍏ュ彛锛歚POST /generate/v1/projects`

1. 鐢ㄦ埛鎻愪氦 `ProjectCreate`锛屽寘鍚?`title`銆乣user_prompt`銆乣style`銆乣target_audience`銆乣key_points`銆乣avoid`銆乣rag_weight`銆乣target_duration`銆乣voice_type`銆乣reference_images`銆乣product_url` 绛夊瓧娈?2. 濡傛灉鎻愪緵浜?`product_url`锛岄€氳繃 `product_crawl_service.crawl()` 鎶撳彇鍟嗗搧淇℃伅锛岃浆涓?JSON 瀛樺叆 `project.product_info`
3. 鍐欏叆 `projects` 琛紝鐘舵€佷负 `draft`
4. 璋冪敤 `script_generation_service.generate_script()` 鐢熸垚鍓ф湰锛圠LM 璋冪敤锛夛紝灏嗘瘡涓満鏅啓鍏?`frames` 琛紝椤圭洰鐘舵€佸彉涓?`script_ready`
5. 璋冪敤 `video_generation_service.submit_generation_task()` 鎻愪氦 Celery 寮傛浠诲姟锛岄」鐩姸鎬佸彉涓?`processing`

### 闃舵 2锛氳棰戠敓浜э紙Celery 寮傛浠诲姟锛?
鏂囦欢锛歚backend/v1/app/generate/temp/video_tasks.py`

| 姝ラ | 鎿嶄綔 | 杈撳叆 | 杈撳嚭 |
|------|------|------|------|
| Step 1 | 璇诲彇甯ф暟鎹?| - | frames 鍒楄〃 |
| Step 2 | 椤圭洰绾?TTS | frame.ai_params.text锛堟嫾鎺ワ級 | project.audio_url |
| Step 2.5 | 甯х骇 TTS | frame.ai_params.text | frame.audio_url |
| Step 3 | 鍥剧墖鐢熸垚 | frame.description | frame.image_url |
| Step 4 | 瑙嗛鐢熸垚 | frame.prompt + frame.image_url | 甯ц棰戠墖娈?|
| Step 5 | 鎷兼帴 | 鎵€鏈夊抚瑙嗛鐗囨 | 鍚堝苟瑙嗛 |
| Step 5.5 | 闊抽鍚堝苟 | TTS 閰嶉煶 + 鍚堝苟瑙嗛 | 甯﹂厤闊宠棰?|
| Step 6 | 涓婁紶 | 鎴愬搧瑙嗛 | project.video_output_url |

---

## 浜屻€丩LM 璋冪敤璇︽儏

### 璋冪敤 1锛氬墽鏈敓鎴?
**鏂囦欢**锛歚backend/v1/app/generate/service/script_generation.py` (绗?348-390 琛?

**System Prompt**锛?```
浣犳槸涓€涓笓涓氱殑甯﹁揣瑙嗛缂栧墽锛屾搮闀垮垱浣滅煭瑙嗛鍓ф湰銆?浣犵殑杈撳嚭蹇呴』鏄弗鏍肩殑 JSON 鏍煎紡锛屼笉瑕佸寘鍚换浣曞叾浠栨枃瀛椼€?image_prompt 瑕佽缁嗘弿杩扮敾闈紙涓讳綋銆佽儗鏅€佸厜绾裤€佽壊璋冿級锛岀敤浜?AI 鍥剧墖鐢熸垚銆?video_prompt 瑕佹弿杩伴暅澶磋繍鍔ㄥ拰鍔ㄦ€佹晥鏋滐紝鐢ㄤ簬 AI 瑙嗛鐢熸垚銆?overlay 鐢ㄤ簬鎸囧畾鐢婚潰涓婂彔鍔犵殑鍏抽敭鏂囧瓧锛岀畝鐭湁鍔涳紝涓嶈秴杩?0涓瓧锛岀敤浜庢彁楂樿浆鍖栫巼銆?```

**User Prompt 缁撴瀯**锛堢敱 `_build_prompt()` 鏂规硶缁勮锛夛細

```
浣犳槸涓€涓笓涓氱殑甯﹁揣瑙嗛缂栧墽...璇风敓鎴愪竴涓害{target_duration}绉掔殑甯﹁揣鐭棰戝墽鏈€?
## 鐢ㄦ埛鍒涗綔鎰忓浘锛堝繀椤讳弗鏍奸伒寰級
{project.user_prompt}

## 琛ュ厖瑕佹眰
- 椋庢牸锛歿style}
- 鐩爣鍙椾紬锛歿target_audience}
- 鍏抽敭鍗栫偣锛歿key_points}
- 閬垮厤鍐呭锛歿avoid}

## 鍟嗗搧淇℃伅
- 鏍囬锛歿title}
- 鎻忚堪锛歿description}
- 浠锋牸锛歿price}
- 瑙勬牸锛歿specs}

## 鐢ㄦ埛鎻愪緵鐨勫弬鑰冨浘鐗?{reference_images URLs}

## 鍙傝€冭祫鏂欙紙浠呬緵鍙傝€冨€熼壌锛屼笉瑕佺収鎼級
### 鍙傝€冨墽鏈ā鏉?{RAG 妫€绱㈢粨鏋渳
### 鍙傝€冭瑙夌礌鏉?{RAG 妫€绱㈢粨鏋渳
### 鍟嗗搧鐭ヨ瘑鍙傝€?{RAG 妫€绱㈢粨鏋渳

## 杈撳嚭瑕佹眰
{JSON 妯℃澘}

## 鍦烘櫙绫诲瀷璇存槑
{鍦烘櫙绫诲瀷瀹氫箟}

## 娉ㄦ剰浜嬮」
{鐢熸垚娉ㄦ剰浜嬮」}
```

**璋冪敤鍙傛暟**锛?- `temperature`: 0.7
- `max_tokens`: 4096

---

### 璋冪敤 2锛氬璇濆紡璋冩暣 - 褰卞搷鑼冨洿鍒嗘瀽

**鏂囦欢**锛歚backend/v1/app/generate/service/chat_service.py` (绗?192-232 琛?

**System Prompt**锛?```
浣犳槸瑙嗛璋冩暣鍔╂墜锛屽垽鏂敤鎴锋兂璋冩暣鍝簺鍦烘櫙銆傚彧杩斿洖JSON銆?```

**User Prompt**锛?```
鐢ㄦ埛鎯宠璋冩暣瑙嗛銆備互涓嬫槸褰撳墠瑙嗛鐨勫満鏅垪琛細
  鍦烘櫙1 (id=xxx, type=0): 鐢婚潰鎻忚堪鍓?0瀛?..
  鍦烘櫙2 ...

鐢ㄦ埛鐨勮皟鏁磋姹傦細{user_message}

璇峰垽鏂奖鍝嶈寖鍥达紝杩斿洖 JSON锛歿"scope": "all" | "single", "frame_id": null | int}
```

**璋冪敤鍙傛暟**锛?- `temperature`: 0.3
- `max_tokens`: 256

---

### 璋冪敤 3锛氬璇濆紡璋冩暣 - 甯у唴瀹归噸鏂扮敓鎴?
**鏂囦欢**锛歚backend/v1/app/generate/service/chat_service.py` (绗?278-297 琛?

**System Prompt**锛?```
浣犳槸甯﹁揣瑙嗛缂栧墽銆傚彧杩斿洖JSON銆?```

**User Prompt**锛堢敱 `_build_frame_regenerate_prompt()` 缁勮锛夛細
```
浣犳槸涓€涓笓涓氱殑甯﹁揣瑙嗛缂栧墽銆傝涓轰互涓嬪満鏅噸鏂扮敓鎴愬唴瀹广€?
## 鍟嗗搧淇℃伅
- 鏍囬锛歿project.title}
- 鎻忚堪锛歿project.description}

## 鐢ㄦ埛鍘熷鎰忓浘
{project.user_prompt}

## 褰撳墠鍦烘櫙
- 绫诲瀷锛歿frame.scene_type}
- 搴忓彿锛歿frame.sequence}
- 褰撳墠鐢婚潰鎻忚堪锛歿frame.description}

## 瀵硅瘽鍘嗗彶
user: xxx
assistant: xxx
锛堟渶杩?0鏉★級

## 璋冩暣鎸囦护
{instruction}

璇疯繑鍥?JSON锛?{"image_prompt": "...", "video_prompt": "...", "text": "...", "overlay_text": "...", "camera": "...", "mood": "..."}
```

**璋冪敤鍙傛暟**锛?- `temperature`: 0.7
- `max_tokens`: 1024

---

## 涓夈€佹ā鍨嬭緭鍑烘牸寮?
### 鍓ф湰鐢熸垚杈撳嚭鏍煎紡

```json
{
  "video_meta": {
    "product_name": "鍟嗗搧鍚嶇О",
    "target_duration": 15,
    "style": "fashion/tech/food/lifestyle",
    "aspect_ratio": "9:16",
    "hook_line": "涓€鍙ヨ瘽寮€鍦洪噾鍙?
  },
  "scenes": [
    {
      "scene_id": 1,
      "type": "hook/selling_point/detail/social_proof/price/cta",
      "duration": 5,
      "text": "閰嶉煶鏂囨锛堝彛璇寲锛?,
      "voice_style": "excited/confident/urgent/warm/professional",
      "visual": {
        "image_prompt": "璇︾粏鐢婚潰鎻忚堪锛堜富浣撱€佽儗鏅€佸厜绾裤€佽壊璋冦€佹瀯鍥撅級",
        "video_prompt": "闀滃ご杩愬姩鍜屽姩鎬佹晥鏋滄弿杩?,
        "camera": "push_in/pull_out/pan_left/pan_right/static/close_up/wide_shot",
        "mood": "warm/bright/dark/energetic/elegant",
        "overlay": {
          "text": "鍙犲姞鏂囧瓧锛堜笉瓒呰繃10瀛楋級",
          "position": "top/center/bottom",
          "style": "highlight/price_tag/call_to_action/subtle"
        }
      }
    }
  ],
  "audio": {
    "tts_voice": "zh_female_cancan_mars_bigtts",
    "bgm": "鑳屾櫙闊充箰椋庢牸鎻忚堪",
    "bgm_volume": 0.3
  }
}
```

### 瀵硅瘽璋冩暣杈撳嚭鏍煎紡

**褰卞搷鑼冨洿鍒嗘瀽**锛?```json
{
  "scope": "all" | "single",
  "frame_id": null | int
}
```

**甯ч噸鏂扮敓鎴?*锛?```json
{
  "image_prompt": "...",
  "video_prompt": "...",
  "text": "...",
  "overlay_text": "...",
  "camera": "...",
  "mood": "..."
}
```

---

## 鍥涖€佹暟鎹祦杞浘

```
鐢ㄦ埛杈撳叆 (ProjectCreate)
    鈹?    鈻?[Project 琛╙ 鈹€鈹€ title, description, user_prompt, style, target_audience,
                key_points, avoid, rag_weight, target_duration, voice_type,
                product_url, product_info(JSON), reference_images(JSON)
    鈹?    鈹? script_generation_service.generate_script()
    鈹? 鈹溾攢鈹€ RAG 妫€绱?鈫?鍙傝€冩枃鏈?    鈹? 鈹溾攢鈹€ _build_prompt() 鈫?瀹屾暣 prompt
    鈹? 鈹溾攢鈹€ LLM 璋冪敤 鈫?JSON 鍓ф湰
    鈹? 鈹斺攢鈹€ 閫愬満鏅啓鍏?Frame 琛?    鈹?    鈻?[Frame 琛╙ 鈹€鈹€ sequence, scene_type(int), description(=image_prompt),
              prompt(=video_prompt), text_overlay, duration, ai_params(JSON),
              metadata_(JSON), status=0(寰呯敓鎴?
    鈹?    鈹? video_generation_service.submit_generation_task()
    鈹? 鈫?Celery 寮傛浠诲姟 generate_video_task
    鈹?    鈻?[Step 2: TTS]
    鈹? 璇诲彇 frame.ai_params.text 鈫?鎷兼帴 鈫?鐏北寮曟搸 TTS API
    鈹? 鈫?project.audio_url (椤圭洰绾?
    鈹? 鈫?frame.audio_url (甯х骇)
    鈹?    鈻?[Step 3: 鍥剧墖鐢熸垚]
    鈹? 璇诲彇 frame.description 鈫?鐏北寮曟搸 Seedream 4.5 API
    鈹? 鍙傝€冨浘: product_info.main_images[0]
    鈹? 鈫?frame.image_url, frame.status=2
    鈹?    鈻?[Step 4: 瑙嗛鐢熸垚]
    鈹? 璇诲彇 frame.prompt + frame.ai_params(camera,mood)
    鈹? + frame.image_url 浣滀负棣栧抚
    鈹? 鈫?Seedance 1.5 API (鍥哄畾5绉?
    鈹? 鈫?瑁佸壀/琛ユ椂鍒?frame.duration
    鈹?    鈻?[Step 5: 鎷兼帴]
    鈹? FFmpeg concat 鎵€鏈夊抚瑙嗛鐗囨
    鈹?    鈻?[Step 5.5: 闊抽鍚堝苟]
    鈹? FFmpeg replace_audio: TTS閰嶉煶 鈫?瑙嗛闊宠建
    鈹?    鈻?[Step 6: 涓婁紶]
    鈹? 鈫?project.video_output_url
    鈹? 鈫?Asset 琛ㄨ褰?    鈹? 鈫?project.status = "completed"
```

---

## 浜斻€佸叧閿暟鎹槧灏勫叧绯?
| LLM 杈撳嚭瀛楁 | 鏁版嵁搴撳瓧娈?| 鐢ㄩ€?|
|-------------|-----------|------|
| `scene.type` (瀛楃涓? | `frame.scene_type` (鏁存暟) | 鍦烘櫙绫诲瀷锛岄€氳繃 SCENE_TYPE_MAP 杞崲 |
| `visual.image_prompt` | `frame.description` | 鐢ㄤ簬鍥剧墖鐢熸垚 prompt |
| `visual.video_prompt` | `frame.prompt` | 鐢ㄤ簬瑙嗛鐢熸垚 prompt |
| `visual.overlay.text` | `frame.text_overlay` | 鐢婚潰鍙犲姞鏂囧瓧 |
| `text` | `frame.ai_params.text` | 閰嶉煶鏂囨 |
| `voice_style` | `frame.ai_params.voice_style` | 璇煶椋庢牸 |
| `camera` | `frame.ai_params.camera` | 闀滃ご杩愬姩 |
| `mood` | `frame.ai_params.mood` | 鐢婚潰姘涘洿 |

### 鍦烘櫙绫诲瀷鏄犲皠 (SCENE_TYPE_MAP)

| LLM 杈撳嚭 | 鏁版嵁搴撳€?| 鍚箟 |
|----------|---------|------|
| hook | 0 | 寮€鍦哄惛寮?|
| selling_point | 1 | 鍗栫偣灞曠ず |
| price | 1 | 浠锋牸灞曠ず |
| detail | 2 | 缁嗚妭灞曠ず |
| social_proof | 2 | 绀句細璇佹槑 |
| cta | 4 | 琛屽姩鍙峰彫 |

---

## 鍏€佹牳蹇冩枃浠剁储寮?
| 鏂囦欢 | 鑱岃矗 |
|------|------|
| `backend/v1/app/generate/controller/generation.py` | API 璺敱灞?|
| `backend/v1/app/generate/service/script_generation.py` | 鍓ф湰鐢熸垚鏈嶅姟 |
| `backend/v1/app/generate/service/video_generation.py` | 瑙嗛鐢熸垚璋冨害鏈嶅姟 |
| `backend/v1/app/generate/temp/video_tasks.py` | Celery 寮傛浠诲姟 |
| `backend/v1/app/generate/service/image_generation_service.py` | 鍥剧墖鐢熸垚鏈嶅姟 |
| `backend/v1/app/generate/service/video_composer.py` | 瑙嗛鍚堟垚鏈嶅姟 |
| `backend/v1/app/generate/service/tts_service.py` | TTS 璇煶鍚堟垚鏈嶅姟 |
| `backend/v1/app/generate/service/chat_service.py` | 瀵硅瘽寮忚皟鏁存湇鍔?|
| `backend/providers/volcano.py` | 鐏北寮曟搸缁熶竴瀹㈡埛绔?|
| `backend/providers/dto/schema.py` | 璇锋眰/鍝嶅簲鏁版嵁缁撴瀯 |
