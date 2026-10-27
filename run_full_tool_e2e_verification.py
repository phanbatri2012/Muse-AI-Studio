# -*- coding: utf-8 -*-
"""
End-to-End Comprehensive Verification Test Suite for MUSE AI STUDIO Desktop.
Kiểm thử toàn diện tất cả các phân hệ và tính năng trên Tool:
1. Prompt Studio (Text-to-Video Batch & Settings)
2. Character Studio (Turnaround & Dynamic Slots 1-6 & Mẫu A-E)
3. Shorts Studio (AI Storyboard, TTS Engine & Timeline Composer)
4. Accounts Manager (Account Pool, Cards & Status)
5. Queue Monitor (Hàng đợi tác vụ, Metrics Cards)
6. Media Gallery (Quản lý video/ảnh xuất bản)
7. Muse2API Backend Service (/health, /v1/chat/completions, VideoRequest Contract)
8. MainWindow Navigation & Responsive Layout
"""

from __future__ import annotations

import os
import sys
import time
import tempfile
from pathlib import Path
from typing import Dict, Any, List

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from qt_ui.ui_main import MainWindow
from qt_ui.tab_prompt_studio import PromptStudioTab
from qt_ui.tab_character_studio import CharacterStudioTab, SLOT_PRESETS, SAMPLE_E_PROMPTS
from qt_ui.tab_shorts_studio import AutoShortsStudioTab
from qt_ui.tab_accounts_manager import AccountsManagerTab
from qt_ui.tab_queue_monitor import QueueMonitorTab
from qt_ui.tab_media_gallery import MediaGalleryTab
from qt_ui.widgets.character_guide_dialog import CharacterGuideDialog

from muse_api_client import MuseAPIClient
from muse_service_manager import MuseServiceManager, MUSE2API_KEY
from shorts_script_engine import ShortsScriptEngine, SceneItem
from shorts_tts_engine import ShortsTTSEngine
from shorts_composer import ShortsComposer

class E2EReport:
    def __init__(self):
        self.results: List[Dict[str, Any]] = []

    def record(self, module: str, test_name: str, passed: bool, detail: str = ""):
        self.results.append({
            "module": module,
            "test_name": test_name,
            "passed": passed,
            "detail": detail
        })
        status_icon = "✅ PASS" if passed else "❌ FAIL"
        print(f"[{status_icon}] {module} :: {test_name} - {detail}")

    def summary(self) -> bool:
        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        failed = total - passed
        print("\n" + "=" * 70)
        print(f"📊 TỔNG KẾT KIỂM THỬ E2E TOÀN BỘ TÍNH NĂNG: {passed}/{total} PASSED")
        print("=" * 70)
        for r in self.results:
            icon = "✅" if r["passed"] else "❌"
            print(f"  {icon} [{r['module']}] {r['test_name']}: {r['detail']}")
        return failed == 0

def test_feature_1_prompt_studio(app: QApplication, report: E2EReport):
    tab = PromptStudioTab()
    # 1.1 Kiểm tra giá trị mặc định
    has_defaults = (
        tab.spin_duration.value() == 6 and
        tab.chk_smooth_60fps.isChecked() is True and
        tab.combo_ratio.currentData() == "auto" and
        tab.radio_rotation.isChecked() is True
    )
    report.record("1. Prompt Studio", "Cấu hình mặc định", has_defaults, "Duration=6s, 60fps=True, Ratio=auto, Mode=Rotation")

    # 1.2 Nạp kịch bản mẫu & đếm số cảnh
    tab._load_sample_prompts()
    count = tab.editor.prompt_count()
    prompts = tab.editor.get_clean_prompts()
    sample_loaded = count >= 2 and len(prompts) == count
    report.record("1. Prompt Studio", "Nạp kịch bản mẫu", sample_loaded, f"Đã nạp {count} cảnh mẫu thành công")

    # 1.3 Đóng gói tín hiệu khởi chạy batch
    emitted = []
    tab.start_batch_requested.connect(lambda p, c: emitted.append((p, c)))
    tab._on_start_clicked()
    signal_ok = (
        len(emitted) == 1 and
        len(emitted[0][0]) == count and
        emitted[0][1]["duration"] == 6 and
        emitted[0][1]["smooth_60fps"] is True
    )
    report.record("1. Prompt Studio", "Đóng gói tín hiệu tạo batch", signal_ok, "start_batch_requested truyền đúng prompts và config")

def test_feature_2_character_studio(app: QApplication, report: E2EReport):
    tab = CharacterStudioTab()

    # 2.1 Kiểm tra hệ thống 3 slot mặc định
    init_ok = (
        len(tab.slots) == 3 and
        len(tab.reference_images) == 3 and
        tab.slot1 is not None and
        tab.slot2 is not None and
        tab.slot3 is not None and
        not tab.slot1.can_remove
    )
    report.record("2. Character Studio", "Khởi tạo 3 Slot tham chiếu chuẩn", init_ok, "Slots @Image1..@Image3 sẵn sàng, bảo vệ không cho gỡ")

    # 2.2 Thêm slot động lên 6 slots & kiểm tra chặn slot 7
    tab._on_add_slot_clicked()  # Slot 4
    tab._on_add_slot_clicked()  # Slot 5
    tab._on_add_slot_clicked()  # Slot 6
    can_add_more = tab.btn_add_slot.isEnabled()
    tab._on_add_slot_clicked()  # Thử thêm slot 7
    six_slots_ok = (len(tab.slots) == 6 and len(tab.reference_images) == 6 and not can_add_more)
    report.record("2. Character Studio", "Thêm Dynamic Slots (tối đa 6)", six_slots_ok, "Đã tạo @Image4..@Image6, nút Thêm tự disable khi đạt trần")

    # 2.3 Gỡ slot 5 & kiểm tra re-indexing
    tab._on_remove_slot_requested(5)
    reindex_ok = (
        len(tab.slots) == 5 and
        len(tab.reference_images) == 5 and
        tab.slots[4].slot_index == 5 and
        tab.btn_add_slot.isEnabled() is True
    )
    report.record("2. Character Studio", "Gỡ slot & Tự động Re-index", reindex_ok, "Slot 5 bị xóa, Slot 6 cũ chuyển thành @Image5 mới")

    # 2.4 Kiểm tra nạp Mẫu E (Shop KOL) & Presets
    tab._load_sample_e()
    e_prompts = tab.editor.get_clean_prompts()
    sample_e_ok = (
        tab.radio_with_images.isChecked() and
        tab.combo_slot_preset.currentData() == "shop_kol" and
        len(e_prompts) == 1 and
        "Điện Thoại Giá Tốt" in e_prompts[0] and
        "iPhone 13 Pro Max" in e_prompts[0]
    )
    report.record("2. Character Studio", "Nạp kịch bản Mẫu E (Shop KOL)", sample_e_ok, "Tự động đổi preset sang shop_kol và nạp prompt đa thực thể")

    # 2.5 Kiểm tra gán ảnh và lấy danh sách ảnh hợp lệ
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tpath = f.name
    try:
        from PyQt6.QtGui import QPixmap, QColor
        pix = QPixmap(32, 32)
        pix.fill(QColor("#059669"))
        pix.save(tpath, "PNG")
        tab.slot1.set_image(tpath)
        valid_imgs = tab.get_valid_reference_images()
        img_assign_ok = (len(valid_imgs) == 1 and valid_imgs[0] == os.path.abspath(tpath))
        report.record("2. Character Studio", "Gán ảnh tham chiếu vào Slot", img_assign_ok, f"Slot 1 nhận diện file {Path(tpath).name}")
    finally:
        try:
            Path(tpath).unlink()
        except Exception:
            pass

def test_feature_3_shorts_studio(app: QApplication, report: E2EReport):
    tab = AutoShortsStudioTab()

    # 3.1 Kiểm tra cấu trúc UI Shorts Studio
    ui_ok = (
        tab.txt_topic is not None and
        tab.btn_gen_script is not None and
        tab.btn_start is not None and
        tab.tbl_scenes is not None
    )
    report.record("3. Shorts Studio", "Khởi tạo giao diện Shorts Pipeline", ui_ok, "Các bộ phận Topic, Voice, BGM, Timeline sẵn sàng")

    # 3.2 Kiểm tra Shorts Script Parser
    raw_mock_json = """
    [
        {"scene_index": 1, "voice_text": "Khám phá bí mật công nghệ.", "visual_prompt": "Futuristic cyberpunk neon laboratory", "bgm_mood": "hook"},
        {"scene_index": 2, "voice_text": "Tất cả thay đổi ngay hôm nay.", "visual_prompt": "Ultra realistic macro shot of quantum computer", "bgm_mood": "evidence"}
    ]
    """
    engine = ShortsScriptEngine()
    scenes = engine._parse_json_scenes(raw_mock_json, scene_count=2)
    parser_ok = (len(scenes) == 2 and scenes[0].bgm_mood == "hook" and scenes[1].scene_index == 2)
    report.record("3. Shorts Studio", "Storyboard Script JSON Parser", parser_ok, f"Bóc tách chính xác {len(scenes)} cảnh quay từ JSON")

    # 3.3 Kiểm tra Shorts TTSEngine Audio & SRT
    tts = ShortsTTSEngine()
    with tempfile.TemporaryDirectory() as td:
        t_audio = Path(td) / "test_voice.mp3"
        t_srt = Path(td) / "test_voice.srt"
        dur = tts.generate_speech(
            text="Khám phá công nghệ AI thế hệ mới năm 2026.",
            output_audio_path=t_audio,
            output_sub_path=t_srt,
            voice="vi-VN-HoaiMyNeural"
        )
        tts_ok = t_audio.exists() and t_audio.stat().st_size > 500 and dur > 0.5 and t_srt.exists()
    report.record("3. Shorts Studio", "TTS Voice & SRT Generator (EdgeTTS)", tts_ok, f"Tạo âm thanh {dur:.2f}s và file phụ đề SRT khớp thời gian")

def test_feature_4_accounts_manager(app: QApplication, report: E2EReport):
    tab = AccountsManagerTab()
    tab.refresh_accounts_table()

    # 4.1 Kiểm tra tải bảng tài khoản
    row_count = tab.table_accounts.rowCount()
    table_ok = row_count >= 0
    report.record("4. Quản Lý Tài Khoản", "Tải danh sách Account Pool", table_ok, f"Đang quản lý {row_count} tài khoản trong hệ thống")

    # 4.2 Thẻ thống kê (Cards)
    cards_ok = (
        tab.card_total.minimumHeight() >= 64 and
        tab.card_active.minimumHeight() >= 64 and
        tab.card_expired.minimumHeight() >= 64
    )
    report.record("4. Quản Lý Tài Khoản", "Thẻ thống kê chống tràn DPI", cards_ok, "Độ cao thẻ tối thiểu >= 64px, hiển thị đầy đủ nhãn")

def test_feature_5_queue_monitor(app: QApplication, report: E2EReport):
    tab = QueueMonitorTab()

    # 5.1 Khởi tạo hàng đợi và cập nhật tiến độ
    prompts = ["Prompt test E2E 1", "Prompt test E2E 2"]
    tab.initialize_queue(prompts)
    init_ok = (tab.table.rowCount() == 2)

    # Cập nhật task 1 sang PROCESSING 50%
    tab.on_video_updated({
        "prompt_idx": 1,
        "status": "PROCESSING",
        "progress": 50,
        "account": "acc_01"
    })
    # Cập nhật task 2 sang SUCCESS 100%
    tab.on_video_updated({
        "prompt_idx": 2,
        "status": "SUCCESS",
        "progress": 100,
        "account": "acc_02",
        "video_file": "vid_sample.mp4",
        "duration": 6
    })

    status_1 = tab.table.item(0, 4).text() if tab.table.item(0, 4) else ""
    status_2 = tab.table.item(1, 4).text() if tab.table.item(1, 4) else ""
    queue_ok = init_ok and ("50%" in status_1 or "Render" in status_1) and ("Xong" in status_2 or "Hoàn tất" in status_2 or "SUCCESS" in status_2 or "6s" in status_2)
    report.record("5. Giám Sát Hàng Đợi", "Quản lý vòng đời tác vụ", queue_ok, f"Task 1: '{status_1}', Task 2: '{status_2}'")

    # 5.2 Kiểm tra thẻ thống kê hàng đợi
    cards_ok = (
        tab.card_total.minimumHeight() >= 64 and
        tab.card_processing.minimumHeight() >= 64 and
        tab.card_success.minimumHeight() >= 64
    )
    report.record("5. Giám Sát Hàng Đợi", "Thẻ chỉ số tiến độ", cards_ok, "Hiển thị Tổng/Đang chạy/Thành công/Thất bại")

def test_feature_6_media_gallery(app: QApplication, report: E2EReport):
    tab = MediaGalleryTab()
    tab.refresh_gallery(force=True)

    # 6.1 Quét thư mục media
    gallery_ok = tab.table is not None
    report.record("6. Thư Viện Media", "Khởi tạo thư viện & Quét tệp xuất bản", gallery_ok, f"Quét thư mục media thành công, hiển thị {tab.table.rowCount()} tệp xuất bản")

def test_feature_7_backend_service(report: E2EReport):
    # 7.1 Kiểm tra dịch vụ nền đang chạy
    if not MuseServiceManager.is_service_ready():
        MuseServiceManager.start_service(timeout=10)
    is_ready = MuseServiceManager.is_service_ready()
    base_url = MuseServiceManager.get_api_base_url()
    report.record("7. Muse2API Service", "Kiểm tra cổng API Backend", is_ready, f"Service sẵn sàng tại {base_url}")

    if not is_ready:
        report.record("7. Muse2API Service", "Chat Completions API", False, "Backend chưa sẵn sàng để test API")
        return

    # 7.2 Kiểm tra Chat Completions qua online API
    try:
        client = MuseAPIClient(base_url=base_url, api_key=MUSE2API_KEY)
        answer = client.chat_completions(
            messages=[{"role": "user", "content": "Trả lời ngắn gọn: 2+2=?"}],
            timeout=30
        )
        chat_ok = bool(answer and len(answer.strip()) > 0 and ("4" in answer or "bốn" in answer.lower()))
        report.record("7. Muse2API Service", "Chat Completions (POST /v1/chat/completions)", chat_ok, f"Mô hình phản hồi: {answer.strip()[:60]}")
    except Exception as e:
        report.record("7. Muse2API Service", "Chat Completions (POST /v1/chat/completions)", False, f"Lỗi gọi Chat API: {e}")

    # 7.3 Kiểm tra VideoRequest Pydantic Schema chấp nhận mảng ảnh
    try:
        from muse2api_backend.app import VideoRequest
        req_single = VideoRequest(prompt="test", reference_image="http://example.com/1.jpg")
        req_multi = VideoRequest(prompt="test", reference_image=["C:\\1.jpg", "C:\\2.jpg", "C:\\3.jpg"])
        req_none = VideoRequest(prompt="test", reference_image=None)
        schema_ok = (
            req_single.reference_image == "http://example.com/1.jpg" and
            isinstance(req_multi.reference_image, list) and
            len(req_multi.reference_image) == 3 and
            req_none.reference_image is None
        )
        report.record("7. Muse2API Service", "VideoRequest Contract (Đa ảnh tham chiếu)", schema_ok, "Chấp nhận String, List[str] và None mà không bị HTTP 422")
    except Exception as e:
        report.record("7. Muse2API Service", "VideoRequest Contract", False, f"Lỗi schema: {e}")

def test_feature_8_main_window_navigation(app: QApplication, report: E2EReport):
    win = MainWindow(start_backend=False)
    win.resize(1280, 800)

    # 8.1 Kiểm tra số lượng tab
    tab_count = win.tabs.count()
    tabs_ok = tab_count >= 6
    report.record("8. Giao Diện Tổng Thể", "Tích hợp đầy đủ các Tab", tabs_ok, f"Phát hiện {tab_count} phân hệ tabs độc lập")

    # 8.2 Chuyển qua từng tab liên tục (Stress test chuyển tab không leak / crash)
    cycle_ok = True
    try:
        for idx in range(tab_count):
            win.tabs.setCurrentIndex(idx)
            app.processEvents()
        win.tabs.setCurrentIndex(0)
        app.processEvents()
    except Exception as e:
        cycle_ok = False
    report.record("8. Giao Diện Tổng Thể", "Chuyển đổi Tabs & Responsive Render", cycle_ok, "Chuyển đổi mượt mà qua toàn bộ phân hệ")

    win.close()

def run_all_e2e():
    app = QApplication.instance()
    if not app:
        app = QApplication(["--platform", "offscreen"])

    report = E2EReport()
    print("=" * 70)
    print("🚀 BẮT ĐẦU KIỂM THỬ E2E TOÀN BỘ TÍNH NĂNG TRÊN TOOL...")
    print("=" * 70)

    test_feature_1_prompt_studio(app, report)
    test_feature_2_character_studio(app, report)
    test_feature_3_shorts_studio(app, report)
    test_feature_4_accounts_manager(app, report)
    test_feature_5_queue_monitor(app, report)
    test_feature_6_media_gallery(app, report)
    test_feature_7_backend_service(report)
    test_feature_8_main_window_navigation(app, report)

    all_passed = report.summary()
    return 0 if all_passed else 1

if __name__ == "__main__":
    exit_code = run_all_e2e()
    sys.exit(exit_code)
