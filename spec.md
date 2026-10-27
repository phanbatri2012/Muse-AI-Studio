# Đặc Tả Kỹ Thuật Hệ Thống (Technical Specification) — Muse AI Studio

> **Sản phẩm**: Muse AI Studio (Automated Video Generator via Meta Muse AI & Local REST API Proxy Engine)
> **Phiên bản**: 1.0.0 (Windows x64 Production Release)
> **Kiến trúc**: Standalone Zero-Configuration Desktop Application & Background Service
> **Kho mã nguồn**: [https://github.com/HulkBetii/muse_studio.git](https://github.com/HulkBetii/muse_studio.git)

---

## 1. Giới Thiệu & Mục Tiêu Kỹ Thuật

**Muse AI Studio** là giải pháp phần mềm máy tính (Desktop Application) tự động hóa toàn diện quy trình sáng tạo video từ văn bản (Text-to-Video) và đồng bộ hình ảnh nhất quán nhân vật (Character Consistency Video) dựa trên nền tảng Meta Muse AI (`muse.ai`).

### Mục tiêu thiết kế cốt lõi:
1. **Zero-Configuration (Khởi chạy không cần cấu hình)**: Người dùng phổ thông (Non-tech) cài đặt theo wizard chuẩn Windows (`Next -> Next -> Finish`), không cần cài đặt Python, không cần cài đặt Git, không cần cấu hình biến môi trường `PATH`.
2. **Quyền hạn người dùng tối thiểu (Lowest Privilege)**: Cài đặt hoàn toàn ở cấp độ Per-User (`%LocalAppData%\Programs\Muse AI Studio`), không đòi hỏi quyền Quản trị viên (UAC Administrator).
3. **Phân tách dữ liệu nghiêm ngặt**: Thư mục chương trình là Read-Only; mọi trạng thái dữ liệu (phiên làm việc, token, tài khoản, video tải về, log) được lưu trữ tại `%LocalAppData%\Muse AI Studio\`.
4. **Tự phục hồi & Tự vận hành (Self-Healing)**: Tự động khởi chạy backend proxy API, tự động bảo lưu phiên (Keepalive Daemon mỗi 15 phút), tự động phát hiện và giải phóng xung đột cổng.

---

## 2. Kiến Trúc Tổng Thể (System Architecture)

```mermaid
flowchart TB
    subgraph UI_Layer ["Lớp Giao Diện Người Dùng (PyQt6 Native GUI)"]
        ACCOUNTS["Quản Lý Tài Khoản (Accounts Manager Tab)"]
        PROMPT["Prompt Studio & Hướng Dẫn Kỹ Thuật"]
        CHAR["Character Consistency Studio (1-6 Turnaround Slots)"]
        QUEUE["Giám Sát Hàng Đợi (Queue Monitor Tab)"]
        GALLERY["Thư Viện & Hậu Kỳ (Media Gallery Tab)"]
        SETTINGS["Cài Đặt & Cấu Hình Dịch Vụ"]
    end

    subgraph Orchestration ["Lớp Điều Phối & Xử Lý Pipeline (Orchestration Engine)"]
        WORKER["Worker Điều Phối Tiến Trình (worker_run_workflow.py)"]
        MOTION["Bộ Làm Mượt Chuyển Động (video_motion_smoother.py)"]
        SHORTS["Tạo Shorts Tự Động (shorts_composer.py + Edge-TTS)"]
        BOOTSTRAP["Bootstrap Runtime Trình Duyệt (runtime_bootstrap.py)"]
    end

    subgraph Backend_Service ["Lớp Dịch Vụ Cục Bộ (muse2api Engine - Port 18610)"]
        UVICORN["Máy Chủ Uvicorn / FastAPI (main.py --muse-service)"]
        STORE["Quản Lý Kho Tài Khoản & Hàng Đợi (store.py)"]
        ENGINE["Bộ Máy Tương Tác CDP & WebSocket (engine.py / cdp.py)"]
        KEEPALIVE["Daemon Bảo Lưu Phiên Ngầm (15 Phút/Lần)"]
    end

    subgraph Browser_Automation ["Lớp Tự Động Hóa Trình Duyệt (Playwright & Chromium)"]
        PW["Playwright Headless Engine"]
        BROWSER_RESOLVER["Trình Quét Đa Tầng (Google Chrome -> Edge -> Managed CFT)"]
        MUSE_WEB["Cổng Tương Tác Trực Tiếp muse.ai"]
    end

    UI_Layer --> Orchestration
    Orchestration --> Backend_Service
    Orchestration --> Browser_Automation
    Backend_Service --> Browser_Automation
    Browser_Automation --> MUSE_WEB
```

---

## 3. Các Phân Hệ Chức Năng (Functional Specifications)

### 3.1. Quản lý Tài khoản & Đăng nhập Tự động (Accounts Manager)
- **Định dạng nhập liệu**: Hỗ trợ định dạng phân tách linh hoạt: `email|password|2fa_secret` (hỗ trợ dấu `|`, dấu phẩy, tab).
- **Giải mã 2FA / TOTP**: Tích hợp thuật toán HMAC-SHA1 sinh mã xác thực 6 chữ số tự động trong `muse_auth.py` (`generate_totp_code`).
- **Cơ chế Fallback Trình duyệt**:
  1. Quét tìm Google Chrome hệ thống (`Program Files`, `Local AppData`).
  2. Fallback sang Microsoft Edge (`msedge.exe`).
  3. Fallback sang Chrome for Testing được tự động tải về `%LocalAppData%\Muse AI Studio\runtime\chrome`.
- **Trích xuất Cookie & Session**: Trích xuất 4 cookie cốt lõi: `hatch_sess`, `hatch_gw`, `hatch_vml`, `hatch_native_auth_device` và tự động nạp vào `accounts.json`.

### 3.2. Soạn Kịch bản & Sinh Video (Prompt Studio)
- Soạn thảo kịch bản đa dòng, hỗ trợ đánh số thứ tự trực quan (`NumberedPromptEdit`).
- Hộp thoại hướng dẫn chuẩn câu lệnh (Prompt Guide Dialog) và thanh gợi ý cấu trúc kịch bản Muse AI.
- Bộ làm giàu mô tả chuyển động (`prompt_motion_enhancer.py`) và bộ lọc an toàn nội dung (`prompt_safety_rewriter.py`).

### 3.3. Đồng bộ Nhân vật Nhất quán (Character Consistency Studio)
- Hỗ trợ **Dynamic Reference Slots** linh hoạt từ 1 đến 6 góc máy tham chiếu:
  - Góc trước (Front View)
  - Góc nghiêng 3/4 (Three-Quarter Angle)
  - Góc bên hông (Profile / Side View)
  - Góc sau lưng (Back View)
  - Biểu cảm khuôn mặt (Facial Detail)
  - Trang phục / Phụ kiện đặc tả (Outfit / Props)
- Tự động đồng bộ hóa góc nhìn và nhúng tham chiếu đa điểm khi kích hoạt workflow sinh video.

### 3.4. Giám sát Hàng đợi (Queue Monitor Tab)
- Theo dõi tiến trình sinh video theo thời gian thực (Status, Progress, Elapsed Time, Log).
- Cơ chế kiểm soát luồng song song (In-flight concurrency control) chống nghẽn và chống rate-limit.
- Tự động thử lại thông minh (Auto-retry policy) khi gặp sự cố mạng hoặc phiên tạm ngắt.

### 3.5. Hậu kỳ & Xử lý Media (Media Gallery & Post-Production)
- Tích hợp **Video Motion Smoother**: Gọi FFmpeg nội bộ nội suy khung hình, tăng độ mượt mà cho chuyển động video.
- Tích hợp **Shorts Composer**:
  - Tự động đọc kịch bản qua engine giọng đọc AI Microsoft Edge-TTS (`edge_tts`).
  - Tự động trộn nhạc nền theo ngữ cảnh từ thư viện `ah_bgm/`.
  - Xuất bản phẩm tỷ lệ 9:16 tương thích YouTube Shorts, TikTok và Reels.

---

## 4. Quản Lý Dữ Liệu & Đường Dẫn Runtime (Data Layout)

| Thành phần | Đường dẫn trên Windows | Mục đích & Quyền hạn |
| :--- | :--- | :--- |
| **Install Directory** | `%LocalAppData%\Programs\Muse AI Studio\` | Chứa file thực thi `Muse AI Studio.exe`, thư viện `_internal`, binary `ffmpeg.exe` (Read-Only) |
| **Data General** | `%LocalAppData%\Muse AI Studio\data_general\` | Lưu trữ `settings.json`, `config.json`, `license_display.json` |
| **API Backend Data** | `%LocalAppData%\Muse AI Studio\muse2api_data\` | Lưu `accounts.json`, `tasks.json`, `server.log` |
| **Media Downloads** | `%LocalAppData%\Muse AI Studio\downloads\` | Lưu trữ video và hình ảnh được tạo thành phẩm |
| **Managed Runtime** | `%LocalAppData%\Muse AI Studio\runtime\` | Chứa Chrome for Testing độc lập khi máy thiếu trình duyệt |

---

## 5. Quy Chuẩn Đóng Gói Windows Standalone

### 5.1. PyInstaller (`Muse_AI_Studio.spec`)
- **Chế độ**: Onedir (`exclude_binaries=True`), Windowed (`console=False`).
- **Binary Bundling**: Đóng gói trực tiếp `ffmpeg.exe` và `ffprobe.exe` vào `_internal/bin/`.
- **Hidden Imports**: Khai báo đầy đủ các module ngầm của FastAPI, Uvicorn, Playwright, PyQt6, Pydantic, và toàn bộ hệ thống workflow (`A_workflow_*`).
- **Nhận diện Icon**: Nhúng trực tiếp file `app_icon.ico` đa kích thước chuẩn (16px đến 256px) vào PE Header của file thực thi.

### 5.2. Inno Setup (`installer/windows/muse_ai_studio.iss`)
- **Tên tệp xuất bản**: `dist-installer\Muse_AI_Studio_Setup.exe`
- **Mã ứng dụng định danh**: `AppId={{EDB31FBC-CC82-4DEB-BF18-6349F465AF0E}}`
- **Cấp quyền**: `PrivilegesRequired=lowest` (Cài đặt sạch không cần quyền Admin).
- **Tự động cài đặt phụ thuộc**: Tích hợp Pascal Script kiểm tra Registry `Microsoft Visual C++ Redistributable (x64)`. Nếu thiếu, tự động chạy ngầm gói `VC_redist.x64.exe` với tham số `/install /quiet /norestart`.
- **Tương thích Taskbar Windows 11**:
  - Gán `AppUserModelID: "Muse.AI.Studio.App"`.
  - Gọi Win32 API `SHChangeNotify(SHCNE_ASSOCCHANGED, ...)` làm mới Icon Cache của Windows Explorer ngay sau khi cài đặt.

---

## 6. Giao Thức API & Hướng Dẫn Tích Hợp

Backend cục bộ của Muse AI Studio hỗ trợ chuẩn giao thức OpenAI API tại `http://127.0.0.1:18610/`:

```http
POST /v1/chat/completions
Headers:
Authorization: Bearer muse_desktop_local_secret
  Content-Type: application/json
```

```http
POST /v1/videos
Headers:
Authorization: Bearer muse_desktop_local_secret
  Content-Type: application/json

Body:
{
  "prompt": "Cinematic shot of futuristic sports car speeding through neon cyberpunk city",
  "aspect_ratio": "16:9",
  "duration": 5
}
```

```http
GET /admin/status
Headers:
Authorization: Bearer muse_desktop_local_secret
```

---

## 7. Quy Trình Tự Động Hóa Build (CI/CD Local)

Để biên dịch bộ cài đặt mới từ mã nguồn, chạy lệnh PowerShell sau:

```powershell
# Chạy toàn bộ quy trình: Virtualenv -> PyInstaller -> Inno Setup Compiler
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

Thành phẩm sẽ được xuất ra tại thư mục:
`dist-installer\Muse_AI_Studio_Setup.exe`
