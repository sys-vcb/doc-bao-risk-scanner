import re
from datetime import datetime, timedelta
from typing import Tuple, List, Optional
from app.config import TARGET_PROVINCES, ALL_RISK_KEYWORDS, get_vietnam_now

# Danh sách chủ đề hoàn toàn không phải tin rủi ro (Loại bỏ các từ rác thuần túy)
EXCLUDE_TOPICS = [
    "dự báo thời tiết", "thời tiết 24h", "du lịch nghỉ dưỡng", "văn nghệ chào mừng",
    "giá cà phê", "giá vàng hôm nay", "giá nông sản", "bảo tồn di sản"
]

# Danh sách Động từ Hành vi Rủi ro rộng mở bao quát toàn bộ tội phạm & vi phạm
ACTION_RISK_VERBS = [
    "khởi tố", "bắt giam", "tạm giam", "tạm giữ", "bắt giữ", "truy nã", "truy tìm", 
    "tuyên án", "xử phạt", "đình chỉ", "thu hồi", "cưỡng chế", "trốn thuế", "nợ thuế", 
    "nợ bhxh", "trốn đóng bhxh", "phong tỏa", "kê biên", "tử vong", "sát hại", "gây án",
    "xả thải", "gây ô nhiễm", "chiếm đoạt", "lừa đảo", "tham nhũng", "nhận hối lộ", 
    "hối lộ", "vỡ nợ", "giải thể", "phá sản", "đình công", "gây rối", "vẽ bệnh", "đột kích",
    "án mạng", "bị can", "bị cáo", "xét xử", "phạt tiền", "sai phạm", "điều tra",
    "đánh bạc", "cờ bạc", "buôn lậu", "tín dụng đen", "cho vay nặng lãi", "tước giấy phép",
    "tước quyền", "xử lý vi phạm", "vi phạm quy định", "vi phạm pháp luật", "tố giác"
]

def is_date_within_t_minus_1(pub_date_str: str) -> bool:
    """Kiểm tra sơ bộ ngày xuất bản bài báo"""
    if not pub_date_str:
        return True
    
    today = get_vietnam_now().date()
    yesterday = today - timedelta(days=1)
    
    match_iso = re.search(r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})', pub_date_str)
    if match_iso:
        try:
            year, month, day = map(int, match_iso.groups())
            if 2000 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                dt = datetime(year, month, day).date()
                return dt >= yesterday
        except ValueError:
            pass

    match_dd = re.search(r'(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})', pub_date_str)
    if match_dd:
        try:
            day, month, year = map(int, match_dd.groups())
            if 2000 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                dt = datetime(year, month, day).date()
                return dt >= yesterday
        except ValueError:
            pass
            
    return True


def is_date_in_range(pub_date_str: str, date_from: Optional[str] = None, date_to: Optional[str] = None) -> bool:
    """Kiểm tra ngày đăng bài có nằm trong khoảng [date_from, date_to] hay không"""
    if not pub_date_str:
        return True

    today = get_vietnam_now().strftime("%Y-%m-%d")
    d_from = date_from or today
    d_to = date_to or today

    m_iso = re.search(r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})', pub_date_str)
    if m_iso:
        y, m, d = map(int, m_iso.groups())
        dt_str = f"{y:04d}-{m:02d}-{d:02d}"
        return d_from <= dt_str <= d_to

    return True


def pre_filter_article(title: str, content: str, default_province_hint: Optional[str] = None) -> Tuple[bool, List[str], List[str]]:
    """
    Lọc 2-Step Regex linh hoạt:
    1. Loại bỏ bài viết thuần rác (thời tiết, giá cà phê...).
    2. Nhận diện Tỉnh thành hoặc chấp nhận tin Toàn quốc đối với báo Trung ương.
    3. Bắt buộc có động từ/dấu hiệu rủi ro.
    """
    full_text = f"{title}\n{content}".lower()
    title_lower = title.lower()

    # 0. Loại bỏ Tin Rác thuần túy
    if any(ex in title_lower for ex in EXCLUDE_TOPICS):
        return False, [], []

    # 1. Nhận diện Tỉnh thành mục tiêu
    matched_provinces = []
    for prov in TARGET_PROVINCES:
        pattern = r'\b' + re.escape(prov.lower()) + r'\b'
        if re.search(pattern, full_text):
            matched_provinces.append(prov)
            
    if not matched_provinces and default_province_hint:
        if default_province_hint in TARGET_PROVINCES:
            matched_provinces.append(default_province_hint)
        elif default_province_hint == "Toàn quốc":
            matched_provinces.append("Toàn quốc")
        
    if not matched_provinces:
        matched_provinces = ["Toàn quốc"]

    # 2. Bắt buộc có Động từ/Dấu hiệu Rủi ro
    has_action_verb = any(re.search(r'\b' + re.escape(v) + r'\b', full_text) for v in ACTION_RISK_VERBS)
    if not has_action_verb:
        return False, matched_provinces, []

    # 3. Gom từ khóa rủi ro
    matched_keywords = []
    for kw in ALL_RISK_KEYWORDS:
        pattern = r'\b' + re.escape(kw.lower()) + r'\b'
        if re.search(pattern, full_text):
            matched_keywords.append(kw)

    if not matched_keywords:
        matched_keywords = ["Rủi ro pháp lý/xử phạt"]

    return True, matched_provinces, matched_keywords

