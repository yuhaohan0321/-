# -*- coding: utf-8 -*-
# config.py - 数据库与应用配置

import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "database": "webapp_db",
    "user": "postgres",
    "password": "yuiopjkl2",
}

# 使用 pg8000 纯 Python 驱动，不依赖 libpq C 库，彻底避免 Windows 编码冲突
SQLALCHEMY_DATABASE_URI = (
    "postgresql+pg8000://" + DB_CONFIG["user"] + ":" + DB_CONFIG["password"]
    + "@" + DB_CONFIG["host"] + ":" + str(DB_CONFIG["port"])
    + "/" + DB_CONFIG["database"]
)

SECRET_KEY = "change-this-to-a-random-secret-key-in-production"
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
MAX_CONTENT_LENGTH = 100 * 1024 * 1024
ALLOWED_EXCEL_EXTENSIONS = {"xlsx", "xls"}
ALLOWED_CSV_EXTENSIONS = {"csv", "tsv", "txt"}
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "bmp", "webp"}
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "webm", "ogg"}

DEFAULT_ADMIN = {
    "username": "admin",
    "password": "admin123",
}
