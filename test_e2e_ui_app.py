import os
import sys
import time
from pathlib import Path

from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox

from qt_ui.tab_muse_ai import MuseAITab
from runtime_paths import MUSE_DOWNLOADS_DIR

TEST_PROMPT = "Tạo video 6 giây một chú cún con corgi đang chạy nhảy vui vẻ trên bãi biển lúc hoàng hôn"


def run_ui_e2e_test():
    print("=" * 65)
    print("🎬 BẮT ĐẦU KIỂM THỬ E2E TẠO VIDEO TRÊN GIAO DIỆN DESKTOP APP (PYQT6)")
    print(f"📝 Test Prompt: {TEST_PROMPT}")
    print("=" * 65)

    # 1. Khởi tạo QApplication
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    # 2. Khởi tạo Tab Muse AI
    print("[1/5] Khởi tạo giao diện MuseAITab...")
    tab = MuseAITab(log_callback=lambda msg: print(f"[UI_LOG] {msg}"))
    tab.show()

    # 3. Nạp Prompt vào khung soạn thảo UI
    print(f"[2/5] Nạp test prompt vào khung txt_prompts...")
    tab.txt_prompts.setPlainText(TEST_PROMPT)

    # Giả lập đóng các hộp thoại QMessageBox để tránh chặn Event Loop
    def mock_msgbox(parent, title, text, *args, **kwargs):
        print(f"💬 [UI MODAL DIALOG] {title}: {text}")
        return QMessageBox.StandardButton.Ok

    QMessageBox.information = mock_msgbox
    QMessageBox.warning = mock_msgbox
    QMessageBox.critical = mock_msgbox

    # Ghi nhận danh sách file hiện có trước khi chạy
    MUSE_DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    before_mp4_files = set(MUSE_DOWNLOADS_DIR.rglob("*.mp4"))

    # 4. Kích hoạt nút 'Bắt Đầu Chạy' trên giao diện
    print("[3/5] Kích hoạt sự kiện nhấn nút 'Bắt Đầu Chạy' (_start_workflow)...")
    loop = QEventLoop()
    automation_finished = False

    orig_complete = tab._on_automation_complete

    def hooked_complete():
        nonlocal automation_finished
        orig_complete()
        automation_finished = True
        loop.quit()

    tab._on_automation_complete = hooked_complete

    # Watchdog timeout: 380 giây
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(380000)

    # Bắt đầu chạy workflow
    tab.btn_start.click()

    # Chạy Qt Event Loop chờ tín hiệu hoàn thành
    print("[4/5] Đang chờ tiến trình UI App & QThread thực thi...")
    loop.exec()

    # 5. Kiểm tra kết quả trên giao diện và file hệ thống
    print("\n" + "=" * 65)
    print("📋 KIỂM CHỨNG KẾT QUẢ TRÊN BẢNG VÀ Ổ ĐĨA")
    print("=" * 65)

    if not automation_finished:
        print("❌ Quy trình UI không phát tín hiệu hoàn tất trước khi hết thời gian (Timeout 240s)!")
        return False

    row_count = tab.table.rowCount()
    print(f"Số dòng trên QTableWidget: {row_count}")
    if row_count != 1:
        print(f"❌ Số dòng không khớp kỳ vọng (1 dòng), thực tế: {row_count}")
        return False

    col_id = tab.table.item(0, 0).text() if tab.table.item(0, 0) else ""
    col_prompt = tab.table.item(0, 1).text() if tab.table.item(0, 1) else ""
    col_status = tab.table.item(0, 2).text() if tab.table.item(0, 2) else ""
    col_file = tab.table.item(0, 3).text() if tab.table.item(0, 3) else ""
    col_actions = tab.table.cellWidget(0, 4)

    print(f"• Cột 0 (ID): {col_id}")
    print(f"• Cột 1 (Prompt): {col_prompt[:60]}...")
    print(f"• Cột 2 (Trạng thái): {col_status}")
    print(f"• Cột 3 (Tên Video): {col_file}")
    print(f"• Cột 4 (Widget Thao tác): {'Có nút [▶️ Xem / 📂 Thư mục]' if col_actions else 'Trống'}")

    # Kiểm tra trạng thái trên bảng
    if "Hoàn thành" not in col_status:
        print(f"❌ Cột trạng thái không đạt 'Hoàn thành'! Thực tế: {col_status}")
        return False

    if not col_file.endswith(".mp4"):
        print(f"❌ Cột video không hiển thị file .mp4 hợp lệ! Thực tế: {col_file}")
        return False

    if not col_actions:
        print("❌ Cột thao tác không render widget chứa nút [▶️ Xem] & [📂 Thư mục]!")
        return False

    # Kiểm tra file trên ổ đĩa
    after_mp4_files = set(MUSE_DOWNLOADS_DIR.rglob("*.mp4")) - before_mp4_files
    print(f"\n[5/5] Kiểm tra file sinh ra trong {MUSE_DOWNLOADS_DIR}:")
    print(f"• Số video mới phát sinh: {len(after_mp4_files)}")
    for f in after_mp4_files:
        print(f"  -> {f.name} ({round(f.stat().st_size / (1024 * 1024), 2)} MB) tại {f.parent.name}")

    # TIÊU CHÍ SỬA LỖI: Chính xác 1 video cho mỗi prompt
    if len(after_mp4_files) != 1:
        print(f"❌ LỖI SỐ LƯỢNG: Kỳ vọng ĐÚNG 1 video mới, nhưng thực tế có {len(after_mp4_files)} video!")
        return False

    single_video = next(iter(after_mp4_files))
    if single_video.stat().st_size < 100 * 1024:
        print(f"❌ Dung lượng file quá nhỏ (< 100 KB): {single_video.stat().st_size} bytes")
        return False

    # Kiểm tra thumbnail và metadata đi kèm
    thumb_file = single_video.with_suffix(".jpg")
    meta_file = single_video.with_name(f"{single_video.stem}_meta.json")

    print(f"• File Thumbnail (.jpg): {'✅ Đã tạo' if thumb_file.is_file() else '❌ Thiếu'}")
    print(f"• File Metadata (.json): {'✅ Đã tạo' if meta_file.is_file() else '❌ Thiếu'}")

    if not thumb_file.is_file() or not meta_file.is_file():
        print("❌ Thiếu thumbnail hoặc metadata JSON!")
        return False

    print("=" * 65)
    print("🎉 KIỂM THỬ E2E TẠO VIDEO QUA GIAO DIỆN DESKTOP APP THÀNH CÔNG 100%!")
    print(f"✅ Video: {single_video.name} ({round(single_video.stat().st_size / (1024 * 1024), 2)} MB)")
    print("✅ Đúng 1 video duy nhất theo prompt.")
    print("✅ Bảng tiến độ và nút bấm UI hoạt động hoàn hảo.")
    print("=" * 65)
    return True


if __name__ == "__main__":
    success = run_ui_e2e_test()
    sys.exit(0 if success else 1)
