# -*- coding: utf-8 -*-
# media_routes.py - 图片与视频上传展示模块

import os
import uuid
from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_from_directory,
    current_app,
)
from flask_login import login_required, current_user

from models import db, MediaFile
from config import (
    UPLOAD_FOLDER,
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_VIDEO_EXTENSIONS,
)

media_bp = Blueprint("media", __name__, url_prefix="/media")


def allowed_file(filename: str) -> tuple:
    """返回 (是否允许, 文件类型: image/video/None)"""
    if "." not in filename:
        return False, None
    ext = filename.rsplit(".", 1)[1].lower()
    if ext in ALLOWED_IMAGE_EXTENSIONS:
        return True, "image"
    if ext in ALLOWED_VIDEO_EXTENSIONS:
        return True, "video"
    return False, None


@media_bp.route("/")
@login_required
def gallery():
    page = request.args.get("page", 1, type=int)
    file_type = request.args.get("type", "all")
    per_page = 12

    query = MediaFile.query.order_by(MediaFile.created_at.desc())
    if file_type in ("image", "video"):
        query = query.filter_by(file_type=file_type)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    media_list = pagination.items

    return render_template(
        "media.html",
        media_list=media_list,
        pagination=pagination,
        current_type=file_type,
    )


@media_bp.route("/upload", methods=["POST"])
@login_required
def upload():
    files = request.files.getlist("files")
    if not files or all(f.filename == "" for f in files):
        flash("请选择要上传的文件", "danger")
        return redirect(url_for("media.gallery"))

    success_count = 0
    for file in files:
        if file.filename == "":
            continue

        allowed, ftype = allowed_file(file.filename)
        if not allowed:
            flash(f"不支持的文件格式: {file.filename}", "warning")
            continue

        # 生成唯一文件名
        ext = file.filename.rsplit(".", 1)[1].lower()
        unique_name = f"{uuid.uuid4().hex}.{ext}"

        # 确定存储子目录
        subdir = "images" if ftype == "image" else "videos"
        save_dir = os.path.join(UPLOAD_FOLDER, subdir)
        os.makedirs(save_dir, exist_ok=True)

        save_path = os.path.join(save_dir, unique_name)
        file.save(save_path)

        file_size = os.path.getsize(save_path)
        mime_map = {
            "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "gif": "image/gif", "bmp": "image/bmp", "webp": "image/webp",
            "mp4": "video/mp4", "webm": "video/webm", "ogg": "video/ogg",
        }
        mime_type = mime_map.get(ext, "application/octet-stream")

        media_record = MediaFile(
            filename=unique_name,
            original_filename=file.filename,
            file_type=ftype,
            file_path=os.path.join(subdir, unique_name).replace("\\", "/"),
            file_size=file_size,
            mime_type=mime_type,
            uploaded_by=current_user.id,
        )
        db.session.add(media_record)
        success_count += 1

    db.session.commit()
    if success_count > 0:
        flash(f"成功上传 {success_count} 个文件", "success")
    return redirect(url_for("media.gallery"))


@media_bp.route("/uploads/<path:subpath>")
@login_required
def serve_upload(subpath):
    """安全地提供上传文件，仅限已登录用户"""
    return send_from_directory(UPLOAD_FOLDER, subpath)


@media_bp.route("/delete/<int:media_id>", methods=["POST"])
@login_required
def delete_media(media_id):
    media = MediaFile.query.get_or_404(media_id)
    try:
        full_path = os.path.join(UPLOAD_FOLDER, media.file_path)
        if os.path.exists(full_path):
            os.remove(full_path)
        db.session.delete(media)
        db.session.commit()
        flash("文件已删除", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"删除失败: {str(e)}", "danger")
    return redirect(url_for("media.gallery"))
