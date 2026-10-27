from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser

if sys.platform == "win32":
    try:
        if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr is not None and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from branding_config import APP_VERSION, WINDOW_TITLE
from runtime_bootstrap import BootstrapError, bootstrap_runtime


def _show_bootstrap_error(message: str) -> None:
    try:
        from tkinter import Tk, messagebox

        root = Tk()
        root.withdraw()
        messagebox.showerror(WINDOW_TITLE, message)
        root.destroy()
    except Exception:
        print(message, file=sys.stderr)


def _open_browser_when_ready(url: str, delay: float = 1.2) -> None:
    time.sleep(delay)
    try:
        print(f"[LAUNCHER] Đang mở giao diện Web Studio tại: {url}")
        webbrowser.open(url)
    except Exception as exc:
        print(f"[LAUNCHER] Không thể tự động mở trình duyệt: {exc}")


def _run_desktop_app() -> None:
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Muse.AI.Studio.App")
        except Exception:
            pass

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QIcon
    from qt_ui import MainWindow, apply_dark_theme
    from runtime_paths import get_icon_path

    print(f"[LAUNCHER] Khởi chạy giao diện Desktop App (PyQt6 Native)...")
    app = QApplication(sys.argv)
    apply_dark_theme(app)

    icon_path = get_icon_path("app_icon.ico") or get_icon_path("logo.png")
    if icon_path and os.path.isfile(icon_path):
        app_icon = QIcon(icon_path)
        if not app_icon.isNull():
            app.setWindowIcon(app_icon)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


def _run_web_server() -> None:
    import os
    import socket

    host = os.getenv("TOOL_VEO_HOST", "127.0.0.1")
    raw_port = os.getenv("PORT") or os.getenv("TOOL_VEO_PORT")
    if raw_port:
        try:
            port = int(raw_port)
        except ValueError:
            port = 8000
    else:
        port = 8000
        for p in range(8000, 8020):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind((host, p))
                    port = p
                    break
                except OSError:
                    continue
    studio_url = f"http://{host}:{port}"

    # Start thread to open browser once server is listening
    browser_thread = threading.Thread(
        target=_open_browser_when_ready,
        args=(studio_url,),
        daemon=True,
    )
    browser_thread.start()

    import uvicorn
    try:
        uvicorn.run(app, host=host, port=port, log_level="info")
    except KeyboardInterrupt:
        print("\n[LAUNCHER] Đã dừng máy chủ VEO Studio. Tạm biệt!")


def main() -> None:
    if "--muse-service" in sys.argv:
        import os
        import uvicorn
        from runtime_paths import ensure_runtime_dirs
        ensure_runtime_dirs()
        from muse2api_backend.app import app
        host = os.getenv("MUSE2API_HOST", "127.0.0.1")
        port = int(os.getenv("MUSE2API_PORT", "18610"))
        try:
            uvicorn.run(app, host=host, port=port, log_level="warning")
        except KeyboardInterrupt:
            pass
        return

    print(f"============================================================")
    print(f"🚀  MUSE AI STUDIO - PROMAX {APP_VERSION}")
    print(f"    Automated Video Generator via Meta Muse AI & REST API Engine")
    print(f"============================================================")

    try:
        bootstrap_runtime()
    except BootstrapError as exc:
        _show_bootstrap_error(f"Không thể khởi động {WINDOW_TITLE}: {exc}")
        return

    _run_desktop_app()


if __name__ == "__main__":
    main()
