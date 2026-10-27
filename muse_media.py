from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Callable
from urllib.error import URLError
from urllib.request import Request, urlopen

from runtime_paths import MUSE_DOWNLOADS_DIR
from runtime_media import resolve_ffmpeg_executable

FFMPEG_EXE = resolve_ffmpeg_executable() or "ffmpeg"


def _log(message: str, logger: Callable[[str], None] | None = None) -> None:
    if callable(logger):
        try:
            logger(message)
            return
        except Exception:
            pass
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [MUSE_MEDIA] {message}")


def sanitize_filename(text: str, max_length: int = 40) -> str:
    """Chuyển đổi text/prompt thành chuỗi tên file an toàn trên Windows."""
    # Xóa ký tự tiếng Việt có dấu hoặc ký tự đặc biệt
    clean = re.sub(r"[^\w\s-]", "", str(text or "")).strip()
    clean = re.sub(r"[\s_-]+", "_", clean)
    if not clean:
        clean = "prompt"
    return clean[:max_length].rstrip("_")


def generate_video_filename(prompt: str, index: int = 1, extension: str = ".mp4") -> str:
    """Tạo tên file theo định dạng chuẩn: MUSE_YYYYMMDD_HHMMSS_idx_prompt.mp4"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_p = sanitize_filename(prompt, max_length=35)
    ext = extension if extension.startswith(".") else f".{extension}"
    return f"MUSE_{timestamp}_{index:02d}_{clean_p}{ext}"


def download_media_file(
    url: str,
    dest_path: Path | str,
    timeout: int = 60,
    chunk_size: int = 64 * 1024,
    headers: dict[str, str] | None = None,
    log_callback: Callable[[str], None] | None = None,
) -> bool:
    """Tải file video/ảnh theo luồng (chunk streaming) để tối ưu RAM."""
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "Accept": "*/*",
    }
    if headers:
        default_headers.update(headers)

    req = Request(url, headers=default_headers)
    _log(f"⬇️ Đang tải media về {dest.name}...", log_callback)

    try:
        with urlopen(req, timeout=timeout) as response:
            if response.status != 200:
                _log(f"❌ Tải thất bại, HTTP status: {response.status}", log_callback)
                return False

            total_downloaded = 0
            with open(dest, "wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    total_downloaded += len(chunk)

            if total_downloaded < 1024:
                _log(f"⚠️ File tải về quá nhỏ ({total_downloaded} bytes)", log_callback)
                return False

            _log(f"✅ Đã tải xong: {dest.name} ({round(total_downloaded / (1024 * 1024), 2)} MB)", log_callback)
            return True

    except (URLError, OSError, Exception) as exc:
        _log(f"❌ Lỗi trong quá trình tải {url}: {exc}", log_callback)
        if dest.exists() and dest.stat().st_size == 0:
            try:
                dest.unlink()
            except Exception:
                pass
        return False


def verify_video_file_integrity(file_path: Path | str) -> tuple[bool, str]:
    """Kiểm tra header magic bytes của file để xác định có phải video thật hay là ảnh/file lỗi.

    Trả về (is_valid_video, detected_format_description).
    """
    p = Path(file_path)
    if not p.is_file():
        return False, "file_not_found"

    size = p.stat().st_size
    if size < 10 * 1024:  # Ít hơn 10KB chắc chắn không phải video thành phẩm
        return False, f"file_too_small_{size}_bytes"

    try:
        with open(p, "rb") as f:
            header = f.read(32)
    except Exception as exc:
        return False, f"read_error_{exc}"

    if len(header) < 12:
        return False, "header_too_short"

    # 1. Nhận diện các định dạng ảnh phổ biến (bị tải nhầm)
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return False, "image_png"
    if header.startswith(b"\xff\xd8\xff"):
        return False, "image_jpeg"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return False, "image_webp"
    if header.startswith(b"GIF87a") or header.startswith(b"GIF89a"):
        return False, "image_gif"

    # 2. Nhận diện chuẩn MP4 / ISO Base Media File Format (4 bytes size + 'ftyp')
    if header[4:8] == b"ftyp":
        major_brand = header[8:12].decode("latin1", errors="ignore").strip()
        return True, f"video_mp4_{major_brand}"

    if header[4:8] in (b"moov", b"mdat", b"wide"):
        return True, "video_mp4_raw"

    # 3. Nhận diện WebM / Matroska (EBML header: 0x1A 0x45 0xDF 0xA3)
    if header.startswith(b"\x1a\x45\xdf\xa3"):
        return True, "video_webm"

    # 4. Nhận diện QuickTime / MOV
    if header[4:8] == b"qt  ":
        return True, "video_quicktime"

    # Nếu file có dung lượng lớn (> 500KB) và không phải ảnh tĩnh đã biết, xem như video hợp lệ
    if size > 500 * 1024:
        return True, "video_generic"

    return False, "unknown_binary"


def extract_video_thumbnail(
    video_path: Path | str,
    thumb_path: Path | str | None = None,
    time_offset_seconds: float = 0.5,
    log_callback: Callable[[str], None] | None = None,
) -> Path | None:
    """Trích xuất 1 frame làm thumbnail xem trước bằng FFmpeg."""
    v_path = Path(video_path)
    if not v_path.is_file():
        return None

    if thumb_path is None:
        t_path = v_path.with_suffix(".jpg")
    else:
        t_path = Path(thumb_path)

    cmd = [
        FFMPEG_EXE,
        "-y",
        "-ss", str(time_offset_seconds),
        "-i", str(v_path),
        "-vframes", "1",
        "-q:v", "2",
        str(t_path),
    ]

    try:
        extra_kwargs = {}
        if os.name == "nt":
            extra_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=15,
            **extra_kwargs,
        )
        if proc.returncode == 0 and t_path.is_file() and t_path.stat().st_size > 0:
            return t_path
    except Exception as exc:
            _log(f"⚠️ Không thể trích xuất thumbnail: {exc}", log_callback)

    return None


def save_video_metadata(
    video_path: Path | str,
    metadata: dict[str, Any],
) -> Path:
    """Lưu file JSON metadata đi kèm video."""
    v_path = Path(video_path)
    meta_path = v_path.with_name(f"{v_path.stem}_meta.json")

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    return meta_path


async def process_and_save_media_async(
    result: Any,  # MuseGenerationResult
    output_dir: Path | str = MUSE_DOWNLOADS_DIR,
    prompt_index: int = 1,
    client: Any = None,
    cookie_header: str | None = None,
    max_videos: int = 1,
    log_callback: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Tải toàn bộ video thành phẩm (hỗ trợ blob bytes & CDN URL), trích xuất thumbnail và lưu metadata."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    downloaded_videos: list[str] = []
    thumbnails: list[str] = []
    metadata_files: list[str] = []

    headers = {}
    if cookie_header:
        headers["Cookie"] = cookie_header

    video_urls = getattr(result, "video_urls", []) or []
    prompt = getattr(result, "prompt", "video")

    # Giới hạn số lượng video cho mỗi prompt (mặc định lấy đúng 1 video mới nhất)
    if max_videos > 0 and len(video_urls) > max_videos:
        video_urls = video_urls[-max_videos:]

    # Nếu không có video_urls nhưng client có nút download video, vẫn thử tải
    if not video_urls and client is not None:
        filename = generate_video_filename(prompt, index=prompt_index)
        dest_file = out_dir / filename
        btn_success = await client.download_video_via_button(dest_file)
        if btn_success:
            video_urls.append("button_download")

    for i, v_url in enumerate(video_urls, start=1):
        if max_videos > 0 and len(downloaded_videos) >= max_videos:
            break

        filename = generate_video_filename(prompt, index=prompt_index if (max_videos == 1 or len(video_urls) == 1) else i)
        dest_file = out_dir / filename
        success = False

        if dest_file.is_file() and dest_file.stat().st_size > 1024:
            is_valid, _ = verify_video_file_integrity(dest_file)
            if is_valid:
                success = True
            else:
                try:
                    dest_file.unlink()
                except Exception:
                    pass
        elif v_url.startswith("blob:") and client is not None:
            # 1. Ưu tiên trích xuất blob bytes trực tiếp từ bộ nhớ browser (siêu tốc, không bị chặn bởi dialog OS)
            _log("📦 Đang trích xuất blob video trực tiếp từ bộ nhớ browser...", log_callback)
            blob_bytes = await client.extract_blob_as_bytes(v_url)
            if blob_bytes and len(blob_bytes) > 1024:
                with open(dest_file, "wb") as f:
                    f.write(blob_bytes)
                _log(f"✅ Đã lưu blob video thành công: {dest_file.name} ({round(len(blob_bytes)/(1024*1024), 2)} MB)", log_callback)
                success = True
            else:
                # 2. Fallback thử kích hoạt nút Download video
                _log(f"⬇️ Thử kích hoạt nút Download video trên giao diện...", log_callback)
        elif v_url == "button_download" and client is not None:
            _log(f"⬇️ Kích hoạt lưu video qua nút Download trên giao diện...", log_callback)
            success = await client.download_video_via_button(dest_file)
        elif v_url != "button_download":
            success = download_media_file(
                url=v_url,
                dest_path=dest_file,
                headers=headers,
                log_callback=log_callback,
            )

        if success and dest_file.is_file():
            is_valid, media_fmt = verify_video_file_integrity(dest_file)
            if not is_valid:
                _log(f"⚠️ File đã tải về không phải video hợp lệ (định dạng: {media_fmt}). Xóa file ảnh/lỗi: {dest_file.name}", log_callback)
                try:
                    dest_file.unlink()
                except Exception:
                    pass
                continue

            _log(f"✅ Xác thực tính toàn vẹn video thành công ({media_fmt}, {round(dest_file.stat().st_size / (1024*1024), 2)} MB)", log_callback)
            downloaded_videos.append(str(dest_file))

            # Trích xuất thumbnail
            thumb = extract_video_thumbnail(dest_file, log_callback=log_callback)
            if thumb:
                thumbnails.append(str(thumb))

            # Lưu metadata
            meta = {
                "prompt": prompt,
                "video_file": filename,
                "source_url": v_url,
                "duration_seconds": getattr(result, "duration_seconds", 0.0),
                "created_at": datetime.now().isoformat(),
                "turn_id": getattr(result, "turn_id", None),
                "reply_text": getattr(result, "reply_text", ""),
            }
            meta_path = save_video_metadata(dest_file, meta)
            metadata_files.append(str(meta_path))

            if max_videos > 0 and len(downloaded_videos) >= max_videos:
                break

    return {
        "downloaded_videos": downloaded_videos,
        "thumbnails": thumbnails,
        "metadata_files": metadata_files,
        "primary_video": downloaded_videos[0] if downloaded_videos else None,
        "primary_thumbnail": thumbnails[0] if thumbnails else None,
    }


def process_and_save_media(
    result: Any,  # MuseGenerationResult
    output_dir: Path | str = MUSE_DOWNLOADS_DIR,
    prompt_index: int = 1,
    cookie_header: str | None = None,
    max_videos: int = 1,
    log_callback: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Tải toàn bộ video thành phẩm (đồng bộ), trích xuất thumbnail và lưu metadata."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    downloaded_videos: list[str] = []
    thumbnails: list[str] = []
    metadata_files: list[str] = []

    headers = {}
    if cookie_header:
        headers["Cookie"] = cookie_header

    video_urls = getattr(result, "video_urls", []) or []
    prompt = getattr(result, "prompt", "video")

    if max_videos > 0 and len(video_urls) > max_videos:
        video_urls = video_urls[-max_videos:]

    for i, v_url in enumerate(video_urls, start=1):
        if max_videos > 0 and len(downloaded_videos) >= max_videos:
            break

        filename = generate_video_filename(prompt, index=prompt_index if (max_videos == 1 or len(video_urls) == 1) else i)
        dest_file = out_dir / filename

        success = download_media_file(
            url=v_url,
            dest_path=dest_file,
            headers=headers,
            log_callback=log_callback,
        )

        if success and dest_file.is_file():
            is_valid, media_fmt = verify_video_file_integrity(dest_file)
            if not is_valid:
                _log(f"⚠️ File đã tải về không phải video hợp lệ (định dạng: {media_fmt}). Xóa file ảnh/lỗi: {dest_file.name}", log_callback)
                try:
                    dest_file.unlink()
                except Exception:
                    pass
                continue

            _log(f"✅ Xác thực tính toàn vẹn video thành công ({media_fmt}, {round(dest_file.stat().st_size / (1024*1024), 2)} MB)", log_callback)
            downloaded_videos.append(str(dest_file))

            # Trích xuất thumbnail
            thumb = extract_video_thumbnail(dest_file, log_callback=log_callback)
            if thumb:
                thumbnails.append(str(thumb))

            # Lưu metadata
            meta = {
                "prompt": prompt,
                "video_file": filename,
                "source_url": v_url,
                "duration_seconds": getattr(result, "duration_seconds", 0.0),
                "created_at": datetime.now().isoformat(),
                "turn_id": getattr(result, "turn_id", None),
                "reply_text": getattr(result, "reply_text", ""),
            }
            meta_path = save_video_metadata(dest_file, meta)
            metadata_files.append(str(meta_path))

            if max_videos > 0 and len(downloaded_videos) >= max_videos:
                break

    return {
        "downloaded_videos": downloaded_videos,
        "thumbnails": thumbnails,
        "metadata_files": metadata_files,
        "primary_video": downloaded_videos[0] if downloaded_videos else None,
        "primary_thumbnail": thumbnails[0] if thumbnails else None,
    }
