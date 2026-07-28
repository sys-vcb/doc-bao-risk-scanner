from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from app.config import get_vietnam_now

class MonitoredSite(Base):
    __tablename__ = "monitored_sites"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    url = Column(String(500), nullable=False, unique=True)
    province_hint = Column(String(100), nullable=True, default="Toàn quốc")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=get_vietnam_now)


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(500), unique=True, index=True, nullable=False)
    url_hash = Column(String(64), unique=True, index=True, nullable=False)
    title = Column(String(500), nullable=False)
    source_site = Column(String(100), nullable=False)
    raw_content = Column(Text, nullable=True)
    published_date = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=get_vietnam_now)

    risk_items = relationship("RiskItem", back_populates="article", cascade="all, delete-orphan")


class RiskItem(Base):
    __tablename__ = "risk_items"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=True)
    
    # 5 Mandated Fields for Word Report & Table
    entity_name = Column(String(255), nullable=False, default="")              # 1. Tên Cá nhân/ Doanh nghiệp/ Tổ chức
    entity_type = Column(String(50), nullable=False, default="Doanh nghiệp")    # Phân loại: Doanh nghiệp / Cá nhân / Chưa xác định
    summary = Column(Text, nullable=False)                                      # 2. Tóm tắt rủi ro (2-3 câu)
    province = Column(String(100), nullable=False)                              # 3. Khu vực (1/6 tỉnh)
    risk_type = Column(String(255), nullable=False)                             # 4. Loại rủi ro / Từ khóa
    published_date = Column(String(100), nullable=False)                        # 5. Ngày tin tức
    source_url = Column(String(500), nullable=False)                            # 5. Link bài gốc

    
    is_ai_extracted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=get_vietnam_now)

    article = relationship("Article", back_populates="risk_items")


class EmailSubscriber(Base):
    __tablename__ = "email_subscribers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    target_province = Column(String(100), nullable=False, default="Tất cả") # "Tất cả" hoặc tên tỉnh
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=get_vietnam_now)


class ScanLog(Base):
    __tablename__ = "scan_logs"

    id = Column(Integer, primary_key=True, index=True)
    scan_time = Column(DateTime, default=get_vietnam_now)
    total_crawled = Column(Integer, default=0)
    pre_filtered_count = Column(Integer, default=0)
    risks_extracted = Column(Integer, default=0)
    status = Column(String(50), default="SUCCESS")
    message = Column(Text, nullable=True)
