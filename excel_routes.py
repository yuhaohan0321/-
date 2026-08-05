# -*- coding: utf-8 -*-
# excel_routes.py - Excel / CSV 上传与可视化模块

import csv
import io
import json
import os
import uuid
from datetime import datetime

import openpyxl
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
)
from flask_login import login_required, current_user
from sqlalchemy import text

from models import db, Dataset
from config import ALLOWED_EXCEL_EXTENSIONS, ALLOWED_CSV_EXTENSIONS

excel_bp = Blueprint("excel", __name__, url_prefix="/excel")

# 预览缓存：token → {rows, filename, max_cols}
_preview_cache = {}
_MAX_CACHE_SIZE = 20
_PREVIEW_MAX_ROWS = 30


# ---------- shared helpers ----------

def allowed_table_file(filename):
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXCEL_EXTENSIONS or ext in ALLOWED_CSV_EXTENSIONS


def sanitize_table_name(name):
    import re
    base = os.path.splitext(name)[0]
    base = re.sub(r"[^a-zA-Z0-9_]", "_", base)
    base = base.strip("_") or "dataset"
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return "excel_" + base + "_" + timestamp


def get_column_type(values):
    has_float = False
    has_int = False
    for v in values:
        if v is None or str(v).strip() == "":
            continue
        if isinstance(v, (int, float)):
            if isinstance(v, float):
                has_float = True
            else:
                has_int = True
        else:
            try:
                float(str(v))
                has_float = True
            except (ValueError, TypeError):
                return "TEXT"
    if has_float:
        return "DOUBLE PRECISION"
    if has_int:
        return "BIGINT"
    return "TEXT"


def make_sql_column_name(display_name, index):
    import re
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", display_name)
    safe = safe.strip("_")
    if safe and safe[0].isdigit():
        safe = "_" + safe
    if not safe:
        safe = "col_" + str(index)
    return safe.lower()


# ========== CSV 解析 ==========

CSV_ENCODINGS = ["utf-8-sig", "utf-8", "utf-16-le", "utf-16", "gbk", "gb18030", "gb2312"]


def _try_decode(raw):
    for enc in CSV_ENCODINGS:
        try:
            text = raw.decode(enc)
            if _looks_reasonable(text):
                return text, enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    text = raw.decode("utf-8", errors="replace")
    return text, "utf-8(replace)"


def _looks_reasonable(text):
    sample = text[:4096]
    has_cjk = any("\u4e00" <= c <= "\u9fff" for c in sample)
    if not has_cjk:
        return True
    replacement_count = sample.count("\ufffd")
    return replacement_count <= max(3, len(sample) // 200)


def _detect_delimiter(text):
    sample = text[:16384]
    lines = [l for l in sample.splitlines() if l.strip()]
    if not lines:
        return ","
    candidate_lines = lines[:min(30, len(lines))]
    try:
        dialect = csv.Sniffer().sniff("\n".join(candidate_lines))
        return dialect.delimiter
    except Exception:
        pass
    candidates = [",", "\t", ";", "|"]
    best, best_score = ",", 0
    for delim in candidates:
        counts = [line.count(delim) for line in candidate_lines if delim in line]
        if not counts:
            continue
        counts.sort()
        median = counts[len(counts) // 2]
        consistent = sum(1 for c in counts if c == median)
        if consistent > best_score and median > 0:
            best_score = consistent
            best = delim
    return best


def parse_all_rows(file_stream, ext):
    """解析文件并返回全部原始行（不做标题行假设）。

    返回: list[list[str]]  每行是一个字符串列表，可能不等长
    """
    if ext in ALLOWED_CSV_EXTENSIONS:
        raw = file_stream.read()
        if not raw:
            raise ValueError("文件为空")
        file_stream.seek(0)
        text, _enc = _try_decode(raw)
        if text is None:
            raise ValueError("无法识别编码，请另存为 UTF-8")
        delimiter = _detect_delimiter(text)
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        rows = [r for r in reader]
    else:
        wb = openpyxl.load_workbook(file_stream, data_only=True)
        ws = wb.active
        rows = [list(r) for r in ws.iter_rows(values_only=True)]

    # 过滤全空行
    rows = [r for r in rows if any(c is not None and str(c).strip() for c in r)]
    if len(rows) < 2:
        raise ValueError("文件至少需要 2 行（标题 + 数据）")

    # 全部转为字符串
    str_rows = [[str(c).strip() if c is not None else "" for c in row] for row in rows]

    # 对齐列数（补齐不足的行到最大列数）
    max_cols = max(len(r) for r in str_rows) if str_rows else 0
    for r in str_rows:
        while len(r) < max_cols:
            r.append("")

    return str_rows


def _cache_put(rows, filename):
    """存入预览缓存，返回 token"""
    token = uuid.uuid4().hex[:10]
    _preview_cache[token] = {"rows": rows, "filename": filename}
    # 清理最旧的缓存
    while len(_preview_cache) > _MAX_CACHE_SIZE:
        oldest = next(iter(_preview_cache))
        del _preview_cache[oldest]
    return token


def _cache_get(token):
    return _preview_cache.pop(token, None)


# ========== 通用导入管道 ==========

def import_table_data(filename, user_id, display_headers, data_rows):
    seen = {}
    final_display = []
    for h in display_headers:
        if h in seen:
            seen[h] += 1
            final_display.append(h + "_" + str(seen[h]))
        else:
            seen[h] = 0
            final_display.append(h)

    col_types = []
    for ci in range(len(final_display)):
        col_vals = [row[ci] if ci < len(row) else None for row in data_rows]
        col_types.append(get_column_type(col_vals))

    sql_headers = [make_sql_column_name(h, i) for i, h in enumerate(final_display)]
    sql_seen = {}
    final_sql = []
    for h in sql_headers:
        if h in sql_seen:
            sql_seen[h] += 1
            final_sql.append(h + "_" + str(sql_seen[h]))
        else:
            sql_seen[h] = 0
            final_sql.append(h)

    # 避免与主键 id 冲突
    RESERVED_COLS = {"id"}
    for i, col in enumerate(final_sql):
        if col.lower() in RESERVED_COLS:
            final_sql[i] = "_" + col

    table_name = sanitize_table_name(filename)
    col_defs = ", ".join('"' + h + '" ' + t for h, t in zip(final_sql, col_types))
    create_sql = (
        'CREATE TABLE IF NOT EXISTS "' + table_name
        + '" (id SERIAL PRIMARY KEY, ' + col_defs + ")"
    )
    db.session.execute(text(create_sql))

    for row in data_rows:
        values = {}
        for ci, h in enumerate(final_sql):
            val = row[ci] if ci < len(row) else None
            if val is None:
                values[h] = None
            elif col_types[ci] in ("DOUBLE PRECISION", "BIGINT"):
                try:
                    values[h] = float(val) if col_types[ci] == "DOUBLE PRECISION" else int(float(val))
                except (ValueError, TypeError):
                    values[h] = None
            else:
                values[h] = str(val)
        placeholders = ", ".join(":" + h for h in final_sql)
        col_names = ", ".join('"' + h + '"' for h in final_sql)
        insert_sql = (
            'INSERT INTO "' + table_name + '" (' + col_names + ") VALUES (" + placeholders + ")"
        )
        db.session.execute(text(insert_sql), values)

    db.session.commit()

    dataset = Dataset(
        name=request.form.get("name", "").strip() or os.path.splitext(filename)[0],
        original_filename=filename,
        table_name=table_name,
        row_count=len(data_rows),
        column_names=json.dumps(final_display, ensure_ascii=False),
        uploaded_by=user_id,
    )
    db.session.add(dataset)
    db.session.commit()
    return len(data_rows)


# ========== routes ==========

@excel_bp.route("/datasets")
@login_required
def datasets():
    all_datasets = Dataset.query.order_by(Dataset.created_at.desc()).all()
    return render_template("datasets.html", datasets=all_datasets)


@excel_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    """上传页：GET 显示表单；POST 解析文件并返回预览"""
    if request.method == "POST":
        file = request.files.get("file")
        if not file or file.filename == "":
            flash("请选择一个文件", "danger")
            return redirect(request.url)

        if not allowed_table_file(file.filename):
            flash("仅支持 .xlsx / .xls / .csv / .tsv 格式", "danger")
            return redirect(request.url)

        ext = file.filename.rsplit(".", 1)[1].lower()
        try:
            all_rows = parse_all_rows(file, ext)
            token = _cache_put(all_rows, file.filename)
        except ValueError as ve:
            flash(str(ve), "danger")
            return redirect(request.url)
        except Exception as e:
            flash("文件解析失败: " + str(e), "danger")
            return redirect(request.url)

        max_cols = len(all_rows[0]) if all_rows else 0
        preview_rows = all_rows[:_PREVIEW_MAX_ROWS]
        total_rows = len(all_rows)

        return render_template(
            "upload_excel.html",
            preview_mode=True,
            token=token,
            filename=file.filename,
            preview_rows=preview_rows,
            total_rows=total_rows,
            max_cols=max_cols,
            preview_limit=_PREVIEW_MAX_ROWS,
        )

    return render_template("upload_excel.html", preview_mode=False)


@excel_bp.route("/upload/confirm", methods=["POST"])
@login_required
def upload_confirm():
    """确认导入：根据用户在预览中选择的标题行/数据行/列执行导入"""
    token = request.form.get("token", "")
    cached = _cache_get(token)
    if not cached:
        flash("预览已过期，请重新上传", "danger")
        return redirect(url_for("excel.upload"))

    all_rows = cached["rows"]
    filename = cached["filename"]

    # 用户选择的标题行（1-based → 0-based）
    header_row = int(request.form.get("header_row", 1)) - 1
    # 用户选择的数据起始行（1-based → 0-based）
    data_start = int(request.form.get("data_start", header_row + 2)) - 1
    # 用户勾选的列索引
    selected_cols_str = request.form.get("selected_cols", "")
    selected_cols = [int(x) for x in selected_cols_str.split(",") if x.strip().isdigit()]

    if header_row < 0 or header_row >= len(all_rows):
        flash("标题行超出范围", "danger")
        return redirect(url_for("excel.upload"))
    if data_start <= header_row or data_start > len(all_rows):
        flash("数据起始行无效", "danger")
        return redirect(url_for("excel.upload"))

    # 从标题行提取标题
    header_row_data = all_rows[header_row]
    if selected_cols:
        display_headers = [
            header_row_data[ci] if ci < len(header_row_data) and header_row_data[ci] else "col_" + str(ci)
            for ci in selected_cols
        ]
    else:
        display_headers = [
            h if h else "col_" + str(i) for i, h in enumerate(header_row_data)
        ]
        selected_cols = list(range(len(header_row_data)))

    # 提取数据行（只取选中的列）
    data_rows = []
    for row in all_rows[data_start:]:
        filtered = [row[ci] if ci < len(row) else "" for ci in selected_cols]
        # 跳过全空行
        if any(c for c in filtered):
            data_rows.append(filtered)

    if not data_rows:
        flash("没有可导入的数据行", "danger")
        return redirect(url_for("excel.upload"))

    try:
        count = import_table_data(
            filename=filename,
            user_id=current_user.id,
            display_headers=display_headers,
            data_rows=data_rows,
        )
        flash("成功导入 " + str(count) + " 条数据", "success")
    except Exception as e:
        db.session.rollback()
        flash("导入失败: " + str(e), "danger")

    return redirect(url_for("excel.datasets"))


@excel_bp.route("/dataset/<int:dataset_id>")
@login_required
def view_dataset(dataset_id):
    dataset = Dataset.query.get_or_404(dataset_id)
    columns = json.loads(dataset.column_names) if dataset.column_names else []

    try:
        query = 'SELECT * FROM "' + dataset.table_name + '" ORDER BY id'
        result = db.session.execute(text(query))
        rows_raw = result.fetchall()
        data_rows = [list(row)[1:] for row in rows_raw]
    except Exception:
        data_rows = []

    return render_template("dataset_view.html", dataset=dataset, columns=columns, data_rows=data_rows)


@excel_bp.route("/dataset/<int:dataset_id>/data")
@login_required
def dataset_data(dataset_id):
    dataset = Dataset.query.get_or_404(dataset_id)
    columns = json.loads(dataset.column_names) if dataset.column_names else []

    try:
        query = 'SELECT * FROM "' + dataset.table_name + '" ORDER BY id'
        result = db.session.execute(text(query))
        rows_raw = result.fetchall()
        data_rows = [list(row)[1:] for row in rows_raw]
    except Exception:
        data_rows = []

    return jsonify({"columns": columns, "rows": data_rows})


@excel_bp.route("/dataset/<int:dataset_id>/delete", methods=["POST"])
@login_required
def delete_dataset(dataset_id):
    dataset = Dataset.query.get_or_404(dataset_id)
    try:
        db.session.execute(text('DROP TABLE IF EXISTS "' + dataset.table_name + '"'))
        db.session.delete(dataset)
        db.session.commit()
        flash("数据集已删除", "success")
    except Exception as e:
        db.session.rollback()
        flash("删除失败: " + str(e), "danger")
    return redirect(url_for("excel.datasets"))
