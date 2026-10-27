# -*- coding: utf-8 -*-
"""
Muse2API Local Service Manager for RUN_VEO_V1.1 Desktop Application.
Manages the background FastAPI microservice lifecycle, port health checks,
and automatically synchronizes session cookies from DATA_GENERAL/muse_session.json.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable
import urllib.request
from urllib.error import URLError

from runtime_paths import (
    BASE_DIR,
    DATA_GENERAL_DIR,
    INSTALL_DIR,
    USER_DATA_DIR,
    MUSE2API_DATA_DIR as _RUNTIME_MUSE2API_DATA_DIR,
)
from runtime_bootstrap import resolve_browser_executable, ensure_chrome_available

logger = logging.getLogger("muse_service_manager")

MUSE2API_HOST = "127.0.0.1"
MUSE2API_PORT = 18610
MUSE2API_CDP_PORT = 19210
MUSE2API_KEY = "muse_desktop_local_secret"
MUSE2API_BACKEND_DIR = BASE_DIR / "muse2api_backend"
MUSE_SESSION_FILE = DATA_GENERAL_DIR / "muse_session.json"

if getattr(sys, "frozen", False):
    MUSE2API_DATA_DIR = _RUNTIME_MUSE2API_DATA_DIR
else:
    legacy_data = BASE_DIR / "muse2api_backend" / "data"
    MUSE2API_DATA_DIR = legacy_data if legacy_data.exists() else _RUNTIME_MUSE2API_DATA_DIR

MUSE2API_ACCOUNTS_FILE = MUSE2API_DATA_DIR / "accounts.json"


def _log(msg: str, cb: Callable[[str], None] | None = None) -> None:
    if callable(cb):
        try:
            cb(msg)
            return
        except Exception:
            pass
    print(f"[{time.strftime('%H:%M:%S')}] [MUSE_SERVICE] {msg}")


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        try:
            s.connect((host, port))
            return True
        except (OSError, socket.timeout, ConnectionRefusedError):
            return False


class MuseServiceManager:
    """Quản lý tiến trình FastAPI server của muse2api."""

    _proc: subprocess.Popen | None = None

    @classmethod
    def get_api_base_url(cls) -> str:
        return f"http://{MUSE2API_HOST}:{MUSE2API_PORT}"

    @classmethod
    def get_api_headers(cls) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {MUSE2API_KEY}",
            "Content-Type": "application/json",
        }

    @classmethod
    def is_service_ready(cls) -> bool:
        """Kiểm tra health-check GET /admin/status trên cổng 18610."""
        if not is_port_in_use(MUSE2API_PORT, host=MUSE2API_HOST):
            return False
        url = f"{cls.get_api_base_url()}/admin/status"
        req = urllib.request.Request(url, headers=cls.get_api_headers())
        try:
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                return resp.status == 200
        except Exception:
            return False

    @classmethod
    def sync_session_from_disk(cls, log_callback: Callable[[str], None] | None = None) -> bool:
        """Tự động đồng bộ cookie và token từ muse_session.json vào accounts.json của muse2api."""
        if not MUSE_SESSION_FILE.exists():
            _log("⚠️ Chưa có file DATA_GENERAL/muse_session.json để đồng bộ.", log_callback)
            return False

        try:
            session_data = json.loads(MUSE_SESSION_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            _log(f"⚠️ Lỗi đọc muse_session.json: {e}", log_callback)
            return False

        cookies_raw = session_data.get("cookies", [])
        if not cookies_raw:
            _log("⚠️ File muse_session.json không chứa cookies.", log_callback)
            return False

        cookie_dict = {}
        cookies_exp = {}
        for c in cookies_raw:
            if isinstance(c, dict) and c.get("name") and c.get("value"):
                cookie_dict[c["name"]] = c["value"]
                exp = c.get("expires")
                if exp and isinstance(exp, (int, float)) and exp > 0:
                    cookies_exp[c["name"]] = int(exp)

        essential_names = ["hatch_sess", "hatch_gw", "hatch_vml", "hatch_native_auth_device"]
        has_essential = any(k in cookie_dict for k in essential_names)
        if not has_essential:
            _log("⚠️ Cookies trong muse_session.json thiếu các session token trọng yếu của Muse.", log_callback)

        MUSE2API_DATA_DIR.mkdir(parents=True, exist_ok=True)
        now_ts = int(time.time())
        vml_exp = cookies_exp.get("hatch_vml") or (now_ts + 2 * 86400)

        accounts = []
        if MUSE2API_ACCOUNTS_FILE.exists():
            try:
                accounts = json.loads(MUSE2API_ACCOUNTS_FILE.read_text(encoding="utf-8"))
                if not isinstance(accounts, list):
                    accounts = []
            except Exception:
                accounts = []

        # Cập nhật hoặc tạo mới account mặc định
        target_acc = None
        for a in accounts:
            if a.get("label") == "Default Desktop Profile":
                target_acc = a
                break

        if target_acc is not None:
            target_acc["cookies"] = cookie_dict
            target_acc["cookies_exp"] = cookies_exp
            target_acc["expires_at"] = vml_exp
            target_acc["enabled"] = True
            target_acc["synced_at"] = now_ts
        else:
            new_acc = {
                "id": "desktop_main",
                "label": "Default Desktop Profile",
                "cookies": cookie_dict,
                "cookies_exp": cookies_exp,
                "expires_at": vml_exp,
                "enabled": True,
                "created_at": now_ts,
                "last_used": None,
                "last_keepalive": None,
                "use_count": 0,
                "ok": True,
                "note": "Auto-synced from desktop muse_session.json",
                "synced_at": now_ts,
            }
            accounts.append(new_acc)

        MUSE2API_ACCOUNTS_FILE.write_text(json.dumps(accounts, ensure_ascii=False, indent=2), encoding="utf-8")
        _log(f"💾 Đã đồng bộ {len(cookie_dict)} cookies vào {MUSE2API_ACCOUNTS_FILE.name}.", log_callback)
        return True

    @classmethod
    def start_service(cls, timeout: int = 15, log_callback: Callable[[str], None] | None = None) -> bool:
        """Khởi động tiến trình uvicorn cho muse2api_backend nếu chưa chạy."""
        cls.sync_session_from_disk(log_callback=log_callback)

        if cls.is_service_ready():
            _log(f"🟢 Muse2API Service đã sẵn sàng tại {cls.get_api_base_url()}.", log_callback)
            return True

        if is_port_in_use(MUSE2API_PORT, host=MUSE2API_HOST):
            _log(f"⚠️ Cổng {MUSE2API_PORT} đang bị tiến trình khác chiếm dụng nhưng không phản hồi, đang dọn dẹp...", log_callback)
            cls.stop_service(log_callback=log_callback)
            time.sleep(1.0)

        # Ưu tiên python từ virtualenv của dự án để đảm bảo có đủ gói (websocket, uvicorn...)
        candidate_pythons = [
            BASE_DIR / ".venv" / "Scripts" / "python.exe",
            BASE_DIR / ".venv" / "bin" / "python",
            Path(sys.executable),
        ]
        python_exe = sys.executable
        for cand in candidate_pythons:
            if cand.is_file():
                python_exe = str(cand.resolve())
                break
        env = dict(os.environ)
        env["MUSE2API_HOST"] = MUSE2API_HOST
        env["MUSE2API_PORT"] = str(MUSE2API_PORT)
        env["MUSE2API_CDP_PORT"] = str(MUSE2API_CDP_PORT)
        env["MUSE2API_KEY"] = MUSE2API_KEY
        if getattr(sys, "frozen", False):
            env["MUSE2API_HOME"] = str(MUSE2API_DATA_DIR.resolve())
        else:
            env["MUSE2API_HOME"] = str(MUSE2API_BACKEND_DIR.resolve())
            env["PYTHONPATH"] = str(MUSE2API_BACKEND_DIR.resolve())
        env["MUSE2API_DATA_DIR"] = str(MUSE2API_DATA_DIR.resolve())

        # Tìm Chrome executable trên Windows với fallback đa tầng (Chrome / Edge / Managed)
        chrome_exe = resolve_browser_executable() or os.getenv("CHROME_EXE_PATH", "").strip()
        if not chrome_exe or not os.path.isfile(chrome_exe):
            try:
                chrome_exe = ensure_chrome_available(progress_callback=log_callback)
            except Exception:
                chrome_exe = ""

        if chrome_exe and os.path.isfile(chrome_exe):
            env["MUSE2API_CHROMIUM"] = str(chrome_exe)
            env["CHROME_EXE_PATH"] = str(chrome_exe)

        _log(f"🚀 Khởi động Muse2API Server tại {cls.get_api_base_url()}...", log_callback)

        creationflags = 0
        if os.name == "nt":
            creationflags = (
                getattr(subprocess, "DETACHED_PROCESS", 0)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                | getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )

        if getattr(sys, "frozen", False):
            cmd = [
                sys.executable,
                "--muse-service",
            ]
            cwd_dir = str(INSTALL_DIR.resolve())
        else:
            cmd = [
                python_exe,
                "-m", "uvicorn",
                "app:app",
                "--host", MUSE2API_HOST,
                "--port", str(MUSE2API_PORT),
                "--log-level", "warning",
            ]
            cwd_dir = str(MUSE2API_BACKEND_DIR.resolve())

        MUSE2API_DATA_DIR.mkdir(parents=True, exist_ok=True)
        log_file_path = MUSE2API_DATA_DIR / "server.log"
        log_file = open(log_file_path, "a", encoding="utf-8")

        try:
            cls._proc = subprocess.Popen(
                cmd,
                cwd=cwd_dir,
                env=env,
                creationflags=creationflags,
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=log_file,
            )
        except Exception as e:
            _log(f"❌ Không thể khởi động uvicorn: {e}", log_callback)
            return False

        # Chờ server khởi động thành công
        deadline = time.time() + timeout
        while time.time() < deadline:
            if cls.is_service_ready():
                _log(f"🎉 Muse2API Server đã khởi động thành công trên cổng {MUSE2API_PORT}!", log_callback)
                return True
            time.sleep(0.5)

        _log(f"⚠️ Muse2API Server khởi động quá thời gian chờ ({timeout}s).", log_callback)
        return False

    @classmethod
    def stop_service(cls, log_callback: Callable[[str], None] | None = None) -> None:
        """Dừng tiến trình server và dọn dẹp Chromium headless."""
        if cls._proc is not None:
            try:
                cls._proc.terminate()
                cls._proc.wait(timeout=3)
            except Exception:
                try:
                    cls._proc.kill()
                except Exception:
                    pass
            cls._proc = None
            _log("🛑 Đã dừng tiến trình Muse2API Service.", log_callback)

        # Giải phóng cổng 18610 nếu còn tiến trình mồ côi chiếm dụng
        if os.name == "nt":
            try:
                ps_port = f"""
                $conns = Get-NetTCPConnection -LocalPort {MUSE2API_PORT} -ErrorAction SilentlyContinue
                foreach ($c in $conns) {{
                    if ($c.OwningProcess -and $c.OwningProcess -ne $PID) {{
                        Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
                    }}
                }}
                """
                subprocess.run(["powershell", "-NoProfile", "-Command", ps_port], capture_output=True, check=False)
            except Exception:
                pass

        # Dọn dẹp Chromium port 19210 nếu còn sót
        if os.name == "nt":
            try:
                ps = "$p = Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | Where-Object { $_.CommandLine -like '*19210*' }; foreach ($x in $p) { Stop-Process -Id $x.ProcessId -Force -ErrorAction SilentlyContinue }"
                subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, check=False)
            except Exception:
                pass

    @classmethod
    def restart_service(cls, log_callback: Callable[[str], None] | None = None, timeout: int = 15) -> bool:
        """Khởi động lại toàn diện dịch vụ Muse2API backend."""
        _log("🔄 Đang tái khởi động Muse2API Server...", log_callback)
        cls.stop_service(log_callback)
        time.sleep(1.0)
        return cls.start_service(timeout=timeout, log_callback=log_callback)
