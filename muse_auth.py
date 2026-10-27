from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import re
import struct
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
try:
    from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright
except ImportError:
    Browser = Any  # type: ignore
    BrowserContext = Any  # type: ignore
    Page = Any  # type: ignore
    Playwright = Any  # type: ignore
    async_playwright = None

def generate_totp_code(secret: str) -> str:
    """Tạo mã TOTP 6 chữ số chuẩn RFC 6238 từ secret key Base32."""
    clean = secret.replace(" ", "").upper()
    pad = len(clean) % 8
    if pad:
        clean += "=" * (8 - pad)
    key = base64.b32decode(clean, casefold=True)
    counter = int(time.time() // 30)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset:offset+4])[0] & 0x7FFFFFFF
    return f"{code % 1000000:06d}"


def validate_tuan89_mailbox_url(email: str, mailbox_url: str) -> str:
    """Validate a Tuan89 mailbox capability URL and return its HTTPS origin."""
    parsed = urlsplit(mailbox_url.strip())
    if parsed.scheme.lower() != "https" or parsed.hostname != "tuan89.site":
        raise ValueError("Link hộp thư phải dùng HTTPS trên tuan89.site.")
    if parsed.username or parsed.password or parsed.port is not None:
        raise ValueError("Link hộp thư không hợp lệ.")
    mailbox_email = (parse_qs(parsed.query).get("email") or [""])[0].strip()
    if mailbox_email.casefold() != email.strip().casefold():
        raise ValueError("Email trong link hộp thư không khớp tài khoản.")
    return "https://tuan89.site"


from runtime_bootstrap import ensure_chrome_available, resolve_browser_executable
from muse_chrome import (
    DEFAULT_MUSE_PROFILE,
    MUSE_CDP_HOST,
    MUSE_CDP_PORT,
    MUSE_URL,
    is_muse_chrome_running,
    open_muse_chrome,
    resolve_muse_profile_dir,
)
from settings_manager import SettingsManager

AUTH_INDICATOR_SELECTORS = [
    "[data-message-item]",
    "[data-testid='hatch-chat-composer']",
    "[data-testid='hatch-chat-typing-indicator']",
    "textarea[placeholder*='Message']",
    "div[contenteditable='true']",
    "[data-copy-exclude]",
    "nav a[href*='/thread/']",
]

AUTH_COOKIE_KEYWORDS = [
    "session",
    "token",
    "auth",
    "jwt",
    "c_user",
    "xs",
    "datr",
    "sb",
    "user_id",
]


def _log(message: str, logger: Callable[[str], None] | None = None) -> None:
    if callable(logger):
        try:
            logger(message)
            return
        except Exception:
            pass
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [MUSE_AUTH] {message}")


class MuseAuthManager:
    """Quản lý kết nối Playwright CDP, kiểm tra đăng nhập và thu hoạch session cho Muse AI."""

    @staticmethod
    async def connect_cdp(
        host: str = MUSE_CDP_HOST,
        port: int = MUSE_CDP_PORT,
        log_callback: Callable[[str], None] | None = None,
    ) -> tuple[Playwright, Browser, BrowserContext, Page]:
        """Kết nối Playwright qua giao thức CDP vào Google Chrome đang chạy."""
        endpoint = f"http://{host}:{int(port)}"
        if async_playwright is None:
            raise RuntimeError(
                "Thư viện 'playwright' không được cài đặt. Hệ thống Muse AI hiện tại đã chuyển sang kiến trúc REST API muse2api."
            )
        playwright = await async_playwright().start()
        try:
            browser = await playwright.chromium.connect_over_cdp(endpoint)
        except Exception as exc:
            await playwright.stop()
            raise RuntimeError(f"Không thể kết nối Playwright CDP tới {endpoint}: {exc}") from exc

        contexts = browser.contexts
        if not contexts:
            context = await browser.new_context()
        else:
            context = contexts[0]

        pages = context.pages
        if not pages:
            page = await context.new_page()
        else:
            page = pages[0]

        _log("✅ Kết nối CDP thành công.", log_callback)
        return playwright, browser, context, page

    @staticmethod
    async def safe_disconnect(
        playwright: Playwright | None,
        browser: Browser | None,
        log_callback: Callable[[str], None] | None = None,
    ) -> None:
        """Ngắt kết nối Playwright an toàn mà KHÔNG đóng tiến trình Chrome của người dùng."""
        if browser is not None:
            try:
                # browser.close() trên CDP chỉ disconnect kết nối CDP, không kill Chrome process
                await browser.close()
            except Exception:
                pass

        if playwright is not None:
            try:
                await playwright.stop()
            except Exception:
                pass
        _log("🔌 Đã ngắt kết nối Playwright CDP an toàn (Chrome vẫn giữ mở).", log_callback)

    @staticmethod
    async def check_authentication(
        page: Page,
        log_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Kiểm tra xem trang hiện tại đã được đăng nhập tài khoản Muse AI chưa."""
        result: dict[str, Any] = {
            "authenticated": False,
            "url": page.url,
            "indicators": [],
            "cookie_count": 0,
            "matched_cookies": [],
            "details": "",
        }

        try:
            cookies = await page.context.cookies()
            result["cookie_count"] = len(cookies)

            # 1. Rà soát cookies có dấu hiệu đăng nhập
            for c in cookies:
                c_name = c.get("name", "").lower()
                c_domain = c.get("domain", "").lower()
                if any(kw in c_name for kw in AUTH_COOKIE_KEYWORDS):
                    result["matched_cookies"].append(f"{c.get('name')} ({c_domain})")

            # 2. Rà soát DOM để tìm các phần tử chỉ xuất hiện khi đã vào màn hình chính
            detected_selectors = []
            for selector in AUTH_INDICATOR_SELECTORS:
                try:
                    locator = page.locator(selector).first
                    if await locator.count() > 0:
                        detected_selectors.append(selector)
                except Exception:
                    continue
            result["indicators"] = detected_selectors

            # 3. Phán đoán trạng thái đăng nhập nghiêm ngặt (KHÔNG dựa vào cookies Meta)
            title = ""
            try:
                title = await page.title()
            except Exception:
                pass

            url_lower = page.url.lower()
            is_login_url = any(x in url_lower for x in ["/login", "/auth", "/signin", "/accounts/login"])

            # 3.1. Nhận diện dấu hiệu của trang Landing / Form đăng nhập
            is_landing = False
            if "your personal ai agent" in title.lower():
                is_landing = True
            else:
                try:
                    landing_input = page.locator("input[placeholder*='Mobile number or email' i]").first
                    if await landing_input.count() > 0 and await landing_input.is_visible():
                        is_landing = True
                except Exception:
                    pass

                if not is_landing:
                    try:
                        heading = page.get_by_text("Log in or create an account").first
                        if await heading.count() > 0 and await heading.is_visible():
                            is_landing = True
                    except Exception:
                        pass

                if not is_landing:
                    try:
                        btn_login_top = page.locator("button:has-text('Log in')").first
                        btn_continue = page.locator("button:has-text('Continue')").first
                        if (await btn_login_top.count() > 0 and await btn_login_top.is_visible()) and (await btn_continue.count() > 0 and await btn_continue.is_visible()):
                            is_landing = True
                    except Exception:
                        pass

            # 3.2. Nhận diện dấu hiệu xác thực đã vào được không gian làm việc (Chat)
            has_chat_ui = False
            if "chat" in title.lower():
                has_chat_ui = True
            elif detected_selectors:
                has_chat_ui = True
            else:
                try:
                    chats_text = page.locator("nav, div").filter(has_text="Chats").first
                    if await chats_text.count() > 0 and await chats_text.is_visible():
                        has_chat_ui = True
                except Exception:
                    pass

            # CHỈ ĐƯỢC COI LÀ ĐĂNG NHẬP KHI: Thấy giao diện Chat VÀ Tuyệt đối KHÔNG ở màn hình Landing/Login
            if has_chat_ui and not is_landing and not is_login_url:
                result["authenticated"] = True
                result["details"] = f"Tiêu đề: '{title}', phát hiện UI: {', '.join(detected_selectors) if detected_selectors else 'Giao diện Chat'}"
            else:
                result["authenticated"] = False
                if is_landing or is_login_url:
                    result["details"] = "Trình duyệt đang ở màn hình chào mừng / đăng nhập (Chưa đăng nhập)"
                else:
                    result["details"] = f"Chưa phát hiện giao diện Chat (Tiêu đề: '{title}')"

        except Exception as exc:
            result["details"] = f"Lỗi khi kiểm tra xác thực: {exc}"

        return result

    @staticmethod
    async def harvest_session(
        page: Page,
        save_to_disk: bool = True,
        log_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Thu hoạch toàn bộ Cookie, LocalStorage và SessionStorage lưu vào file quản lý phiên."""
        _log("📦 Bắt đầu thu hoạch session và tokens từ Muse AI...", log_callback)

        # 1. Thu thập cookies
        cookies = await page.context.cookies()
        muse_cookies = [
            c for c in cookies
            if any(dom in c.get("domain", "") for dom in ["muse.ai", "metaaivm.com", "facebook.com", "instagram.com"])
        ]
        cookie_header = "; ".join([f"{c['name']}={c['value']}" for c in (muse_cookies or cookies)])

        # 2. Thu thập LocalStorage & SessionStorage
        local_storage: dict[str, str] = {}
        session_storage: dict[str, str] = {}
        try:
            local_storage = await page.evaluate(
                "() => { const o = {}; for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); o[k] = localStorage.getItem(k); } return o; }"
            )
        except Exception:
            pass

        try:
            session_storage = await page.evaluate(
                "() => { const o = {}; for (let i = 0; i < sessionStorage.length; i++) { const k = sessionStorage.key(i); o[k] = sessionStorage.getItem(k); } return o; }"
            )
        except Exception:
            pass

        # 3. Đóng gói dữ liệu phiên
        now_iso = datetime.now(timezone.utc).isoformat()
        session_data: dict[str, Any] = {
            "captured_at": now_iso,
            "url": page.url,
            "cookie_count": len(cookies),
            "cookies": cookies,
            "cookie_header": cookie_header,
            "localStorage": local_storage,
            "sessionStorage": session_storage,
            "user_agent": await page.evaluate("navigator.userAgent"),
            "is_authenticated": True,
        }

        if save_to_disk:
            SettingsManager.save_muse_session(session_data)
            _log(f"💾 Đã lưu phiên đăng nhập ({len(cookies)} cookies) vào muse_session.json", log_callback)

        return session_data

    @classmethod
    async def auto_capture_login(
        cls,
        profile_name: str | None = None,
        port: int | None = None,
        target_url: str = MUSE_URL,
        timeout_seconds: int = 180,
        poll_interval: float = 2.0,
        log_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Tự động mở Chrome Muse AI, chờ người dùng đăng nhập và thu hoạch session."""
        chosen_profile = profile_name or DEFAULT_MUSE_PROFILE
        chosen_port = int(port or MUSE_CDP_PORT)

        # 1. Kiểm tra xem Chrome trên port này đã chạy chưa, nếu chưa thì mở
        if not is_muse_chrome_running(chosen_port):
            _log(f"🚀 Khởi chạy Google Chrome profile '{chosen_profile}' trên port {chosen_port}...", log_callback)
            launch_info = open_muse_chrome(chosen_profile, url=target_url, wait_ready=True)
            chosen_port = launch_info["port"]

        # 2. Kết nối Playwright CDP
        playwright = None
        browser = None
        try:
            playwright, browser, context, page = await cls.connect_cdp(
                port=chosen_port,
                log_callback=log_callback,
            )

            # Nếu trang đang trắng hoặc khác muse.ai, điều hướng tới MUSE_URL
            if "muse.ai" not in page.url:
                _log(f"🌐 Điều hướng trình duyệt tới {target_url}...", log_callback)
                await page.goto(target_url, wait_until="commit", timeout=30000)

            _log("⏳ Đang giám sát trạng thái đăng nhập (Bạn có thể thao tác trên cửa sổ Chrome vừa mở)...", log_callback)
            deadline = time.time() + float(timeout_seconds)

            while time.time() < deadline:
                auth_info = await cls.check_authentication(page, log_callback=None)
                if auth_info["authenticated"]:
                    _log(f"🎉 Đăng nhập thành công! {auth_info['details']}", log_callback)
                    session_data = await cls.harvest_session(page, save_to_disk=True, log_callback=log_callback)
                    return {
                        "success": True,
                        "session": session_data,
                        "auth_info": auth_info,
                    }

                await asyncio.sleep(poll_interval)

            return {
                "success": False,
                "error": f"Quá thời gian chờ đăng nhập ({timeout_seconds}s). Hãy thử lại.",
            }

        finally:
            await cls.safe_disconnect(playwright, browser, log_callback)

    @classmethod
    async def auto_login(
        cls,
        email: str,
        password: str,
        two_factor_secret: str | None = None,
        profile_name: str | None = None,
        port: int = MUSE_CDP_PORT,
        timeout_seconds: int = 120,
        target_url: str = MUSE_URL,
        log_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Tự động điền email, password & giải mã 2FA TOTP để đăng nhập vào Muse AI qua Playwright CDP."""
        chosen_profile = profile_name or DEFAULT_MUSE_PROFILE
        chosen_port = port

        if not is_muse_chrome_running(chosen_port):
            _log(f"🚀 Khởi chạy Google Chrome profile '{chosen_profile}'...", log_callback)
            launch_info = open_muse_chrome(chosen_profile, url=target_url, wait_ready=True)
            chosen_port = launch_info["port"]

        playwright = None
        browser = None
        try:
            playwright, browser, context, page = await cls.connect_cdp(
                port=chosen_port,
                log_callback=log_callback,
            )

            if "muse.ai" not in page.url:
                _log(f"🌐 Điều hướng trình duyệt tới {target_url}...", log_callback)
                await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)

            # Chờ 2.5 giây để React SPA hydrate và render DOM đầy đủ
            await asyncio.sleep(2.5)

            auth_info = await cls.check_authentication(page, log_callback=None)
            if auth_info["authenticated"]:
                _log(f"✅ Tài khoản đã đăng nhập sẵn trong hồ sơ Chrome này! ({auth_info['details']})", log_callback)
                session_data = await cls.harvest_session(page, save_to_disk=True, log_callback=log_callback)
                return {"success": True, "session": session_data, "already_logged_in": True}

            _log(f"🔑 Bắt đầu tự động đăng nhập với tài khoản: {email}...", log_callback)

            # 1. Tìm trường nhập Email / Số điện thoại
            email_selectors = [
                "input[placeholder*='Mobile number or email' i]",
                "input[type='email']",
                "input[name='email']",
                "input[placeholder*='email' i]",
                "input[type='text']",
                "#email",
            ]
            email_field = None
            for sel in email_selectors:
                try:
                    field = page.locator(sel).first
                    if await field.is_visible(timeout=1500):
                        email_field = field
                        break
                except Exception:
                    continue

            # Nếu chưa thấy ô nhập email, thử nhấn nút "Log in" / "Sign in" ở header
            if not email_field:
                for signin_sel in [
                    "button:has-text('Log In')", "button:has-text('Log in')", "button:has-text('Sign In')",
                    "a[href*='signin']", "a[href*='login']", "button:has-text('Đăng nhập')"
                ]:
                    try:
                        btn = page.locator(signin_sel).first
                        if await btn.is_visible(timeout=1500):
                            _log(f"🖱️ Nhấn nút đăng nhập ở thanh điều hướng...", log_callback)
                            await btn.click()
                            await asyncio.sleep(2.0)
                            break
                    except Exception:
                        continue
                # Tìm lại sau khi nhấn nút
                for sel in email_selectors:
                    try:
                        field = page.locator(sel).first
                        if await field.is_visible(timeout=2000):
                            email_field = field
                            break
                    except Exception:
                        continue

            if email_field:
                _log(f"📝 Điền tài khoản/email: {email}...", log_callback)
                await email_field.click()
                await email_field.fill(email)
                await asyncio.sleep(1.0)

                # Nhấn nút Continue của form nhập email
                cont_btn = page.locator("button:has-text('Continue'), button[type='submit']").first
                if await cont_btn.is_visible(timeout=2500):
                    _log("🖱️ Nhấn nút Tiếp tục (Continue)...", log_callback)
                    await cont_btn.click()
                    await asyncio.sleep(3.5)
                else:
                    await email_field.press("Enter")
                    await asyncio.sleep(3.5)

                # 2. Kiểm tra xem có xuất hiện tùy chọn 'Use password instead' không
                try:
                    use_pwd_btn = page.get_by_text("Use password instead").first
                    if await use_pwd_btn.is_visible(timeout=3500):
                        _log("🔑 Phát hiện 'Use password instead', đang chuyển sang nhập mật khẩu...", log_callback)
                        await use_pwd_btn.click()
                        await asyncio.sleep(2.5)
                except Exception:
                    pass

                # 3. Tìm trường nhập mật khẩu
                pwd_selectors = [
                    "input[type='password']",
                    "input[name='password']",
                    "input[autocomplete='current-password']",
                    "#password",
                ]
                pwd_field = None
                for sel in pwd_selectors:
                    try:
                        field = page.locator(sel).first
                        if await field.is_visible(timeout=3500):
                            pwd_field = field
                            break
                    except Exception:
                        continue

                if pwd_field:
                    _log("🔒 Đang điền mật khẩu...", log_callback)
                    await pwd_field.click()
                    await pwd_field.fill(password)
                    await asyncio.sleep(1.0)

                    sub_btn = page.locator("button:has-text('Next'), button[type='submit'], button:has-text('Log in'), button:has-text('Continue')").first
                    if await sub_btn.is_visible(timeout=2500):
                        _log("🖱️ Nhấn gửi mật khẩu (Next/Submit)...", log_callback)
                        await sub_btn.click()
                        await asyncio.sleep(3.5)
                    else:
                        await pwd_field.press("Enter")
                        await asyncio.sleep(3.5)
                else:
                    _log("⚠️ Không thấy ô mật khẩu tự động (có thể trang chuyển hướng thẳng sang 2FA).", log_callback)

                # 3.5. Kiểm tra màn hình chọn profile nếu email liên kết nhiều Meta Accounts
                try:
                    acc_btn = page.locator("button[data-pel-click='login_account_selection_row_click'], button:has-text('Meta Account')").first
                    if await acc_btn.is_visible(timeout=3500):
                        _log("👤 Phát hiện màn hình chọn tài khoản (nhiều Meta Accounts) -> Tự động chọn hồ sơ đầu tiên...", log_callback)
                        await acc_btn.click()
                        await asyncio.sleep(3.5)
                except Exception:
                    pass

                # 4. Kiểm tra màn hình chọn phương thức 2FA (nếu có)
                try:
                    two_fa_radio = page.locator("input[name='two-factor-method'], input[type='radio']").first
                    if await two_fa_radio.is_visible(timeout=3000):
                        _log("🛡️ Phát hiện màn hình chọn phương thức 2FA (Authenticator App)...", log_callback)
                        await two_fa_radio.check()
                        await asyncio.sleep(0.5)
                        next_method_btn = page.locator("button:has-text('Next'), button[type='submit']").first
                        if await next_method_btn.is_visible(timeout=2500):
                            await next_method_btn.click()
                            await asyncio.sleep(3.5)
                except Exception:
                    pass

                # 5. Kiểm tra trường nhập mã 2FA / TOTP Authenticator code
                code_selectors = [
                    "input[placeholder*='Confirmation code' i]",
                    "input[autocomplete='one-time-code']",
                    "input[placeholder*='code' i]",
                    "input[maxlength='6']",
                    "input[name='code']",
                    "input[name='approvals_code']",
                    "input[type='text']",
                ]
                code_field = None
                for c_sel in code_selectors:
                    try:
                        c_loc = page.locator(c_sel).first
                        if await c_loc.is_visible(timeout=3500):
                            code_field = c_loc
                            break
                    except Exception:
                        continue

                if code_field:
                    if two_factor_secret:
                        totp_code = generate_totp_code(two_factor_secret)
                        _log(f"🛡️ Phát hiện yêu cầu 2FA! Tự động tạo mã TOTP: {totp_code}...", log_callback)
                        await code_field.click()
                        await code_field.fill(totp_code)
                        await asyncio.sleep(1.0)

                        two_fa_sub = page.locator("button:has-text('Next'), button[type='submit'], button:has-text('Continue'), button:has-text('Confirm')").first
                        if await two_fa_sub.is_visible(timeout=2500):
                            _log("🖱️ Nhấn xác nhận mã 2FA...", log_callback)
                            await two_fa_sub.click()
                        else:
                            await code_field.press("Enter")
                        await asyncio.sleep(5.0)
                    else:
                        _log("⚠️ Phát hiện yêu cầu 2FA nhưng chưa có secret key. Vui lòng xác thực mã trên Chrome...", log_callback)
            else:
                _log("⚠️ Không tìm thấy ô nhập email tự động. Có thể phiên đã sẵn sàng hoặc hãy thao tác trên Chrome.", log_callback)

            # 7. Giám sát trạng thái đăng nhập hoàn tất
            _log("⏳ Đang giám sát trạng thái đăng nhập hoàn tất vào giao diện Muse AI...", log_callback)
            deadline = time.time() + float(timeout_seconds)
            while time.time() < deadline:
                auth_info = await cls.check_authentication(page, log_callback=None)
                if auth_info["authenticated"]:
                    _log(f"🎉 Đăng nhập hoàn tất thành công! {auth_info['details']}", log_callback)
                    session_data = await cls.harvest_session(page, save_to_disk=True, log_callback=log_callback)
                    return {"success": True, "session": session_data, "auth_info": auth_info}
                await asyncio.sleep(2.0)

            return {
                "success": False,
                "error": f"Quá thời gian chờ đăng nhập ({timeout_seconds}s). Vui lòng thử lại.",
            }

        except Exception as exc:
            _log(f"❌ Lỗi trong quá trình tự động đăng nhập: {exc}", log_callback)
            return {"success": False, "error": str(exc)}
        finally:
            await cls.safe_disconnect(playwright, browser, log_callback)

    @classmethod
    async def renew_session_http(
        cls,
        context: Optional[BrowserContext] = None,
        log_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Gọi trực tiếp muse.ai/api/session và /api/hatch/vm/wake để tự động gia hạn hatch_vml (+48h)
        và hatch_sess (+30d), đồng thời đánh thức Cloud VM sang RUNNING mà không cần mở lại trình duyệt.
        """
        import urllib.request
        from http.cookies import SimpleCookie
        import uuid

        _log("🔄 Bắt đầu kiểm tra và gia hạn phiên đăng nhập qua /api/session...", log_callback)

        cookie_dict: dict[str, str] = {}
        saved_session = SettingsManager.load_muse_session() or {}
        user_agent = saved_session.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36")

        # 1. Thu thập cookies từ Playwright context hoặc từ file session đã lưu
        if context is not None:
            try:
                browser_cookies = await context.cookies()
                for c in browser_cookies:
                    if c.get("name") and c.get("value"):
                        cookie_dict[c["name"]] = c["value"]
            except Exception as e:
                _log(f"⚠️ Không thể đọc cookie từ context: {e}", log_callback)

        if not cookie_dict:
            for c in saved_session.get("cookies", []):
                if c.get("name") and c.get("value"):
                    cookie_dict[c["name"]] = c["value"]

        if not cookie_dict:
            _log("❌ Chưa có cookie nào để gia hạn phiên. Vui lòng đăng nhập trước.", log_callback)
            return {"success": False, "error": "Chưa có cookie nào trong phiên"}

        cookie_header_str = "; ".join(f"{k}={v}" for k, v in cookie_dict.items())

        headers = {
            "User-Agent": user_agent,
            "Origin": "https://muse.ai",
            "Referer": "https://muse.ai/thread/new",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Cookie": cookie_header_str,
        }

        def _do_http_renew():
            req = urllib.request.Request("https://muse.ai/api/session", headers=headers)
            with urllib.request.urlopen(req, timeout=12) as resp:
                status = resp.status
                body = resp.read().decode("utf-8")
                raw_set_cookies = resp.headers.get_all("Set-Cookie") if hasattr(resp.headers, "get_all") else []
                return status, body, raw_set_cookies

        try:
            status_code, body_text, set_cookies_headers = await asyncio.to_thread(_do_http_renew)
        except Exception as exc:
            _log(f"❌ Lỗi mạng khi gọi /api/session: {exc}", log_callback)
            return {"success": False, "error": f"Lỗi mạng /api/session: {exc}"}

        if status_code != 200:
            _log(f"⚠️ /api/session trả về mã HTTP {status_code}", log_callback)
            return {"success": False, "error": f"HTTP {status_code}"}

        try:
            sj = json.loads(body_text)
        except Exception:
            _log("⚠️ /api/session trả về dữ liệu không phải JSON", log_callback)
            return {"success": False, "error": "Invalid JSON response"}

        if not isinstance(sj, dict) or sj.get("status") != "assigned":
            _log(f"⚠️ /api/session trả về trạng thái không khả dụng: {sj.get('status')}", log_callback)
            return {"success": False, "status": sj.get("status"), "error": "Session unassigned"}

        vm_id = sj.get("vm_id")
        vm_state = sj.get("vm_state", "RUNNING")
        _log(f"✅ Phiên Muse AI hợp lệ! Trạng thái: {sj.get('status')}, VM ID: {vm_id}, VM State: {vm_state}", log_callback)

        # 2. Xử lý các Cookie mới được cấp từ Set-Cookie
        renewed_names = []
        cookies_to_add_to_context = []
        now_ts = time.time()

        for raw_header in set_cookies_headers:
            sc = SimpleCookie()
            try:
                sc.load(raw_header)
            except Exception:
                continue

            for name, morsel in sc.items():
                val = morsel.value
                if not val:
                    continue
                cookie_dict[name] = val
                renewed_names.append(name)

                # Tính hạn sử dụng
                max_age = morsel.get("max-age")
                try:
                    exp_ts = now_ts + float(max_age) if max_age else now_ts + 7 * 86400
                except (ValueError, TypeError):
                    exp_ts = now_ts + 7 * 86400

                cookies_to_add_to_context.append({
                    "name": name,
                    "value": val,
                    "domain": morsel.get("domain") or ".muse.ai",
                    "path": morsel.get("path") or "/",
                    "secure": True,
                    "sameSite": "Lax",
                    "expires": exp_ts,
                })

        # 3. Đồng bộ cookies mới vào Playwright context nếu context đang sống
        if context is not None and cookies_to_add_to_context:
            try:
                await context.add_cookies(cookies_to_add_to_context)
                _log(f"🍪 Đã đồng bộ {len(cookies_to_add_to_context)} cookie gia hạn vào trình duyệt.", log_callback)
            except Exception as e:
                _log(f"⚠️ Không thể cập nhật cookie vào context: {e}", log_callback)

        # 4. Cập nhật và lưu lại file muse_session.json
        if saved_session:
            existing_cookies = saved_session.get("cookies", [])
            existing_map = {c.get("name"): c for c in existing_cookies if isinstance(c, dict)}
            for new_c in cookies_to_add_to_context:
                existing_map[new_c["name"]] = new_c
            saved_session["cookies"] = list(existing_map.values())
            saved_session["cookie_count"] = len(saved_session["cookies"])
            saved_session["captured_at"] = datetime.now(timezone.utc).isoformat()
            saved_session["last_renewed_at"] = datetime.now(timezone.utc).isoformat()
            saved_session["vm_id"] = vm_id
            saved_session["vm_state"] = vm_state
            saved_session["is_authenticated"] = True
            SettingsManager.save_muse_session(saved_session)
            _log("💾 Đã cập nhật session và thời hạn cookie mới vào DATA_GENERAL/muse_session.json", log_callback)

        # 5. Thử gọi /api/hatch/vm/wake nếu có vm_id
        if vm_id and vm_state != "DISABLED":
            def _do_wake():
                wake_headers = dict(headers)
                wake_headers["Content-Type"] = "application/json"
                wake_payload = json.dumps({
                    "vm_id": vm_id,
                    "retry_count": 0,
                    "connect_attempt_id": str(uuid.uuid4()),
                }).encode("utf-8")
                wake_req = urllib.request.Request("https://muse.ai/api/hatch/vm/wake", data=wake_payload, headers=wake_headers, method="POST")
                try:
                    with urllib.request.urlopen(wake_req, timeout=8) as r:
                        return r.status
                except Exception:
                    return None
            try:
                await asyncio.to_thread(_do_wake)
            except Exception:
                pass

        return {
            "success": True,
            "status": sj.get("status"),
            "vm_id": vm_id,
            "vm_state": vm_state,
            "renewed_cookies": renewed_names,
            "message": f"Gia hạn phiên thành công! Cloud VM: {vm_state}",
        }

    @staticmethod
    def is_saved_session_valid() -> bool:
        """Kiểm tra nhanh xem file muse_session.json đã có phiên hợp lệ chưa."""
        session = SettingsManager.load_muse_session()
        if not session or not isinstance(session, dict):
            return False

        if not session.get("is_authenticated"):
            return False

        cookies = session.get("cookies", [])
        if not cookies or not isinstance(cookies, list):
            return False

        # Kiểm tra xem có cookie nào chưa hết hạn không
        now_ts = time.time()
        valid_cookies = 0
        for c in cookies:
            expires = c.get("expires", -1)
            # expires = -1 nghĩa là session cookie, vẫn hợp lệ
            if expires == -1 or expires > now_ts:
                valid_cookies += 1

        return valid_cookies > 0

    @classmethod
    async def login_standalone(
        cls,
        email: str,
        password: str,
        two_factor_secret: str | None = None,
        mailbox_url: str | None = None,
        timeout_seconds: int = 60,
        log_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Tự động đăng nhập vào Muse AI hoàn toàn độc lập (Headless Playwright) và trả về cookies.
        Hỗ trợ:
        - Nhập Email và nhấn Tiếp tục
        - Chọn 'Use password instead' và nhập Mật khẩu
        - Hoặc nhận mã đăng nhập từ link hộp thư Tuan89
        - Tự động chọn hồ sơ Meta Account đầu tiên nếu xuất hiện màn hình chọn hồ sơ
        - Tự động vượt qua 2FA TOTP với secret key Base32
        - Chờ cấp phát session cookies (hatch_sess, hatch_vml, hatch_gw)
        """
        if async_playwright is None:
            return {"success": False, "error": "Playwright chưa được cài đặt"}

        _log(f"🚀 Bắt đầu đăng nhập độc lập cho tài khoản: {email}...", log_callback)
        playwright = None
        browser = None
        try:
            playwright = await async_playwright().start()

            browser_exe = resolve_browser_executable()
            if not browser_exe or not os.path.isfile(browser_exe):
                _log("🔍 Đang kiểm tra/chuẩn bị trình duyệt Chromium...", log_callback)
                browser_exe = ensure_chrome_available(progress_callback=log_callback)

            launch_kwargs = {
                "headless": True,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            }
            if browser_exe and os.path.isfile(browser_exe):
                launch_kwargs["executable_path"] = browser_exe

            browser = await playwright.chromium.launch(**launch_kwargs)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800},
            )
            page = await context.new_page()

            mailbox_origin = ""
            baseline_message_ids: set[str] = set()
            if mailbox_url:
                mailbox_origin = validate_tuan89_mailbox_url(email, mailbox_url)
                baseline_response = await context.request.get(
                    f"{mailbox_origin}/api/temp-mail/inbox",
                    params={"email": email},
                    timeout=10000,
                )
                baseline_data = await baseline_response.json()
                if not baseline_response.ok or not baseline_data.get("success"):
                    raise RuntimeError("Không thể mở hộp thư nhận mã đăng nhập.")
                baseline_message_ids = {
                    str(item.get("id"))
                    for item in baseline_data.get("messages", [])
                    if item.get("id") is not None
                }

            _log("🌐 Đang kết nối tới https://muse.ai/...", log_callback)
            await page.goto("https://muse.ai/", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2.0)

            # 1. Điền email
            _log(f"📝 Điền email: {email}...", log_callback)
            email_input = page.locator("input[placeholder*='Mobile number or email']").first
            if await email_input.count() == 0:
                email_input = page.locator("input[type='email'], input[type='text']").first
            await email_input.fill(email)
            await asyncio.sleep(1.0)

            cont_btn = page.locator("button:has-text('Continue')").first
            _log("🖱️ Nhấn Tiếp tục (Continue)...", log_callback)
            await cont_btn.click()
            await asyncio.sleep(3.5)

            if mailbox_url:
                _log("📨 Đang chờ mã đăng nhập mới từ hộp thư...", log_callback)
                code_input = page.locator(
                    "input[autocomplete='one-time-code'], input[placeholder*='code' i], "
                    "input[maxlength='6'], input[name='code'], input[name='approvals_code']"
                ).first
                await code_input.wait_for(state="visible", timeout=15000)
                mailbox_deadline = time.time() + float(timeout_seconds)
                mailbox_code = ""
                while time.time() < mailbox_deadline and not mailbox_code:
                    response = await context.request.get(
                        f"{mailbox_origin}/api/temp-mail/inbox",
                        params={"email": email},
                        timeout=10000,
                    )
                    data = await response.json()
                    if response.ok and data.get("success"):
                        for item in data.get("messages", []):
                            message_id = str(item.get("id"))
                            otp_code = str(item.get("otp_code") or "").strip()
                            if (
                                message_id not in baseline_message_ids
                                and re.fullmatch(r"\d{4,8}", otp_code)
                            ):
                                mailbox_code = otp_code
                                break
                    if not mailbox_code:
                        await asyncio.sleep(2.0)
                if not mailbox_code:
                    raise TimeoutError("Không nhận được mã đăng nhập mới từ hộp thư.")
                await code_input.fill(mailbox_code)
                submit_code = page.locator(
                    "button:has-text('Next'), button:has-text('Continue'), "
                    "button:has-text('Confirm'), button[type='submit']"
                ).first
                await asyncio.sleep(1.0)
                session_cookies = {item["name"]: item["value"] for item in await context.cookies()}
                if not any(name in session_cookies for name in ("hatch_sess", "hatch_vml")):
                    try:
                        if (
                            await submit_code.count() > 0
                            and await submit_code.is_visible()
                            and await submit_code.is_enabled()
                        ):
                            await submit_code.click(timeout=5000)
                    except Exception:
                        # Meta may auto-submit the OTP and replace the button during navigation.
                        pass
                await asyncio.sleep(3.5)
            else:
                # 2. Click 'Use password instead' (nếu xuất hiện)
                use_pwd = page.locator("button:has-text('Use password instead'), a:has-text('Use password instead')").first
                if await use_pwd.count() > 0 and await use_pwd.is_visible():
                    _log("🔑 Chuyển sang nhập mật khẩu...", log_callback)
                    await use_pwd.click()
                    await asyncio.sleep(2.5)

                # 3. Điền Password
                pwd_input = page.locator("input[type='password']").first
                if await pwd_input.count() > 0 and await pwd_input.is_visible():
                    _log("🔒 Đang điền mật khẩu...", log_callback)
                    await pwd_input.fill(password)
                    await asyncio.sleep(1.0)
                    next_btn = page.locator("button:has-text('Next'), button[type='submit']").first
                    await next_btn.click()
                    await asyncio.sleep(4.5)
                else:
                    _log("⚠️ Không tìm thấy ô mật khẩu", log_callback)

            # 4. Chọn hồ sơ Meta Account nếu có màn hình chọn
            acc_btn = page.locator("button[data-pel-click='login_account_selection_row_click'], button:has-text('Meta Account')").first
            if await acc_btn.count() > 0 and await acc_btn.is_visible():
                _log("👤 Phát hiện nhiều hồ sơ -> Chọn hồ sơ Meta Account đầu tiên...", log_callback)
                await acc_btn.click()
                await asyncio.sleep(4.0)

            # 5. Màn hình chọn phương thức 2FA
            method_radio = page.locator("input[name='two-factor-method']").first
            if await method_radio.count() > 0 and await method_radio.is_visible():
                _log("🛡️ Chọn phương thức Authenticator App -> Tiếp tục...", log_callback)
                method_next = page.locator("button:has-text('Next'), button[type='submit']").first
                await method_next.click()
                await asyncio.sleep(4.0)

            # 6. Nhập mã 2FA TOTP
            if two_factor_secret:
                code_input = page.locator(
                    "input[autocomplete='one-time-code'], input[placeholder*='code' i], "
                    "input[maxlength='6'], input[name='code'], input[name='approvals_code'], input[type='text']"
                ).first
                if await code_input.count() > 0 and await code_input.is_visible():
                    totp = generate_totp_code(two_factor_secret)
                    _log(f"🔢 Nhập mã 2FA TOTP tự động: {totp}...", log_callback)
                    await code_input.fill(totp)
                    await asyncio.sleep(1.0)
                    sub_2fa = page.locator("button:has-text('Next'), button:has-text('Continue'), button:has-text('Confirm'), button[type='submit']").first
                    await sub_2fa.click()

            # 7. Chờ cấp session cookies
            _log("⏳ Chờ Meta xác thực và cấp session cookies...", log_callback)
            deadline = time.time() + float(timeout_seconds)
            cookies = []
            cookie_dict = {}

            while time.time() < deadline:
                await asyncio.sleep(2.0)
                cookies = await context.cookies()
                cookie_dict = {c["name"]: c["value"] for c in cookies}
                if any(k in cookie_dict for k in ["hatch_sess", "hatch_vml"]):
                    _log("🎉 Đã nhận được session cookies thành công!", log_callback)
                    break

            if not any(k in cookie_dict for k in ["hatch_sess", "hatch_vml"]):
                _log("❌ Hết thời gian chờ cấp session cookies", log_callback)
                return {"success": False, "error": "Không nhận được session cookies sau khi đăng nhập", "email": email}

            # Trích xuất hạn cookie
            cookies_exp = {}
            for c in cookies:
                exp = c.get("expires")
                if exp and isinstance(exp, (int, float)) and exp > 0:
                    cookies_exp[c["name"]] = int(exp)

            now_ts = int(time.time())
            vml_exp = cookies_exp.get("hatch_vml") or (now_ts + 2 * 86400)

            try:
                ua = await page.evaluate("navigator.userAgent")
            except Exception:
                ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"

            return {
                "success": True,
                "email": email,
                "cookies": cookie_dict,
                "cookies_list": cookies,
                "cookies_exp": cookies_exp,
                "expires_at": vml_exp,
                "user_agent": ua,
            }

        except Exception as e:
            _log(f"❌ Lỗi đăng nhập độc lập cho {email}: {e}", log_callback)
            return {"success": False, "error": str(e), "email": email}
        finally:
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass
            if playwright:
                try:
                    await playwright.stop()
                except Exception:
                    pass
