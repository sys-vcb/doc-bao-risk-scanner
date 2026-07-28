# 🛡️ Risk News Scanner & Automated Word/Email Reporter

> Hệ thống tự động quét tin tức báo chí, phát hiện **Rủi ro Doanh nghiệp / Tổ chức / Cá nhân** tại 6 Tỉnh/Thành phố mục tiêu, trích xuất dữ liệu bằng Gemini AI, tự động tổng hợp báo cáo file Word (`.docx`) 5 cột hằng ngày và gửi Email cảnh báo linh hoạt theo Khu vực.

Giao diện Web được thiết kế theo phong cách **Glassmorphism (Kính mờ xuyên thấu)** sang trọng, hỗ trợ xem live dữ liệu, kích hoạt quét thủ công và quản lý danh sách email nhận tin.

---

## 🌟 Tính Năng Nổi Bật

1. **Giám sát 9 Website Báo chí Mục tiêu**:
   - Báo Hải Phòng (`baohaiphong.vn`)
   - Báo Hưng Yên (`baohungyen.vn`)
   - Báo Ninh Bình (`baoninhbinh.org.vn`)
   - Báo Bắc Ninh TV (`baobacninhtv.vn`)
   - Báo Phú Thọ (`baophutho.vn`)
   - Báo Quảng Ninh (`baoquangninh.vn`)
   - VnExpress Pháp luật (`vnexpress.net`)
   - Báo Pháp Luật Việt Nam (`baophapluat.vn`)

2. **Giám sát 6 Tỉnh / Thành phố**:
   - *Quảng Ninh, Hải Phòng, Hưng Yên, Ninh Bình, Bắc Ninh, Phú Thọ*.

3. **Quy trình Lọc 2 Bước (2-Step Filtering) Tiết Tiết Chi Phí API Gemini**:
   - **Step 1**: Cào HTML bài viết, lọc thời gian trong ngày hiện tại ($T$) và 1 ngày trước đó ($T-1$). Deduplication qua URL Hash trong CSDL SQLite.
   - **Step 2**: Dùng Python Regex kiểm tra chứa **[Ít nhất 1 trong 6 Tỉnh]** VÀ **[Ít nhất 1 Từ khóa Rủi ro]** (Pháp lý/Hình sự, Thuế/BHXH, Giấy phép/Xử phạt, Lao động/Môi trường).
   - **Step 3**: CHỈ NẾU bài viết qua vòng sơ bộ mới gửi văn bản sang Gemini API để trích xuất 5 thông tin cấu trúc.

4. **Xuất File Word (.docx) Chuẩn 5 Cột**:
   - Tên file: `Bao_Cao_Rui_Ro_YYYY-MM-DD.docx`.
   - Bảng 5 cột:
     1. Tên Cá nhân / Doanh nghiệp / Tổ chức
     2. Nội dung tóm tắt rủi ro (2-3 câu)
     3. Khu vực (Tỉnh/Thành)
     4. Loại rủi ro / Từ khóa phát hiện
     5. Ngày tin tức & Link bài gốc (có hyperlink)

5. **Gửi Email Cảnh Báo Phân Loại Theo Khu Vực**:
   - Quản lý subscriber trên giao diện Web.
   - Tự động lọc bài viết thuộc địa bàn người nhận đăng ký và đính kèm file Word `.docx` tương ứng.

6. **Lịch Chạy Tự Động (Scheduler)**:
   - APScheduler chạy tự động 2 lần/ngày (Vào lúc **07:00 sáng** và **17:00 chiều**).

---

## 🚀 Hướng Dẫn Chạy Thử Nghiệm Trên Localhost (`http://localhost:8000`)

### Cách 1: Chạy trực tiếp bằng Python Virtual Environment (Khuyên dùng khi dev)

1. **Cài đặt Python 3.10+**:
   Đảm bảo máy đã cài đặt Python 3.10 trở lên.

2. **Cài đặt thư viện dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Cấu hình file `.env`**:
   Tạo hoặc chỉnh sửa file `.env`:
   ```ini
   APP_NAME="Risk News Scanner & Reporter"
   DEBUG=True
   PORT=8000

   # Điền Gemini API Key (Nếu không điền, hệ thống sẽ dùng chế độ Fallback Regex)
   GEMINI_API_KEY="AIzaSy..."

   # Cấu hình Email SMTP (Điền nếu muốn gửi email thực tế)
   SMTP_SERVER="smtp.gmail.com"
   SMTP_PORT=587
   SMTP_USER="your-email@gmail.com"
   SMTP_PASSWORD="your-app-password"
   SENDER_EMAIL="your-email@gmail.com"
   SENDER_NAME="Hệ Thống Cảnh Báo Rủi Ro Doanh Nghiệp"

   DATABASE_URL="sqlite:///./risk_scanner.db"
   ```

4. **Khởi chạy ứng dụng Web**:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

5. **Truy cập Giao diện Dashboard**:
   Mở trình duyệt web và truy cập: [http://localhost:8000](http://localhost:8000)

---

### Cách 2: Khởi chạy nhanh bằng Docker & Docker Compose (1 Lệnh duy nhất)

1. **Khởi chạy Docker Container**:
   ```bash
   docker-compose up -d --build
   ```

2. **Kiểm tra trạng thái**:
   ```bash
   docker-compose ps
   ```

3. **Xem log hoạt động**:
   ```bash
   docker-compose logs -f
   ```

4. **Truy cập Giao diện**:
   Truy cập [http://localhost:8000](http://localhost:8000)

---

## ☁️ Hướng Dẫn Deploy Lên Máy Chủ Cloud VPS (Ubuntu / Debian)

### 1. Chuẩn bị trên VPS
- Đảm bảo VPS đã cài đặt Docker và Docker Compose:
  ```bash
  sudo apt update && sudo apt install -y docker.io docker-compose
  ```

### 2. Copy Mã nguồn và Khởi chạy
- Git clone hoặc Upload thư mục mã nguồn lên VPS (ví dụ `/opt/risk-scanner`).
- Tạo file `.env` chứa API Key và Email SMTP.
- Chạy lệnh Docker Compose:
  ```bash
  cd /opt/risk-scanner
  docker-compose up -d --build
  ```

### 3. Cấu hình Nginx Reverse Proxy (Tùy chọn HTTPS)
Tạo file cấu hình Nginx `/etc/nginx/sites-available/risk-scanner`:
```nginx
server {
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
Kích hoạt vhost và cấp chứng chỉ SSL miễn phí bằng Certbot:
```bash
sudo ln -s /etc/nginx/sites-available/risk-scanner /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d your-domain.com
```

---

## 🛠️ Trực Quan Hóa Cấu Trúc Dự Án

```
d:/Project/Doc Bao/
├── app/
│   ├── main.py                 # FastAPI Router & Web Entrypoint
│   ├── config.py               # 9 trang web, 6 tỉnh & từ khóa rủi ro
│   ├── database.py             # SQLAlchemy Engine & Session
│   ├── models.py               # Bảng CSDL (Article, RiskItem, EmailSubscriber, ScanLog)
│   ├── scraper/
│   │   ├── engine.py           # Async Scraper (httpx & BeautifulSoup)
│   │   └── regex_filter.py     # Lọc sơ bộ 2-step Regex (Tiết kiệm Gemini API)
│   ├── ai/
│   │   └── gemini_extractor.py # AI Gemini Trích xuất JSON 5 trường chuẩn
│   ├── services/
│   │   ├── docx_exporter.py    # Xuất File Word (.docx) 5 cột chuẩn
│   │   ├── email_service.py    # Phân loại & gửi Email đính kèm .docx
│   │   └── scheduler.py        # APScheduler chạy tự động 07:00 & 17:00
│   ├── static/
│   │   ├── css/glassmorphism.css # Hệ thống Kính mờ xuyên thấu sang trọng
│   │   └── js/main.js          # AJAX, Bảng live, Lọc tỉnh, Trigger Quét
│   └── templates/
│       └── index.html          # Web Dashboard HTML5 Glassmorphic
├── storage/reports/            # Thư mục lưu các file Bao_Cao_Rui_Ro_YYYY-MM-DD.docx
├── Dockerfile                  # Script build Docker image
├── docker-compose.yml          # Config chạy Docker 1 lệnh
├── requirements.txt            # Thư viện Python
└── README.md                   # Hướng dẫn chi tiết
```

---

## 📊 API Reference (FastAPI Documentation)

- `GET /`: Giao diện Web Dashboard Glassmorphism
- `GET /api/news`: Lấy danh sách tin rủi ro (Hỗ trợ query `province` và `search`)
- `POST /api/scan`: Kích hoạt cào tin thủ công & trích xuất Gemini ngay lập tức
- `GET /api/reports/download/{date}`: Tải file `.docx` báo cáo theo ngày (Ví dụ: `2026-07-26`)
- `GET /api/stats`: Lấy thống kê realtime cho Dashboard
- `GET /api/settings/email`: Danh sách Email nhận cảnh báo
- `POST /api/settings/email`: Thêm Email mới nhận cảnh báo theo tỉnh
- `DELETE /api/settings/email/{id}`: Xóa Email subscriber
