import os
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from app.config import settings, BASE_DIR, REPORTS_DIR, TARGET_PROVINCES, get_vietnam_today_str, get_vietnam_now
from app.database import engine, Base, get_db, init_db
from app.models import Article, RiskItem, EmailSubscriber, ScanLog, MonitoredSite

from app.services.scheduler import start_scheduler, execute_full_scan_pipeline
from app.services.docx_exporter import generate_daily_docx_report
from app.services.excel_exporter import generate_excel_report

app = FastAPI(
    title=settings.APP_NAME,
    description="Hệ thống tự động quét tin tức rủi ro doanh nghiệp, xuất báo cáo Excel/Word và gửi Email cảnh báo",
    version="2.0.0"
)

import traceback
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    err_tb = traceback.format_exc()
    return JSONResponse(
        status_code=500,
        content={
            "status": "ERROR",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "traceback": err_tb
        }
@app.middleware("http")
async def add_no_cache_header(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response



# Mount Static Files & Templates an toàn cho Serverless
static_dir = BASE_DIR / "app" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

templates_dir = BASE_DIR / "app" / "templates"
if templates_dir.exists():
    templates = Jinja2Templates(directory=str(templates_dir))


# Startup Event
@app.on_event("startup")
def startup_event():
    start_scheduler()
    init_db()


def seed_demo_data_if_empty():
    """Tạo một vài bản ghi dữ liệu mẫu nếu CSDL chưa có tin rủi ro nào để UI hiển thị đẹp mắt ngay khi khởi chạy"""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        count = db.query(RiskItem).count()
        if count == 0:
            today_str = datetime.now().strftime("%Y-%m-%d")
            demo_items = [
                RiskItem(
                    entity_name="Công ty TNHH Đầu tư & Thương mại X (Hải Phòng)",
                    summary="Cơ quan thuế phát hiện doanh nghiệp có hành vi cưỡng chế hóa đơn và trốn đóng BHXH cho hơn 100 người lao động trong 6 tháng liên tiếp.",
                    province="Hải Phòng",
                    risk_type="Thuế / Trốn đóng BHXH",
                    published_date=today_str,
                    source_url="https://baohaiphong.vn/phap-luat/tin-tuc",
                    is_ai_extracted=True
                ),
                RiskItem(
                    entity_name="Ông Nguyễn Văn B - Giám đốc Công ty Y (Quảng Ninh)",
                    summary="Công an tỉnh Quảng Ninh vừa khởi tố bị can, bắt tạm giam đối tượng về hành vi lừa đảo chiếm đoạt tài sản qua dự án bất động sản ma.",
                    province="Quảng Ninh",
                    risk_type="Khởi tố / Bắt tạm giam / Lừa đảo",
                    published_date=today_str,
                    source_url="https://baoquangninh.vn/phap-luat",
                    is_ai_extracted=True
                ),
                RiskItem(
                    entity_name="Công ty Cổ phần Chế biến Thực phẩm Z (Hưng Yên)",
                    summary="Cơ quan chuyên môn ra quyết định xử phạt hành chính 150 triệu đồng và đình chỉ hoạt động 3 tháng do vi phạm quy định xả thải chui gây ô nhiễm môi trường.",
                    province="Hưng Yên",
                    risk_type="Đình chỉ hoạt động / Ô nhiễm môi trường",
                    published_date=today_str,
                    source_url="https://baohungyen.vn/phap-luat-doi-song",
                    is_ai_extracted=True
                )
            ]
            db.add_all(demo_items)
            db.commit()
            
            # Seed email subscriber mẫu
            if db.query(EmailSubscriber).count() == 0:
                sub = EmailSubscriber(
                    name="Quản trị viên Hệ thống",
                    email="admin@example.com",
                    target_province="Tất cả"
                )
                db.add(sub)
                db.commit()
    finally:
        db.close()

def serializable_risk_item(i: RiskItem) -> dict:
    c_at = None
    if i.created_at:
        if isinstance(i.created_at, str):
            c_at = i.created_at
        elif hasattr(i.created_at, "strftime"):
            c_at = i.created_at.strftime("%Y-%m-%d %H:%M:%S")
        else:
            c_at = str(i.created_at)

    return {
        "id": i.id,
        "article_id": i.article_id,
        "entity_name": i.entity_name or "",
        "entity_type": i.entity_type or "Doanh nghiệp",
        "summary": i.summary or "",
        "province": i.province or "Toàn quốc",
        "risk_type": i.risk_type or "",
        "published_date": i.published_date or "",
        "source_url": i.source_url or "",
        "is_ai_extracted": bool(i.is_ai_extracted),
        "created_at": c_at
    }

def serializable_scan_log(l: ScanLog) -> dict:
    s_time = None
    if l.scan_time:
        if isinstance(l.scan_time, str):
            s_time = l.scan_time
        elif hasattr(l.scan_time, "strftime"):
            s_time = l.scan_time.strftime("%Y-%m-%d %H:%M:%S")
        else:
            s_time = str(l.scan_time)

    return {
        "id": l.id,
        "scan_time": s_time,
        "articles_crawled": l.articles_crawled,
        "regex_passed": l.regex_passed,
        "risks_extracted": l.risks_extracted,
        "status": l.status or "SUCCESS",
        "message": l.message or ""
    }

def serializable_site(s: MonitoredSite) -> dict:
    c_at = None
    if s.created_at:
        if isinstance(s.created_at, str):
            c_at = s.created_at
        elif hasattr(s.created_at, "strftime"):
            c_at = s.created_at.strftime("%Y-%m-%d %H:%M:%S")
        else:
            c_at = str(s.created_at)

    return {
        "id": s.id,
        "name": s.name,
        "url": s.url,
        "province_hint": s.province_hint or "Toàn quốc",
        "is_active": bool(s.is_active),
        "created_at": c_at
    }


# Web Dashboard Page
@app.get("/", response_class=HTMLResponse)
def render_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


# API: Lấy danh sách tin rủi ro (hỗ trợ lọc Ngày từ - đến, Tỉnh, Loại đối tượng và Kỳ tin hôm nay)
@app.get("/api/news")

def get_risk_news(
    province: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None), # "Tất cả", "Doanh nghiệp", "Cá nhân"
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    period: Optional[str] = Query(None), # "today" hoặc "earlier"
    search: Optional[str] = Query(""),
    db: Session = Depends(get_db)
):
    try:
        query = db.query(RiskItem)
        today_str = get_vietnam_today_str()
        
        if period == "today":
            query = query.filter(RiskItem.published_date >= today_str)
        elif period in ["earlier", "past"]:
            query = query.filter(RiskItem.published_date < today_str)

        if province and province != "Tất cả":
            if province in ["6 tỉnh ĐBSH", "ĐBSH", "Vùng trọng điểm"]:
                dbsh_list = ["Quảng Ninh", "Hải Phòng", "Hưng Yên", "Ninh Bình", "Bắc Ninh", "Phú Thọ"]
                query = query.filter(RiskItem.province.in_(dbsh_list))
            else:
                query = query.filter(RiskItem.province == province)

        if entity_type and entity_type != "Tất cả":
            query = query.filter(RiskItem.entity_type == entity_type)
            
        if date_from:
            query = query.filter(RiskItem.published_date >= date_from)
            
        if date_to:
            query = query.filter(RiskItem.published_date <= date_to)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                (RiskItem.entity_name.like(search_pattern)) | 
                (RiskItem.summary.like(search_pattern)) | 
                (RiskItem.risk_type.like(search_pattern))
            )
            
        items = query.order_by(RiskItem.id.desc()).all()
        item_dicts = [serializable_risk_item(i) for i in items]
        return {"total": len(item_dicts), "items": item_dicts}
    except Exception as exc:
        err_tb = traceback.format_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "ERROR", "error": str(exc), "traceback": err_tb}
        )



# API: Health Check trạng thái CSDL Supabase
@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    import os
    from app.database import sanitize_db_url
    raw_env = os.getenv("DATABASE_URL", "")
    sanitized = sanitize_db_url(raw_env)
    
    masked_raw = raw_env
    if "@" in raw_env:
        last_at = raw_env.rfind("@")
        masked_raw = "***@" + raw_env[last_at+1:]

    masked_sanitized = sanitized
    if "@" in sanitized:
        last_at = sanitized.rfind("@")
        masked_sanitized = "***@" + sanitized[last_at+1:]

    is_supabase = "supabase" in raw_env or "postgres" in raw_env
    
    risk_count = 0
    article_count = 0
    try:
        risk_count = db.query(RiskItem).count()
        article_count = db.query(Article).count()
    except Exception as e:
        print(f"Error counting in health: {e}")

    return {
        "status": "OK",
        "using_supabase": is_supabase,
        "database_type": "PostgreSQL (Supabase)" if is_supabase else "SQLite (Fallback)",
        "has_gemini_key": bool(os.getenv("GEMINI_API_KEY") or settings.GEMINI_API_KEY),
        "masked_raw_env": masked_raw,
        "masked_sanitized_db_url": masked_sanitized,
        "risk_items_in_db": risk_count,
        "articles_in_db": article_count
    }





@app.get("/api/debug-db")
def debug_db(db: Session = Depends(get_db)):
    try:
        from app.database import db_url
        c_risks = db.query(RiskItem).count()
        c_articles = db.query(Article).count()
        c_sites = db.query(MonitoredSite).count()
        sample_risks = [i.entity_name for i in db.query(RiskItem).limit(5).all()]
        return {
            "status": "OK",
            "db_url_prefix": db_url[:35] if db_url else "",
            "risk_items_count": c_risks,
            "articles_count": c_articles,
            "sites_count": c_sites,
            "sample_risks": sample_risks
        }
    except Exception as e:
        import traceback
        return {
            "status": "ERROR",
            "error": str(e),
            "traceback": traceback.format_exc()
        }


# Pydantic Schemas cho Quản lý Trang báo

class SiteCreateSchema(BaseModel):
    name: str
    url: str
    province_hint: Optional[str] = "Toàn quốc"

# API: Lấy danh sách Trang báo đang giám sát từ CSDL
@app.get("/api/sites")
def get_monitored_sites(db: Session = Depends(get_db)):
    sites = db.query(MonitoredSite).filter(MonitoredSite.is_active == True).all()
    return [serializable_site(s) for s in sites]

# API: Thêm Trang báo giám sát mới
@app.post("/api/sites")
def add_monitored_site(site_data: SiteCreateSchema, db: Session = Depends(get_db)):
    existing = db.query(MonitoredSite).filter(MonitoredSite.url == site_data.url.strip()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Trang báo này đã có trong danh sách giám sát")

    new_site = MonitoredSite(
        name=site_data.name.strip(),
        url=site_data.url.strip(),
        province_hint=site_data.province_hint.strip() if site_data.province_hint else "Toàn quốc"
    )
    db.add(new_site)
    db.commit()
    db.refresh(new_site)
    return serializable_site(new_site)

# API: Xóa Trang báo giám sát
@app.delete("/api/sites/{site_id}")
def delete_monitored_site(site_id: int, db: Session = Depends(get_db)):
    site = db.query(MonitoredSite).filter(MonitoredSite.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Không tìm thấy trang báo")
        
    db.delete(site)
    db.commit()
    return {"message": "Đã xóa trang báo thành công"}



# API: Thống kê Dashboard
@app.get("/api/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    total_risks = db.query(RiskItem).count()
    total_crawled = db.query(Article).count()
    
    # Tìm khu vực có nhiều rủi ro nhất
    top_prov = "Chưa có"
    if total_risks > 0:
        from sqlalchemy import func
        result = db.query(RiskItem.province, func.count(RiskItem.id).label("cnt"))\
                   .group_by(RiskItem.province)\
                   .order_by(func.count(RiskItem.id).desc()).first()
        if result:
            top_prov = f"{result[0]} ({result[1]})"
            
    return {
        "total_risks": total_risks,
        "total_crawled": total_crawled,
        "top_province": top_prov,
        "next_scan": "07:00 / 17:00 Hằng ngày"
    }

# API: Phân tích Dữ liệu Phân bổ theo Tỉnh & Loại Rủi Ro
@app.get("/api/analytics")
def get_analytics_data(db: Session = Depends(get_db)):
    from sqlalchemy import func
    
    # Phân bổ theo Tỉnh
    prov_counts = {}
    for prov in TARGET_PROVINCES:
        cnt = db.query(RiskItem).filter(RiskItem.province == prov).count()
        prov_counts[prov] = cnt
        
    # Phân bổ theo Loại Rủi ro
    all_items = db.query(RiskItem).all()
    category_counts = {
        "Pháp lý / Hình sự": 0,
        "Thuế / Tài chính / BHXH": 0,
        "Giấy phép / Xử phạt": 0,
        "Lao động / Môi trường": 0
    }
    
    for item in all_items:
        rt = (item.risk_type or "").lower()
        if any(k in rt for k in ["bắt", "khởi tố", "lừa đảo", "hình sự", "bị can", "bị cáo"]):
            category_counts["Pháp lý / Hình sự"] += 1
        elif any(k in rt for k in ["thuế", "bhxh", "tài chính", "nợ"]):
            category_counts["Thuế / Tài chính / BHXH"] += 1
        elif any(k in rt for k in ["giấy phép", "xử phạt", "đình chỉ", "cưỡng chế"]):
            category_counts["Giấy phép / Xử phạt"] += 1
        else:
            category_counts["Lao động / Môi trường"] += 1

    return {
        "by_province": prov_counts,
        "by_category": category_counts
    }

# API: Lấy Lịch sử Nhật ký Quét (Scan Logs)
@app.get("/api/logs")
def get_scan_logs(db: Session = Depends(get_db)):
    logs = db.query(ScanLog).order_by(ScanLog.id.desc()).limit(20).all()
    return [serializable_scan_log(l) for l in logs]

class ManualScanPayload(BaseModel):
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    province: Optional[str] = None
    max_articles: Optional[int] = 50

async def run_bg_scan_task(d_from: Optional[str], d_to: Optional[str], prov: Optional[str], max_art: int):
    try:
        await execute_full_scan_pipeline(
            date_from=d_from, 
            date_to=d_to, 
            selected_province=prov,
            max_articles=max_art
        )
    except Exception as e:
        print(f"Lỗi chạy background scan task: {e}")

# API: Kích hoạt quét thủ công có lọc Khoảng thời gian & Khu vực & Số lượng bài (Chạy ngầm BackgroundTasks)
@app.post("/api/scan")
async def trigger_manual_scan(background_tasks: BackgroundTasks, payload: Optional[ManualScanPayload] = None):
    d_from = payload.date_from if payload else None
    d_to = payload.date_to if payload else None
    prov = payload.province if payload else None
    max_art = payload.max_articles if (payload and payload.max_articles) else 50
    
    background_tasks.add_task(run_bg_scan_task, d_from, d_to, prov, max_art)
    
    return {
        "status": "PROCESSING",
        "message": f"⚡ Đã khởi chạy tiến trình cào & quét AI ngầm ({max_art} bài/báo). Hệ thống sẽ tự động cập nhật kết quả lên màn hình!",
        "max_articles": max_art
    }



# API Endpoint cho Vercel Cron Jobs tự động kích hoạt
@app.get("/api/cron/scan")
async def vercel_cron_scan():
    today_str = get_vietnam_today_str()
    result = await execute_full_scan_pipeline(
        date_from=today_str,
        date_to=today_str,
        selected_province="Tất cả",
        max_articles=50
    )
    return {"cron": "SUCCESS", "result": result}





# API: Tải báo cáo Excel (.xlsx) theo Khoảng thời gian và Khu vực
@app.get("/api/reports/download/excel")
def download_excel_report(
    province: str = Query("Tất cả"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(RiskItem)
    if province and province != "Tất cả":
        query = query.filter(RiskItem.province == province)
    if date_from:
        query = query.filter(RiskItem.published_date >= date_from)
    if date_to:
        query = query.filter(RiskItem.published_date <= date_to)

    risk_items = query.order_by(RiskItem.id.desc()).all()
    
    # Tạo file Excel mới
    excel_path = generate_excel_report(
        risk_items=risk_items,
        date_from=date_from,
        date_to=date_to,
        province=province
    )
    
    filename = os.path.basename(excel_path)
    return FileResponse(
        path=excel_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# API: Tải file báo cáo .docx theo ngày
@app.get("/api/reports/download/{date_str}")
def download_docx_report(date_str: str, db: Session = Depends(get_db)):
    filename = f"Bao_Cao_Rui_Ro_{date_str}.docx"
    file_path = REPORTS_DIR / filename
    
    if not file_path.exists():
        # Nếu chưa có file sẵn, tổng hợp từ DB và tạo mới
        all_risks = db.query(RiskItem).all()
        generated_path = generate_daily_docx_report(all_risks, date_str)
        file_path = generated_path

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


# Pydantic Schema cho Email Subscriber
class SubscriberCreate(BaseModel):
    name: str
    email: EmailStr
    target_province: str = "Tất cả"

# API: Lấy danh sách Email Subscriber
@app.get("/api/settings/email")
def list_email_subscribers(db: Session = Depends(get_db)):
    return db.query(EmailSubscriber).all()

# API: Thêm Email Subscriber
@app.post("/api/settings/email")
def add_email_subscriber(sub: SubscriberCreate, db: Session = Depends(get_db)):
    existing = db.query(EmailSubscriber).filter(EmailSubscriber.email == sub.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email này đã tồn tại trong danh sách nhận tin!")
        
    subscriber = EmailSubscriber(
        name=sub.name,
        email=sub.email,
        target_province=sub.target_province
    )
    db.add(subscriber)
    db.commit()
    db.refresh(subscriber)
    return subscriber

# API: Xóa Email Subscriber
@app.delete("/api/settings/email/{sub_id}")
def delete_email_subscriber(sub_id: int, db: Session = Depends(get_db)):
    sub = db.query(EmailSubscriber).filter(EmailSubscriber.id == sub_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Không tìm thấy subscriber")
    db.delete(sub)
    db.commit()
    return {"status": "SUCCESS", "message": f"Đã xóa subscriber #{sub_id}"}
