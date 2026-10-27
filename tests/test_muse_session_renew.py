"""Unit test kiểm thử cơ chế tự động gia hạn phiên (Session Auto-Renew & Cloud VM) cho Muse AI."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Thêm root vào sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from muse_auth import MuseAuthManager
from settings_manager import SettingsManager


async def _async_test_session_renew():
    print("🧪 [TEST] Bắt đầu kiểm tra MuseAuthManager.renew_session_http...")

    session = SettingsManager.load_muse_session()
    if not session or not session.get("cookies"):
        print("⚠️ Không có session cookies trong file DATA_GENERAL/muse_session.json để test.")
        return

    res = await MuseAuthManager.renew_session_http(context=None, log_callback=print)
    print("\n📊 Kết quả gia hạn:")
    print("  Success:", res.get("success"))
    print("  Status:", res.get("status"))
    print("  VM ID:", res.get("vm_id"))
    print("  VM State:", res.get("vm_state"))
    print("  Renewed Cookies:", res.get("renewed_cookies"))

    assert res.get("success") is True, f"Gia hạn thất bại: {res.get('error')}"
    assert res.get("status") == "assigned", f"Status không phải assigned: {res.get('status')}"
    assert res.get("vm_state") in ("RUNNING", "STOPPED", "STARTING", "live", "SUSPENDED"), f"VM state lạ: {res.get('vm_state')}"

    # Kiểm tra session file đã được lưu lại
    updated_session = SettingsManager.load_muse_session()
    assert "last_renewed_at" in updated_session, "Thiếu trường last_renewed_at"
    assert updated_session.get("vm_id") == res.get("vm_id")
    print("\n✅ PASS: Test tự động gia hạn phiên Muse AI thành công 100%!")


def test_session_renew():
    asyncio.run(_async_test_session_renew())


if __name__ == "__main__":
    test_session_renew()
