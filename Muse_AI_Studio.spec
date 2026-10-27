# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

project_root = Path(SPECPATH)
build_assets_root = project_root / "build-assets" / "windows"
bin_root = build_assets_root / "bin"

datas = []

# Web UI not required for Muse AI Studio desktop

# muse2api_backend assets
backend_admin = project_root / "muse2api_backend" / "admin.html"
if backend_admin.exists():
    datas.append((str(backend_admin), "muse2api_backend"))
backend_version = project_root / "muse2api_backend" / "version.json"
if backend_version.exists():
    datas.append((str(backend_version), "muse2api_backend"))
backend_env = project_root / "muse2api_backend" / ".env"
if backend_env.exists():
    datas.append((str(backend_env), "muse2api_backend"))

# App branding assets
for asset_name in ("app_icon.ico", "logo.jpeg", "logo.png"):
    candidate = project_root / asset_name
    if candidate.exists():
        datas.append((str(candidate), "."))

# Package datas and metadata
datas += collect_data_files("playwright")
datas += collect_data_files("imageio_ffmpeg")
try:
    datas += copy_metadata("google-genai")
except Exception:
    pass
try:
    datas += copy_metadata("edge-tts")
except Exception:
    pass
try:
    datas += copy_metadata("playwright")
except Exception:
    pass

binaries = []
if bin_root.exists():
    for item in sorted(bin_root.iterdir()):
        if item.is_file() and item.suffix.lower() == ".exe":
            binaries.append((str(item), "bin"))

hiddenimports = sorted(
    set(
        collect_submodules("playwright")
        + collect_submodules("uvicorn")
        + collect_submodules("fastapi")
        + collect_submodules("starlette")
        + collect_submodules("qt_ui")
        + collect_submodules("muse2api_backend")
        + [
            "google.genai",
            "PyQt6.QtCore",
            "PyQt6.QtGui",
            "PyQt6.QtWidgets",
            "PyQt6.QtSvg",
            "PyQt6.QtNetwork",
            "PyQt6.sip",
            "imageio_ffmpeg",
            "edge_tts",
            "cryptography",
            "websockets",
            "websocket",
            "requests",
            "urllib3",
            "aiohttp",
            "pydantic",
            "pydantic_core",
            "python_multipart",
            "video_motion_smoother",
            "shorts_composer",
            "shorts_tts_engine",
            "pipeline_shorts_generator",
            "muse_chrome",
            "muse_auth",
            "muse_client",
            "muse_media",
            "muse_service_manager",
            "A_workflow_muse_text_to_video",
            "base_workflow",
            "worker_run_workflow",
            "workflow_error_policy",
            "workflow_run_control",
        ]
    )
)

icon_path = None
candidates = [
    project_root / "app_icon.ico",
    project_root / "icons" / "app_icon.ico",
    project_root / "logo.ico",
]
for candidate in candidates:
    if candidate.exists():
        icon_path = str(candidate)
        break

a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Muse AI Studio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=icon_path,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Muse AI Studio",
)
