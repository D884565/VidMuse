# VidMuse 瑙嗛鐢熸垚 - 瀹屾暣鏁版嵁娴佽浆閾捐矾

## 2026-05-30 workflow remediation notes

- The canonical workflow is `script -> image -> video -> completed`, tracked by `projects.workflow_stage`, `projects.stage_status`, `projects.last_task_id`, and `projects.dirty_stage`.
- Manual render requires all frames to have successful HTTP `image_url` values before the video task is queued.
- `auto_render` uses the same Celery `generate_video_task`, but submits with `require_ready_images=False` and `trigger_source="auto_render"` so the full chain can generate images and video in one run.
- Project-level TTS is generated once per render. TTS failures create an explicit `TtsResult(fallback_used=True)`, and production renders fail by default unless `ALLOW_DEGRADED_AUDIO` is enabled.
- Frame video generation is strict by default. Placeholder video segments are only used when `allow_placeholder_segments=True` is passed explicitly.
- Clean `frame.video_url` values are reusable when `frame.dirty == 0`; regeneration of a frame video invalidates the project from the `video` stage onward.
- Target duration is normalized through `generation_limits.py` with a supported range of 12-20 seconds. Storyboard edits validate total frame duration against the normalized project target, not a fixed 15-second limit.
- Frontend polling must continue while `stage_status === "running"` or while a workflow stage awaits review; `script_ready` alone is not a terminal polling state.

## 鎬昏

```
鍟嗗搧淇℃伅锛圥roject 琛級
    鈫?
Step 1: LLM 鐢熸垚鍒嗛暅鑴氭湰锛堢伀灞卞紩鎿?doubao-seed-2.0-pro锛?
    鈫?
鍒嗛暅鑴氭湰 JSON锛堝瓨鍏?scripts 琛級
    鈫?
Step 2: TTS 鐢熸垚閰嶉煶锛堢伀灞卞紩鎿?TTS API锛?
    鈫?
audio.mp3
    鈫?
Step 3: 涓烘瘡涓満鏅敓鎴愬浘鐗囷紙鐏北寮曟搸 Seedream 5.0锛?
    鈫?
image_urls[]
    鈫?
Step 4: 涓烘瘡涓満鏅敓鎴愯棰戯紙鐏北寮曟搸 Seedance 1.5锛屽浘鐗囦綔棣栧抚锛?
    鈫?
video_clips[]
    鈫?
Step 5: FFmpeg 鎷兼帴鎵€鏈夎棰戠墖娈?
    鈫?
final_video.mp4
    鈫?
Step 6: 涓婁紶 TOS锛屾洿鏂伴」鐩姸鎬?
```

---

## 鎶€鏈爤

| 鐜妭 | 鏈嶅姟 | 妯″瀷/API |
|------|------|----------|
| LLM 鍓ф湰鐢熸垚 | 鐏北寮曟搸 Ark | doubao-seed-2.0-pro |
| TTS 璇煶鍚堟垚 | 鐏北寮曟搸 TTS | openspeech.bytedance.com |
| 鍥剧墖鐢熸垚 | 鐏北寮曟搸 Ark | doubao-seedream-5-0-260128 |
| 瑙嗛鐢熸垚 | 鐏北寮曟搸 Ark | Seedance 1.5 |
| 瑙嗛鎷兼帴 | 鏈湴 FFmpeg | - |
| 瀵硅薄瀛樺偍 | 鐏北寮曟搸 TOS | tos-cn-beijing.volces.com |

---

## Step 1: LLM 鐢熸垚鍒嗛暅鑴氭湰

### 鍏ュ彛

**鏂囦欢**: `backend/v1/app/generate/service/script_generation.py`
**绫?*: `ScriptGenerationService`
**鏂规硶**: `generate_script(db, project_id, target_duration)`

### 杈撳叆

浠?MySQL 璇诲彇 Project 琛細

```python
project = db.execute(select(Project).where(Project.id == project_id))
# project.title       - 鍟嗗搧鏍囬
# project.description - 鍟嗗搧鎻忚堪
# project.product_info - 鍟嗗搧璇︽儏
```

### 鎿嶄綔

1. **妫€绱㈠弬鑰冭祫鏂?*锛堝綋鍓嶄负 Mock锛孴ODO: 鎺ュ叆 ChromaDB锛?

2. **鏋勯€?Prompt**
   ```
   浣犳槸涓€涓笓涓氱殑甯﹁揣瑙嗛缂栧墽...
   鍟嗗搧鏍囬锛歿project.title}
   鍟嗗搧鎻忚堪锛歿project.description}
   鍟嗗搧璇︽儏锛歿project.product_info}
   ```

3. **璋冪敤 LLM**
   ```python
   from backend.providers import VolcanoLLM, ChatRequest, ChatMessage

   self.llm = VolcanoLLM(key=None, model_name=None)  # 鍗曚緥
   request = ChatRequest(
       messages=[
           ChatMessage(role="system", content="浣犳槸涓€涓笓涓氱殑甯﹁揣瑙嗛缂栧墽..."),
           ChatMessage(role="user", content=prompt),
       ],
       temperature=0.7,
       max_tokens=4096,
   )
   response = await loop.run_in_executor(None, self.llm.chat, request)
   ```

4. **VolcanoLLM 鍐呴儴璋冪敤**锛坄backend/providers/volcano.py`锛?
   ```python
   self.client = Ark(
       api_key=os.getenv("DOUBAO_SEED_API_KEY"),
       base_url="https://ark.cn-beijing.volces.com/api/v3",
   )
   result = self.client.chat.completions.create(
       messages=[...],
       model="doubao-seed-2.0-pro",
       stream=False,
   )
   ```

### 杈撳嚭

鍒嗛暅鑴氭湰 JSON锛屽瓨鍏?`scripts` 琛細

```json
{
  "video_meta": {
    "product_name": "绮夎壊纰庤姳瑁?,
    "target_duration": 15,
    "style": "fashion",
    "aspect_ratio": "9:16",
    "hook_line": "杩樺湪涓洪€夎瀛愬彂鎰侊紵"
  },
  "scenes": [
    {
      "scene_id": 1,
      "type": "hook",
      "duration": 5,
      "text": "濮愬浠紒杩欐潯瑁欏瓙鎴戠┛浜嗕竴鍛ㄩ兘娌℃崲锛?,
      "voice_style": "excited",
      "visual": {
        "image_prompt": "涓€浣嶅勾杞诲コ鎬х┛鐫€绮夎壊纰庤姳杩炶。瑁欙紝姝ｉ潰灞曠ず锛屾椂灏氳鎷嶏紝鑷劧鍏夌嚎锛岀敎缇庣瑧瀹癸紝鑳屾櫙妯＄硦",
        "video_prompt": "闀滃ご浠庡叏韬紦鎱㈡帹杩戣嚦鑵伴儴鐗瑰啓锛屽睍绀烘敹鑵拌璁?,
        "camera": "push_in",
        "mood": "warm",
        "overlay": {
          "text": "绮夎壊纰庤姳瑁?,
          "position": "bottom",
          "style": "highlight"
        }
      }
    },
    {
      "scene_id": 2,
      "type": "selling_point",
      "duration": 5,
      "text": "鐪嬭繖涓敹鑵拌璁★紝鍚冩拺浜嗕篃涓嶅嫆鑲氬瓙锛?,
      "voice_style": "confident",
      "visual": {
        "image_prompt": "杩炶。瑁欒叞閮ㄧ粏鑺傜壒鍐欙紝鏀惰叞璁捐锛岃ざ鐨卞鐞嗭紝妯＄壒渚ч潰灞曠ず",
        "video_prompt": "闀滃ご浠庡乏鍚戝彸缂撴參骞崇Щ锛屽睍绀鸿叞閮ㄧ嚎鏉?,
        "camera": "pan_left",
        "mood": "warm",
        "overlay": {
          "text": "娉曞紡鏀惰叞",
          "position": "bottom",
          "style": "highlight"
        }
      }
    }
  ],
  "audio": {
    "tts_voice": "zh_female_cancan_mars_bigtts",
    "bgm": "杞绘澗鎰夊揩鐨勮儗鏅煶涔?,
    "bgm_volume": 0.3
  }
}
```

### 鏁版嵁娴佽浆

```
Project 琛?鈫?ScriptGenerationService 鈫?Script 琛?
```

---

## Step 2: TTS 鐢熸垚閰嶉煶

### 鍏ュ彛

**鏂囦欢**: `backend/v1/app/generate/service/tts_service.py`
**绫?*: `TtsService`
**鏂规硶**: `generate_audio(text, voice_type)`

### 杈撳叆

```python
# 鎷兼帴鎵€鏈夊満鏅殑鏂囨
full_text = " ".join([scene.get("text", "") for scene in scenes])
tts_voice = audio_config.get("tts_voice", "zh_female_cancan_mars_bigtts")
```

### 鎿嶄綔

璋冪敤鐏北寮曟搸 TTS HTTP API锛?

```python
TTS_API_URL = "https://openspeech.bytedance.com/api/v1/tts"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer;{self.token}",  # TTS_SECRET_KEY
}

payload = {
    "app": {
        "appid": self.app_id,  # TTS_ACCESS_KEY
        "token": "fake_token",
        "cluster": "volcano_tts",
    },
    "user": {
        "uid": "vidmuse_user",
    },
    "audio": {
        "voice_type": voice_type,  # "zh_female_cancan_mars_bigtts"
        "encoding": "mp3",
        "speed_ratio": 1.0,
        "volume_ratio": 1.0,
    },
    "request": {
        "reqid": uuid.uuid4().hex,
        "text": text,
        "operation": "query",
    },
}

response = requests.post(TTS_API_URL, json=payload, headers=headers, timeout=30)
```

### 杈撳嚭

- 鏈湴闊抽鏂囦欢锛歚/tmp/tts_{uuid}.mp3`
- 涓婁紶鍒?TOS锛歚projects/{project_id}/audio_{script_id}.mp3`
- 璁板綍鍒?Asset 琛紙type=3锛岄煶棰戯級

### 鏁版嵁娴佽浆

```
Script.content 鈫?TtsService 鈫?/tmp/tts_xxx.mp3 鈫?TOS 鈫?Asset 琛?
```

---

## Step 3: 涓烘瘡涓満鏅敓鎴愬浘鐗?

### 鍏ュ彛

**鏂囦欢**: `backend/v1/app/generate/service/image_generation_service.py`
**绫?*: `ImageGenerationService`
**鏂规硶**: `generate_scene_images(scenes, project_id, product_images)`

### 杈撳叆

```python
scenes = script_content.get("scenes", [])
# 姣忎釜 scene 鍖呭惈 visual.image_prompt
```

### 鎿嶄綔

璋冪敤鐏北寮曟搸 Ark 鍥剧墖鐢熸垚 API锛?

```python
IMAGE_API_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
IMAGE_MODEL = "doubao-seedream-5-0-260128"

# 鏂囩敓鍥?
payload = {
    "model": IMAGE_MODEL,
    "prompt": image_prompt,
    "size": "2K",
    "response_format": "url",
    "sequential_image_generation": "disabled",
    "stream": False,
    "watermark": False,
}

# 鍥剧敓鍥撅紙鏈夊弬鑰冨浘鏃讹級
payload = {
    "model": IMAGE_MODEL,
    "prompt": image_prompt,
    "image": reference_image_url,  # 鍟嗗搧鍥剧墖浣滀负鍙傝€?
    "size": "2K",
    "response_format": "url",
    "sequential_image_generation": "disabled",
    "stream": False,
    "watermark": False,
}

response = requests.post(
    IMAGE_API_URL,
    json=payload,
    headers={"Authorization": f"Bearer {self.api_key}"},
    timeout=60,
)
```

### 杈撳嚭

- 鍥剧墖 URL 鍒楄〃锛歚["https://xxx/scene_1.png", "https://xxx/scene_2.png", ...]`
- 涓嬭浇鍒版湰鍦?鈫?涓婁紶 TOS 鈫?杩斿洖 HTTP URL

### 鏁版嵁娴佽浆

```
scenes[].visual.image_prompt 鈫?ImageGenerationService 鈫?TOS URL 鈫?image_urls[]
```

---

## Step 4: 涓烘瘡涓満鏅敓鎴愯棰?

### 鍏ュ彛

**鏂囦欢**: `backend/v1/app/generate/service/video_composer.py`
**绫?*: `VideoComposer`
**鏂规硶**: `compose(audio_path, scenes, image_urls, output_dir)`

### 杈撳叆

```python
scenes = script_content.get("scenes", [])
image_urls = ["https://xxx/scene_1.png", "https://xxx/scene_2.png", ...]
```

### 鎿嶄綔

涓烘瘡涓満鏅皟鐢ㄧ伀灞卞紩鎿?Seedance 1.5锛?

```python
# 鏋勯€?prompt
prompt = scene.visual.video_prompt + "\n闀滃ご杩愬姩锛? + camera + "\n姘涘洿锛? + mood

# 鏋勯€犺姹?
video_request = VideoRequest(
    duration=duration,      # 2-10绉?
    ratio="9:16",           # 绔栧睆
    generate_audio=False,   # 涓嶇敓鎴愰煶棰戯紝鐢?TTS
    draft=False,
    watermark=False,
)

# 璋冪敤瑙嗛鐢熸垚锛堝悓姝ワ級
response = self.llm.generate_video_sync(
    request=video_request,
    prompt=prompt,
    image=image_url,  # 棣栧抚鍥剧墖
)
```

**VolcanoLLM.generate_video_sync 鍐呴儴**锛?

```python
# 鏋勯€犺姹傚唴瀹?
content = [
    {"type": "text", "text": prompt},
    {"type": "image_url", "image_url": {"url": image_url}},  # 棣栧抚
]

# 鍒涘缓浠诲姟
create_result = self.client.content_generation.tasks.create(
    content=content,
    model=self.video_model,  # Seedance 1.5
    generate_audio=False,
    duration=duration,
    ratio="9:16",
)

# 杞浠诲姟鐘舵€侊紙鏈€澶?30 娆★紝姣忔 10 绉掞級
while retry_count < max_retry:
    get_result = self.client.content_generation.tasks.get(task_id=task_id)
    if status == "succeeded":
        video_url = get_result.content.video_url
        break
    elif status == "failed":
        raise Exception(...)
    else:
        time.sleep(10)
```

### 杈撳嚭

- 姣忎釜鍦烘櫙瑙嗛锛歚/tmp/project_xxx/scene_{i}_{uuid}.mp4`
- 瑙嗛 URL 鍒楄〃

### 鏁版嵁娴佽浆

```
scenes[].visual.video_prompt + image_urls[] 鈫?VideoComposer 鈫?video_paths[]
```

---

## Step 5: FFmpeg 鎷兼帴瑙嗛鐗囨

### 鍏ュ彛

**鏂囦欢**: `backend/v1/app/generate/service/video_composer.py`
**鏂规硶**: `_concat_videos(video_paths, output_dir)`

### 杈撳叆

```python
video_paths = [
    "/tmp/project_xxx/scene_0_xxx.mp4",
    "/tmp/project_xxx/scene_1_xxx.mp4",
    "/tmp/project_xxx/scene_2_xxx.mp4",
]
```

### 鎿嶄綔

```python
# 鍒涘缓 concat 鏂囦欢鍒楄〃
with open(concat_file, "w") as f:
    for video_path in video_paths:
        f.write(f"file '{video_path}'\n")

# FFmpeg 鎷兼帴
cmd = [
    "ffmpeg",
    "-f", "concat",
    "-safe", "0",
    "-i", concat_file,
    "-c", "copy",
    "-y",
    output_path,
]
subprocess.run(cmd, capture_output=True, text=True, timeout=300)
```

濡傛灉 FFmpeg 澶辫触锛屼娇鐢?moviepy 浣滀负 fallback锛?

```python
from moviepy import VideoFileClip, concatenate_videoclips

clips = [VideoFileClip(path) for path in video_paths]
final_clip = concatenate_videoclips(clips, method="compose")
final_clip.write_videofile(output_path, fps=24)
```

### 杈撳嚭

- 鎷兼帴鍚庣殑瑙嗛锛歚/tmp/project_xxx/concat_{uuid}.mp4`

### 鏁版嵁娴佽浆

```
video_paths[] 鈫?FFmpeg concat 鈫?concat_video.mp4
```

---

## Step 6: 涓婁紶 TOS锛屾洿鏂伴」鐩姸鎬?

### 鍏ュ彛

**鏂囦欢**: `backend/v1/app/generate/temp/video_tasks.py`
**鍑芥暟**: `generate_video_task(project_id, script_id)`

### 鎿嶄綔

```python
# 涓婁紶鎴愬搧瑙嗛鍒?TOS
video_object = f"projects/{project_id}/output.mp4"
get_storage_client().upload_file(video_path, video_object)

# 璁板綍璧勪骇
db.add(Asset(
    user_id=project.user_id,
    type=2,  # 瑙嗛
    title="鎴愬搧瑙嗛",
    url=video_object,
    format="mp4",
    source_type=1,  # AI鐢熸垚
))

# 鏇存柊椤圭洰鐘舵€?
project.video_output_url = video_object
project.status = "completed"
db.commit()
```

### 杈撳嚭

- TOS 瑙嗛 URL锛歚projects/{project_id}/output.mp4`
- Project 琛ㄦ洿鏂帮細`video_output_url`銆乣status = "completed"`
- Asset 琛ㄦ柊澧烇細瑙嗛璧勪骇璁板綍

### 鏁版嵁娴佽浆

```
concat_video.mp4 鈫?TOS 鈫?Project.video_output_url
                      鈫?Asset 琛?
```

---

## 瀹屾暣璋冪敤閾捐矾鍥?

```
API 璇锋眰
    鈫?
VideoGenerationService.submit_generation_task()
    鈫?
Celery 寮傛浠诲姟锛歡enerate_video_task()
    鈫?
鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
鈹?Step 1: 璇诲彇 Script                                                     鈹?
鈹?    Script.content 鈫?script_content (dict)                              鈹?
鈹溾攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
鈹?Step 2: TTS                                                             鈹?
鈹?    full_text 鈫?TtsService.generate_audio() 鈫?audio.mp3                 鈹?
鈹?    audio.mp3 鈫?TOS 鈫?Asset(type=3)                                     鈹?
鈹溾攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
鈹?Step 3: 鍥剧墖鐢熸垚                                                         鈹?
鈹?    scenes[].image_prompt 鈫?ImageGenerationService.generate_scene_images鈹?
鈹?    鈫?image_urls[] (TOS URL)                                            鈹?
鈹溾攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
鈹?Step 4: 瑙嗛鐢熸垚                                                         鈹?
鈹?    scenes[].video_prompt + image_urls[] 鈫?VideoComposer.compose()      鈹?
鈹?    鈫?video_paths[] (鏈湴鏂囦欢)                                          鈹?
鈹溾攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
鈹?Step 5: 瑙嗛鎷兼帴                                                         鈹?
鈹?    video_paths[] 鈫?FFmpeg concat 鈫?concat_video.mp4                    鈹?
鈹溾攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
鈹?Step 6: 涓婁紶 & 鏇存柊                                                      鈹?
鈹?    concat_video.mp4 鈫?TOS 鈫?Project.video_output_url                  鈹?
鈹?                          鈫?Asset(type=2)                               鈹?
鈹?    Project.status = "completed"                                        鈹?
鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
```

---

## 鏁版嵁鏍煎紡姹囨€?

| 姝ラ | 杈撳叆 | 杈撳嚭 | 瀛樺偍浣嶇疆 |
|------|------|------|----------|
| 1. LLM 鍓ф湰 | Project 琛?| 鍒嗛暅鑴氭湰 JSON | Script 琛?|
| 2. TTS 閰嶉煶 | scenes[].text | audio.mp3 | TOS + Asset 琛?|
| 3. 鍥剧墖鐢熸垚 | scenes[].image_prompt | image_urls[] | TOS |
| 4. 瑙嗛鐢熸垚 | scenes[].video_prompt + image_urls | video_paths[] | 鏈湴涓存椂鐩綍 |
| 5. 瑙嗛鎷兼帴 | video_paths[] | concat_video.mp4 | 鏈湴涓存椂鐩綍 |
| 6. 涓婁紶鏇存柊 | concat_video.mp4 | video_url | TOS + Project 琛?|

---

## 鍏抽敭閰嶇疆锛?env锛?

```bash
# 鐏北寮曟搸 LLM
DOUBAO_SEED_API_KEY=xxx
DOUBAO_SEED=doubao-1.5-pro

# 鐏北寮曟搸瑙嗛鐢熸垚
DOUBAO_SEEDDANCE=seedance-1.5

# 鐏北寮曟搸 TTS
TTS_ACCESS_KEY=xxx      # 浣滀负 appid
TTS_SECRET_KEY=xxx      # 浣滀负 access_token

# 鐏北寮曟搸鍥剧墖鐢熸垚
IMAGE_API_KEY=xxx

# 鐏北寮曟搸瀵硅薄瀛樺偍
TOS_ACCESS_KEY=xxx
TOS_SECRET_KEY=xxx
TOS_BUCKET_NAME=vidmuse
```

---

## 鐩綍缁撴瀯

```
backend/v1/app/generate/
鈹溾攢鈹€ controller/
鈹?  鈹斺攢鈹€ generation.py              # API 鎺у埗鍣?
鈹溾攢鈹€ dao/
鈹?  鈹溾攢鈹€ generation.py              # 鏁版嵁璁块棶
鈹?  鈹溾攢鈹€ project.py
鈹?  鈹斺攢鈹€ script.py
鈹溾攢鈹€ service/
鈹?  鈹溾攢鈹€ script_generation.py       # Step 1: LLM 鐢熸垚鍓ф湰
鈹?  鈹溾攢鈹€ tts_service.py             # Step 2: TTS 璇煶鍚堟垚
鈹?  鈹溾攢鈹€ image_generation_service.py # Step 3: 鍥剧墖鐢熸垚
鈹?  鈹溾攢鈹€ image_service.py           # 鍥剧墖澶勭悊锛堟贩鍚堟柟妗堬級
鈹?  鈹溾攢鈹€ video_composer.py          # Step 4+5: 瑙嗛鐢熸垚+鎷兼帴
鈹?  鈹斺攢鈹€ video_generation.py        # 瑙嗛鐢熸垚璋冨害
鈹斺攢鈹€ temp/
    鈹溾攢鈹€ celery_app.py              # Celery 閰嶇疆
    鈹斺攢鈹€ video_tasks.py             # Step 6: 寮傛浠诲姟涓绘祦绋?

backend/providers/
鈹溾攢鈹€ volcano.py                     # 鐏北寮曟搸 API 灏佽
鈹斺攢鈹€ dto/
    鈹斺攢鈹€ schema.py                  # 鏁版嵁妯″瀷瀹氫箟
```

---

## 鎬ц兘棰勪及

| 姝ラ | 鑰楁椂 | 璇存槑 |
|------|------|------|
| LLM 鍓ф湰鐢熸垚 | 3-5 绉?| doubao-seed-2.0-pro |
| TTS 閰嶉煶 | 5-10 绉?| 鍏ㄦ枃涓€娆℃€х敓鎴?|
| 鍥剧墖鐢熸垚 | 10-20 绉?寮?| Seedream 5.0锛屽彲骞惰 |
| 瑙嗛鐢熸垚 | 30-60 绉?娈?| Seedance 1.5锛岃疆璇㈢瓑寰?|
| 瑙嗛鎷兼帴 | 2-5 绉?| FFmpeg 鏈湴璁＄畻 |
| **鎬昏锛?鍦烘櫙锛?* | **绾?3-5 鍒嗛挓** | 涓昏鑰楁椂鍦ㄨ棰戠敓鎴?|
