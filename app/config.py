import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent
if os.getenv("VERCEL"):
    STORAGE_DIR = Path("/tmp/storage")
else:
    STORAGE_DIR = BASE_DIR / "storage"

REPORTS_DIR = STORAGE_DIR / "reports"
try:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass


VN_TZ = timezone(timedelta(hours=7))

def get_vietnam_now() -> datetime:
    """Trả về thời gian hiện tại theo đúng múi giờ GMT+7 Việt Nam"""
    return datetime.now(VN_TZ)

def get_vietnam_today_str() -> str:
    """Trả về chuỗi ngày YYYY-MM-DD theo múi giờ GMT+7 Việt Nam"""
    return datetime.now(VN_TZ).strftime("%Y-%m-%d")


class Settings(BaseSettings):
    APP_NAME: str = "Risk News Scanner & Reporter"
    DEBUG: bool = True
    PORT: int = 8000
    
    # Gemini API Key
    GEMINI_API_KEY: str = ""
    
    # SMTP Email Config
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SENDER_EMAIL: str = ""
    SENDER_NAME: str = "Hệ Thống Cảnh Báo Rủi Ro Doanh Nghiệp"
    
    # Database
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/risk_scanner.db"
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# 9 Target Websites
TARGET_SITES = [
    {"name": "Báo Hải Phòng", "url": "https://baohaiphong.vn/phap-luat/tin-tuc", "province_hint": "Hải Phòng"},
    {"name": "Báo Hưng Yên (Pháp luật)", "url": "https://baohungyen.vn/phap-luat-doi-song", "province_hint": "Hưng Yên"},
    {"name": "Báo Hưng Yên (Đời sống)", "url": "https://baohungyen.vn/doi-song", "province_hint": "Hưng Yên"},
    {"name": "Báo Ninh Bình", "url": "https://baoninhbinh.org.vn/vu-an", "province_hint": "Ninh Bình"},
    {"name": "Báo Bắc Ninh TV", "url": "https://baobacninhtv.vn/phap-luat", "province_hint": "Bắc Ninh"},
    {"name": "Báo Phú Thọ", "url": "https://baophutho.vn/phutho24h", "province_hint": "Phú Thọ"},
    {"name": "Báo Quảng Ninh", "url": "https://baoquangninh.vn/phap-luat", "province_hint": "Quảng Ninh"},
    {"name": "VnExpress (Pháp luật)", "url": "https://vnexpress.net/phap-luat", "province_hint": "Toàn quốc"},
    {"name": "Báo Pháp Luật VN", "url": "https://baophapluat.vn/chuyen-muc/phap-luat.html", "province_hint": "Toàn quốc"},
]

# 6 Target Provinces
TARGET_PROVINCES = [
    "Quảng Ninh",
    "Hải Phòng",
    "Hưng Yên",
    "Ninh Bình",
    "Bắc Ninh",
    "Phú Thọ"
]

# Risk Keywords Categorized
RISK_KEYWORDS = {
    "Pháp lý / Hình sự": [
        "bắt giam", "khởi tố", "tạm giam", "lừa đảo", "phong tỏa tài sản",
        "truy nã", "vi phạm pháp luật", "bị can", "bị cáo", "truy tố",
        "tuyên án", "tham nhũng", "hối lộ", "chiếm đoạt", "lạm dụng tín nhiệm",
        "vỡ nợ", "cưỡng chế"
    ],
    "Thuế / Tài chính / BHXH": [
        "trốn thuế", "nợ thuế", "cưỡng chế thuế", "nợ bhxh", "trốn đóng bhxh",
        "nợ lương", "nợ bảo hiểm", "cưỡng chế hóa đơn", "ngưng hoạt động",
        "phá sản", "giải thể", "kê biên"
    ],
    "Giấy phép / Xử phạt": [
        "thu hồi giấy phép", "tước giấy phép", "đình chỉ hoạt động",
        "xử phạt hành chính", "vi phạm quy định", "phạt tiền",
        "cưỡng chế thi hành", "thu hồi đất", "hủy bỏ dự án"
    ],
    "Lao động / An toàn / Môi trường": [
        "tai nạn lao động", "vi phạm môi trường", "xả thải chui",
        "gây ô nhiễm", "đình công", "lãng công", "cháy nổ",
        "sự cố môi trường", "mất an toàn lao động", "tử vong lao động"
    ]
}

# Flatten list of all risk keywords for fast Regex check
ALL_RISK_KEYWORDS = [kw for group in RISK_KEYWORDS.values() for kw in group]
