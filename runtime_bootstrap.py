from __future__ import annotations

import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

from runtime_media import prepare_media_environment
from runtime_paths import (
    APP_DISPLAY_NAME,
    CHROME_USER_DATA_ROOT,
    INSTALL_DIR,
    MANAGED_CHROME_ROOT,
    RUNTIME_DIR,
    USER_DATA_DIR,
    ensure_runtime_dirs,
)

CHROME_FOR_TESTING_LKG_URL = (
    "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json"
)
MANAGED_CHROME_META_FILE = MANAGED_CHROME_ROOT / "manifest.json"


class BootstrapError(RuntimeError):
    pass


def _emit(progress_callback, message: str) -> None:
    text = str(message or "").strip()
    if not text:
        return
    if callable(progress_callback):
        try:
            progress_callback(text)
            return
        except Exception:
            pass
    print(text)


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


def _system_chrome_candidates() -> list[Path]:
    if os.name != "nt":
        return []
    return [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path(os.getenv("LOCALAPPDATA", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    ]


def _resolve_system_chrome() -> str:
    if os.name == "nt":
        for candidate in _system_chrome_candidates():
            try:
                if candidate.is_file():
                    return str(candidate.resolve())
            except Exception:
                if candidate.is_file():
                    return str(candidate)
        for name in ("chrome", "chrome.exe", "msedge", "msedge.exe"):
            resolved = shutil.which(name)
            if resolved:
                return resolved
        return ""

    if os.name == "posix":
        if Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome").is_file():
            return str(Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"))
        mac_user = Path("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome").expanduser()
        if mac_user.is_file():
            return str(mac_user)

        for chrome_name in ("google-chrome", "google-chrome-stable", "chromium-browser", "chromium"):
            resolved = shutil.which(chrome_name)
            if resolved:
                return resolved
    return ""


def _resolve_managed_chrome_from_manifest() -> str:
    try:
        if not MANAGED_CHROME_META_FILE.is_file():
            return ""
        payload = json.loads(MANAGED_CHROME_META_FILE.read_text(encoding="utf-8"))
    except Exception:
        return ""

    chrome_path = _resolve_existing_file(payload.get("chrome_exe"))
    if chrome_path:
        return chrome_path
    return ""


def _resolve_managed_chrome_by_scan() -> str:
    patterns = [
        ("chrome-win64", "chrome.exe"),
        ("chrome-win32", "chrome.exe"),
        ("chrome-linux64", "chrome"),
        ("chrome-mac-x64", "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"),
        ("chrome-mac-arm64", "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"),
    ]
    for subdir in sorted(MANAGED_CHROME_ROOT.glob("*"), reverse=True):
        if not subdir.is_dir():
            continue
        for chrome_dir, exe_rel in patterns:
            candidate = subdir / chrome_dir / exe_rel
            try:
                if candidate.is_file():
                    return str(candidate.resolve())
            except Exception:
                if candidate.is_file():
                    return str(candidate)
    return ""


def resolve_managed_chrome() -> str:
    manifest_path = _resolve_managed_chrome_from_manifest()
    if manifest_path:
        return manifest_path
    return _resolve_managed_chrome_by_scan()


def resolve_browser_executable() -> str:
    env_chrome = _resolve_existing_file(os.getenv("CHROME_EXE_PATH") or os.getenv("CHROME_PATH"))
    if env_chrome:
        return env_chrome

    system_chrome = _resolve_system_chrome()
    if system_chrome:
        return system_chrome

    return resolve_managed_chrome()


def _read_json(url: str, timeout: int = 30) -> dict:
    request = Request(
        url,
        headers={
            "User-Agent": f"{APP_DISPLAY_NAME} bootstrap",
            "Accept": "application/json",
        },
    )
    with urlopen(request, timeout=int(timeout)) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload or "{}")


def _download_to_file(url: str, destination: Path, progress_callback=None, timeout: int = 120) -> None:
    request = Request(url, headers={"User-Agent": f"{APP_DISPLAY_NAME} bootstrap"})
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(request, timeout=int(timeout)) as response, open(destination, "wb") as handle:
        total = int(response.headers.get("Content-Length") or 0)
        downloaded = 0
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
            downloaded += len(chunk)
            if total > 0:
                percent = min(100, int((downloaded * 100) / total))
                _emit(progress_callback, f"Dang tai Chrome runtime... {percent}%")


def _resolve_cft_download() -> tuple[str, str]:
    payload = _read_json(CHROME_FOR_TESTING_LKG_URL)
    channels = dict(payload.get("channels") or {})
    stable = dict(channels.get("Stable") or {})
    version = str(stable.get("version") or "").strip()
    downloads = dict(stable.get("downloads") or {})
    candidates = list(downloads.get("chrome") or [])
    platform_name = "win64"
    for item in candidates:
        if str(item.get("platform") or "").strip() == platform_name:
            url = str(item.get("url") or "").strip()
            if url and version:
                return version, url
    raise BootstrapError("Khong tim thay ban Chrome for Testing phu hop cho Windows x64.")


def install_managed_chrome(progress_callback=None) -> str:
    if os.name != "nt":
        return ""

    current = resolve_managed_chrome()
    if current:
        return current

    _emit(progress_callback, "Dang chuan bi Chrome runtime...")
    version, url = _resolve_cft_download()
    version_dir = MANAGED_CHROME_ROOT / version
    version_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="tool_veo_cft_") as tmpdir:
        archive_path = Path(tmpdir) / "chrome-win64.zip"
        _download_to_file(url, archive_path, progress_callback=progress_callback)
        _emit(progress_callback, "Dang giai nen Chrome runtime...")
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(version_dir)

    chrome_exe = version_dir / "chrome-win64" / "chrome.exe"
    if not chrome_exe.is_file():
        raise BootstrapError("Da tai Chrome runtime nhung khong tim thay chrome.exe sau giai nen.")

    MANAGED_CHROME_META_FILE.parent.mkdir(parents=True, exist_ok=True)
    MANAGED_CHROME_META_FILE.write_text(
        json.dumps(
            {
                "version": version,
                "chrome_exe": str(chrome_exe),
                "source": "chrome-for-testing",
                "url": url,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return str(chrome_exe.resolve())


def ensure_chrome_available(progress_callback=None) -> str:
    chrome_exe = resolve_browser_executable()
    if chrome_exe:
        return chrome_exe

    if os.name != "nt":
        return ""

    return install_managed_chrome(progress_callback=progress_callback)


def prepare_runtime_environment(progress_callback=None) -> dict[str, str]:
    ensure_runtime_dirs()

    prepared = {
        "TOOL_VEO_USER_DATA_DIR": str(USER_DATA_DIR),
        "TOOL_VEO_INSTALL_DIR": str(INSTALL_DIR),
        "TOOL_VEO_RUNTIME_DIR": str(RUNTIME_DIR),
        "CHROME_USER_DATA_ROOT": str(CHROME_USER_DATA_ROOT),
    }
    for key, value in prepared.items():
        os.environ[key] = value

    prepared.update(prepare_media_environment())

    chrome_exe = ensure_chrome_available(progress_callback=progress_callback)
    if chrome_exe:
        os.environ["CHROME_EXE_PATH"] = chrome_exe
        prepared["CHROME_EXE_PATH"] = chrome_exe

    return prepared


def bootstrap_runtime(progress_callback=None) -> dict[str, str]:
    try:
        return prepare_runtime_environment(progress_callback=progress_callback)
    except Exception as exc:
        raise BootstrapError(str(exc)) from exc
