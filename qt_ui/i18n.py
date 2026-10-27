"""
qt_ui/i18n.py — Minimal VI/EN translation module.

Usage:
    from qt_ui.i18n import t, toggle_lang, register_listener

    label.setText(t("btn_retry"))          # returns translated string
    register_listener(self._retranslate)   # called automatically on lang switch
"""
from __future__ import annotations

# ── State ──────────────────────────────────────────────────────────────────────
_LANG: str = "vi"          # default: Vietnamese
_LISTENERS: list = []

# ── Translation table ──────────────────────────────────────────────────────────
_T: dict[str, dict[str, str]] = {
    "vi": {
        # ── Toolbar (status_panel) ──────────────────────────────────────────
        "btn_join_video":               "Nối video",
        "btn_retry":                    "Tạo lại video",
        "btn_retry_failed":             "Chạy lại mục lỗi",
        "btn_cut_last":                 "Cắt ảnh cuối",
        "btn_del":                      "Xóa kết quả",
        "btn_open_log":                 "Màn hình log",
        "btn_help_guide":               "📖 Hướng dẫn sử dụng",
        "btn_guide":                    "Xem Hướng Dẫn Sử Dụng TOOL",
        "btn_tele":                     "✈ Liên Hệ Tele",
        # ── Log panel ──────────────────────────────────────────────────────
        "log_group":                    "Nhật ký chạy",
        "log_empty":                    "Chưa có log chạy.",
        "btn_log_back":                 "Quay lại",
        "btn_log_copy":                 "Sao chép",
        "btn_log_clear":                "Xóa log",
        # ── Bottom bar (ui.py) ─────────────────────────────────────────────
        "btn_start":                    "Tạo video",
        "btn_stop":                     "Dừng",
        "btn_view":                     "Xem video/Ảnh",
        "lbl_aspect":                   "Tỷ lệ khung hình",
        "lbl_duration":                 "Thời gian",
        "lbl_model":                    "Model VEO3",
        "lbl_out":                      "Thư mục lưu",
        # ── Tabs (ui.py) ───────────────────────────────────────────────────
        "tab_text_to_video":            "📝 Text to Video",
        "tab_image_to_video":           "🖼️ Image to Video",
        "tab_char_sync":                "🎭 Đồng Nhất NV",
        "tab_create_image":             "🎨 Tạo Ảnh",
        "tab_settings":                 "⚙️ Cài Đặt",
        "tab_main_veo":                 "🚀 VEO 3",
        # ── Lang button ────────────────────────────────────────────────────
        "lang_btn":                     "🌐 EN",   # shows target lang
        "lang_btn_tip":                 "Switch to English",
        # ── Status summary (status_panel.py) ──────────────────────────────
        "status_done":                  "Hoàn thành",
        "status_creating":              "Đang tạo",
        "status_waiting":               "Đang chờ",
        "status_error":                 "Lỗi",
        "status_waiting_msg":           "⏳ Đang chờ {n} video hoàn thành...",
        # ── Table headers ─────────────────────────────────────────────────
        "col_check":                    "Chọn",
        "col_stt":                      "STT",
        "col_video":                    "Video",
        "col_status":                   "Trạng thái",
        "col_mode":                     "Mode",
        "col_prompt":                   "Prompt",
        # ── Aspect ratio combos (ui.py) ───────────────────────────────────
        "aspect_landscape":             "Ngang 16:9",
        "aspect_portrait":              "Dọc 9:16",
        "aspect_square":                "Vuông 1:1",
        # ── TextToVideo tab ───────────────────────────────────────────────
        "ttv_label":                    "Nhập prompt (mỗi dòng là 1 prompt)",
        "ttv_placeholder":              "Mỗi dòng = 1 video. Nên viết tiếng Anh để Veo tạo đẹp hơn.\n\nVí dụ:\n- A young woman walking through a neon-lit Tokyo street at night, slow motion, cinematic wide shot\n- Aerial drone view of golden rice fields at harvest time, camera slowly pulling back, 4K\n- Close-up of rain drops falling on a lotus leaf, macro lens, soft natural light, slow motion\n\n💡 Thêm: góc quay (aerial, close-up, wide shot) + ánh sáng (golden hour, studio) + phong cách (cinematic, 4K, slow motion)",
        # ── ImageToVideo tab ──────────────────────────────────────────────
        "itv_tab1":                     "Tạo Video Từ Ảnh",
        "itv_tab2":                     "Tạo video từ Ảnh Đầu - Ảnh Cuối",
        "itv_step1":                    "Bước 1: Chọn hàng loạt ảnh (Sẽ crop về tỷ lệ đã chọn)",
        "itv_step2":                    "Bước 2: Nhập hàng loạt prompt tương ứng",
        "itv_placeholder":              "Mỗi dòng = 1 prompt, tool TỰ ĐỘNG khớp với ảnh theo thứ tự. Để trống = không có prompt.\n\nVí dụ:\n- The subject slowly turns their head, camera gently zooms in, cinematic light\n- Hair blowing in the wind, camera pans right, golden hour atmosphere\n- Waves moving in and out, slow motion, aerial view pulling back\n\n💡 Tập trung mô tả CHUYỂN ĐỘNG (camera zooms, pans, subject walks/turns) thay vì mô tả tĩnh.\n⚠ Không chấp nhận ảnh nhạy cảm, người nổi tiếng, trẻ em, bạo lực.",
        "itv_col_img":                  "Ảnh",
        "itv_no_img":                   "Chưa chọn ảnh",
        "itv_del":                      "Xóa",
        "itv_prompt_ph":                "Mô tả chuyển động / hành động cho ảnh này (tiếng Anh tốt hơn)...",
        "itv_step1b":                   "Bước 1: Chọn hàng loạt ảnh BẮT ĐẦU",
        "itv_step2b":                   "Bước 2: Chọn hàng loạt ảnh KẾT THÚC",
        "itv_step3b":                   "Bước 3: Nhập hàng loạt prompt tương ứng",
        "itv_placeholder2":             "Mỗi dòng = 1 prompt. Tool ghép cặp tự động: ảnh_đầu[0] + ảnh_cuối[0] + prompt[0], ...\n\nVí dụ:\n- The scene transitions smoothly from day to night, cinematic motion blur\n- A flower blooms from bud to full bloom, macro close-up, soft natural light\n- The figure walks forward as fog rolls in, slow motion, wide shot\n\n💡 Mô tả quá trình BIẾN ĐỔI từ ảnh đầu → ảnh cuối sẽ cho kết quả tốt nhất.\n⚠ Không chấp nhận ảnh nhạy cảm, người nổi tiếng, trẻ em, bạo lực.",
        "itv_no_start":                 "Chưa chọn ảnh bắt đầu",
        "itv_no_end":                   "Chưa chọn ảnh kết thúc",
        # ── CharacterSync tab ─────────────────────────────────────────────
        "char_drop_text":               "⬆\n\nClick để chọn ảnh\nhoặc kéo & thả ảnh vào đây",
        "char_prompt_label":            "Prompt hàng loạt",
        "char_placeholder":             "Mỗi dòng = 1 prompt. Gọi đúng tên nhân vật đã đặt để tool nhúng ảnh vào.\n\nVí dụ (đã đặt tên \"Anna\" và \"Marco\"):\n- Anna đang uống cà phê trong quán nhỏ, nhìn ra cửa sổ mơ màng, cinematic light\n- Marco bước vào căn phòng, mỉm cười tự tin, bokeh background, golden hour\n- Anna và Marco đứng trên cầu nhìn xuống sông lúc hoàng hôn, wide shot\n\n*LƯU Ý:\n- Ảnh nhân vật nên có nền trắng hoặc PNG không nền\n- Tên nhân vật ≥ 4 ký tự, tránh tên phổ thông ngắn (VD: \"Nam\", \"Lan\")\n- Tối đa 3 nhân vật mỗi prompt; nếu nhiều hơn, ghép 2 người vào 1 ảnh",
        "char_name_ph":                 "Tên nhân vật (≥ 4 ký tự, VD: Anna, Marco)...",
        # ── CreateImage tab ───────────────────────────────────────────────
        "ci_label":                     "Nhập prompt (mỗi dòng là 1 prompt)",
        "ci_placeholder":               "Mỗi dòng = 1 ảnh. Nên viết tiếng Anh để Imagen tạo đẹp hơn.\n\nVí dụ:\n- A serene Japanese garden with cherry blossoms, soft morning mist, photorealistic, 8K\n- Portrait of a young woman with flowing hair in the wind, golden hour, cinematic, bokeh\n- Futuristic city skyline at night with neon reflections on wet streets, cyberpunk style, ultra-detailed\n\n💡 Thêm: phong cách nghệ thuật (photorealistic, watercolor, cinematic) + chất lượng (8K, sharp focus, highly detailed)",
        "ci_ref_placeholder":           "Mỗi dòng = 1 ảnh. Gọi đúng tên tham chiếu đã đặt để tool nhúng ảnh vào.\n\nVí dụ (đã đặt tên \"logo_veo\" và \"bgr_city\"):\n- logo_veo placed on a clean white product card, studio lighting, sharp focus, minimalist\n- A character standing in front of bgr_city at night, dramatic lighting, cinematic portrait\n- logo_veo and bgr_city combined in a modern poster layout, bold typography\n\n*LƯU Ý:\n- Không gọi tên → tool tự dùng 3 ảnh tham chiếu đầu tiên\n- Tên tham chiếu ≥ 4 ký tự để tránh nhận nhầm\n- Mỗi prompt gửi tối đa 3 ảnh khớp tên",
        "ci_model_label":               "Model Tạo ảnh",
        "ci_send_btn":                  "Chuyển ảnh đã chọn → Image to Video",
        "ci_tab1":                      "Tạo Ảnh Từ Prompt",
        "ci_tab2":                      "Tạo Ảnh Từ Ảnh Tham Chiếu",
        "ci_ref_name_ph":               "Tên tham chiếu (≥ 4 ký tự, VD: logo_veo, bgr_city)...",
        # ── Settings tab ──────────────────────────────────────────────────
        "settings_veo_group":           "Tài khoản VEO3",
        "settings_save":                "Lưu cài đặt",
        "settings_saved_ok":            "Cấu hình đã được lưu.",
        "settings_open_profile":        "Mở Profile",
        "settings_del_profile":         "Xóa Profile",
        "settings_notes_btn":           "Xem ghi chú thông số",
        "settings_test_conn":           "🔌 Test kết nối",
        "settings_test_conn_testing":   "Đang kiểm tra...",
        "settings_test_conn_ok":        "✅ Kết nối thành công",
        "settings_test_conn_bad_key":   "❌ API key không hợp lệ",
        "settings_test_conn_no_key":    "⚠ Chưa nhập API key",
        "settings_test_conn_err":       "❌ Lỗi kết nối",
        # ── Usage guide ───────────────────────────────────────────────────
        "guide_title":                  "Hướng Dẫn Sử Dụng",
    },
    "en": {
        # ── Toolbar (status_panel) ──────────────────────────────────────────
        "btn_join_video":               "Merge video",
        "btn_retry":                    "Regenerate",
        "btn_retry_failed":             "Retry errors",
        "btn_cut_last":                 "Trim last frame",
        "btn_del":                      "Clear results",
        "btn_open_log":                 "Log screen",
        "btn_help_guide":               "📖 User Guide",
        "btn_guide":                    "View Usage Guide",
        "btn_tele":                     "✈ Contact Tele",
        # ── Log panel ──────────────────────────────────────────────────────
        "log_group":                    "Run log",
        "log_empty":                    "No run log yet.",
        "btn_log_back":                 "Back",
        "btn_log_copy":                 "Copy",
        "btn_log_clear":                "Clear log",
        # ── Bottom bar (ui.py) ─────────────────────────────────────────────
        "btn_start":                    "Generate video",
        "btn_stop":                     "Stop",
        "btn_view":                     "View videos/Images",
        "lbl_aspect":                   "Aspect ratio",
        "lbl_duration":                 "Duration",
        "lbl_model":                    "VEO3 model",
        "lbl_out":                      "Save to",
        # ── Tabs (ui.py) ───────────────────────────────────────────────────
        "tab_text_to_video":            "📝 Text to Video",
        "tab_image_to_video":           "🖼️ Image to Video",
        "tab_char_sync":                "🎭 Character Sync",
        "tab_create_image":             "🎨 Create Image",
        "tab_settings":                 "⚙️ Settings",
        "tab_main_veo":                 "🚀 VEO 3",
        # ── Lang button ────────────────────────────────────────────────────
        "lang_btn":                     "🌐 VI",   # shows target lang
        "lang_btn_tip":                 "Chuyển sang Tiếng Việt",
        # ── Status summary (status_panel.py) ──────────────────────────────
        "status_done":                  "Done",
        "status_creating":              "Creating",
        "status_waiting":               "Waiting",
        "status_error":                 "Error",
        "status_waiting_msg":           "⏳ Waiting for {n} video(s) to complete...",
        # ── Table headers ─────────────────────────────────────────────────
        "col_check":                    "Select",
        "col_stt":                      "#",
        "col_video":                    "Video",
        "col_status":                   "Status",
        "col_mode":                     "Mode",
        "col_prompt":                   "Prompt",
        # ── Aspect ratio combos (ui.py) ───────────────────────────────────
        "aspect_landscape":             "Landscape 16:9",
        "aspect_portrait":              "Portrait 9:16",
        "aspect_square":                "Square 1:1",
        # ── TextToVideo tab ───────────────────────────────────────────────
        "ttv_label":                    "Enter prompts (one per line)",
        "ttv_placeholder":              "One prompt per line = one video.\n\nExample:\n- A young woman walking through a neon-lit Tokyo street at night, slow motion, cinematic wide shot\n- Aerial drone view of golden rice fields at harvest, camera slowly pulling back, 4K\n- Close-up of rain drops on a lotus leaf, macro lens, soft natural light, slow motion\n\n💡 Include: camera movement (aerial, close-up, dolly) + lighting (golden hour, studio) + style (cinematic, 4K, slow motion)",
        # ── ImageToVideo tab ──────────────────────────────────────────────
        "itv_tab1":                     "Image to Video",
        "itv_tab2":                     "First & Last Frame Video",
        "itv_step1":                    "Step 1: Select images (will be cropped to selected ratio)",
        "itv_step2":                    "Step 2: Enter matching prompts",
        "itv_placeholder":              "One prompt per line — tool AUTOMATICALLY matches to images in order. Leave blank = no prompt.\n\nExample:\n- The subject slowly turns their head, camera gently zooms in, cinematic light\n- Hair blowing in the wind, camera pans right, golden hour atmosphere\n- Waves moving in and out, slow motion, aerial view pulling back\n\n💡 Describe MOTION (camera zooms, pans, subject walks/turns) not static descriptions.\n⚠ No sensitive images, celebrities, children, or violence.",
        "itv_col_img":                  "Image",
        "itv_no_img":                   "No image selected",
        "itv_del":                      "Clear",
        "itv_prompt_ph":                "Describe the motion or action for this image...",
        "itv_step1b":                   "Step 1: Select START images",
        "itv_step2b":                   "Step 2: Select END images",
        "itv_step3b":                   "Step 3: Enter matching prompts",
        "itv_placeholder2":             "One prompt per line. Tool AUTO-pairs: start_img[0] + end_img[0] + prompt[0], ...\n\nExample:\n- The scene transitions smoothly from day to night, cinematic motion blur\n- A flower blooms from bud to full bloom, macro close-up, soft natural light\n- The figure walks forward as fog rolls in, slow motion, wide shot\n\n💡 Describe the TRANSFORMATION between start and end frame for best results.\n⚠ No sensitive images, celebrities, children, or violence.",
        "itv_no_start":                 "No start image selected",
        "itv_no_end":                   "No end image selected",
        # ── CharacterSync tab ─────────────────────────────────────────────
        "char_drop_text":               "⬆\n\nClick to select image\nor drag & drop image here",
        "char_prompt_label":            "Batch prompts",
        "char_placeholder":             "One prompt per line. Use the exact character name you set to embed their image.\n\nExample (named \"Anna\" and \"Marco\"):\n- Anna is drinking coffee in a small café, gazing out the window, soft cinematic light\n- Marco walks into the room, smiling confidently, bokeh background, golden hour\n- Anna and Marco standing on a bridge overlooking the river at sunset, wide shot\n\n*NOTE:\n- Use white background or transparent PNG for character images\n- Character names must be ≥ 4 characters; avoid short common names\n- Max 3 characters per prompt; combine 2 people into one image if needed",
        "char_name_ph":                 "Character name (≥ 4 chars, e.g. Anna, Marco)...",
        # ── CreateImage tab ───────────────────────────────────────────────
        "ci_label":                     "Enter prompts (one per line)",
        "ci_placeholder":               "One prompt per line = one image.\n\nExample:\n- A serene Japanese garden with cherry blossoms, soft morning mist, photorealistic, 8K\n- Portrait of a young woman with flowing hair in the wind, golden hour, cinematic, bokeh\n- Futuristic city skyline at night with neon reflections on wet streets, cyberpunk style, ultra-detailed\n\n💡 Include: art style (photorealistic, watercolor, cinematic) + quality (8K, sharp focus, highly detailed)",
        "ci_ref_placeholder":           "One prompt per line. Use the exact reference name you set to embed that image.\n\nExample (named \"logo_veo\" and \"bgr_city\"):\n- logo_veo placed on a clean white product card, studio lighting, sharp focus, minimalist\n- A character standing in front of bgr_city at night, dramatic lighting, cinematic portrait\n- logo_veo and bgr_city combined in a modern poster layout, bold typography\n\n*NOTE:\n- No name called → tool uses the first 3 reference images automatically\n- Reference names must be ≥ 4 characters to avoid false matches\n- Each prompt sends up to 3 matching images",
        "ci_model_label":               "Image model",
        "ci_send_btn":                  "Send selected → Image to Video",
        "ci_tab1":                      "From Prompt",
        "ci_tab2":                      "From Reference Image",
        "ci_ref_name_ph":               "Reference name (≥ 4 chars, e.g. logo_veo, bgr_city)...",
        # ── Settings tab ──────────────────────────────────────────────────
        "settings_veo_group":           "VEO3 Account",
        "settings_save":                "Save settings",
        "settings_saved_ok":            "Settings saved.",
        "settings_open_profile":        "Open Profile",
        "settings_del_profile":         "Delete Profile",
        "settings_notes_btn":           "View parameter notes",
        "settings_test_conn":           "🔌 Test connection",
        "settings_test_conn_testing":   "Testing...",
        "settings_test_conn_ok":        "✅ Connection successful",
        "settings_test_conn_bad_key":   "❌ Invalid API key",
        "settings_test_conn_no_key":    "⚠ No API key entered",
        "settings_test_conn_err":       "❌ Connection error",
        # ── Usage guide ───────────────────────────────────────────────────
        "guide_title":                  "User Guide",
    },
}


# ── Public API ─────────────────────────────────────────────────────────────────

def t(key: str) -> str:
    """Return translated string for current language. Falls back to key."""
    return _T.get(_LANG, _T["vi"]).get(key, key)


def current_lang() -> str:
    return _LANG


def set_lang(lang: str) -> None:
    """Set language and notify all registered listeners."""
    global _LANG
    if lang not in _T:
        return
    _LANG = lang
    for fn in list(_LISTENERS):
        try:
            fn()
        except Exception:
            pass


def toggle_lang() -> str:
    """Toggle VI ↔ EN, notify listeners, return new lang."""
    new = "en" if _LANG == "vi" else "vi"
    set_lang(new)
    return new


def register_listener(fn) -> None:
    """Register a callable to be called whenever the language changes."""
    if fn not in _LISTENERS:
        _LISTENERS.append(fn)


def unregister_listener(fn) -> None:
    if fn in _LISTENERS:
        _LISTENERS.remove(fn)
