from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+pg8000://", 1)
elif db_url.startswith("postgresql://") and "+pg8000" not in db_url and "+psycopg2" not in db_url:
    db_url = db_url.replace("postgresql://", "postgresql+pg8000://", 1)

# For SQLite vs PostgreSQL
connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
engine_kwargs = {"connect_args": connect_args, "echo": False}

if not db_url.startswith("sqlite"):
    engine_kwargs["pool_pre_ping"] = True

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
    from app import models
    from app.config import TARGET_SITES
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
