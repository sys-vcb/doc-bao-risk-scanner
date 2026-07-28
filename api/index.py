import sys
from pathlib import Path

# Thêm thư mục gốc dự án vào Python Path để Vercel import ứng dụng
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app
