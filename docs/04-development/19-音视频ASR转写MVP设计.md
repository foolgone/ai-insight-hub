# 音视频 ASR 转写 MVP 详细设计（双声道优先）

> **状态**：待实施
> **日期**：2026-11-07
> **范围**：方案 B（云 ASR API）+ 双声道通话录音
> **原则**：最大复用现有链路；**0 张新表、0 个新迁移、0 个新任务类型**
> **不做**：视频画面理解（OCR/场景）、单声道说话人分离（MVP 仅降级）、长音频断点续传

---

## 1. 目标与边界

### 1.1 目标

上传音频/视频后，自动完成：

```
音视频 → 抽音轨/拆声道 → 云 ASR 转写 → 组装「客户/坐席」对话
      → 复用清洗落库 → 质量评估 → 知识提取 → 洞察 → 报告
```

### 1.2 MVP 边界

| 项 | MVP 行为 |
|---|---|
| 输入格式 | 音频：mp3 / wav / m4a；视频：mp4 / mov |
| 文件大小 | 沿用 100MB（更大文件后续改流式上传） |
| 声道 | **优先双声道**（左客户 / 右坐席）；单声道降级为单段文本 |
| ASR | OpenAI 兼容转写接口（可配置 base_url/model） |
| 说话人 | 双声道按声道区分；不做本地 diarization |
| 视频 | 只抽音轨，不做画面分析 |
| 转写文本 | 存 `raw_data.raw_content`，不新建表 |
| 任务 | 复用 `task_type='clean'`，转写作为清洗的 `PARSING` 阶段 |

---

## 2. 总体流程

```
POST /datasources/{id}/upload (media)
  │
  ├─ 校验扩展名/大小
  ├─ storage_service.save_upload(content)
  ├─ raw_data(
  │     raw_content={format:"media", media:{...}, asr:{status:"pending"}},
  │     file_info={filename,size,mime_type,object_name,storage_backend}
  │   )
  └─ cleaning_service.create_clean_task(raw_data_id) + enqueue_clean
        │
        ▼
  _execute_clean（复用）
    ├─ PARSING: media_service.transcribe_media(raw)
    │     ├─ 下载原文件到临时目录
    │     ├─ ffprobe 读时长/声道
    │     ├─ ffmpeg 抽 16k 单声道；双声道拆 L/R
    │     ├─ 超过 ASR_CHUNK_SECONDS 则切片
    │     ├─ 逐片调用 ASR（带偏移合并）
    │     ├─ 按声道配对成 dialogues
    │     └─ 写回 raw_content.text / asr / records
    ├─ NORMALIZING: 媒体已有 records，跳过清洗 Agent
    ├─ DEDUPLICATING: 复用近似重复标记（可选）
    ├─ VALIDATING: 复用 _persist_dialogues 写 cleaned_data
    └─ COMPLETED（后续 evaluate/extract/insight/report 不变）
```

---

## 3. 复用与新增清单

### 3.1 复用（不改）

| 组件 | 复用点 |
|---|---|
| `POST /datasources/{id}/upload` | 媒体分支，不新增上传接口 |
| `storage_service.save_upload/read_upload` | 原文件存储与读取 |
| `raw_data` 表 | `raw_content` JSONB 存媒体元数据、转写、records |
| `tasks` 表 / 5 态 / 重试 / 取消 / SSE | 复用 `clean` 任务 |
| `cleaning_service._execute_clean` | 增加媒体分支，其余流程不变 |
| `_persist_dialogues` | 复用幂等写入 `cleaned_data` |
| `cleaned_data` 表 | 不新增字段，ASR 来源写 `metadata` |
| `evaluate / extract / insight / report` | 完全复用 |
| `TaskListItem` / 任务列表 | 增加 `current_step` 字段（无迁移） |
| 前端上传弹窗 / 任务列表 | 改 accept、文案、阶段列 |

### 3.2 新增（仅代码/配置）

| 新增 | 类型 | 说明 |
|---|---|---|
| `backend/app/services/media_service.py` | 模块 | ffprobe/ffmpeg/ASR/声道配对 |
| `ASR_*` 配置 | 配置项 | 不涉及 DB |
| `backend/Dockerfile` 安装 `ffmpeg` | 镜像 | 无 Python 新依赖（用已有 httpx） |
| 前端 accept/文案/阶段列 | UI | 不新增页面 |

**明确不做**：新表、新迁移、新任务类型、新页面、新队列。

---

## 4. 数据结构

### 4.1 `raw_data.raw_content`（媒体）

```json
{
  "format": "media",
  "text": "完整转写文本……",
  "media": {
    "filename": "call-20261107.mp4",
    "mime_type": "video/mp4",
    "size": 24117248,
    "duration": 312.4,
    "channels": 2,
    "sample_rate": 44100
  },
  "asr": {
    "provider": "openai_compatible",
    "model": "whisper-1",
    "language": "zh",
    "status": "completed",
    "chunks": 1,
    "duration": 312.4,
    "cost_estimate": 0.03,
    "error": null,
    "finished_at": "2026-11-07T10:00:00"
  },
  "records": [
    {
      "dialogue_id": "asr-1",
      "timestamp": "2026-11-07T10:00:01",
      "user_message": "我的订单怎么还没发货？",
      "ai_response": "您好，我帮您查一下，预计今天发出。",
      "quality_score": null,
      "issues": ["asr_transcript"],
      "source": "asr",
      "speaker_pair": "L/R"
    }
  ]
}
```

- `format="media"` 是唯一新增的格式值；
- `records` 与清洗 Agent 输出的 `dialogues` 结构一致，便于复用 `_persist_dialogues`；
- `quality_score=null`：ASR 不伪造质量分，真实质量由后续评估 Agent 给出；
- `asr.status`：`pending | transcribing | completed | failed`。

### 4.2 `cleaned_data.metadata`

```json
{
  "agent": "asr",
  "source": "asr",
  "source_dialogue_id": "asr-1",
  "speaker_pair": "L/R"
}
```

### 4.3 `task.result`（追加字段）

```json
{
  "raw_records": 1,
  "cleaned_records": 12,
  "asr": {
    "provider": "openai_compatible",
    "duration": 312.4,
    "chunks": 1,
    "cost_estimate": 0.03
  }
}
```

---

## 5. 上传接口改造

文件：`backend/app/api/v1/datasources.py`

### 5.1 分支逻辑

```python
extension = Path(filename).suffix.lower().lstrip(".")
media_exts = settings.MEDIA_UPLOAD_EXTENSIONS  # mp3,wav,m4a,mp4,mov

if extension in media_exts:
    # 1) 只校验大小，不解析文本
    # 2) 存对象存储（沿用 save_upload）
    # 3) raw_content = {format: "media", media: {...}, asr: {status: "pending"}}
    # 4) 创建 clean 任务（沿用 create_clean_task）
else:
    # 现有 parse_upload 流程不变
```

### 5.2 要点

- 媒体上传**不调用** `parsers.parse_upload`；
- `file_info` 增加 `object_name` / `storage_backend`（当前已有）；
- `raw_content.media.duration/channels` 在上传时未知，留空，由 worker `ffprobe` 回填；
- 上传响应结构不变（`task_id` / `file_info`）；
- 100MB 限制沿用；超过返回 413。

### 5.3 配置（用户级配置层，不写 `.env`）

ASR 的 `base_url` / `api_key` / `model` / `language` 属于**用户自己的服务凭据**，
与 LLM API Key 同构：前端「语音转写设置」填写 → Fernet 加密 → 存
`user_llm_credentials`（`provider='asr'`）→ worker 按任务归属用户解析。

`backend/app/core/config.py` 只保留 ops 级旋钮：

```python
MEDIA_UPLOAD_EXTENSIONS: str = "mp3,wav,m4a,mp4,mov"
ASR_ENABLED: bool = True          # 功能总开关（关闭时媒体上传 415、配置端点 404）
ASR_TIMEOUT: int = 300            # 单次 HTTP 超时
ASR_CHUNK_SECONDS: int = 600      # 标准接口单文件切片时长
ASR_CHAT_CHUNK_SECONDS: int = 240 # 千问 chat 协议切片（单次上限 5 分钟）
ASR_MAX_RETRIES: int = 2          # 网络/5xx 重试次数（4xx 不重试）
ASR_PRICE_PER_MINUTE: float = 0.006  # 仅用于成本估算展示
ASR_ALLOW_HTTP: bool = False      # SSRF：默认强制 https
ASR_ALLOWED_HOSTS: str = ""       # SSRF：自建内网 ASR 的域名白名单
```

**凭据表（迁移 013）**：`user_llm_credentials` 的唯一键由 `(user_id)` 改为
`(user_id, provider)`，新增 `language` 列；`provider='deepseek'` 为模型 Key，
`provider='asr'` 为语音转写配置。

**端点**（与 LLM 凭据对称）：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `PUT` | `/api/v1/users/me/asr-credential` | 保存前服务端真调一次转写接口校验，失败不入库 |
| `GET` | `/api/v1/users/me/asr-credential` | 只回 `base_url` / `model` / `language` / `key_hint` |
| `DELETE` | `/api/v1/users/me/asr-credential` | 幂等删除（204） |

**SSRF 防护**（`app/core/url_guard.py`）：只允许 `https`、禁止 URL 内嵌账号密码、
域名解析到内网/回环/链路本地/保留段一律拒绝；`ASR_ALLOWED_HOSTS` 可放行自建内网服务。

> **BYOK 守门说明**：`POST /upload` 目前带 `require_llm_credential` 依赖。
> 媒体转写本身不调用 LLM，但后续评估/报告仍需要 BYOK，MVP 保持该守门不变；
> 若未来希望「只转写、不评估」也能上传，再把守门下沉到 clean/evaluate 阶段。
>
> **ASR 关闭时**：`ASR_ENABLED=false` 时媒体上传直接返回 415
> `FILE_FORMAT_INVALID`（`details.reason="asr_disabled"`），避免文件入库后无法处理；
> 文本类格式不受影响。
>
> **未配置 ASR 时**：媒体上传返回 428 `ASR_CREDENTIAL_NOT_CONFIGURED`，
> 前端 428 拦截器直接把弹窗定位到「语音转写」页；文本上传不受影响。

---

## 6. `media_service.py` 详细设计

### 6.1 对外接口

```python
@dataclass
class MediaInfo:
    duration: float
    channels: int
    sample_rate: int

@dataclass
class AsrSegment:
    start: float
    end: float
    text: str
    speaker: str | None = None

@dataclass
class AsrResult:
    text: str
    segments: list[AsrSegment]
    language: str
    duration: float
    cost_estimate: float

async def transcribe_media(
    raw: RawData,
    *,
    progress: Callable[[str], Awaitable[None]] | None = None,
) -> dict:
    """返回 {text, media, asr, records}，写回 raw_content 由调用方完成。"""
```

### 6.2 处理步骤

1. **下载原文件**：`storage_service.read_upload(file_info["object_name"], backend=...)` 写入临时目录；
2. **ffprobe**：
   ```bash
   ffprobe -v error -print_format json -show_format -show_streams input
   ```
   取 `duration`、`channels`、`sample_rate`；
3. **抽音轨**：
   ```bash
   ffmpeg -y -i input -vn -ac 1 -ar 16000 -c:a libmp3lame -b:a 32k audio.mp3
   ```
4. **双声道拆分**（`channels >= 2`）：
   ```bash
   ffmpeg -y -i input -vn -filter_complex "[0:a]channelsplit=channel_layout=stereo[L][R]" \
     -map "[L]" -ac 1 -ar 16000 L.mp3 -map "[R]" -ac 1 -ar 16000 R.mp3
   ```
5. **切片**（时长 > `ASR_CHUNK_SECONDS`）：
   ```bash
   ffmpeg -y -i L.mp3 -f segment -segment_time 600 -c copy L_%03d.mp3
   ```
6. **逐片 ASR**：每片调用 `_transcribe_file`，返回 segment 时间加片偏移；
7. **配对**：双声道按 L/R 合并；单声道生成单段记录；
8. **清理临时目录**。

### 6.3 ASR 调用（OpenAI 兼容）

```http
POST {ASR_BASE_URL}/audio/transcriptions
Content-Type: multipart/form-data
file=@chunk.mp3
model=whisper-1
language=zh
response_format=verbose_json
timestamp_granularities[]=segment
```

响应解析：

```json
{
  "text": "...",
  "language": "zh",
  "duration": 312.4,
  "segments": [{"start": 0.0, "end": 3.2, "text": "..."}]
}
```

实现要点：

- 复用 `httpx.AsyncClient`，`timeout=ASR_TIMEOUT`；
- `ASR_MAX_RETRIES` 次指数退避（仅网络/5xx 重试，4xx 不重试）；
- 成本估算：`duration / 60 * ASR_PRICE_PER_MINUTE`；
- 未配置 `ASR_API_KEY` 时直接抛 `AsrNotConfiguredError`，任务失败并提示配置。

### 6.4 双声道配对算法

输入：`left_segments`（客户）、`right_segments`（坐席），均已按时间排序。

```text
按 start 归并所有 segment，标注 speaker=L/R
逐段累积：
  连续同一 speaker 的文本合并为一段
  当遇到 speaker 切换：
    - 若当前段是 L，且下一段是 R → 生成一条 dialogue
    - 若当前段是 R 但没有前置 L → 作为上一条的 ai_response 追加
    - 连续 R 段合并
时间戳取该 dialogue 的 L 段 start
```

输出示例：

```json
{
  "dialogue_id": "asr-1",
  "timestamp": "2026-11-07T10:00:01",
  "user_message": "我的订单怎么还没发货？",
  "ai_response": "您好，我帮您查一下，预计今天发出。",
  "issues": ["asr_transcript"],
  "source": "asr",
  "speaker_pair": "L/R"
}
```

### 6.5 单声道降级

- `channels == 1` 且 ASR 无 speaker 标签：
  - 生成 **1 条**记录：`user_message=完整转写`、`ai_response=""`、`issues=["asr_transcript","mono_speaker_unknown"]`；
  - **评估入口直接排除**：`evaluation_service._load_targets` 过滤 `ai_response` 为空的记录，
    避免「客户说了话、客服没回」造成误导性低分；被跳过的数量写入 `task.result.skipped_no_reply`；
  - 若数据源**全部**是单声道记录，任务失败并提示「只有单声道转写记录（没有客服回复），
    不参与对话质量评估」；这些数据仍可用于知识提取与经营洞察；
  - 后续可接支持 diarization 的 provider，在同一接口返回 `speaker` 字段。

> **双声道同源检测（dual-mono）**：桌面录制、会议录音常导出 2 声道但左右是同一路信号。
> 仅凭 `channels == 2` 就按 L/R 配对，会得到 `user_message == ai_response` 的假对话。
> 因此转写前用 `ffmpeg pan=mono|c0=c0-c1,astats` 计算 L-R 差分 RMS：
> 低于 `ASR_DUAL_MONO_DB`（默认 -45 dB）即判定同源，改走单声道路径，
> 并在 `raw_content.media.channel_mode` 标记 `dual_mono`。

### 6.5.1 接口协议（按模型名自动识别）

| 协议 | 端点 | 输入 | 时间戳 | 典型模型 |
| --- | --- | --- | --- | --- |
| `transcriptions` | `POST {base}/audio/transcriptions` | multipart 文件 | 有 `segments` | `whisper-1`、`whisper-large-v3`、SenseVoice |
| `chat_audio` | `POST {base}/chat/completions` | `input_audio`（base64 Data URI） | **无** | `qwen3-asr-flash` |

- 识别规则：模型名以 `qwen3-asr` / `qwen-audio-asr` / `qwen2-audio` 开头 → `chat_audio`，其余走标准接口；
- 千问单次上限 5 分钟、base64 后 10MB，因此 `chat_audio` 用更短的切片
  `ASR_CHAT_CHUNK_SECONDS=240`；无时间戳时用「切片偏移 + 返回时长」构造粗粒度 segment，
  双声道按片配对（粒度约 4 分钟），单声道仍是整段文本；
- 千问的 `asr_options`（`language` / `enable_itn`）是非标准参数，放在请求体顶层。

### 6.6 错误类型

```python
class MediaError(Exception): ...
class AsrNotConfiguredError(MediaError): ...
class AsrRequestError(MediaError): ...
class MediaDecodeError(MediaError): ...
```

错误信息写入 `task.error_message`，沿用现有失败/重试。

---

## 7. 清洗链路改造

文件：`backend/app/services/cleaning_service.py`

### 7.1 媒体分支

在 `_execute_clean` 的 raw 循环内、调用 `agent.clean` 之前：

```python
content = raw.raw_content or {}
if content.get("format") == "media":
    if (content.get("asr") or {}).get("status") != "completed":
        task.current_step = f"parsing asr {index}/{raw_records}"
        await session.flush()
        transcript = await media_service.transcribe_media(
            raw,
            progress=lambda step: _set_step(session, task, step),
        )
        raw.raw_content = {**content, **transcript}
        await session.flush()

    _advance_state(task, CleaningState.NORMALIZING, detail=f"{index}/{raw_records}")
    data = {"dialogues": (raw.raw_content or {}).get("records") or []}
    # 跳过 DataCleaningAgent，直接进入去重/校验
else:
    # 现有 agent.clean 流程
```

### 7.2 复用 `_persist_dialogues`

需要做两个小调整：

1. **允许质量分为空**：
   ```python
   raw_score = item.get("quality_score")
   score = None if raw_score is None else min(100.0, max(0.0, float(raw_score)))
   ```
2. **metadata 带来源**：
   ```python
   "metadata": {
       "agent": item.get("source", "cleaning_agent"),
       "source": item.get("source"),
       "source_dialogue_id": dialogue_id,
       "speaker_pair": item.get("speaker_pair"),
   }
   ```

`_persist_dialogues` 返回的 `quality_total` 只累加非空分数；`datasource.statistics.quality_score_avg` 用「有分数条数」做分母（新增 `scored_total` 局部变量），避免 NULL 被当 0 拉低均值。

### 7.3 状态机

不新增状态：

```text
PARSING ("parsing asr 1/3")
  → NORMALIZING ("normalizing 1/1")
  → DEDUPLICATING ("deduplicating 1/1")
  → VALIDATING ("validating 1/1")
  → COMPLETED
```

`_current_state` 只解析空格前的 `parsing`，detail 不影响状态机。

### 7.4 进度

| 阶段 | progress |
|---|---|
| 任务开始 | 5 |
| ASR 转写 | 10–40（按片数） |
| 落库 | 40–90 |
| 完成 | 100 |

### 7.5 取消

- ASR HTTP 请求无法中途 abort；转写完成后立即检查 `task_service.is_cancelled`，命中则保留已转写文本并返回 `cancelled`；
- 重试时若 `asr.status=completed`，跳过 ASR 直接落库。

---

## 8. 前端改造

### 8.1 上传弹窗

`frontend/src/components/datasource/UploadDataModal.jsx`：

```js
const ACCEPT = '.csv,.json,.xlsx,.txt,.mp3,.wav,.m4a,.mp4,.mov'
```

文案：

> 支持 CSV / JSON / XLSX / TXT / MP3 / WAV / M4A / MP4 / MOV，单文件 ≤ 100MB；
> 音视频会先转写为文本再进入清洗；建议上传双声道通话录音。

### 8.2 任务阶段

- `TaskListItem` 增加 `current_step` 字段（只加 schema 字段，无迁移）；
- 数据清洗任务表增加「阶段」列，展示 `current_step`（如 `parsing asr 1/2`）；
- SSE 已返回 `current_step`，前端订阅逻辑不变。

### 8.3 清洗结果

- `CleanedDataDrawer` 展示 `metadata.source`：
  - `asr` → 徽章「ASR 转写」；
  - 显示 `speaker_pair`（L/R）与原始对话；
- 不新增页面。

---

## 9. 失败、重试与幂等

| 场景 | 行为 |
|---|---|
| ASR 未配置 Key | 任务失败，`error_message=ASR 未配置`，提示管理员 |
| ASR 网络/5xx | 重试 `ASR_MAX_RETRIES` 次；仍失败则任务 failed |
| ASR 4xx（Key 错/格式错） | 不重试，直接失败 |
| ffmpeg 解析失败 | 任务 failed，`MediaDecodeError` |
| 任务重试 | 若 `asr.status=completed` 跳过转写，直接落库 |
| 同一 raw 重复清洗 | `(raw_data_id, dialogue_id)` 唯一索引 + `ON CONFLICT DO NOTHING` |
| 取消 | 转写完成后检查取消，保留已转写结果 |

---

## 10. 安全与合规

- 音视频会发送到 ASR 服务商：`.env` 明确 `ASR_ENABLED`，文档标注隐私边界；
- 不在 MVP 做 PII 脱敏（ASR 前脱敏不可行；转写后可复用现有清洗/评估链路）；
- 临时音频文件只落 worker 临时目录，任务结束删除；
- 媒体文件仍存对象存储，沿用现有数据源删除级联/保留策略。

---

## 11. 测试计划

### 11.1 单元测试（不依赖外部服务）

`backend/tests/unit/test_media_service.py`：

- `_pair_dialogues`：L/R 交替、连续同声道、R 开头、空输入；
- `_chunk_ranges`：时长/切片计算；
- ASR 响应解析：segments 合并偏移；
- 单声道降级生成 1 条记录；
- 未配置 Key 抛 `AsrNotConfiguredError`。

### 11.2 集成测试（mock ASR / ffmpeg）

`backend/tests/integration/test_media_upload.py`：

- 上传 mp3 → 创建 `raw_data(format=media)` + clean 任务；
- mock `media_service.transcribe_media` 返回 2 条 records；
- 跑 `run_clean_task` → `cleaned_data` 2 行、`metadata.source=asr`；
- 重跑任务 → ASR 只调用 1 次（幂等）；
- 单声道 → 1 行 + `mono_speaker_unknown` issue。

### 11.3 E2E

- 上传 2 分钟双声道 mp4（mock 或真实 ASR）；
- 任务阶段显示 `parsing asr`；
- 清洗结果出现成对对话；
- 质量评估/报告可跑通。

---

## 12. 验收标准

- [ ] 上传 mp3/mp4 返回 202，任务进入 clean 队列；
- [ ] 任务详情 `current_step` 出现 `parsing asr x/y`；
- [ ] 双声道文件生成成对 `user_message` / `ai_response`；
- [ ] `cleaned_data.metadata.source == "asr"`；
- [ ] 质量评估、知识提取、洞察、报告可继续执行；
- [ ] 重试同一任务不重复调用 ASR；
- [ ] 单声道文件有明确降级提示；
- [ ] 未配置 ASR Key 时任务失败且错误可读；
- [ ] 前端上传弹窗 accept/文案更新。

---

## 13. 工作量与里程碑

| 里程碑 | 内容 | 预估 |
|---|---|---|
| M1 | `media_service`（ffprobe/ffmpeg/ASR/配对）+ 单测 | 1.5 天 |
| M2 | 上传分支 + clean 媒体分支 + 幂等/状态 | 1 天 |
| M3 | 前端 accept/阶段列/来源徽章 | 0.5 天 |
| M4 | 集成测试 + 真实双声道样本验收 | 1 天 |
| **合计** | | **4 天** |

---

## 14. 风险与后续

| 风险 | 应对 |
|---|---|
| 云 ASR 不支持中文说话人分离 | 双声道方案不依赖 diarization；单声道降级 |
| 100MB 视频时长有限 | 后续改流式上传（分片直传） |
| 长音频超过 Celery 30 分钟 | 切片 + 进度；必要时提高 `task_time_limit` |
| ASR 成本不可见 | `task.result.asr.cost_estimate`；后续接成本页 |
| 单声道评估失真 | 打 `mono_speaker_unknown`，前端提示，评估可跳过空 `ai_response` |

**后续扩展**（不在 MVP）：
- 腾讯/阿里 ASR 适配器（原生 diarization）；
- 转写文本预览/编辑；
- 视频画面 OCR/多模态分析；
- 媒体文件保留策略与配额。

---

## 15. 附录：关键命令与请求示例

### ffprobe

```bash
ffprobe -v error -print_format json -show_format -show_streams input.mp4
```

### ffmpeg 抽音轨

```bash
ffmpeg -y -i input.mp4 -vn -ac 1 -ar 16000 -c:a libmp3lame -b:a 32k audio.mp3
```

### ffmpeg 双声道拆分

```bash
ffmpeg -y -i input.mp4 -vn -filter_complex \
  "[0:a]channelsplit=channel_layout=stereo[L][R]" \
  -map "[L]" -ac 1 -ar 16000 L.mp3 \
  -map "[R]" -ac 1 -ar 16000 R.mp3
```

### ASR 请求

```bash
curl -X POST "$ASR_BASE_URL/audio/transcriptions" \
  -H "Authorization: Bearer $ASR_API_KEY" \
  -F file=@L.mp3 \
  -F model=whisper-1 \
  -F language=zh \
  -F response_format=verbose_json \
  -F "timestamp_granularities[]=segment"
```

---

## 16. 兼容性与回滚

| 项 | 说明 |
|---|---|
| 现有文本格式 | CSV/JSON/XLSX/TXT 路径完全不变 |
| 数据库 | 无新表、无迁移；`raw_content` 只新增 JSON 字段 |
| 任务类型 | 复用 `clean`，现有任务/重试/取消/SSE 不受影响 |
| 关闭功能 | `ASR_ENABLED=false` 时拒绝媒体上传，文本上传正常 |
| 回滚 | 回退代码即可；已写入的媒体 `raw_data` 不影响文本链路 |
| 成本口径 | ASR 成本只写 `task.result` / `raw_content.asr`，不进入 `llm_calls` |

