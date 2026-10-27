import os
import asyncio
import sys
from muse_auth import MuseAuthManager
from settings_manager import SettingsManager

async def main():
    settings = SettingsManager.load_muse_settings()
    email = settings.get("email", os.getenv("MUSE_TEST_EMAIL", ""))
    password = settings.get("password", os.getenv("MUSE_TEST_PASSWORD", ""))
    two_fa = settings.get("two_factor_secret", os.getenv("MUSE_TEST_TOTP_SECRET", ""))
    profile = settings.get("current_profile", "MUSE_PROFILE_1")

    print("=" * 60)
    print("🚀 BẮT ĐẦU CHẠY E2E AUTO LOGIN MUSE AI")
    print(f"📧 Email: {email}")
    print(f"🔑 Password: {'*' * len(password)}")
    print(f"🛡️ 2FA Secret: {two_fa}")
    print(f"👤 Chrome Profile: {profile}")
    print("=" * 60)

    res = await MuseAuthManager.auto_login(
        email=email,
        password=password,
        two_factor_secret=two_fa,
        profile_name=profile,
        timeout_seconds=120,
        log_callback=print,
    )

    print("=" * 60)
    print("KẾT QUẢ ĐĂNG NHẬP:")
    print(f"Success: {res.get('success')}")
    if res.get("success"):
        session = SettingsManager.load_muse_session()
        print(f"✅ Đã lưu phiên: {len(session.get('cookies', []))} cookies")
        print(f"✅ Trạng thái phiên: {MuseAuthManager.is_saved_session_valid()}")
        sys.exit(0)
    else:
        print(f"❌ Thất bại: {res.get('error')}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
