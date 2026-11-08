"""音视频转写服务（MVP：云 ASR + 双声道优先）。

设计见 ``docs/04-development/19-音视频ASR转写MVP设计.md``：
- ffprobe/ffmpeg 抽音轨、拆双声道、按需切片；
- 调用 OpenAI 兼容的 ``/audio/transcriptions``；
- 双声道按 L/R 配对成 ``user_message`` / ``ai_response``；
- 结果写入 ``raw_data.raw_content``，不新建表。
"""
from __future__ import annotations

import asyncio
import json
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
from app.services.asr_service import AsrConfig


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


async def _transcribe_file(
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
    retries = max(0, settings.ASR_MAX_RETRIES)
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=settings.ASR_TIMEOUT) as client:
                response = await client.post(
                    config.endpoint,
                    headers={"Authorization": f"Bearer {config.api_key}"},
                    data=data,
                    files={"file": (path.name, content, "audio/mpeg")},
                )
            if response.status_code >= 500:
                raise AsrRequestError(f"ASR 服务异常：{response.status_code}")
            if response.status_code >= 400:
                # 4xx 不重试（Key 错误/格式错误）
                raise AsrRequestError(
                    f"ASR 请求失败：{response.status_code} {response.text[:300]}",
                    retryable=False,
                )
            payload = response.json()
            break
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
    else:  # pragma: no cover - 循环内已抛错
        raise AsrRequestError(f"ASR 请求失败：{last_error}")

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


async def _transcribe_track(
    path: Path,
    config: AsrConfig,
    *,
    speaker: str | None,
    progress: Callable[[str], Awaitable[None]] | None,
) -> tuple[AsrResult, int]:
    chunks = await chunk_audio(path, settings.ASR_CHUNK_SECONDS)
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

        if info.channels >= 2:
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
                segment.text for segment in sorted(
                    left_result.segments + right_result.segments,
                    key=lambda item: item.start,
                )
            ).strip()
            duration = max(left_result.duration, right_result.duration, info.duration)
            cost = left_result.cost_estimate + right_result.cost_estimate
            language = left_result.language or right_result.language
            chunks = left_chunks + right_chunks
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

        if not records:
            raise MediaDecodeError("转写结果为空")

        logger.info(
            "media transcribed raw={} channels={} records={} chunks={}",
            raw.id,
            info.channels,
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
