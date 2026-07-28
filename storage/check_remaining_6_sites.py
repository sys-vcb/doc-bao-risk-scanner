import sys
import re
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urlparse

sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')

from app.config import TARGET_SITES
from app.scraper.engine import parse_article_links, extract_clean_pub_date, HEADERS

client = httpx.Client(verify=False, headers=HEADERS, timeout=15.0)

# 6 trang còn lại
remaining_sites = [
    {"name": "Báo Hải Phòng", "url": "https://baohaiphong.vn/phap-luat/tin-tuc"},
    {"name": "Báo Hưng Yên", "url": "https://baohungyen.vn/phap-luat-doi-song"},
    {"name": "Báo Phú Thọ", "url": "https://baophutho.vn/phutho24h"},
    {"name": "Báo Quảng Ninh", "url": "https://baoquangninh.vn/phap-luat"},
    {"name": "VnExpress (Pháp luật)", "url": "https://vnexpress.net/phap-luat"},
    {"name": "Báo Pháp Luật VN", "url": "https://baophapluat.vn/chuyen-muc/phap-luat.html"}
]

print("=== KIỂM TRA NGÀY ĐĂNG BÀI TRÊN 6 TRANG BÁO CÒN LẠI ===")

for site in remaining_sites:
    name = site["name"]
    url = site["url"]
    print("\n" + "="*80)
    print(f"🌐 Trang: {name}")
    try:
        r = client.get(url)
        if r.status_code == 200:
            links = parse_article_links(url, r.text)
            if links:
                # Chọn bài thứ 2 hoặc thứ 3 để đảm bảo bài viết thực tế
                art_url = links[min(1, len(links)-1)]
                art_resp = client.get(art_url)
                if art_resp.status_code == 200:
                    soup = BeautifulSoup(art_resp.text, "html.parser")
                    extracted_date = extract_clean_pub_date(art_url, art_resp.text, soup)
                    print(f"   🔗 URL bài viết: {art_url}")
                    print(f"   📅 Ngày đăng bóc tách (YYYY-MM-DD): '{extracted_date}'")
            else:
                print("   ⚠️ Không tìm thấy link bài viết nào.")
    except Exception as e:
        print(f"   ❌ Lỗi: {e}")
