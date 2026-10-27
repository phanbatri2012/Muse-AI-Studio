from __future__ import annotations

import os
import signal
import shutil
import socket
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from runtime_paths import (
    BASE_DIR,
    MUSE_CHROME_USER_DATA_ROOT,
    MUSE_DOWNLOADS_DIR,
)
from runtime_bootstrap import ensure_chrome_available, resolve_browser_executable
from settings_manager import SettingsManager

MUSE_CDP_HOST = os.getenv("MUSE_CDP_HOST", "127.0.0.1")
MUSE_CDP_PORT = int(os.getenv("MUSE_CDP_PORT", "9322"))
DEFAULT_MUSE_PROFILE = os.getenv("MUSE_PROFILE_NAME", "MUSE_PROFILE_1")
MUSE_URL = "https://muse.ai/"

# Cờ tối ưu chống bot detection cho Muse AI / Meta AI
MUSE_CHROME_STEALTH_ARGS = [
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-blink-features=AutomationControlled",  # Loại bỏ cờ navigator.webdriver
    "--remote-allow-origins=*",
    "--window-size=1280,850",
]


def _win_hidden_kwargs() -> dict:
    if os.name != "nt":
        return {}
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
        return {"startupinfo": si, "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    except Exception:
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}


def _normalize_chrome_candidate(raw_path: str | os.PathLike[str] | None) -> Path | None:
    try:
        candidate = Path(str(raw_path or "")).expanduser()
    except Exception:
        return None

    if not str(candidate):
        return None

    if candidate.is_file():
        return candidate

    if candidate.suffix.lower() == ".app":
        app_binary = candidate / "Contents" / "MacOS" / "Google Chrome"
        if app_binary.is_file():
            return app_binary

    return None


def get_chrome_executable_path() -> str:
    for env_name in ("CHROME_EXE_PATH", "CHROME_PATH"):
        env_value = os.getenv(env_name)
        resolved = _normalize_chrome_candidate(env_value)
        if resolved is not None:
            return str(resolved)

    if os.name == "nt":
        resolved = resolve_browser_executable()
        if resolved:
            return resolved
        resolved = ensure_chrome_available()
        if resolved:
            return resolved
    elif os.name == "posix" and os.uname().sysname == "Darwin":
        candidates: list[Path] = [
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome").expanduser(),
        ]
        for path in candidates:
            if path.is_file():
                return str(path)
    else:
        for chrome_name in ("google-chrome", "google-chrome-stable", "chromium-browser", "chromium"):
            chrome_path = shutil.which(chrome_name)
            if chrome_path:
                return chrome_path

    raise FileNotFoundError("Không tìm thấy Google Chrome. Hãy cài đặt Google Chrome hoặc thiết lập CHROME_EXE_PATH.")


def can_bind_port(host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, int(port)))
        return True
    except OSError:
        return False


def is_port_open(host: str, port: int, timeout: float = 0.03) -> bool:
    """Kiểm tra siêu tốc xem cổng có đang lắng nghe hay không (<1ms)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((host, int(port)))
            return True
    except (OSError, socket.timeout, ConnectionRefusedError):
        return False


def is_muse_cdp_ready(cdp_url: str, host: str = MUSE_CDP_HOST, port: int | None = None) -> bool:
    """Kiểm tra xem Chrome CDP đã sẵn sàng hay chưa bằng socket ping trước, urlopen sau."""
    target_port = port
    if target_port is None:
        try:
            parts = cdp_url.split(":")
            if len(parts) >= 3:
                target_port = int(parts[2].split("/")[0])
        except Exception:
            target_port = MUSE_CDP_PORT

    if target_port and not is_port_open(host, target_port):
        return False

    try:
        with urlopen(f"{cdp_url}/json/version", timeout=0.8) as response:
            return response.status == 200
    except (URLError, OSError):
        return False


def wait_for_muse_cdp(cdp_url: str, timeout_seconds: int = 30) -> bool:
    deadline = time.time() + int(timeout_seconds)
    while time.time() < deadline:
        if is_muse_cdp_ready(cdp_url):
            return True
        time.sleep(0.5)
    return False


def pick_muse_cdp_port(host: str = MUSE_CDP_HOST, start_port: int = MUSE_CDP_PORT, max_tries: int = 40) -> int:
    base = int(start_port or 9322)
    for p in range(base, base + int(max_tries)):
        cdp_url = f"http://{host}:{p}"
        if is_muse_cdp_ready(cdp_url):
            continue
        if can_bind_port(host, p):
            return p
    raise RuntimeError(f"Không tìm được port CDP trống cho Muse AI từ {base} (tries={max_tries}).")


def resolve_muse_profile_dir(profile_name: str | None = None) -> Path:
    chosen_profile = str(profile_name or "").strip()
    if not chosen_profile:
        settings = SettingsManager.load_muse_settings()
        chosen_profile = str(settings.get("current_profile") or "").strip()
    if not chosen_profile:
        chosen_profile = DEFAULT_MUSE_PROFILE
    return MUSE_CHROME_USER_DATA_ROOT / chosen_profile


def kill_muse_chrome_by_profile(profile_dir: Path | str) -> None:
    try:
        target = str(Path(profile_dir).resolve())

        if os.name == "nt":
            ps = "\n".join([
                "$target = '" + target.replace("'", "''") + "'",
                "$procs = Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | Where-Object {",
                "  $_.CommandLine -and ($_.CommandLine -like '*--user-data-dir*') -and ($_.CommandLine -like ('*' + $target + '*'))",
                "}",
                "foreach ($p in $procs) {",
                "  try { Stop-Process -Id $p.ProcessId -ErrorAction SilentlyContinue } catch {}",
                "}",
                "Start-Sleep -Milliseconds 900",
                "foreach ($p in $procs) {",
                "  try {",
                "    $alive = Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue",
                "    if ($alive) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }",
                "  } catch {}",
                "}",
            ])
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                **_win_hidden_kwargs(),
            )
            return

        result = subprocess.run(
            ["ps", "ax", "-o", "pid=,command="],
            capture_output=True,
            text=True,
            check=False,
        )
        candidate_pids: list[int] = []
        for raw_line in result.stdout.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) != 2:
                continue
            pid_text, command_line = parts
            if "--user-data-dir" not in command_line or target not in command_line:
                continue
            try:
                candidate_pids.append(int(pid_text))
            except ValueError:
                continue

        for pid in candidate_pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass

        if candidate_pids:
            time.sleep(0.9)

        for pid in candidate_pids:
            try:
                os.kill(pid, 0)
            except OSError:
                continue
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
    except Exception:
        pass


def reset_muse_user_data(profile_name: str | None = None) -> Path:
    profile_dir = resolve_muse_profile_dir(profile_name)
    try:
        kill_muse_chrome_by_profile(profile_dir)
        time.sleep(0.8)
    except Exception:
        pass

    try:
        if profile_dir.exists():
            shutil.rmtree(profile_dir, ignore_errors=True)
    except Exception:
        pass

    profile_dir.mkdir(parents=True, exist_ok=True)
    return profile_dir


def start_muse_chrome_debug(
    chrome_exe: str,
    host: str,
    port: int,
    user_data_dir: Path,
    url: str = MUSE_URL,
    extra_args: list[str] | None = None,
) -> subprocess.Popen:
    user_data_dir.mkdir(parents=True, exist_ok=True)

    cmd: list[str] = [
        chrome_exe,
        f"--remote-debugging-port={int(port)}",
        f"--remote-debugging-address={host}",
        f"--user-data-dir={str(user_data_dir)}",
    ]
    merged_args = list(MUSE_CHROME_STEALTH_ARGS)
    if isinstance(extra_args, list) and extra_args:
        merged_args.extend([str(arg) for arg in extra_args if str(arg or "").strip()])
    cmd.extend(merged_args)
    cmd.append(str(url or MUSE_URL))

    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def open_muse_chrome(
    profile_name: str | None = None,
    url: str = MUSE_URL,
    wait_ready: bool = True,
) -> dict:
    profile_dir = resolve_muse_profile_dir(profile_name)
    profile_dir.mkdir(parents=True, exist_ok=True)
    port = pick_muse_cdp_port(MUSE_CDP_HOST, MUSE_CDP_PORT)
    chrome_exe = get_chrome_executable_path()
    cdp_url = f"http://{MUSE_CDP_HOST}:{port}"

    proc = start_muse_chrome_debug(
        chrome_exe=chrome_exe,
        host=MUSE_CDP_HOST,
        port=port,
        user_data_dir=profile_dir,
        url=url,
    )

    ready = False
    if wait_ready:
        ready = wait_for_muse_cdp(cdp_url, timeout_seconds=15)

    return {
        "success": True,
        "pid": proc.pid,
        "profile_dir": str(profile_dir),
        "port": int(port),
        "cdp_url": cdp_url,
        "cdp_ready": ready,
    }


def is_muse_chrome_running(port: int, host: str = MUSE_CDP_HOST) -> bool:
    """Kiểm tra nhanh xem Chrome CDP có đang chạy trên port hay không (<1ms nếu đóng)."""
    if not is_port_open(host, port, timeout=0.03):
        return False
    return is_muse_cdp_ready(f"http://{host}:{port}", host=host, port=port)


def cleanup_all_muse_processes() -> None:
    """Quét và tiêu diệt triệt để tất cả các tiến trình Chrome zombie thuộc Muse AI."""
    try:
        if os.name == "nt":
            ps = "\n".join([
                "$procs = Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | Where-Object {",
                "  $_.CommandLine -and (($_.CommandLine -like '*muse_profiles*') -or ($_.CommandLine -like '*--remote-debugging-port=932*'))",
                "}",
                "foreach ($p in $procs) {",
                "  try { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue } catch {}",
                "}",
            ])
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                **_win_hidden_kwargs(),
            )
    except Exception:
        pass


import atexit
import sys
import threading

atexit.register(cleanup_all_muse_processes)

try:
    if threading.current_thread() is threading.main_thread():
        def _on_muse_signal(signum, frame):
            cleanup_all_muse_processes()
            sys.exit(0)

        signal.signal(signal.SIGINT, _on_muse_signal)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _on_muse_signal)
except Exception:
    pass
