import hashlib
import logging
import asyncio
import re
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse, urldefrag


import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.config import TARGET_SITES, get_vietnam_today_str, VN_TZ

from app.models import Article
from app.scraper.regex_filter import pre_filter_article, is_date_within_t_minus_1, is_date_in_range

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ScraperEngine")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}

IGNORE_PATH_PATTERNS = [
    "/tag/", "/chuyen-muc/", "/page/", "facebook.com", "twitter.com",
    "/multimedia/", "/podcast/", "/ban-doc/", "/video/", "/error/", 
    "/search", "/thoi-tiet", "/pho-bien-phap-luat", "/an-toan-giao-thong",
    "/ong-kinh-phong-vien", "/van-ban-chinh-sach"
]

def generate_url_hash(url: str) -> str:
    """Tạo SHA256 hash cho URL để chống trùng lặp"""
    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()

async def fetch_html(client: httpx.AsyncClient, url: str) -> Optional[str]:
    """Fetch nội dung HTML từ URL"""
    try:
        response = await client.get(url, headers=HEADERS, timeout=15.0, follow_redirects=True)
        if response.status_code == 200:
            return response.text
        logger.warning(f"Fetch URL {url} trả về HTTP status {response.status_code}")
    except Exception as e:
        logger.error(f"Lỗi khi cào URL {url}: {e}")
    return None

def parse_article_links(base_url: str, html: str) -> List[str]:
    """Bóc tách danh sách URL chi tiết bài báo (Hỗ trợ URL có gạch chéo /, clean slug và query param)"""
    soup = BeautifulSoup(html, "lxml" if "lxml" in html else "html.parser")
    links = set()
    domain = urlparse(base_url).netloc
    base_path = urlparse(base_url).path.rstrip("/")

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
            
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        path = parsed.path.lower()
        clean_path = path.rstrip("/")
        
        if parsed.netloc == domain and clean_path != base_path:
            if any(ign in path for ign in IGNORE_PATH_PATTERNS):
                continue
                
            has_valid_ext = any(clean_path.endswith(ext) for ext in [".html", ".htm", ".bbg", ".asp", ".aspx"])
            has_numeric_id = bool(re.search(r'\d{5,}', path))
            has_clean_slug = path.count("-") >= 3
            
            if (has_valid_ext or has_numeric_id or has_clean_slug) and len(href) > 12:
                links.add(full_url)
                
    return list(links)

def parse_raw_date_to_iso(found_raw: str) -> str:
    """Parse chuỗi ngày thô đa dạng sang YYYY-MM-DD theo đúng múi giờ GMT+7 Việt Nam"""
    if not found_raw:
        return ""

    # 1. Thử parse ISO 8601 chứa múi giờ (VD: 2026-07-27T23:58:00Z hoặc 2026-07-27T23:58:00+00:00)
    try:
        clean_iso = found_raw.strip().replace("Z", "+00:00")
        if "T" in clean_iso or "+" in clean_iso:
            dt = datetime.fromisoformat(clean_iso)
            if dt.tzinfo:
                dt_vn = dt.astimezone(VN_TZ)
                return dt_vn.strftime("%Y-%m-%d")
    except Exception:
        pass

    # 2. Parse chuỗi YYYY-MM-DD
    m_iso = re.search(r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})', found_raw)
    if m_iso:
        y, m, d = map(int, m_iso.groups())
        if 2000 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= 31:
            return f"{y:04d}-{m:02d}-{d:02d}"

    # 3. Parse chuỗi DD/MM/YYYY hoặc MM/DD/YYYY
    m_mdy = re.search(r'(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})', found_raw)
    if m_mdy:
        p1, p2, y = map(int, m_mdy.groups())
        if 2000 <= y <= 2100:
            if p2 > 12 and 1 <= p1 <= 12: # Month/Day/Year (VD: 7/26/2026)
                return f"{y:04d}-{p1:02d}-{p2:02d}"
            elif p1 > 12 and 1 <= p2 <= 12: # Day/Month/Year (VD: 26/07/2026)
                return f"{y:04d}-{p2:02d}-{p1:02d}"
            elif 1 <= p1 <= 31 and 1 <= p2 <= 12:
                return f"{y:04d}-{p2:02d}-{p1:02d}" # Mặc định DD/MM/YYYY

    return ""


def extract_clean_pub_date(url: str, html: str, soup: BeautifulSoup) -> str:
    """
    Trích xuất ngày xuất bản FIX CỨNG chuẩn xác 100% theo từng Domain tòa báo.
    Loại bỏ hoàn toàn các thẻ giờ hệ thống ở Header và thẻ quảng cáo/sidebar.
    """
    domain = urlparse(url).netloc.lower()
    found_raw = ""

    # 1. Báo Bắc Ninh TV (Chỉ lấy trong tin chi tiết div.news-detail__head)
    if "baobacninhtv.vn" in domain:
        elem = soup.find(class_=lambda c: c and "news-detail" in str(c)) or soup.find(class_="news-detail__head")
        if elem:
            found_raw = elem.get_text().strip()

    # 2. Báo Ninh Bình (Lấy từ thẻ span id="date")
    elif "baoninhbinh.org.vn" in domain:
        elem = soup.find(id="date") or soup.find("span", id="date")
        if elem:
            found_raw = elem.get_text().strip()

    # 3. Báo Hưng Yên & Báo Quảng Ninh (Dùng div.date.font5)
    elif "baohungyen.vn" in domain or "baoquangninh.vn" in domain:
        elem = soup.find("div", class_=lambda c: c and "date" in c and "font5" in c)
        if elem:
            found_raw = elem.get_text().strip()

    # 4. VnExpress (Dùng meta pubdate hoặc span.date)
    elif "vnexpress.net" in domain:
        meta = soup.find("meta", attrs={"name": "pubdate"}) or soup.find("meta", property="article:published_time")
        if meta and meta.get("content"):
            found_raw = meta["content"]
        else:
            elem = soup.find("span", class_="date")
            if elem:
                found_raw = elem.get_text().strip()

    # 5. Báo Phú Thọ & Báo Pháp Luật VN
    elif "baophutho.vn" in domain or "baophapluat.vn" in domain:
        meta = soup.find("meta", property="article:published_time")
        if meta and meta.get("content"):
            found_raw = meta["content"]
        else:
            elem = soup.find(class_=lambda c: c and any(k in c.lower() for k in ["pdate", "stime", "date-detail"]))
            if elem:
                found_raw = elem.get_text().strip()

    # 6. Báo Hải Phòng (Meta article:published_time hoặc span.block-sc-publish-time)
    elif "baohaiphong.vn" in domain:
        meta = soup.find("meta", property="article:published_time") or soup.find("meta", attrs={"name": "pubdate"})
        if meta and meta.get("content"):
            found_raw = meta["content"]
        else:
            elem = soup.find(class_=lambda c: c and any(k in c.lower() for k in ["publish-time", "c-detail-head__date", "detail-date"]))
            if elem:
                found_raw = elem.get_text().strip()

    return parse_raw_date_to_iso(found_raw)


def parse_article_detail(url: str, html: str) -> Optional[Dict[str, Any]]:
    """Bóc tách tiêu đề, ngày đăng, nội dung chi tiết bài báo"""
    soup = BeautifulSoup(html, "lxml" if "lxml" in html else "html.parser")
    
    title = ""
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = og_title["content"].strip()
    elif soup.find("h1"):
        title = soup.find("h1").get_text().strip()
    elif soup.title:
        title = soup.title.get_text().strip()

    if not title or len(title) < 10:
        return None

    pub_date = extract_clean_pub_date(url, html, soup)

    for s in soup(["script", "style", "aside", "iframe", "footer", "nav"]):
        s.extract()

    paragraphs = []
    for p in soup.find_all(["p", "h2", "h3"]):
        txt = p.get_text().strip()
        if len(txt) > 20 and txt not in paragraphs:
            paragraphs.append(txt)

    if len(paragraphs) < 2:
        for d in soup.find_all("div"):
            if not d.find_all(["div", "p"]):
                txt = d.get_text().strip()
                if len(txt) > 25 and txt not in paragraphs:
                    paragraphs.append(txt)

    full_content = "\n\n".join(paragraphs)
    if not full_content or len(full_content) < 80:
        return None

    return {
        "url": url,
        "title": title,
        "published_date": pub_date,
        "content": full_content
    }

async def run_scrape_process(
    db: Session,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    selected_province: Optional[str] = None,
    max_articles: int = 50
) -> Dict[str, Any]:
    """
    Tiến trình quét tin tức chính:
    1. Lấy danh sách các trang báo đang theo dõi từ CSDL
    2. Cào chuẩn các URL chi tiết bài báo theo giới hạn max_articles
    3. Lọc theo Khoảng thời gian [date_from, date_to] & Tỉnh thành lựa chọn
    4. Lọc 2-Step Regex (Tỉnh thành & Động từ hành vi rủi ro bắt buộc)
    5. Trả về danh sách để Gemini 3.5 Flash Lite thẩm định & trích xuất
    """
    logger.info(f"Bắt đầu tiến trình cào tin tức (Giới hạn: {max_articles} bài/báo, Khu vực: {selected_province or 'Tất cả'}, Từ ngày: {date_from}, Đến ngày: {date_to})...")
    dbsh_list = ["Quảng Ninh", "Hải Phòng", "Hưng Yên", "Ninh Bình", "Bắc Ninh", "Phú Thọ"]
    crawled_articles = []
    pre_filtered_candidates = []
    seen_hashes = set()


    from app.models import MonitoredSite
    query_sites = db.query(MonitoredSite).filter(MonitoredSite.is_active == True)
    if selected_province and selected_province != "Tất cả":
        if selected_province in ["6 tỉnh ĐBSH", "ĐBSH", "Vùng trọng điểm"]:
            query_sites = query_sites.filter(
                (MonitoredSite.province_hint.in_(dbsh_list)) | (MonitoredSite.province_hint == "Toàn quốc")
            )
        else:
            query_sites = query_sites.filter(
                (MonitoredSite.province_hint == selected_province) | (MonitoredSite.province_hint == "Toàn quốc")
            )
    db_sites = query_sites.all()
    
    target_sites_list = []
    if db_sites:
        for s in db_sites:
            target_sites_list.append({"name": s.name, "url": s.url, "province_hint": s.province_hint})
    else:
        target_sites_list = TARGET_SITES
    
    async with httpx.AsyncClient(verify=False) as client:
        for site in target_sites_list:
            site_url = site["url"]
            site_name = site["name"]
            hint_prov = site.get("province_hint")
            
            logger.info(f"Đang cào danh mục: {site_name} ({site_url})")
            cat_html = await fetch_html(client, site_url)
            if not cat_html:
                continue
                
            limit_links = max_articles if max_articles else 50
            article_urls = parse_article_links(site_url, cat_html)[:limit_links]

            for raw_art_url in article_urls:
                art_url = urldefrag(raw_art_url)[0]
                url_hash = generate_url_hash(art_url)

                
                if url_hash in seen_hashes:
                    continue
                seen_hashes.add(url_hash)
                
                existing = db.query(Article).filter(Article.url_hash == url_hash).first()
                if existing:
                    continue
                    
                art_html = await fetch_html(client, art_url)
                if not art_html:
                    continue
                    
                art_data = parse_article_detail(art_url, art_html)
                if not art_data:
                    continue

                if art_data["published_date"] and not is_date_in_range(art_data["published_date"], date_from, date_to):
                    continue
                    
                is_passed, matched_provs, matched_kws = pre_filter_article(
                    art_data["title"], 
                    art_data["content"], 
                    default_province_hint=hint_prov
                )

                if selected_province and selected_province != "Tất cả":
                    if selected_province in ["6 tỉnh ĐBSH", "ĐBSH", "Vùng trọng điểm"]:
                        if not any(p in dbsh_list for p in matched_provs) and "Toàn quốc" not in matched_provs:
                            continue
                    else:
                        if selected_province not in matched_provs and "Toàn quốc" not in matched_provs:
                            continue


                article_obj = Article(

                    url=art_url,
                    url_hash=url_hash,
                    title=art_data["title"],
                    source_site=site_name,
                    raw_content=art_data["content"],
                    published_date=art_data["published_date"]
                )

                try:
                    db.add(article_obj)
                    db.commit()
                    db.refresh(article_obj)
                    crawled_articles.append(article_obj)

                    pre_filtered_candidates.append({
                        "article_id": article_obj.id,
                        "title": art_data["title"],
                        "url": art_url,
                        "content": art_data["content"],
                        "pub_date": art_data["published_date"],
                        "matched_provs": matched_provs,
                        "matched_kws": matched_kws
                    })
                except Exception as db_err:
                    db.rollback()
                    logger.warning(f"Bỏ qua URL trùng lặp database: {art_url} ({db_err})")
                    continue

    logger.info(f"Cào hoàn tất: Bài mới: {len(crawled_articles)}, Bài thỏa mãn lọc rủi ro: {len(pre_filtered_candidates)}")
    return {
        "total_crawled": len(crawled_articles),
        "candidates": pre_filtered_candidates
    }
