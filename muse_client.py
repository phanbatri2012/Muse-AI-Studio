from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
from pathlib import Path
import re
import time
try:
    from playwright.async_api import Browser, BrowserContext, Page, Playwright
except ImportError:
    Browser = BrowserContext = Page = Playwright = Any  # type: ignore

from muse_auth import MuseAuthManager
from muse_chrome import (
    DEFAULT_MUSE_PROFILE,
    MUSE_CDP_HOST,
    MUSE_CDP_PORT,
    MUSE_URL,
    is_muse_chrome_running,
    open_muse_chrome,
)
from settings_manager import SettingsManager


class TaskStatus(str, Enum):
    IDLE = "IDLE"
    INITIALIZING = "INITIALIZING"
    SUBMITTED = "SUBMITTED"
    WAITING_REPLY = "WAITING_REPLY"
    STREAMING = "STREAMING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"


ERROR_KEYWORDS = [
    "rate limit",
    "too many requests",
    "limit reached",
    "out of tokens",
    "insufficient token",
    "unable to complete",
    "failed to generate",
    "error occurred",
    "something went wrong",
]

ERROR_SELECTORS = [
    "[data-testid='error-banner']",
    "[role='alert']",
    ".error-message",
    "[data-message-error='true']",
]

_LAST_SESSION_RENEW_TS: float = 0.0


@dataclass
class MuseGenerationResult:
    success: bool
    prompt: str
    status: TaskStatus
    reply_text: str = ""
    video_urls: list[str] = field(default_factory=list)
    image_urls: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    error: Optional[str] = None
    turn_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "prompt": self.prompt,
            "status": self.status.value,
            "reply_text": self.reply_text,
            "video_urls": self.video_urls,
            "image_urls": self.image_urls,
            "duration_seconds": round(self.duration_seconds, 2),
            "error": self.error,
            "turn_id": self.turn_id,
            "metadata": self.metadata,
        }


# Selectors chuẩn đã được reverse-engineer từ DOM thực tế của Muse AI / Meta AI
COMPOSER_SELECTORS = [
    "textarea[placeholder*='Message']",
    "textarea[placeholder*='Ask']",
    "[data-testid='hatch-chat-composer'] textarea",
    "div[contenteditable='true'][role='textbox']",
    "div[contenteditable='true']",
    "textarea",
]

SEND_BUTTON_SELECTORS = [
    "button[data-testid='hatch-composer-send-button']",
    "button[aria-label*='Send']",
    "button[aria-label*='Gửi']",
    "button:has(svg[data-icon='paper-plane'])",
    "button[type='submit']",
]

STOP_BUTTON_SELECTORS = [
    "button:has-text('Stop')",
    "button[aria-label*='Stop']",
    "[data-testid='hatch-composer-stop-button']",
]

TYPING_INDICATOR_SELECTOR = "[data-testid='hatch-chat-typing-indicator']"
STREAMING_INDICATOR_SELECTOR = "[data-hatch-markdown-streaming='true']"
ASSISTANT_MESSAGE_SELECTOR = "[data-message-item][data-message-role='assistant'], div[data-message-role='assistant']"
USER_MESSAGE_SELECTOR = "[data-message-item][data-message-role='user'], div[data-message-role='user']"


def _log(message: str, logger: Callable[[str], None] | None = None) -> None:
    if callable(logger):
        try:
            logger(message)
            return
        except Exception:
            pass
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [MUSE_CLIENT] {message}")


class MuseClient:
    """Core Client tự động hóa phiên làm việc, gửi prompt và trích xuất kết quả video từ Muse AI."""

    def __init__(
        self,
        page: Page,
        context: BrowserContext,
        browser: Browser,
        playwright: Playwright,
        log_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.page = page
        self.context = context
        self.browser = browser
        self.playwright = playwright
        self.log_callback = log_callback
        self._intercepted_media_urls: list[str] = []
        self._setup_network_interception()

    def _setup_network_interception(self) -> None:
        """Lắng nghe các luồng mạng để bắt trực tiếp các link video MP4/WebM và blob CDN."""
        def on_response(response):
            try:
                url = response.url
                # Lọc các URL chứa định dạng video hoặc luồng media streaming của Meta / Muse CDN
                if any(ext in url.lower() for ext in [".mp4", ".webm", ".m3u8", "video/mp4"]):
                    if url not in self._intercepted_media_urls:
                        self._intercepted_media_urls.append(url)
                        _log(f"🎬 Bắt được media URL từ network: {url[:100]}...", self.log_callback)
            except Exception:
                pass

        self.page.on("response", on_response)

    @classmethod
    async def create(
        cls,
        profile_name: str | None = None,
        port: int | None = None,
        host: str = MUSE_CDP_HOST,
        ensure_browser: bool = True,
        log_callback: Callable[[str], None] | None = None,
    ) -> MuseClient:
        """Khởi tạo MuseClient bằng cách kết nối qua CDP."""
        chosen_profile = profile_name or DEFAULT_MUSE_PROFILE
        chosen_port = int(port or MUSE_CDP_PORT)

        if ensure_browser and not is_muse_chrome_running(chosen_port, host=host):
            _log(f"Khởi chạy Chrome profile '{chosen_profile}' tại {host}:{chosen_port}...", log_callback)
            open_info = open_muse_chrome(chosen_profile, url=MUSE_URL, wait_ready=True)
            chosen_port = open_info["port"]

        playwright, browser, context, page = await MuseAuthManager.connect_cdp(
            host=host,
            port=chosen_port,
            log_callback=log_callback,
        )

        # Tự động gia hạn session hatch_vml (+48h) và đánh thức Cloud VM nếu quá 10 phút
        global _LAST_SESSION_RENEW_TS
        now_ts = time.time()
        if now_ts - _LAST_SESSION_RENEW_TS > 600:
            try:
                renew_res = await MuseAuthManager.renew_session_http(context=context, log_callback=log_callback)
                if renew_res.get("success"):
                    _LAST_SESSION_RENEW_TS = now_ts
            except Exception as e:
                _log(f"⚠️ Kiểm tra gia hạn phiên ngầm: {e}", log_callback)

        # Tìm page đang ở muse.ai hoặc điều hướng nếu chưa có
        target_page = None
        for p in context.pages:
            if "muse.ai" in p.url:
                target_page = p
                break

        if not target_page:
            target_page = page
            if "muse.ai" not in target_page.url:
                await asyncio.sleep(1.0)
            if "muse.ai" not in target_page.url:
                _log(f"🌐 Điều hướng trình duyệt tới {MUSE_URL}...", log_callback)
                try:
                    await target_page.goto(MUSE_URL, wait_until="domcontentloaded", timeout=30000)
                except Exception as exc:
                    if "interrupted" in str(exc).lower():
                        _log("Trình duyệt đang tự tải trang muse.ai, đợi hoàn tất...", log_callback)
                        try:
                            await target_page.wait_for_load_state("domcontentloaded", timeout=15000)
                        except Exception:
                            pass
                    else:
                        raise
                await asyncio.sleep(2.5)
        else:
            # Chờ trang ổn định nếu vừa nạp
            await asyncio.sleep(1.0)

        return cls(target_page, context, browser, playwright, log_callback=log_callback)

    async def open_new_thread(self, timeout_seconds: int = 30) -> bool:
        """Mở một thread chat hoàn toàn mới (cách ly ngữ cảnh)."""
        new_thread_url = "https://muse.ai/thread/new"
        _log(f"Mở luồng hội thoại mới tại {new_thread_url}...", self.log_callback)
        self._intercepted_media_urls.clear()

        try:
            await self.page.goto(new_thread_url, wait_until="commit", timeout=timeout_seconds * 1000)
            # Chờ composer hiển thị
            for selector in COMPOSER_SELECTORS:
                try:
                    locator = self.page.locator(selector).first
                    if await locator.count() > 0 and await locator.is_visible():
                        _log(f"✅ Composer đã sẵn sàng: {selector}", self.log_callback)
                        return True
                except Exception:
                    continue

            # Chờ thêm tối đa 5 giây cho hydration
            await asyncio.sleep(2)
            return True
        except Exception as exc:
            _log(f"⚠️ Mở new thread gặp cảnh báo: {exc}", self.log_callback)
            return False

    async def _scroll_to_bottom(self) -> None:
        """Cuộn xuống cuối danh sách tin nhắn để virtual list của React mount thẻ video mới."""
        js_scroll = """() => {
            const els = [...document.querySelectorAll('*')].filter(e => {
                const s = getComputedStyle(e);
                return (s.overflowY === 'auto' || s.overflowY === 'scroll') && e.scrollHeight > e.clientHeight + 100;
            });
            els.sort((a, b) => b.scrollHeight - a.scrollHeight);
            if (els[0]) els[0].scrollTop = els[0].scrollHeight;
            const s = document.scrollingElement || document.body;
            if (s) s.scrollTop = s.scrollHeight;
        }"""
        try:
            await self.page.evaluate(js_scroll)
        except Exception:
            pass

    async def _find_composer(self):
        """Tìm phần tử input/composer khả dụng trên trang."""
        for selector in COMPOSER_SELECTORS:
            try:
                locator = self.page.locator(selector).first
                if await locator.count() > 0:
                    return locator
            except Exception:
                continue
        return None

    async def submit_prompt(self, prompt: str) -> dict[str, int]:
        """Nhập prompt vào khung soạn thảo và gửi đi, trả về baseline count của video và tin nhắn."""
        clean_prompt = prompt.strip()
        if not clean_prompt:
            raise ValueError("Prompt không được để trống")

        # Xóa media intercepted từ các lượt prompt trước
        self._intercepted_media_urls.clear()

        # Ghi nhận baseline các thành phần trước khi gửi prompt
        initial_video_count = 0
        initial_assistant_count = 0
        initial_dl_btn_count = 0
        try:
            initial_video_count = await self.page.locator("video").count()
            initial_assistant_count = await self.page.locator(ASSISTANT_MESSAGE_SELECTOR).count()
            initial_dl_btn_count = await self.page.locator("button[aria-label*='Download video']").count()
        except Exception:
            pass

        _log(f"📝 Đang bơm prompt ({len(clean_prompt)} ký tự) qua React setter...", self.log_callback)

        # 1. Bơm text siêu tốc bằng React 18 Prototype Setter (<0.1s, không lag, kích hoạt React state)
        js_setter = """(text) => {
            const ta = document.querySelector('textarea, div[contenteditable="true"]');
            if (!ta) return false;
            ta.scrollIntoView({block: 'center', inline: 'nearest'});
            ta.focus();
            if (ta.tagName === 'TEXTAREA') {
                const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')?.set;
                if (setter) {
                    setter.call(ta, text);
                } else {
                    ta.value = text;
                }
            } else {
                ta.innerText = text;
            }
            ta.dispatchEvent(new Event('input', {bubbles: true}));
            ta.dispatchEvent(new Event('change', {bubbles: true}));
            return (ta.value || ta.innerText || '').length > 0;
        }"""

        setter_ok = False
        try:
            setter_ok = bool(await self.page.evaluate(js_setter, clean_prompt))
        except Exception:
            setter_ok = False

        if not setter_ok:
            composer = await self._find_composer()
            if not composer:
                raise RuntimeError("Không tìm thấy khung nhập prompt (composer) trên giao diện Muse AI")
            await composer.click()
            try:
                await composer.fill(clean_prompt)
            except Exception:
                await composer.evaluate("(el, text) => { el.innerText = text; el.dispatchEvent(new Event('input', { bubbles: true })); }", clean_prompt)

        await asyncio.sleep(0.3)

        # 2. Thử kích hoạt nút Send trực tiếp qua React state check
        sent = False
        js_click_send = """() => {
            const b = [...document.querySelectorAll('button,[role=button]')].find(x => {
                const label = x.getAttribute('aria-label') || '';
                const tid = x.getAttribute('data-testid') || '';
                const txt = x.innerText || '';
                return /send|gửi/i.test(label) || /send/i.test(tid) || /send/i.test(txt);
            });
            if (!b) return 'no-button';
            if (b.disabled) return 'disabled';
            b.click();
            return 'clicked';
        }"""
        try:
            click_res = await self.page.evaluate(js_click_send)
            if click_res == 'clicked':
                sent = True
                _log("🚀 Đã nhấn nút Send trên giao diện (qua React trigger)", self.log_callback)
        except Exception:
            pass

        if not sent:
            for btn_sel in SEND_BUTTON_SELECTORS:
                try:
                    btn = self.page.locator(btn_sel).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click()
                        sent = True
                        _log("🚀 Đã nhấn nút Send trên giao diện", self.log_callback)
                        break
                except Exception:
                    continue

        if not sent:
            _log("⌨️ Nhấn phím Enter để gửi prompt...", self.log_callback)
            ta = self.page.locator("textarea").first
            if await ta.count() > 0:
                await ta.press("Enter")
            else:
                composer = await self._find_composer()
                if composer:
                    await composer.press("Enter")

        return {
            "initial_video_count": initial_video_count,
            "initial_assistant_count": initial_assistant_count,
            "initial_dl_btn_count": initial_dl_btn_count,
        }

    async def wait_for_generation_complete(
        self,
        prompt: str,
        timeout_seconds: int = 240,
        poll_interval: float = 1.5,
        initial_video_count: int = 0,
        initial_assistant_count: int = 0,
        initial_dl_btn_count: int = 0,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> MuseGenerationResult:
        """Theo dõi tiến độ sinh dữ liệu của Muse AI đến khi kết thúc và bóc tách kết quả."""
        start_time = time.time()
        deadline = start_time + float(timeout_seconds)

        _log("⏳ Đang theo dõi tiến độ sinh video/nội dung từ Muse AI...", self.log_callback)

        last_text = ""
        text_stable_counter = 0
        has_started = False
        detected_turn_id = None

        while time.time() < deadline:
            elapsed = time.time() - start_time
            await asyncio.sleep(poll_interval)

            # 1. Kiểm tra typing indicator, nút Stop hoặc trạng thái đang sinh/lưu video
            is_typing = False
            is_streaming = False
            try:
                stop_count = await self.page.locator("button:has-text('Stop'), button[aria-label*='Stop'], button[aria-label*='Dừng']").count()
                saving_count = await self.page.locator("text='Saving video', text='Generating', text='Rendering'").count()
                anim_dots = await self.page.locator("[class*='animate-bounce'], [class*='dot']").count()
                is_typing = (stop_count > 0) or (saving_count > 0) or (anim_dots > 0) or (await self.page.locator(TYPING_INDICATOR_SELECTOR).count() > 0)
                is_streaming = await self.page.locator(STREAMING_INDICATOR_SELECTOR).count() > 0
            except Exception:
                pass

            # 2. Lấy nội dung tin nhắn assistant mới nhất
            current_reply_text = ""
            assistant_count = 0
            try:
                assistant_items = self.page.locator(ASSISTANT_MESSAGE_SELECTOR)
                assistant_count = await assistant_items.count()
                if assistant_count > 0:
                    latest_item = assistant_items.nth(assistant_count - 1)
                    current_reply_text = (await latest_item.inner_text()).strip()
                    detected_turn_id = await latest_item.get_attribute("data-message-turn-id")
            except Exception:
                pass

            if is_typing or is_streaming or (assistant_count > initial_assistant_count and current_reply_text) or elapsed > 3.0:
                has_started = True

            # Kiểm tra lỗi hoặc rate limit xuất hiện trong nội dung
            current_lower = current_reply_text.lower()
            if any(kw in current_lower for kw in ["rate limit", "too many requests", "limit reached"]):
                _log(f"⚠️ Phát hiện giới hạn tần suất (Rate limit): {current_reply_text[:100]}", self.log_callback)
                return MuseGenerationResult(
                    success=False,
                    prompt=prompt,
                    status=TaskStatus.RATE_LIMITED,
                    reply_text=current_reply_text,
                    duration_seconds=elapsed,
                    error="Rate limit reached",
                )

            # Gửi thông tin cập nhật tiến độ nếu có callback
            if callable(progress_callback):
                try:
                    progress_callback({
                        "status": TaskStatus.STREAMING.value if is_streaming else (TaskStatus.WAITING_REPLY.value if is_typing else TaskStatus.SUBMITTED.value),
                        "elapsed": round(elapsed, 1),
                        "reply_preview": current_reply_text[:120] if current_reply_text else ("Đang sinh/lưu video..." if is_typing else "AI đang khởi tạo..."),
                        "media_found": len(self._intercepted_media_urls),
                    })
                except Exception:
                    pass

            # 3. Cuộn trang định kỳ để kích hoạt virtual rendering của React
            if int(elapsed) % 3 == 0:
                await self._scroll_to_bottom()

            # 4. Kiểm tra xem đã có video thực sự xuất hiện chưa (loại bỏ ảnh bìa poster)
            has_finished_video = False
            try:
                js_check_video = """() => {
                    const vs = Array.from(document.querySelectorAll('video'));
                    for (let i = vs.length - 1; i >= 0; i--) {
                        const v = vs[i];
                        if (v.closest('header, nav, [class*="avatar"]')) continue;
                        const src = v.currentSrc || v.src || '';
                        if (src && !src.includes('avatar') && !src.includes('emoji')) {
                            return {
                                found: true,
                                src: src,
                                w: v.videoWidth || 0,
                                h: v.videoHeight || 0,
                                ready: v.readyState >= 1 || v.videoWidth > 0
                            };
                        }
                    }
                    return {found: false};
                }"""
                v_info = await self.page.evaluate(js_check_video)
                curr_dl_btn_count = await self.page.locator("button[aria-label*='Download video']").count()
                curr_video_count = await self.page.locator("video").count()

                if curr_dl_btn_count > initial_dl_btn_count:
                    has_finished_video = True
                elif v_info and v_info.get("found"):
                    if curr_video_count > initial_video_count or v_info.get("ready"):
                        has_finished_video = True
            except Exception:
                pass

            if (has_started or has_finished_video) and has_finished_video and not is_typing and not is_streaming:
                _log(f"🎬 Đã phát hiện video thành phẩm mới hoàn tất sau {round(elapsed, 1)}s!", self.log_callback)
                return await self._extract_result(prompt, current_reply_text, elapsed, detected_turn_id)

            # 5. Xử lý phản hồi bằng văn bản: KHÔNG ngắt sớm nếu chỉ là câu thoại thông thường
            is_refusal = any(kw in current_lower for kw in [
                "rate limit", "too many requests", "limit reached", "unable to",
                "cannot fulfill", "sorry, i cannot", "tôi không thể", "violate", "violation", "policy"
            ])
            if has_started and not is_typing and not is_streaming and (assistant_count > initial_assistant_count):
                if is_refusal:
                    _log(f"⚠️ Phát hiện thông điệp từ chối/giới hạn từ AI: {current_reply_text[:120]}", self.log_callback)
                    return await self._extract_result(prompt, current_reply_text, elapsed, detected_turn_id)
                elif elapsed > 240 and current_reply_text and current_reply_text == last_text:
                    text_stable_counter += 1
                    if text_stable_counter >= 5:
                        _log(f"⚠️ Quá hạn chờ video (sau {round(elapsed, 1)}s), kết thúc với nội dung hiện tại.", self.log_callback)
                        return await self._extract_result(prompt, current_reply_text, elapsed, detected_turn_id)
                else:
                    text_stable_counter = 0
                    last_text = current_reply_text
            else:
                text_stable_counter = 0

        # Nếu hết thời gian chờ
        elapsed = time.time() - start_time
        _log(f"⚠️ Quá thời gian chờ ({timeout_seconds}s)", self.log_callback)
        return MuseGenerationResult(
            success=False,
            prompt=prompt,
            status=TaskStatus.TIMEOUT,
            reply_text=last_text,
            duration_seconds=elapsed,
            error=f"Timeout sau {timeout_seconds} giây",
        )

    async def extract_blob_as_bytes(self, blob_url: str) -> bytes | None:
        """Trích xuất file binary từ blob URL bên trong trình duyệt siêu tốc bằng fetch + chunked ArrayBuffer."""
        try:
            js_code = """async (url) => {
                const res = await fetch(url);
                if (!res.ok) return null;
                const blob = await res.blob();
                const ab = await blob.arrayBuffer();
                const bytes = new Uint8Array(ab);
                let binary = '';
                const chunk = 32768;
                for (let i = 0; i < bytes.length; i += chunk) {
                    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
                }
                return btoa(binary);
            }"""
            import base64
            base64_str = await self.page.evaluate(js_code, blob_url)
            if base64_str:
                return base64.b64decode(base64_str)
        except Exception as exc:
            _log(f"⚠️ Lỗi trích xuất blob bytes: {exc}", self.log_callback)
        return None

    async def download_video_via_button(self, dest_path: Path | str, timeout: int = 4) -> bool:
        """Tải video bằng cách bắt sự kiện download từ nút 'Download video' trên giao diện hoặc trích xuất blob."""
        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            download_btn = self.page.locator("button[aria-label*='Download video']").last
            if await download_btn.count() > 0 and await download_btn.is_visible():
                _log("⬇️ Đang kích hoạt nút 'Download video' để lưu file...", self.log_callback)
                # 1. Thử click và bắt sự kiện expect_download nhanh
                try:
                    async with self.page.expect_download(timeout=min(timeout, 3) * 1000) as download_info:
                        await download_btn.click()
                    download = await download_info.value
                    await download.save_as(str(dest))
                    if dest.is_file() and dest.stat().st_size > 1024:
                        _log(f"✅ Đã tải video thành công qua nút Download: {dest.name} ({round(dest.stat().st_size / (1024*1024), 2)} MB)", self.log_callback)
                        return True
                except Exception:
                    pass

                # 2. Nếu không bắt được sự kiện download OS, trích xuất blob video trực tiếp
                for v in await self.page.locator("video").all():
                    v_src = await v.get_attribute("src") or ""
                    if v_src.startswith("blob:"):
                        blob_bytes = await self.extract_blob_as_bytes(v_src)
                        if blob_bytes and len(blob_bytes) > 1024:
                            dest.write_bytes(blob_bytes)
                            _log(f"✅ Đã trích xuất và lưu blob video thành công: {dest.name} ({round(len(blob_bytes)/(1024*1024), 2)} MB)", self.log_callback)
                            return True
        except Exception as exc:
            _log(f"⚠️ Thử tải qua nút Download: {exc}", self.log_callback)
        return False

    async def _extract_result(
        self,
        prompt: str,
        reply_text: str,
        elapsed: float,
        turn_id: str | None,
    ) -> MuseGenerationResult:
        """Bóc tách link video, ảnh và các metadata từ DOM của assistant turn với bộ lọc nghiêm ngặt."""
        video_urls: list[str] = list(self._intercepted_media_urls)
        image_urls: list[str] = []

        try:
            # 1. Ưu tiên quét thẻ video trong tin nhắn Assistant mới nhất
            assistant_items = self.page.locator(ASSISTANT_MESSAGE_SELECTOR)
            found_in_latest = False
            if await assistant_items.count() > 0:
                latest_item = assistant_items.last
                vid_loc = latest_item.locator("video, video source, a[download], a[href*='.mp4']")
                vid_count = await vid_loc.count()
                for i in range(vid_count):
                    el = vid_loc.nth(i)
                    src = await el.get_attribute("src") or await el.get_attribute("href")
                    if src and src not in video_urls:
                        video_urls.append(src)
                        found_in_latest = True

            # 2. Nếu không tìm thấy trong latest assistant, chỉ quét trong các tin nhắn chat assistant, tránh lấy video avatar/mascot ngoài trang
            if not found_in_latest and await assistant_items.count() > 0:
                chat_vid = self.page.locator(f"{ASSISTANT_MESSAGE_SELECTOR} video").last
                if await chat_vid.count() > 0:
                    src = await chat_vid.get_attribute("src")
                    if src and src not in video_urls:
                        video_urls.append(src)

            # 3. Luôn kiểm tra xem có nút Download video trên giao diện không
            try:
                dl_btn = self.page.locator("button[aria-label*='Download video']").last
                if await dl_btn.count() > 0 and await dl_btn.is_visible():
                    if "button_download" not in video_urls:
                        video_urls.append("button_download")
            except Exception:
                pass

            # 4. Tìm ảnh tạo kèm (nhưng tuyệt đối không nhầm ảnh bìa này với video)
            img_loc = self.page.locator("img:not([alt*='avatar']):not([src*='icon'])").last
            if await img_loc.count() > 0:
                src = await img_loc.get_attribute("src")
                if src and src not in image_urls and not src.startswith("data:"):
                    image_urls.append(src)

        except Exception as exc:
            _log(f"Lỗi khi trích xuất media elements từ DOM: {exc}", self.log_callback)

        # 5. Quét regex từ reply_text tìm các URL có đuôi mp4/video nếu DOM không có thẻ video
        url_matches = re.findall(r"https?://[^\s<>\"']+\.(?:mp4|webm|mkv)", reply_text)
        for u in url_matches:
            if u not in video_urls:
                video_urls.append(u)

        # 6. Đảm bảo mỗi prompt chỉ lấy đúng 1 video mới nhất
        if len(video_urls) > 1:
            video_urls = [video_urls[-1]]
        if len(image_urls) > 1:
            image_urls = [image_urls[-1]]

        # 7. Đánh giá tính hợp lệ của video thành phẩm
        has_video = bool(video_urls)
        is_success = has_video
        error_msg = None
        status = TaskStatus.COMPLETED if is_success else TaskStatus.FAILED

        if not is_success:
            if image_urls:
                error_msg = "Chỉ nhận diện được ảnh tĩnh bìa (poster frame), chưa có video thành phẩm hoàn chỉnh."
            else:
                error_msg = "Không tìm thấy video thành phẩm trong tin nhắn phản hồi của AI."

        return MuseGenerationResult(
            success=is_success,
            prompt=prompt,
            status=status,
            reply_text=reply_text,
            video_urls=video_urls,
            image_urls=image_urls,
            duration_seconds=elapsed,
            turn_id=turn_id,
            error=error_msg,
            metadata={
                "media_count": len(video_urls),
                "timestamp": datetime.now().isoformat(),
            },
        )

    async def generate(
        self,
        prompt: str,
        new_thread: bool = True,
        timeout_seconds: int = 240,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> MuseGenerationResult:
        """Hàm API cấp cao: Mở thread mới, nạp prompt, theo dõi tiến độ và trả về kết quả video hoàn chỉnh."""
        if new_thread:
            await self.open_new_thread()

        baseline = await self.submit_prompt(prompt)
        return await self.wait_for_generation_complete(
            prompt=prompt,
            timeout_seconds=timeout_seconds,
            initial_video_count=baseline.get("initial_video_count", 0),
            initial_assistant_count=baseline.get("initial_assistant_count", 0),
            initial_dl_btn_count=baseline.get("initial_dl_btn_count", 0),
            progress_callback=progress_callback,
        )

    async def generate_with_retry(
        self,
        prompt: str,
        new_thread: bool = True,
        max_retries: int = 2,
        retry_delay: float = 5.0,
        timeout_seconds: int = 240,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> MuseGenerationResult:
        """Thực thi sinh video với cơ chế tự động thử lại khi gặp rate limit hoặc timeout."""
        last_result: MuseGenerationResult | None = None
        for attempt in range(1, max_retries + 2):
            if attempt > 1:
                wait_time = retry_delay * (2 ** (attempt - 2))
                _log(f"🔁 Thử lại lần {attempt}/{max_retries + 1} sau {wait_time}s...", self.log_callback)
                await asyncio.sleep(wait_time)

            result = await self.generate(
                prompt=prompt,
                new_thread=new_thread,
                timeout_seconds=timeout_seconds,
                progress_callback=progress_callback,
            )
            last_result = result
            if result.success:
                return result

            # Nếu lỗi không thể giải quyết bằng retry (hết token) thì thoát sớm
            if "out of tokens" in (result.reply_text or "").lower():
                break

        return last_result or MuseGenerationResult(
            success=False,
            prompt=prompt,
            status=TaskStatus.FAILED,
            error="Không thành công sau các lần thử lại",
        )

    async def close(self) -> None:
        """Đóng kết nối Playwright an toàn."""
        await MuseAuthManager.safe_disconnect(self.playwright, self.browser, self.log_callback)
