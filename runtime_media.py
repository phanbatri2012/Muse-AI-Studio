from __future__ import annotations

import os
import shutil
from pathlib import Path

from runtime_paths import INSTALL_DIR, BUNDLE_DIR, RUNTIME_BIN_DIR

try:
    import imageio_ffmpeg
except Exception:  # pragma: no cover - optional runtime dependency
    imageio_ffmpeg = None


def _resolve_existing_file(raw_path: str | os.PathLike[str] | None) -> str:
    try:
        candidate = Path(str(raw_path or "")).expanduser()
    except Exception:
        return ""
    if not str(candidate):
        return ""
    try:
        return str(candidate.resolve()) if candidate.is_file() else ""
    except Exception:
        return str(candidate) if candidate.is_file() else ""


def resolve_packaged_binary(binary_name: str) -> str:
    filename = str(binary_name or "").strip()
    if not filename:
        return ""
    candidates = [
        RUNTIME_BIN_DIR / filename,
        INSTALL_DIR / "bin" / filename,
        BUNDLE_DIR / "bin" / filename,
        INSTALL_DIR / "_internal" / "bin" / filename,
        BUNDLE_DIR / "_internal" / "bin" / filename,
        INSTALL_DIR / "build-assets" / "macos" / "bin" / filename,
        BUNDLE_DIR / "build-assets" / "macos" / "bin" / filename,
    ]
    for candidate in candidates:
        try:
            if candidate.is_file():
                return str(candidate.resolve())
        except Exception:
            continue
    return ""


def resolve_ffmpeg_executable() -> str:
    env_value = _resolve_existing_file(os.getenv("IMAGEIO_FFMPEG_EXE"))
    if env_value:
        return env_value

    packaged = resolve_packaged_binary("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if packaged:
        return packaged

    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    for raw_path in (
        "/opt/homebrew/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
    ):
        candidate = _resolve_existing_file(raw_path)
        if candidate:
            return candidate

    try:
        if imageio_ffmpeg is not None:
            return str(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        pass
    return ""


def resolve_ffprobe_executable() -> str:
    env_value = _resolve_existing_file(os.getenv("TOOL_VEO_FFPROBE_EXE"))
    if env_value:
        return env_value

    packaged = resolve_packaged_binary("ffprobe.exe" if os.name == "nt" else "ffprobe")
    if packaged:
        return packaged

    system_ffprobe = shutil.which("ffprobe")
    if system_ffprobe:
        return system_ffprobe

    for raw_path in (
        "/opt/homebrew/bin/ffprobe",
        "/usr/local/bin/ffprobe",
    ):
        candidate = _resolve_existing_file(raw_path)
        if candidate:
            return candidate

    ffmpeg_exe = resolve_ffmpeg_executable()
    if ffmpeg_exe:
        ffmpeg_path = Path(ffmpeg_exe)
        sibling = ffmpeg_path.with_name(ffmpeg_path.name.replace("ffmpeg", "ffprobe"))
        try:
            if sibling.is_file():
                return str(sibling.resolve())
        except Exception:
            if sibling.is_file():
                return str(sibling)
    return ""


def prepare_media_environment() -> dict[str, str]:
    prepared: dict[str, str] = {}
    ffmpeg_exe = resolve_ffmpeg_executable()
    if ffmpeg_exe:
        os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_exe
        prepared["IMAGEIO_FFMPEG_EXE"] = ffmpeg_exe
    ffprobe_exe = resolve_ffprobe_executable()
    if ffprobe_exe:
        os.environ["TOOL_VEO_FFPROBE_EXE"] = ffprobe_exe
        prepared["TOOL_VEO_FFPROBE_EXE"] = ffprobe_exe
    return prepared
