import os
import asyncio
import json
import time
from pathlib import Path
from playwright.async_api import async_playwright
from muse_auth import generate_totp_code
from runtime_bootstrap import resolve_browser_executable, ensure_chrome_available

ACCOUNT = {
    "email": os.getenv("MUSE_TEST_EMAIL", ""),
    "password": os.getenv("MUSE_TEST_PASSWORD", ""),
    "two_factor_secret": os.getenv("MUSE_TEST_TOTP_SECRET", "").replace(" ", ""),
}

async def run_complete_login():
    async with async_playwright() as p:
        browser_exe = resolve_browser_executable() or ensure_chrome_available()
        launch_kwargs = {
            "headless": True,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        }
        if browser_exe:
            launch_kwargs["executable_path"] = browser_exe
        browser = await p.chromium.launch(**launch_kwargs)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        print("🌐 1. Đang truy cập https://muse.ai/...")
        await page.goto("https://muse.ai/", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2.0)

        # 1. Điền email
        print(f"📝 2. Điền email: {ACCOUNT['email']}...")
        email_input = page.locator("input[placeholder*='Mobile number or email']").first
        if await email_input.count() == 0:
            email_input = page.locator("input[type='email'], input[type='text']").first
        await email_input.fill(ACCOUNT["email"])
        await asyncio.sleep(1.0)

        cont_btn = page.locator("button:has-text('Continue')").first
        print("🖱️ 3. Nhấn Continue...")
        await cont_btn.click()
        await asyncio.sleep(3.5)

        # 2. Click 'Use password instead'
        use_pwd = page.locator("button:has-text('Use password instead'), a:has-text('Use password instead')").first
        if await use_pwd.count() > 0 and await use_pwd.is_visible():
            print("🔑 4. Chuyển sang nhập mật khẩu...")
            await use_pwd.click()
            await asyncio.sleep(2.5)

        # 3. Điền Password
        pwd_input = page.locator("input[type='password']").first
        if await pwd_input.count() > 0 and await pwd_input.is_visible():
            print("🔒 5. Điền mật khẩu...")
            await pwd_input.fill(ACCOUNT["password"])
            await asyncio.sleep(1.0)
            next_btn = page.locator("button:has-text('Next'), button[type='submit']").first
            await next_btn.click()
            await asyncio.sleep(4.5)

        # 4. Chọn tài khoản (Select an account to continue)
        acc_btn = page.locator("button[data-pel-click='login_account_selection_row_click'], button:has-text('Meta Account')").first
        if await acc_btn.count() > 0 and await acc_btn.is_visible():
            print("👤 6. Chọn hồ sơ Meta Account đầu tiên...")
            await acc_btn.click()
            await asyncio.sleep(4.0)

        # 5. Màn hình xác thực 2FA: chọn method (mặc định Authenticator App đã radio checked)
        method_radio = page.locator("input[name='two-factor-method']").first
        if await method_radio.count() > 0 and await method_radio.is_visible():
            print("🛡️ 7. Màn hình chọn phương thức 2FA -> Nhấn Next...")
            method_next = page.locator("button:has-text('Next'), button[type='submit']").first
            await method_next.click()
            await asyncio.sleep(4.0)

        # 6. Nhập mã TOTP 6 chữ số
        code_input = page.locator(
            "input[autocomplete='one-time-code'], input[placeholder*='code' i], "
            "input[maxlength='6'], input[name='code'], input[name='approvals_code'], input[type='text']"
        ).first

        if await code_input.count() > 0 and await code_input.is_visible():
            totp = generate_totp_code(ACCOUNT["two_factor_secret"])
            print(f"🔢 8. Nhập mã 2FA TOTP: {totp}...")
            await code_input.fill(totp)
            await asyncio.sleep(1.0)

            sub_2fa = page.locator("button:has-text('Next'), button:has-text('Continue'), button:has-text('Confirm'), button[type='submit']").first
            print("🖱️ 9. Nhấn xác nhận mã 2FA...")
            await sub_2fa.click()

        print("⏳ 10. Đang chờ Meta hoàn tất OAuth/OIDC callback và cấp session cookies...")
        deadline = time.time() + 25.0
        cookie_dict = {}
        cookies = []

        while time.time() < deadline:
            await asyncio.sleep(2.0)
            cookies = await context.cookies()
            cookie_dict = {c["name"]: c["value"] for c in cookies}
            if any(k in cookie_dict for k in ["hatch_sess", "hatch_vml"]):
                print(f"🎉 Đã phát hiện session cookies sau {int(time.time() - (deadline - 25))}s!")
                break

        try:
            print(f"🌐 URL cuối cùng: {page.url}")
            print(f"📄 Title cuối cùng: {await page.title()}")
        except Exception:
            pass

        print(f"🍪 Tổng số cookies: {len(cookies)}")
        essential = ["hatch_sess", "hatch_gw", "hatch_vml", "hatch_native_auth_device"]
        found = [k for k in essential if k in cookie_dict]
        print(f"🔑 Cookies trọng yếu tìm thấy: {found}")

        if any(k in cookie_dict for k in ["hatch_sess", "hatch_vml"]):
            print("🎉🎉🎉 ĐĂNG NHẬP THÀNH CÔNG VÀ LẤY ĐƯỢC SESSION! 🎉🎉🎉")

            # Đảm bảo lấy user agent chuẩn
            try:
                ua = await page.evaluate("navigator.userAgent")
            except Exception:
                ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"

            session_data = {
                "captured_at": time.time(),
                "url": page.url,
                "cookie_count": len(cookies),
                "cookies": cookies,
                "cookie_header": "; ".join([f"{c['name']}={c['value']}" for c in cookies]),
                "user_agent": ua,
                "is_authenticated": True,
            }

            # Ghi ra file data_general/muse_session.json
            sess_file = Path("data_general/muse_session.json")
            sess_file.parent.mkdir(parents=True, exist_ok=True)
            sess_file.write_text(json.dumps(session_data, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"💾 Đã lưu session vào: {sess_file.resolve()}")

            # Cập nhật muse_settings.json
            from runtime_paths import MUSE_DOWNLOADS_DIR
            settings_file = Path("data_general/muse_settings.json")
            settings_data = {
                "target_url": "https://muse.ai/",
                "current_profile": "MUSE_PROFILE_1",
                "max_concurrent_tasks": 3,
                "task_timeout_seconds": 249,
                "download_dir": str(MUSE_DOWNLOADS_DIR),
                "email": ACCOUNT["email"],
                "password": ACCOUNT["password"],
                "two_factor_secret": ACCOUNT["two_factor_secret"],
                "max_retries": 4
            }
            settings_file.write_text(json.dumps(settings_data, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"💾 Đã cập nhật muse_settings.json với tài khoản mới.")

            # Cập nhật accounts.json của muse2api_backend
            acc_file = Path("muse2api_backend/data/accounts.json")
            acc_file.parent.mkdir(parents=True, exist_ok=True)
            cookies_exp = {}
            for c in cookies:
                exp = c.get("expires")
                if exp and isinstance(exp, (int, float)) and exp > 0:
                    cookies_exp[c["name"]] = int(exp)

            now_ts = int(time.time())
            vml_exp = cookies_exp.get("hatch_vml") or (now_ts + 2 * 86400)
            new_acc = [{
                "id": "desktop_main",
                "label": "CTD TECH (New Account)",
                "cookies": cookie_dict,
                "cookies_exp": cookies_exp,
                "expires_at": vml_exp,
                "enabled": True,
                "created_at": now_ts,
                "last_used": None,
                "last_keepalive": None,
                "use_count": 0,
                "ok": True,
                "note": f"Auto-synced from new account {ACCOUNT['email']}",
                "synced_at": now_ts,
            }]
            acc_file.write_text(json.dumps(new_acc, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"💾 Đã lưu và đồng bộ accounts.json: {acc_file.resolve()}")
            return True

        else:
            print("⚠️ Chưa thấy session cookie sau khi đăng nhập.")
            return False

if __name__ == "__main__":
    success = asyncio.run(run_complete_login())
    if not success:
        sys.exit(1)
