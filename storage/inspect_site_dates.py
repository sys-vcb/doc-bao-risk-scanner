import sys
import re
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urlparse

sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')

from app.config import TARGET_SITES
from app.scraper.engine import parse_article_links, HEADERS

client = httpx.Client(verify=False, headers=HEADERS, timeout=15.0)

print("=== KHẢO SÁT VỊ TRÍ NGÀY ĐĂNG BÀI TRÊN 9 TRANG BÁO ===")

for site in TARGET_SITES:
    name = site["name"]
    url = site["url"]
    domain = urlparse(url).netloc
    
    print("\n" + "="*70)
    print(f"🌐 Trang: {name} (Domain: {domain})")
    
    try:
        r = client.get(url)
        if r.status_code != 200:
            continue
            
        links = parse_article_links(url, r.text)
        if not links:
            continue
            
        art_url = links[0]
        print(f"   Sample Article URL: {art_url}")
        
        art_resp = client.get(art_url)
        if art_resp.status_code != 200:
            continue
            
        soup = BeautifulSoup(art_resp.text, 'html.parser')
        
        # 1. Inspect meta tags
        meta_dates = []
        for m in soup.find_all('meta'):
            prop = m.get('property', '').lower()
            mname = m.get('name', '').lower()
            content = m.get('content', '').strip()
            if content and any(k in prop or k in mname for k in ['date', 'time', 'pubdate']):
                meta_dates.append(f"{prop or mname} = '{content}'")
        print(f"   [Meta Tags Date]: {meta_dates if meta_dates else 'Không có'}")

        # 2. Inspect specific HTML date elements
        date_elems = []
        for el in soup.find_all(class_=True):
            cls_str = " ".join(el.get("class", [])).lower()
            if any(k in cls_str for k in ["date", "time", "pubdate", "ngay", "detail-time", "meta-time", "pdate", "post-date"]):
                txt = el.get_text().strip()
                if len(txt) > 5 and len(txt) < 120 and re.search(r'\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}', txt):
                    date_elems.append(f"<{el.name} class='{cls_str}'> -> '{txt}'")
                    
        print(f"   [HTML Class Elements Date]:")
        for de in date_elems[:5]:
            print(f"      {de}")
            
    except Exception as e:
        print(f"❌ Error on {domain}: {e}")
