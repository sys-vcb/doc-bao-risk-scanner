import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.config import settings, TARGET_PROVINCES, get_vietnam_today_str
from app.scraper.regex_filter import ACTION_RISK_VERBS

logger = logging.getLogger("GeminiExtractor")

INVALID_ENTITIES = [
    "báo ninh bình", "báo bắc ninh", "báo hải phòng", "báo hưng yên", 
    "báo quảng ninh", "báo phú thọ", "vnexpress", "báo pháp luật",
    "công ty trách nhiệm hữu hạn thương mại", "cá nhân / doanh nghiệp liên quan",
    "một công ty", "doanh nghiệp", "tổ chức", "thanh thiếu niên", "đối tượng"
]

def clean_extracted_province(ai_province: str, candidate_provs: List[str]) -> str:
    """Trích xuất và làm sạch tên Tỉnh/Thành phố cụ thể (VD: Hà Nội, TP. Hồ Chí Minh, Quảng Ninh...)"""
    dbsh_list = ["Quảng Ninh", "Hải Phòng", "Hưng Yên", "Ninh Bình", "Bắc Ninh", "Phú Thọ"]
    prov_raw = (ai_province or "").strip()
    
    cleaned = re.sub(r'^(Tỉnh|Thành phố|TP\.?)\s+', '', prov_raw, flags=re.IGNORECASE).strip()
    
    if not cleaned or cleaned.lower() in ["toàn quốc", "chưa xác định", "không có", "n/a"]:
        if candidate_provs and candidate_provs[0] != "Toàn quốc":
            return candidate_provs[0]
        return "Toàn quốc"

    # Nếu AI trích xuất Hà Nội (do C03 Bộ Công an xử lý) nhưng bài viết từ báo địa phương / có nhãn tỉnh ĐBSH
    if cleaned not in dbsh_list and candidate_provs:
        for cp in candidate_provs:
            if cp in dbsh_list:
                return cp

    return cleaned or "Toàn quốc"

def determine_entity_type(entity_name: str, ai_type: Optional[str] = None) -> str:
    """Tự động phân loại Doanh nghiệp / Tổ chức vs Cá nhân"""
    if ai_type and "doanh nghiệp" in ai_type.lower():
        return "Doanh nghiệp"
    if ai_type and "cá nhân" in ai_type.lower():
        return "Cá nhân"
        
    if not entity_name:
        return "Chưa xác định"
        
    lower_name = entity_name.lower()
    corp_keywords = [
        "công ty", "tnhh", "tập đoàn", "ngân hàng", "phòng khám", "doanh nghiệp", 
        "jsc", "ltd", "cp", "chi nhánh", "cơ sở", "nhà máy", "xí nghiệp", "ubnd", 
        "bệnh viện", "trường", "trung tâm", "quỹ", "hợp tác xã", "htx"
    ]
    if any(kw in lower_name for kw in corp_keywords):
        return "Doanh nghiệp"
    return "Cá nhân"

SYSTEM_PROMPT = """Bạn là Chuyên gia Đánh giá Rủi ro Doanh nghiệp & Phân tích Tin tức Báo chí tại Việt Nam.
Nhiệm vụ của bạn là đọc toàn bộ bài báo được cung cấp, thẩm định tính hợp lệ của tin tức rủi ro và trích xuất dữ liệu cấu trúc JSON.

Yêu cầu định dạng JSON đầu ra (CHỈ TRẢ VỀ JSON HỢP LỆ, KHÔNG KÈM LỜI DẪN HAY CODEBLOCK):
{
  "has_valid_risk": true,
  "entity_name": "Tên riêng cụ thể của Cá nhân, Doanh nghiệp, Công ty, Tổ chức chính bị xử lý/khởi tố/xử phạt/nợ thuế trong bài. NẾU KHÔNG CÓ TÊN RIÊNG CỤ THỂ, ĐỂ TRỐNG TRƯỜNG NÀY (\\"\\").",
  "entity_type": "Điền 'Doanh nghiệp' nếu đối tượng bị xử lý là Công ty, Doanh nghiệp, Tập đoàn, Ngân hàng, Phòng khám, Tổ chức; HOẶC điền 'Cá nhân' nếu là người riêng lẻ.",
  "summary": "Tóm tắt 2 đến 3 câu ngắn gọn làm rõ hành vi sai phạm, mức phạt hoặc hậu quả pháp lý/tài chính/môi trường",
  "province": "Tên Tỉnh/Thành phố trực thuộc Trung ương CỤ THỂ xảy ra vụ việc/sai phạm trong bài (VD: Hà Nội, TP. Hồ Chí Minh, Quảng Ninh, Hải Phòng, Hưng Yên, Ninh Bình, Bắc Ninh, Phú Thọ, Lào Cai, Vĩnh Phúc, Lâm Đồng, Vĩnh Long...). KHÔNG GHI CHUNG CHUNG 'Toàn quốc', hãy đọc bài để ghi tên Tỉnh/Thành phố chính xác nhất.",
  "risk_type": "Phân loại ngắn gọn (VD: Khởi tố/Bắt tạm giam, Nợ thuế/BHXH, Vi phạm môi trường, Xử phạt hành chính,...)",
  "verified_date": "Ngày xuất bản chính xác của bài báo dạng YYYY-MM-DD. NẾU pub_date ĐƯỢC TRUYỀN VÀO LÀ RỖNG (\\"\\"), HÃY ĐỌC NỘI DUNG VĂN BẢN ĐỂ XÁC ĐỊNH NGÀY XẢY RA/ĐĂNG BÀI (YYYY-MM-DD), TUYỆT ĐỐI KHÔNG TỰ Ý GÁN NGÀY HÔM NAY."
}

Quy tắc thẩm định tin rủi ro của Gemini:
1. ĐẶT "has_valid_risk": false NẾU:
   - Bài viết KHÔNG mô tả sự việc/hành vi rủi ro thực tế nào (chỉ là dự báo thời tiết, văn nghệ, du lịch, thể thao, tuyên truyền, dự thảo luật, hội thảo, kỷ niệm, việc làm, tuyển dụng).
2. "entity_name": Chỉ điền tên riêng thực sự của Doanh nghiệp, Công ty, Tổ chức hoặc Cá nhân. Tuyệt đối KHÔNG trả về tên tòa báo hay từ chung chung như 'Doanh nghiệp', 'Cá nhân'.
"""

BATCH_SYSTEM_PROMPT = """Bạn là Chuyên gia Đánh giá Rủi ro Doanh nghiệp & Phân tích Tin tức Báo chí tại Việt Nam.
Nhiệm vụ của bạn là đọc DANH SÁCH CÁC BÀI BÁO được cung cấp, thẩm định tính hợp lệ của tin tức rủi ro cho TỪNG BÀI BÁO và trích xuất danh sách kết quả dạng JSON ARRAY.

Yêu cầu định dạng JSON đầu ra (CHỈ TRẢ VỀ MỘT MẢNG JSON HỢP LỆ, KHÔNG KÈM LỜI DẪN HAY CODEBLOCK):
[
  {
    "article_index": 1,
    "source_url": "COPY CHÍNH XÁC URL BÀI GỐC ĐƯỢC TRUYỀN VÀO CHO BÀI BÁO NÀY (VD: https://baohaiphong.vn/...)",
    "has_valid_risk": true,
    "entity_name": "Tên riêng cụ thể của Cá nhân, Doanh nghiệp, Công ty, Tổ chức chính bị xử lý/khởi tố/xử phạt/nợ thuế trong bài. NẾU KHÔNG CÓ TÊN RIÊNG CỤ THỂ, ĐỂ TRỐNG (\\"\\").",
    "entity_type": "Điền 'Doanh nghiệp' nếu đối tượng bị xử lý là Công ty, Doanh nghiệp, Tập đoàn, Ngân hàng, Phòng khám, Tổ chức; HOẶC điền 'Cá nhân' nếu là người riêng lẻ.",
    "summary": "Tóm tắt 2 đến 3 câu ngắn gọn làm rõ hành vi sai phạm, mức phạt hoặc hậu quả pháp lý/tài chính/môi trường",
    "province": "Tên Tỉnh/Thành phố trực thuộc Trung ương CỤ THỂ xảy ra vụ việc/sai phạm trong bài (VD: Hà Nội, TP. Hồ Chí Minh, Quảng Ninh, Hải Phòng, Hưng Yên, Ninh Bình, Bắc Ninh, Phú Thọ, Lào Cai, Vĩnh Phúc, Lâm Đồng, Vĩnh Long...). KHÔNG GHI CHUNG CHUNG 'Toàn quốc', hãy đọc bài để ghi tên Tỉnh/Thành phố chính xác nhất.",
    "risk_type": "Phân loại ngắn gọn (VD: Khởi tố/Bắt tạm giam, Nợ thuế/BHXH, Vi phạm môi trường, Xử phạt hành chính,...)",
    "verified_date": "Ngày xuất bản chính xác của bài báo dạng YYYY-MM-DD. NẾU pub_date ĐƯỢC TRUYỀN VÀO LÀ RỖNG (\\"\\"), HÃY ĐỌC NỘI DUNG VĂN BẢN ĐỂ XÁC ĐỊNH NGÀY XẢY RA/ĐĂNG BÀI (YYYY-MM-DD), TUYỆT ĐỐI KHÔNG TỰ Ý GÁN NGÀY HÔM NAY."
  }
]

Quy tắc thẩm định tin rủi ro của Gemini:
1. ĐẶT "has_valid_risk": false NẾU:
   - Bài viết KHÔNG mô tả sự việc/hành vi rủi ro thực tế nào (chỉ là dự báo thời tiết, văn nghệ, du lịch, thể thao, tuyên truyền, dự thảo luật, hội thảo, kỷ niệm, việc làm, tuyển dụng).
2. "entity_name": Chỉ điền tên riêng thực sự của Doanh nghiệp, Công ty, Tổ chức hoặc Cá nhân. Tuyệt đối KHÔNG trả về tên tòa báo hay từ chung chung như 'Doanh nghiệp', 'Cá nhân'.
"""





def extract_risk_with_gemini(title: str, content: str, url: str, pub_date: str, matched_provs: List[str], matched_kws: List[str]) -> Optional[Dict[str, Any]]:
    """
    Trích xuất bài báo đơn lẻ bằng Gemini 3.5 Flash Lite
    """
    today_str = get_vietnam_today_str()
    pub_date_to_use = pub_date or ""

    if not settings.GEMINI_API_KEY or len(settings.GEMINI_API_KEY.strip()) < 10:
        logger.warning("Không tìm thấy GEMINI_API_KEY hợp lệ trong .env. Đang dùng chế độ Fallback Regex trích xuất.")
        return fallback_rule_based_extract(title, content, url, pub_date_to_use or today_str, matched_provs, matched_kws)

    try:
        raw_text = ""
        user_prompt = f"Bài báo tiêu đề: {title}\nURL bài gốc: {url}\nNgày đăng gợi ý: {pub_date_to_use}\n\nNội dung bài báo:\n{content[:3800]}"

        import time
        from google import genai
        client = genai.Client(api_key=settings.GEMINI_API_KEY.strip())
        
        time.sleep(2.0)
        
        max_retries = 3
        target_model = "gemini-3.5-flash-lite"
        
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=target_model,
                    contents=user_prompt,
                    config={'system_instruction': SYSTEM_PROMPT}
                )
                raw_text = response.text
                break
            except Exception as req_err:
                err_str = str(req_err)
                if ("404" in err_str or "NOT_FOUND" in err_str) and target_model != "gemini-2.5-flash-lite":
                    target_model = "gemini-2.5-flash-lite"
                    logger.info(f"Đang thử lại với mô hình dự phòng: {target_model}")
                    continue
                elif "429" in err_str and attempt < max_retries - 1:
                    wait_sec = 4 * (attempt + 1)
                    logger.warning(f"Gặp lỗi 429 Quota/Rate-limit. Đang chờ {wait_sec} giây để thử lại (Lần {attempt + 1}/{max_retries})...")
                    time.sleep(wait_sec)
                else:
                    raise req_err

        clean_json = re.sub(r"```json\s*", "", raw_text)
        clean_json = re.sub(r"```\s*$", "", clean_json).strip()
        
        data = json.loads(clean_json)
        
        if not data.get("has_valid_risk", True):
            logger.info(f"Gemini AI đánh giá bài viết không có rủi ro thực tế: {title}")
            return None
            
        province = data.get("province", "").strip()
        matched_p = clean_extracted_province(province, matched_provs)
        
        entity_name = clean_entity_name(data.get("entity_name", "")) or ""
        entity_type = determine_entity_type(entity_name, data.get("entity_type"))
        verified_date = data.get("verified_date", "").strip() or pub_date_to_use or today_str

        m_date = re.search(r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})', verified_date)
        if m_date:
            y, m, d = map(int, m_date.groups())
            verified_date = f"{y:04d}-{m:02d}-{d:02d}"

        logger.info(f"✅ Gemini 3.5 Flash Lite trích xuất thành công cho bài: {title}")
        return {
            "entity_name": entity_name,
            "entity_type": entity_type,
            "summary": data.get("summary", title),
            "province": matched_p,
            "risk_type": data.get("risk_type", ", ".join(matched_kws[:3]) if matched_kws else "Rủi ro pháp lý/xử phạt"),
            "published_date": verified_date,
            "source_url": url
        }
        
    except Exception as e:
        logger.warning(f"Lỗi gọi Gemini API: {e}. Tự động chuyển sang chế độ Fallback Regex trích xuất...")
        return fallback_rule_based_extract(title, content, url, pub_date_to_use or today_str, matched_provs, matched_kws)


def batch_extract_risk_with_gemini(candidates: List[Dict[str, Any]], batch_size: int = 5) -> List[Dict[str, Any]]:
    """
    Gom nhiều bài viết (batch_size=5 bài) vào 1 Request duy nhất để tận dụng TPM 250K/phút, giảm 80% RPM!
    """
    if not candidates:
        return []

    results = []
    today_str = get_vietnam_today_str()

    if not settings.GEMINI_API_KEY or len(settings.GEMINI_API_KEY.strip()) < 10:
        logger.warning("Không tìm thấy GEMINI_API_KEY hợp lệ. Chuyển sang Fallback từng bài...")
        for cand in candidates:
            res = fallback_rule_based_extract(
                cand["title"], cand["content"], cand["url"], 
                cand["pub_date"] or today_str, cand["matched_provs"], cand["matched_kws"]
            )
            if res:
                res["article_id"] = cand["article_id"]
                results.append(res)
        return results

    for i in range(0, len(candidates), batch_size):
        batch = candidates[i:i + batch_size]
        logger.info(f"📦 Đang xử lý Batch Gemini AI gồm {len(batch)} bài viết ({i+1}-{i+len(batch)}/{len(candidates)})...")
        
        prompt_parts = []
        for idx, item in enumerate(batch, start=1):
            prompt_parts.append(
                f"--- BÀI BÁO #{idx} ---\n"
                f"Tiêu đề: {item['title']}\n"
                f"URL bài gốc: {item['url']}\n"
                f"Ngày đăng gợi ý: {item['pub_date'] or ''}\n"
                f"Nội dung:\n{item['content'][:3000]}\n"
            )

        user_prompt = "\n\n".join(prompt_parts)

        import time
        from google import genai
        client = genai.Client(api_key=settings.GEMINI_API_KEY.strip())

        time.sleep(2.0)

        max_retries = 3
        target_model = "gemini-3.5-flash-lite"
        raw_text = ""

        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=target_model,
                    contents=user_prompt,
                    config={'system_instruction': BATCH_SYSTEM_PROMPT}
                )
                raw_text = response.text
                break
            except Exception as req_err:
                err_str = str(req_err)
                if ("404" in err_str or "NOT_FOUND" in err_str) and target_model != "gemini-2.5-flash-lite":
                    target_model = "gemini-2.5-flash-lite"
                    logger.info(f"Batch AI retry với mô hình dự phòng: {target_model}")
                    continue
                elif "429" in err_str and attempt < max_retries - 1:
                    wait_sec = 4 * (attempt + 1)
                    logger.warning(f"Batch AI gặp lỗi 429 Quota. Đang chờ {wait_sec}s thử lại...")
                    time.sleep(wait_sec)
                else:
                    logger.error(f"Lỗi Batch Gemini API ({req_err}). Chuyển sang Fallback Regex cho batch này...")
                    raw_text = ""
                    break

        if raw_text:
            try:
                clean_json = re.sub(r"```json\s*", "", raw_text)
                clean_json = re.sub(r"```\s*$", "", clean_json).strip()
                data_list = json.loads(clean_json)

                if isinstance(data_list, list):
                    for data in data_list:
                        target_url = (data.get("source_url") or "").strip()
                        cand = None
                        
                        # 1. Tìm theo URL khớp chính xác
                        if target_url:
                            cand = next((c for c in batch if c["url"] == target_url), None)
                            if not cand:
                                # 2. Tìm theo URL chứa / được chứa
                                cand = next((c for c in batch if target_url in c["url"] or c["url"] in target_url), None)
                        
                        # 3. Tìm theo article_index NẾU ĐƯỢC CHỈ ĐỊNH CỤ THỂ HỢP LỆ TRONG JSON
                        if not cand and "article_index" in data:
                            try:
                                idx_val = int(data["article_index"]) - 1
                                if 0 <= idx_val < len(batch):
                                    cand = batch[idx_val]
                            except Exception:
                                pass
                                
                        # 4. Nếu vẫn không tìm thấy, bỏ qua mục này thay vì gán nhầm vào batch[0]
                        if not cand:
                            logger.warning(f"Bỏ qua kết quả trích xuất do không tìm thấy bài gốc tương ứng: {target_url}")
                            continue

                        if cand and data.get("has_valid_risk", True):

                                matched_p = clean_extracted_province(data.get("province", ""), cand["matched_provs"])

                                verified_date = data.get("verified_date", "").strip() or cand["pub_date"] or today_str
                                
                                m_date = re.search(r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})', verified_date)
                                if m_date:
                                    y, m, d = map(int, m_date.groups())
                                    verified_date = f"{y:04d}-{m:02d}-{d:02d}"

                                ent_name = clean_entity_name(data.get("entity_name", "")) or ""
                                ent_type = determine_entity_type(ent_name, data.get("entity_type"))

                                results.append({
                                    "article_id": cand["article_id"],
                                    "entity_name": ent_name,
                                    "entity_type": ent_type,
                                    "summary": data.get("summary", cand["title"]),
                                    "province": matched_p,
                                    "risk_type": data.get("risk_type", ", ".join(cand["matched_kws"][:3]) if cand["matched_kws"] else "Rủi ro pháp lý/xử phạt"),
                                    "published_date": verified_date,
                                    "source_url": cand["url"]
                                })

                    logger.info(f"✅ Batch Gemini AI trích xuất thành công {len(results)} rủi ro cho {len(batch)} bài báo.")
                    continue
            except Exception as parse_err:
                logger.error(f"Lỗi parse JSON Batch Gemini ({parse_err}). Chuyển sang Fallback từng bài...")

        # Fallback từng bài trong batch nếu Gemini lỗi
        for cand in batch:
            res = fallback_rule_based_extract(
                cand["title"], cand["content"], cand["url"], 
                cand["pub_date"] or today_str, cand["matched_provs"], cand["matched_kws"]
            )
            if res:
                res["article_id"] = cand["article_id"]
                results.append(res)

    return results


def clean_entity_name(raw_name: str) -> str:
    """Làm sạch và kiểm tra tính hợp lệ của Tên Doanh nghiệp / Cá nhân"""
    if not raw_name:
        return ""

    name = re.sub(r'^(Bắc Ninh|Hải Phòng|Quảng Ninh|Hưng Yên|Ninh Bình|Phú Thọ)[\s:]+', '', raw_name, flags=re.IGNORECASE).strip()
    name_lower = name.lower()

    if any(inv in name_lower for inv in INVALID_ENTITIES) or len(name) < 3:
        return ""

    return name


def fallback_rule_based_extract(title: str, content: str, url: str, pub_date: str, matched_provs: List[str], matched_kws: List[str]) -> Optional[Dict[str, Any]]:
    """Fallback trích xuất dữ liệu rủi ro"""
    full_text = f"{title}\n{content}".lower()

    has_risk_verb = any(re.search(r'\b' + re.escape(v) + r'\b', full_text) for v in ACTION_RISK_VERBS)
    if not has_risk_verb:
        return None

    extracted_entities = []
    text_raw = f"{title}\n{content}"

    comp_pat = r'\b(?:Công ty|Doanh nghiệp|Tập đoàn|Ngân hàng|Hợp tác xã|Phòng khám)\s+[^,;\.\n\)]+'
    raw_comps = re.findall(comp_pat, text_raw)
    for c in raw_comps:
        cleaned_c = re.split(r'\b(?:cùng|và|đã|vừa|bị|do|có|về|ký|thuê|ở|tại)\b', c)[0].strip(' "\'()')
        valid = clean_entity_name(cleaned_c)
        if len(cleaned_c) > 6 and valid:
            extracted_entities.append(valid)

    person_pat = r'\b(ông|Ông|bà|Bà|bị can|Bị can|bị cáo|Bị cáo|đối tượng|Đối tượng)\s+([A-ZĐÀÁẢẠÃĂẮẰẲẴẶÂẤẦẨẪẬÊẾỀỂỄỆÔỐỒỔỖỘƠỚỜỞỠỢƯỨỪỬỮỰÍÌỈỊĨÝỲỶỊỸ][a-zàáảạãăắcằẳẵặcâấầuẩẫậnêếềểễệôốồổỗộơớờởỡợưứừửữựíìỉịĩýỳỷịỹA-ZĐÀÁẢẠÃĂẮẰẲẴẶÂẤẦẨẪẬÊẾỀỂỄỆÔỐỒỔỖỘƠỚỜỞỠỢƯỨỪỬỮỰÍÌỈỊĨÝỲỶỊỸ]*+(?:\s+[A-ZĐÀÁẢẠÃĂẮẰẲẴẶÂẤẦẨẪẬÊẾỀỂỄỆÔỐỒỔỖỘƠỚỜỞỠỢƯỨỪỬỮỰÍÌỈỊĨÝỲỶỊỸ][a-zàáảạãăắcằẳẵặcâấầuẩẫậnêếềểễệôốồổỗộơớờởỡợưứừửữựíìỉịĩýỳỷịỹA-ZĐÀÁẢẠÃĂẮẰẲẴẶÂẤẦẨẪẬÊẾỀỂỄỆÔỐỒỔỖỘƠỚỜỞỠỢƯỨỪỬỮỰÍÌỈỊĨÝỲỶỊỸ]*+){1,4})'
    person_matches = re.finditer(person_pat, text_raw)
    for pm in person_matches:
        prefix = pm.group(1).capitalize()
        name_part = pm.group(2).strip()
        full_person_str = f"{prefix} {name_part}"
        if name_part not in ["Việt Nam", "Hải Phòng", "Quảng Ninh", "Hưng Yên", "Ninh Bình", "Bắc Ninh", "Phú Thọ"]:
            valid_p = clean_entity_name(full_person_str)
            if valid_p:
                extracted_entities.append(valid_p)

    unique_entities = []
    seen_lower = set()
    for e in extracted_entities:
        e_lower = e.lower()
        if e_lower not in seen_lower:
            if not any(e_lower != s and e_lower in s for s in seen_lower):
                unique_entities.append(e)
                seen_lower.add(e_lower)

    entity_result = "; ".join(unique_entities[:5]) if unique_entities else ""

    paragraphs = [p.strip() for p in content.split("\n\n") if len(p.strip()) > 30]
    relevant_paras = []
    for p in paragraphs:
        if any(kw in p.lower() for kw in matched_kws):
            relevant_paras.append(p)
            if len(relevant_paras) >= 2:
                break
                
    if not relevant_paras:
        relevant_paras = paragraphs[:2]

    summary = ". ".join(relevant_paras) if relevant_paras else title
    if len(summary) > 350:
        summary = summary[:347] + "..."
        
    prov = matched_provs[0] if matched_provs else "Chưa xác định"
    risk_type = ", ".join(matched_kws[:3]) if matched_kws else "Rủi ro pháp lý/xử phạt"
    entity_type = determine_entity_type(entity_result)
    
    return {
        "entity_name": entity_result,
        "entity_type": entity_type,
        "summary": summary,
        "province": prov,
        "risk_type": risk_type,
        "published_date": pub_date,
        "source_url": url
    }

