"""音视频转写服务（MVP：云 ASR + 双声道优先）。

设计见 ``docs/04-development/19-音视频ASR转写MVP设计.md``：
- ffprobe/ffmpeg 抽音轨、拆双声道、按需切片；
- 按模型自动选择协议：OpenAI ``/audio/transcriptions`` 或千问 ``/chat/completions``；
- 双声道按 L/R 配对成 ``user_message`` / ``ai_response``；
- 结果写入 ``raw_data.raw_content``，不新建表。
"""
from __future__ import annotations

import asyncio
import base64
import json
import re
import subprocess
import tempfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from app.core.config import settings
from app.services import storage_service
from app.services.asr_service import (
    PROTOCOL_CHAT_AUDIO,
    AsrConfig,
    build_chat_audio_payload,
)


class MediaError(Exception):
    """媒体处理异常基类。"""


class MediaDecodeError(MediaError):
    """ffprobe/ffmpeg 失败或文件无音轨。"""


class AsrRequestError(MediaError):
    """ASR 请求失败；``retryable=False`` 表示 4xx（Key/格式错误）。"""

    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True)
class MediaInfo:
    duration: float
    channels: int
    sample_rate: int


@dataclass(frozen=True)
class AsrSegment:
    start: float
    end: float
    text: str
    speaker: str | None = None


@dataclass(frozen=True)
class AsrResult:
    text: str
    segments: list[AsrSegment]
    language: str
    duration: float
    cost_estimate: float


def _now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _run(cmd: list[str], *, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise MediaDecodeError("ffmpeg/ffprobe 未安装") from exc
    except subprocess.TimeoutExpired as exc:
        raise MediaDecodeError("媒体处理超时") from exc


async def probe(path: Path) -> MediaInfo:
    """读取时长、声道数与采样率。"""
    proc = await asyncio.to_thread(
        _run,
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
    )
    if proc.returncode != 0:
        raise MediaDecodeError(f"ffprobe 失败：{proc.stderr[-500:]}")
    payload = json.loads(proc.stdout or "{}")
    audio = next(
        (item for item in payload.get("streams") or [] if item.get("codec_type") == "audio"),
        None,
    )
    if audio is None:
        raise MediaDecodeError("文件中没有音轨")
    duration = float((payload.get("format") or {}).get("duration") or 0)
    return MediaInfo(
        duration=max(0.0, duration),
        channels=int(audio.get("channels") or 1),
        sample_rate=int(audio.get("sample_rate") or 16000),
    )


async def extract_audio(
    input_path: Path,
    output_path: Path,
    *,
    channel: str | None = None,
) -> None:
    """抽取 16k 单声道 mp3；``channel`` 为 L/R 时按声道拆分。"""
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-map",
        "0:a:0",
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "32k",
    ]
    if channel == "L":
        cmd += ["-af", "pan=mono|c0=c0"]
    elif channel == "R":
        cmd += ["-af", "pan=mono|c0=c1"]
    cmd.append(str(output_path))
    proc = await asyncio.to_thread(_run, cmd)
    if proc.returncode != 0:
        raise MediaDecodeError(f"ffmpeg 抽音轨失败：{proc.stderr[-500:]}")


async def channels_duplicated(path: Path) -> bool:
    """判断左右声道是否同源（L-R 差分近似静音）。

    桌面录制、会议录音常导出「双声道同源」：若按 L/R 当客户/坐席配对，
    会出现 ``user_message`` 与 ``ai_response`` 完全相同（自己和自己对话）。
    用 ffmpeg 计算 L-R 的 RMS（dB），低于 ``ASR_DUAL_MONO_DB`` 即视为同源。
    """
    proc = await asyncio.to_thread(
        _run,
        [
            "ffmpeg",
            "-v",
            "info",
            "-i",
            str(path),
            "-af",
            "pan=mono|c0=c0-c1,astats=metadata=1:reset=0",
            "-f",
            "null",
            "-",
        ],
    )
    if proc.returncode != 0:
        return False
    matches = re.findall(r"RMS level dB:\s*(-inf|-?\d+(?:\.\d+)?)", proc.stderr or "")
    if not matches:
        return False
    last = matches[-1]
    if last == "-inf":
        return True
    try:
        return float(last) <= settings.ASR_DUAL_MONO_DB
    except ValueError:  # pragma: no cover - 正则已保证可解析
        return False


async def chunk_audio(path: Path, chunk_seconds: int) -> list[tuple[Path, float]]:
    """按固定时长切片，返回 (文件, 起始偏移)。"""
    if chunk_seconds <= 0:
        return [(path, 0.0)]
    out_dir = path.parent / f"{path.stem}-chunks"
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / "chunk-%03d.mp3"
    proc = await asyncio.to_thread(
        _run,
        [
            "ffmpeg",
            "-y",
            "-i",
            str(path),
            "-f",
            "segment",
            "-segment_time",
            str(chunk_seconds),
            "-c",
            "copy",
            str(pattern),
        ],
    )
    if proc.returncode != 0:
        raise MediaDecodeError(f"ffmpeg 切片失败：{proc.stderr[-500:]}")
    files = sorted(out_dir.glob("chunk-*.mp3"))
    if not files:
        return [(path, 0.0)]
    return [(item, index * float(chunk_seconds)) for index, item in enumerate(files)]


async def _post_asr(
    url: str,
    headers: dict[str, str],
    *,
    data: dict | None = None,
    files: dict | None = None,
    json_body: dict | None = None,
) -> dict:
    """带重试的 ASR 请求：5xx/网络错误重试，4xx 不重试。"""
    retries = max(0, settings.ASR_MAX_RETRIES)
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=settings.ASR_TIMEOUT) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    data=data,
                    files=files,
                    json=json_body,
                )
            if response.status_code >= 500:
                raise AsrRequestError(f"ASR 服务异常：{response.status_code}")
            if response.status_code >= 400:
                # 4xx 不重试（Key 错误/格式错误）
                raise AsrRequestError(
                    f"ASR 请求失败：{response.status_code} {response.text[:300]}",
                    retryable=False,
                )
            return response.json()
        except AsrRequestError as exc:
            last_error = exc
            if not exc.retryable or attempt >= retries:
                raise
            await asyncio.sleep(2**attempt)
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt >= retries:
                raise AsrRequestError(f"ASR 网络错误：{exc}") from exc
            await asyncio.sleep(2**attempt)
    # pragma: no cover - 循环内已抛错
    raise AsrRequestError(f"ASR 请求失败：{last_error}")


async def _transcribe_file(path: Path, config: AsrConfig, *, offset: float = 0.0) -> AsrResult:
    """按协议分发：标准 /audio/transcriptions 或千问 chat/completions。"""
    if config.effective_protocol == PROTOCOL_CHAT_AUDIO:
        return await _transcribe_chat_audio(path, config, offset=offset)
    return await _transcribe_transcriptions(path, config, offset=offset)


async def _transcribe_transcriptions(
    path: Path, config: AsrConfig, *, offset: float = 0.0
) -> AsrResult:
    data = {
        "model": config.model,
        "response_format": "verbose_json",
        "timestamp_granularities[]": "segment",
    }
    if config.language and config.language != "auto":
        data["language"] = config.language
    content = path.read_bytes()
    payload = await _post_asr(
        config.endpoint,
        {"Authorization": f"Bearer {config.api_key}"},
        data=data,
        files={"file": (path.name, content, "audio/mpeg")},
    )

    segments_payload = payload.get("segments") or []
    segments: list[AsrSegment] = []
    for item in segments_payload:
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        start = float(item.get("start") or 0) + offset
        end = float(item.get("end") or start) + offset
        segments.append(AsrSegment(start=start, end=end, text=text))

    duration = float(payload.get("duration") or 0)
    text = str(payload.get("text") or "").strip()
    if not segments and text:
        segments = [AsrSegment(start=offset, end=offset + duration, text=text)]
    if not segments:
        raise AsrRequestError("ASR 返回空转写")

    return AsrResult(
        text=text or " ".join(item.text for item in segments),
        segments=segments,
        language=str(payload.get("language") or config.language or "zh"),
        duration=duration,
        cost_estimate=round(duration / 60 * settings.ASR_PRICE_PER_MINUTE, 6),
    )


async def _transcribe_chat_audio(
    path: Path, config: AsrConfig, *, offset: float = 0.0
) -> AsrResult:
    """千问 Qwen3-ASR：base64 Data URI + chat/completions，无时间戳。"""
    data_uri = "data:audio/mpeg;base64," + base64.b64encode(path.read_bytes()).decode()
    payload = await _post_asr(
        config.endpoint,
        {"Authorization": f"Bearer {config.api_key}"},
        json_body=build_chat_audio_payload(config, data_uri),
    )

    choices = payload.get("choices") or []
    message = (choices[0] or {}).get("message") if choices else None
    message = message or {}
    raw_content = message.get("content")
    if isinstance(raw_content, list):
        text = " ".join(
            str(item.get("text") or "") for item in raw_content if isinstance(item, dict)
        ).strip()
    else:
        text = str(raw_content or "").strip()
    if not text:
        raise AsrRequestError("ASR 返回空转写")

    usage = payload.get("usage") or {}
    duration = float(usage.get("seconds") or 0)
    annotations = message.get("annotations") or []
    language = config.language or "zh"
    for item in annotations:
        if isinstance(item, dict) and item.get("language"):
            language = str(item["language"])
            break

    # 无时间戳：用切片偏移构造一段粗粒度 segment（单声道/按片配对都依赖它）
    return AsrResult(
        text=text,
        segments=[AsrSegment(start=offset, end=offset + duration, text=text)],
        language=language,
        duration=duration,
        cost_estimate=round(duration / 60 * settings.ASR_PRICE_PER_MINUTE, 6),
    )


def _chunk_seconds(protocol: str) -> int:
    """千问单次上限 5 分钟，这里按 4 分钟切片；标准接口沿用 ASR_CHUNK_SECONDS。"""
    if protocol == PROTOCOL_CHAT_AUDIO:
        return max(30, min(settings.ASR_CHAT_CHUNK_SECONDS, 240))
    return settings.ASR_CHUNK_SECONDS


async def _transcribe_track(
    path: Path,
    config: AsrConfig,
    *,
    speaker: str | None,
    progress: Callable[[str], Awaitable[None]] | None,
) -> tuple[AsrResult, int]:
    chunks = await chunk_audio(path, _chunk_seconds(config.effective_protocol))
    all_segments: list[AsrSegment] = []
    texts: list[str] = []
    language = config.language or "zh"
    duration = 0.0
    cost = 0.0

    for index, (chunk_path, offset) in enumerate(chunks, start=1):
        if progress is not None:
            await progress(f"parsing asr {index}/{len(chunks)}")
        result = await _transcribe_file(chunk_path, config, offset=offset)
        language = result.language
        duration += result.duration
        cost += result.cost_estimate
        texts.append(result.text)
        for segment in result.segments:
            all_segments.append(
                AsrSegment(
                    start=segment.start,
                    end=segment.end,
                    text=segment.text,
                    speaker=speaker,
                )
            )

    return (
        AsrResult(
            text=" ".join(texts).strip(),
            segments=all_segments,
            language=language,
            duration=duration,
            cost_estimate=round(cost, 6),
        ),
        len(chunks),
    )


def _pair_dialogues(
    left: list[AsrSegment],
    right: list[AsrSegment],
    *,
    anchor: datetime,
) -> list[dict[str, Any]]:
    """双声道按时间合并，配对成 user/ai 对话。"""
    items = [(segment.start, "L", segment.text) for segment in left]
    items += [(segment.start, "R", segment.text) for segment in right]
    items.sort(key=lambda item: (item[0], 0 if item[1] == "L" else 1))

    dialogues: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        user_text = " ".join(current["user"]).strip()
        ai_text = " ".join(current["ai"]).strip()
        if not user_text and not ai_text:
            current = None
            return
        issues = ["asr_transcript", "relative_timestamp"]
        if not user_text:
            issues.append("missing_user_message")
        if not ai_text:
            issues.append("missing_ai_response")
        dialogues.append(
            {
                "dialogue_id": f"asr-{len(dialogues) + 1}",
                "timestamp": (anchor + timedelta(seconds=current["start"])).isoformat(),
                "user_message": user_text,
                "ai_response": ai_text,
                "quality_score": None,
                "issues": issues,
                "source": "asr",
                "speaker_pair": "L/R",
            }
        )
        current = None

    for start, speaker, text in items:
        if speaker == "L":
            # 坐席先开口时（只有 ai 没有 user）不单独成条，合并到客户第一句
            if current is not None and current["ai"] and current["user"]:
                flush()
            if current is None:
                current = {"start": start, "user": [], "ai": []}
            elif not current["user"]:
                current["start"] = start
            current["user"].append(text)
        else:
            if current is None:
                current = {"start": start, "user": [], "ai": []}
            current["ai"].append(text)
    flush()
    return dialogues


def _mono_records(result: AsrResult, *, anchor: datetime) -> list[dict[str, Any]]:
    text = result.text.strip()
    if not text:
        return []
    return [
        {
            "dialogue_id": "asr-1",
            "timestamp": anchor.isoformat(),
            "user_message": text,
            "ai_response": "",
            "quality_score": None,
            "issues": ["asr_transcript", "mono_speaker_unknown"],
            "source": "asr",
            "speaker_pair": "mono",
        }
    ]


async def transcribe_media(
    raw: Any,
    asr: AsrConfig,
    *,
    progress: Callable[[str], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    """下载媒体 → 抽音轨/拆声道 → ASR → 返回写回 ``raw_content`` 的字段。

    ``asr`` 由调用方按任务归属用户解析（见 ``asr_service.resolve_for_user``）。
    """
    file_info = raw.file_info or {}
    object_name = file_info.get("object_name")
    filename = str(file_info.get("filename") or "upload.media")
    if not object_name:
        raise MediaDecodeError("媒体文件缺少 object_name，无法读取")

    with tempfile.TemporaryDirectory(prefix="asr-") as tmp:
        root = Path(tmp)
        suffix = Path(filename).suffix or ".bin"
        input_path = root / f"input{suffix}"
        content = await asyncio.to_thread(
            storage_service.read_upload,
            object_name,
            backend=file_info.get("storage_backend"),
        )
        input_path.write_bytes(content)

        info = await probe(input_path)
        if info.duration <= 0:
            raise MediaDecodeError("媒体时长为 0")

        if progress is not None:
            await progress("parsing asr extracting")

        # 双声道不一定是「左客户/右坐席」：桌面录制、会议录音常见左右同源，
        # 强行拆分会导致 user_message 与 ai_response 完全相同（自己和自己对话）。
        dual_mono = info.channels >= 2 and await channels_duplicated(input_path)

        if info.channels >= 2 and not dual_mono:
            left_path = root / "left.mp3"
            right_path = root / "right.mp3"
            await extract_audio(input_path, left_path, channel="L")
            await extract_audio(input_path, right_path, channel="R")
            left_result, left_chunks = await _transcribe_track(
                left_path, asr, speaker="L", progress=progress
            )
            right_result, right_chunks = await _transcribe_track(
                right_path, asr, speaker="R", progress=progress
            )
            records = _pair_dialogues(
                left_result.segments,
                right_result.segments,
                anchor=raw.created_at or _now_naive(),
            )
            text = " ".join(
                segment.text
                for segment in sorted(
                    left_result.segments + right_result.segments,
                    key=lambda item: item.start,
                )
            ).strip()
            duration = max(left_result.duration, right_result.duration, info.duration)
            cost = left_result.cost_estimate + right_result.cost_estimate
            language = left_result.language or right_result.language
            chunks = left_chunks + right_chunks
            channel_mode = "stereo"
        else:
            mono_path = root / "mono.mp3"
            await extract_audio(input_path, mono_path)
            mono_result, chunks = await _transcribe_track(
                mono_path, asr, speaker=None, progress=progress
            )
            records = _mono_records(
                mono_result,
                anchor=raw.created_at or _now_naive(),
            )
            text = mono_result.text
            duration = max(mono_result.duration, info.duration)
            cost = mono_result.cost_estimate
            language = mono_result.language
            channel_mode = "dual_mono" if dual_mono else "mono"

        if not records:
            raise MediaDecodeError("转写结果为空")

        logger.info(
            "media transcribed raw={} channels={} mode={} records={} chunks={}",
            raw.id,
            info.channels,
            channel_mode,
            len(records),
            chunks,
        )
        return {
            "text": text,
            "media": {
                "filename": filename,
                "mime_type": file_info.get("mime_type"),
                "size": file_info.get("size"),
                "duration": round(info.duration, 3),
                "channels": info.channels,
                "sample_rate": info.sample_rate,
                "channel_mode": channel_mode,
            },
            "asr": {
                "provider": "openai_compatible",
                "model": asr.model,
                "language": language,
                "status": "completed",
                "chunks": chunks,
                "duration": round(duration, 3),
                "cost_estimate": round(cost, 6),
                "finished_at": _now_naive().isoformat(),
                "error": None,
            },
            "records": records,
        }


__all__ = [
    "AsrRequestError",
    "MediaDecodeError",
    "MediaError",
    "transcribe_media",
]
