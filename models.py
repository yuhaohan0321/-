# -*- coding: utf-8 -*-
# models.py - 数据库模型定义

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"


class Dataset(db.Model):
    """代表一个上传的 Excel 数据集"""
    __tablename__ = "datasets"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    table_name = db.Column(db.String(255), unique=True, nullable=False)
    row_count = db.Column(db.Integer, default=0)
    column_names = db.Column(db.Text)  # JSON: list of column names
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    uploader = db.relationship("User", backref="datasets")

    def __repr__(self):
        return f"<Dataset {self.name}>"


class MediaFile(db.Model):
    """存储上传的图片/视频元数据"""
    __tablename__ = "media_files"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(20), nullable=False)  # "image" 或 "video"
    file_path = db.Column(db.String(512), nullable=False)
    file_size = db.Column(db.Integer)  # 字节
    mime_type = db.Column(db.String(100))
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    uploader = db.relationship("User", backref="media_files")

    def __repr__(self):
        return f"<MediaFile {self.original_filename}>"


class SavedChart(db.Model):
    """保存的图表配置"""
    __tablename__ = "saved_charts"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    dataset_id = db.Column(db.Integer, db.ForeignKey("datasets.id"), nullable=False)
    chart_type = db.Column(db.String(20), nullable=False)
    x_column = db.Column(db.String(255), nullable=False)
    y_column = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    dataset = db.relationship("Dataset", backref="saved_charts")
    user = db.relationship("User", backref="saved_charts")

    def __repr__(self):
        return f"<SavedChart {self.name}>"
