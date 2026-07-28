import sys
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')

from app.scraper.engine import parse_article_links, HEADERS

cat_url = "https://baobacninhtv.vn/phap-luat"
client = httpx.Client(verify=False, headers=HEADERS, timeout=15.0)

print(f"=== SOÁT DANH SÁCH LINK BÀI VIẾT TRÊN TRANG MỤC {cat_url} ===")
r = client.get(cat_url)
links = parse_article_links(cat_url, r.text)

print(f"Tổng số link tìm thấy trên trang 1 danh mục ({cat_url}): {len(links)}")
target_url = "https://baobacninhtv.vn/cong-an-bac-ninh-triet-pha-duong-day-co-bac-truc-tuyen-xuyen-quoc-gia-co-hon-30-000-thanh-vien-tham-gia-postid450068.bbg"

is_found = target_url in links
print(f"URL vụ Đinh Đức Phụng (postid450068.bbg) có nằm trong top link trang 1 không? -> {is_found}")

if not is_found:
    print("\n🔍 TOÀN BỘ DANH SÁCH LINK HIỆN CÓ TRÊN TRANG 1:")
    for idx, l in enumerate(links, 1):
        print(f"  {idx}. {l}")
