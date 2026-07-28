import os
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import List
from sqlalchemy.orm import Session

from app.config import settings
from app.models import EmailSubscriber, RiskItem

logger = logging.getLogger("EmailService")

def send_risk_alert_email(subscriber_email: str, subscriber_name: str, province_filter: str, docx_path: str, risk_items: List[RiskItem]) -> bool:
    """
    Gửi email cảnh báo rủi ro qua SMTP đính kèm file Word (.docx)
    """
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning(f"SMTP chưa được cấu hình. Bỏ qua gửi email tới {subscriber_email}")
        return False

    if not os.path.exists(docx_path):
        logger.error(f"File đính kèm không tồn tại: {docx_path}")
        return False

    # Lọc danh sách bài viết khớp với khu vực của subscriber
    if province_filter == "Tất cả":
        relevant_risks = risk_items
    else:
        relevant_risks = [r for r in risk_items if r.province.lower() == province_filter.lower()]

    if not relevant_risks and risk_items:
        # Nếu subscriber đăng ký 1 tỉnh cụ thể mà hôm nay không có bài nào của tỉnh đó, bỏ qua gửi
        logger.info(f"Không có bài viết rủi ro nào cho khu vực {province_filter} của {subscriber_email}")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = f"{settings.SENDER_NAME} <{settings.SENDER_EMAIL or settings.SMTP_USER}>"
        msg['To'] = subscriber_email
        msg['Subject'] = f"[CẢNH BÁO RỦI RO] Báo cáo tin tức rủi ro - Khu vực: {province_filter}"

        # Soạn nội dung Email HTML
        items_html = ""
        for r in relevant_risks[:10]: # Liệt kê tối đa 10 item tiêu biểu trong email
            items_html += f"""
            <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 8px; font-weight: bold; color: #1e293b;">{r.entity_name}</td>
                <td style="padding: 8px; color: #334155;">{r.summary}</td>
                <td style="padding: 8px; color: #d97706; font-weight: bold;">{r.province}</td>
                <td style="padding: 8px; color: #dc2626;">{r.risk_type}</td>
                <td style="padding: 8px;"><a href="{r.source_url}" style="color: #2563eb;">Xem bài gốc</a></td>
            </tr>
            """

        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #0f172a; line-height: 1.6;">
            <div style="max-width: 700px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px;">
                <h2 style="color: #1e293b; border-bottom: 2px solid #3b82f6; padding-bottom: 8px;">
                    📢 CẢNH BÁO RỦI RO DOANH NGHIỆP / TỔ CHỨC / CÁ NHÂN
                </h2>
                <p>Kính gửi <strong>{subscriber_name}</strong>,</p>
                <p>Hệ thống tự động phát hiện <strong>{len(relevant_risks)}</strong> tin tức cảnh báo rủi ro liên quan đến khu vực <strong>{province_filter}</strong>.</p>
                
                <table style="width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 13px;">
                    <thead>
                        <tr style="background-color: #0f172a; color: white; text-align: left;">
                            <th style="padding: 8px;">Đối tượng</th>
                            <th style="padding: 8px;">Nội dung rủi ro</th>
                            <th style="padding: 8px;">Khu vực</th>
                            <th style="padding: 8px;">Loại rủi ro</th>
                            <th style="padding: 8px;">Link gốc</th>
                        </tr>
                    </thead>
                    <tbody>
                        {items_html}
                    </tbody>
                </table>
                
                <p>📎 <em>Chi tiết toàn bộ báo cáo xin vui lòng xem file Word (.docx) đính kèm email này.</em></p>
                <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
                <p style="font-size: 12px; color: #64748b;">Trân trọng,<br/><strong>{settings.SENDER_NAME}</strong></p>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(body_html, 'html', 'utf-8'))

        # Đính kèm file Word .docx
        with open(docx_path, 'rb') as f:
            attach = MIMEApplication(f.read(), _subtype="docx")
            attach.add_header('Content-Disposition', 'attachment', filename=os.path.basename(docx_path))
            msg.attach(attach)

        # Connect SMTP server
        server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()

        logger.info(f"Đã gửi email thành công tới {subscriber_email}")
        return True
    except Exception as e:
        logger.error(f"Lỗi gửi email tới {subscriber_email}: {e}")
        return False

def dispatch_daily_emails(db: Session, docx_path: str, risk_items: List[RiskItem]):
    """Gửi email tới toàn bộ subscribers active trong CSDL"""
    subscribers = db.query(EmailSubscriber).filter(EmailSubscriber.is_active == True).all()
    if not subscribers:
        logger.info("Không có email subscriber nào trong hệ thống.")
        return

    for sub in subscribers:
        send_risk_alert_email(
            subscriber_email=sub.email,
            subscriber_name=sub.name,
            province_filter=sub.target_province,
            docx_path=docx_path,
            risk_items=risk_items
        )
