from typing import Optional, Dict, Any, List
import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger


from app.database import SessionLocal
from app.models import RiskItem, ScanLog
from app.scraper.engine import run_scrape_process
from app.ai.gemini_extractor import extract_risk_with_gemini
from app.services.docx_exporter import generate_daily_docx_report
from app.services.excel_exporter import generate_excel_report
from app.services.email_service import dispatch_daily_emails

logger = logging.getLogger("SchedulerService")
scheduler = AsyncIOScheduler()

async def execute_full_scan_pipeline(
    date_from: Optional[str] = None, 
    date_to: Optional[str] = None, 
    selected_province: Optional[str] = None,
    max_articles: int = 50
):
    """
    Toàn bộ Quy trình Quét tin Tự động / Thủ công có bộ lọc tùy chỉnh:
    1. Cào tin từ website mục tiêu
    2. Lọc 2-step Regex sơ bộ theo Khoảng thời gian & Khu vực
    3. Trích xuất Batch Gemini AI
    4. Lưu CSDL
    5. Xuất file Excel (.xlsx) & Word (.docx)
    6. Gửi Email đính kèm báo cáo
    """
    logger.info(f"Scheduler kích hoạt quy trình quét tin ({max_articles} bài/báo, Khu vực: {selected_province or 'Tất cả'}, Từ ngày: {date_from}, Đến ngày: {date_to})...")
    db = SessionLocal()
    try:
        # Step 1 & 2: Cào tin & Lọc sơ bộ Regex
        scrape_result = await run_scrape_process(
            db, 
            date_from=date_from, 
            date_to=date_to, 
            selected_province=selected_province,
            max_articles=max_articles
        )

        candidates = scrape_result["candidates"]

        
        extracted_risks = []
        
        # Step 3: Phân tích Batch Gemini AI 3.5 Flash Lite (Gom 5 bài / 1 Request)
        from app.ai.gemini_extractor import batch_extract_risk_with_gemini
        extracted_risks_data = batch_extract_risk_with_gemini(candidates, batch_size=5)

        dbsh_list = ["Quảng Ninh", "Hải Phòng", "Hưng Yên", "Ninh Bình", "Bắc Ninh", "Phú Thọ"]

        for risk_data in extracted_risks_data:
            # Nếu người dùng chọn 6 tỉnh ĐBSH hoặc 1 tỉnh cụ thể, lọc chặt chẽ kết quả trích xuất theo đúng phạm vi đó
            item_prov = risk_data.get("province", "")
            if selected_province and selected_province != "Tất cả":
                if selected_province in ["6 tỉnh ĐBSH", "ĐBSH", "Vùng trọng điểm"]:
                    if not any(p.lower() in item_prov.lower() for p in dbsh_list):
                        continue
                else:
                    if selected_province.lower() not in item_prov.lower():
                        continue

            # Kiểm tra xem bài báo rủi ro này đã được lưu vào RiskItem chưa (chống trùng lặp khi chạy song song)
            existing_risk = None
            if risk_data.get("article_id"):
                existing_risk = db.query(RiskItem).filter(RiskItem.article_id == risk_data["article_id"]).first()
            if not existing_risk and risk_data.get("source_url"):
                existing_risk = db.query(RiskItem).filter(RiskItem.source_url == risk_data["source_url"]).first()
                
            if existing_risk:
                continue


            risk_item = RiskItem(
                article_id=risk_data.get("article_id"),
                entity_name=risk_data["entity_name"],
                entity_type=risk_data.get("entity_type", "Doanh nghiệp"),
                summary=risk_data["summary"],
                province=risk_data["province"],
                risk_type=risk_data["risk_type"],
                published_date=risk_data["published_date"],
                source_url=risk_data["source_url"],
                is_ai_extracted=True
            )
            db.add(risk_item)
            extracted_risks.append(risk_item)


            
        db.commit()


        # Lấy danh sách rủi ro trong ngày
        today_str = datetime.now().strftime("%Y-%m-%d")
        all_today_risks = db.query(RiskItem).all()

        # Step 5: Xuất file Excel (.xlsx) và Word (.docx)
        excel_path = generate_excel_report(all_today_risks, date_from=today_str, date_to=today_str)
        docx_path = generate_daily_docx_report(all_today_risks, today_str)

        # Step 6: Gửi Email (đính kèm Excel)
        dispatch_daily_emails(db, excel_path, all_today_risks)

        # Ghi nhật ký ScanLog
        log_entry = ScanLog(
            total_crawled=scrape_result["total_crawled"],
            pre_filtered_count=len(candidates),
            risks_extracted=len(extracted_risks),
            status="SUCCESS",
            message=f"Hoàn thành quét tự động. Đã tạo {excel_path}"
        )
        db.add(log_entry)
        db.commit()

        logger.info(f"Hoàn tất pipeline: {len(extracted_risks)} rủi ro mới được phát hiện.")
        return {
            "status": "SUCCESS",
            "total_crawled": scrape_result["total_crawled"],
            "pre_filtered": len(candidates),
            "risks_extracted": len(extracted_risks),
            "excel_path": excel_path,
            "docx_path": docx_path
        }


    except Exception as e:
        logger.error(f"Lỗi trong tiến trình quét tự động: {e}")
        log_entry = ScanLog(
            status="FAILED",
            message=str(e)
        )
        db.add(log_entry)
        db.commit()
        return {"status": "FAILED", "error": str(e)}
    finally:
        db.close()

def start_scheduler():
    """Khởi chạy Scheduler với 2 mốc thời gian: 07:00 AM và 17:00 PM hàng ngày"""
    import os
    if os.getenv("VERCEL"):
        logger.info("Môi trường Vercel Serverless: Sử dụng Vercel Cron Jobs thay cho APScheduler")
        return
    try:
        # 07:00 Sáng
        scheduler.add_job(
            execute_full_scan_pipeline,
            trigger=CronTrigger(hour=7, minute=0),
            id="daily_scan_morning",
            replace_existing=True
        )
        # 17:00 Chiều
        scheduler.add_job(
            execute_full_scan_pipeline,
            trigger=CronTrigger(hour=17, minute=0),
            id="daily_scan_afternoon",
            replace_existing=True
        )
        scheduler.start()
        logger.info("APScheduler đã bắt đầu (Lịch chạy: 07:00 và 17:00 hàng ngày)")
    except Exception as e:
        logger.warning(f"Không thể khởi chạy APScheduler: {e}")

