"""语音晨报（TTS）：文稿生成 → 合成音频 → 存档 → 可推送。

引擎：
- edge（默认，免费，无需 Key）→ MP3
- openai（需 API Key）→ MP3 / OGG(opus)

输出目录：`<DATA_DIR>/audio`
"""
import asyncio
import logging
import re
import shutil
import subprocess
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai import processing
from ..models import TTSAsset
from ..report import export_dir
from ..settings import DATA_DIR
from ..utils.text import estimate_duration_sec, md_to_plain, truncate

logger = logging.getLogger("morning_insight.tts")

DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"


def audio_dir() -> Path:
    path = Path(DATA_DIR) / "audio"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_name(text: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|\s]+", "_", text or "voice")[:60]
    return cleaned or "voice"


def synthesize(
    db: Session,
    user_id: int,
    text: str,
    cfg: dict,
    *,
    report_id: int | None = None,
    periodical_id: int | None = None,
    provider: str = "",
    voice: str = "",
    fmt: str = "",
) -> TTSAsset:
    """合成语音晨报并入库。text 为口语化文稿（可先用 build_script 生成）。"""
    tts_cfg = cfg.get("tts_config") or {}
    provider = (provider or tts_cfg.get("provider") or "edge").lower()
    voice = voice or tts_cfg.get("voice") or DEFAULT_VOICE
    fmt = (fmt or tts_cfg.get("format") or "mp3").lower()
    text = (text or "").strip()
    if not text:
        raise ValueError("文稿为空，无法合成语音")

    stamp = __import__("datetime").datetime.now().strftime("%Y%m%d-%H%M%S")
    target = audio_dir() / f"{stamp}-{user_id}-{_safe_name(voice)}.{fmt}"

    if provider == "openai":
        _synthesize_openai(text, voice, fmt, target, cfg.get("ai_config") or {})
    else:
        _synthesize_edge(text, voice, fmt, target)

    size = target.stat().st_size if target.exists() else 0
    asset = TTSAsset(
        user_id=user_id, report_id=report_id, periodical_id=periodical_id,
        provider=provider, voice=voice, fmt=fmt, path=str(target),
        script_text=truncate(text, 50000), duration_sec=estimate_duration_sec(text),
        size_bytes=size,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def _synthesize_edge(text: str, voice: str, fmt: str, target: Path) -> None:
    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError("未安装 edge-tts，请执行：pip install edge-tts") from exc

    mp3_path = target if fmt == "mp3" else target.with_suffix(".mp3")
    try:
        async def _run():
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(mp3_path))

        asyncio.run(_run())
    except Exception as exc:
        raise RuntimeError(
            f"Edge TTS 合成失败：{exc}。该引擎需要访问微软语音服务，"
            "若网络受限可改用 OpenAI TTS 或本地 TTS。"
        ) from exc

    if fmt != "mp3":
        if not _convert_audio(mp3_path, target):
            raise RuntimeError(
                f"Edge TTS 仅输出 MP3，转 {fmt} 需要系统安装 ffmpeg。"
                "请安装 ffmpeg 后重试，或把格式改回 MP3。"
            )
        mp3_path.unlink(missing_ok=True)


def _convert_audio(src: Path, dst: Path) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    try:
        subprocess.run(
            [ffmpeg, "-y", "-loglevel", "error", "-i", str(src), str(dst)],
            check=True, timeout=180,
        )
        return dst.exists()
    except Exception as exc:
        logger.warning("ffmpeg 转码失败：%s", exc)
        return False


def _synthesize_openai(text: str, voice: str, fmt: str, target: Path, ai_cfg: dict) -> None:
    base_url = (ai_cfg.get("base_url") or "").rstrip("/")
    api_key = (ai_cfg.get("api_key") or "").strip()
    if not base_url or not api_key:
        raise ValueError("OpenAI TTS 需要先配置 AI 模型地址与 Key")
    response_format = "opus" if fmt == "ogg" else fmt
    try:
        resp = httpx.post(
            f"{base_url}/audio/speech",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": (ai_cfg.get("tts_model") or "tts-1"),
                "voice": voice or "alloy",
                "input": text,
                "response_format": response_format,
            },
            timeout=180.0,
        )
        resp.raise_for_status()
    except Exception as exc:
        raise RuntimeError(f"OpenAI TTS 合成失败：{exc}") from exc
    target.write_bytes(resp.content)


def build_script(db: Session, user_id: int, content_md: str, cfg: dict, *, length: str = "brief") -> str:
    """把晨报 Markdown 转成适合朗读的口语文稿。"""
    ai_cfg = cfg.get("ai_config") or {}
    if not ai_cfg.get("base_url"):
        return md_to_plain(content_md)
    return processing.build_tts_script(content_md, ai_cfg, length=length, db=db, user_id=user_id)


def full_flow(
    db: Session,
    user_id: int,
    cfg: dict,
    content_md: str,
    *,
    report_id: int | None = None,
    periodical_id: int | None = None,
    provider: str = "",
    voice: str = "",
    fmt: str = "",
) -> TTSAsset:
    """文稿 + 合成一步完成。"""
    tts_cfg = cfg.get("tts_config") or {}
    script = build_script(db, user_id, content_md, cfg, length=tts_cfg.get("length") or "brief")
    return synthesize(
        db, user_id, script, cfg,
        report_id=report_id, periodical_id=periodical_id,
        provider=provider, voice=voice, fmt=fmt,
    )


def list_assets(db: Session, user_id: int, limit: int = 50) -> list[dict]:
    rows = db.scalars(
        select(TTSAsset).where(TTSAsset.user_id == user_id).order_by(TTSAsset.id.desc()).limit(min(limit, 200))
    ).all()
    return [
        {"id": a.id, "report_id": a.report_id, "periodical_id": a.periodical_id,
         "provider": a.provider, "voice": a.voice, "fmt": a.fmt,
         "duration_sec": a.duration_sec, "size_bytes": a.size_bytes,
         "created_at": a.created_at.isoformat() if a.created_at else "",
         "exists": Path(a.path).exists() if a.path else False}
        for a in rows
    ]


def is_available(provider: str = "edge") -> tuple[bool, str]:
    if provider == "openai":
        return True, ""
    try:
        import edge_tts  # noqa: F401

        return True, ""
    except ImportError:
        return False, "未安装 edge-tts，请执行：pip install edge-tts"
