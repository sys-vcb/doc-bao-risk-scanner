from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

import os
import urllib.parse

def sanitize_db_url(raw_url: str) -> str:
    url = (raw_url or "").strip()
    if not url or url.startswith("sqlite"):
        return url
    
    if "postgres://" in url or "postgresql://" in url:
        prefix_idx = url.find("://")
        rest = url[prefix_idx + 3:]
        if "@" in rest:
            last_at = rest.rfind("@")
            user_pass = rest[:last_at]
            host_db = rest[last_at + 1:]
            if ":" in user_pass:
                user, pwd = user_pass.split(":", 1)
                pwd = pwd.strip("[]")
                pwd_quoted = urllib.parse.quote(pwd, safe='')
                if user == "postgres" and "pooler.supabase.com" in host_db:
                    user = "postgres.zoanjqbybeqquycdrsmx"
                return f"postgresql+pg8000://{user}:{pwd_quoted}@{host_db}"
            return f"postgresql+pg8000://{rest}"
    return url



raw_db_url = os.getenv("DATABASE_URL") or settings.DATABASE_URL
db_url = sanitize_db_url(raw_db_url)

import ssl
from sqlalchemy.pool import NullPool

connect_args = {}
if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
else:
    try:
        ssl_ctx = ssl._create_unverified_context()
        connect_args["ssl_context"] = ssl_ctx
        connect_args["timeout"] = 10
    except Exception as e:
        print(f"SSL context setup warning: {e}")

engine_kwargs = {"connect_args": connect_args, "echo": False}
if not db_url.startswith("sqlite"):
    engine_kwargs["poolclass"] = NullPool

engine = create_engine(db_url, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Khởi tạo các bảng CSDL và seed 9 trang báo mặc định nếu chưa có"""
    try:
        from app import models
        from app.config import TARGET_SITES
        
        # Chỉ gọi create_all() với SQLite local, bỏ qua cho Supabase PostgreSQL để khởi động trong < 0.1s
        if db_url.startswith("sqlite"):
            Base.metadata.create_all(bind=engine)
        
        db = SessionLocal()
        try:
            existing_count = db.query(models.MonitoredSite).count()
            if existing_count == 0:
                for s in TARGET_SITES:
                    site_obj = models.MonitoredSite(
                        name=s["name"],
                        url=s["url"],
                        province_hint=s.get("province_hint", "Toàn quốc")
                    )
                    db.add(site_obj)
                db.commit()
        finally:
            db.close()
    except Exception as err:
        print(f"Lỗi init_db trên môi trường Vercel: {err}")


