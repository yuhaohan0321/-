# -*- coding: utf-8 -*-
# param_query.py - 参数条件查询与结果展示

import json
from flask import Blueprint, render_template, request, jsonify, flash
from flask_login import login_required
from sqlalchemy import text

from models import db, Dataset
from excel_routes import make_sql_column_name

param_bp = Blueprint("param_query", __name__, url_prefix="/param")


def get_sql_columns(dataset) -> tuple:
    """返回 (显示列名列表, SQL列名列表) 的配对"""
    display_columns = json.loads(dataset.column_names) if dataset.column_names else []
    sql_columns = [make_sql_column_name(h, i) for i, h in enumerate(display_columns)]

    # 去重（与 excel_routes 中逻辑一致）
    seen = {}
    final_sql = []
    for h in sql_columns:
        if h in seen:
            seen[h] += 1
            final_sql.append(f"{h}_{seen[h]}")
        else:
            seen[h] = 0
            final_sql.append(h)

    return display_columns, final_sql


@param_bp.route("/")
@login_required
def index():
    """参数查询入口：选择数据集"""
    datasets = Dataset.query.order_by(Dataset.created_at.desc()).all()
    return render_template("param_query.html", datasets=datasets, results=None, selected=None)


@param_bp.route("/query/<int:dataset_id>", methods=["GET", "POST"])
@login_required
def query(dataset_id):
    """对指定数据集执行参数条件查询"""
    dataset = Dataset.query.get_or_404(dataset_id)
    display_columns, sql_columns = get_sql_columns(dataset)
    datasets = Dataset.query.order_by(Dataset.created_at.desc()).all()

    results = None
    selected = None

    if request.method == "POST":
        conditions = []
        params = {}
        selected = {}

        for ci, display_name in enumerate(display_columns):
            operator = request.form.get(f"op_{ci}", "")
            value = request.form.get(f"val_{ci}", "").strip()

            if not value or not operator:
                continue

            selected[display_name] = {"operator": operator, "value": value}
            sql_col = sql_columns[ci]  # 用真实的 SQL 列名

            param_key = f"p_{ci}"
            if operator == "=":
                conditions.append(f'"{sql_col}" = :{param_key}')
                params[param_key] = value
            elif operator == ">":
                conditions.append(f'"{sql_col}" > :{param_key}')
                params[param_key] = value
            elif operator == "<":
                conditions.append(f'"{sql_col}" < :{param_key}')
                params[param_key] = value
            elif operator == ">=":
                conditions.append(f'"{sql_col}" >= :{param_key}')
                params[param_key] = value
            elif operator == "<=":
                conditions.append(f'"{sql_col}" <= :{param_key}')
                params[param_key] = value
            elif operator == "like":
                conditions.append(f'"{sql_col}" LIKE :{param_key}')
                params[param_key] = f"%{value}%"
            elif operator == "between":
                parts = value.split(",")
                if len(parts) == 2:
                    key1 = f"{param_key}_min"
                    key2 = f"{param_key}_max"
                    conditions.append(f'"{sql_col}" BETWEEN :{key1} AND :{key2}')
                    params[key1] = parts[0].strip()
                    params[key2] = parts[1].strip()

        if conditions:
            where_clause = " AND ".join(conditions)
            try:
                query_sql = f'SELECT * FROM "{dataset.table_name}" WHERE {where_clause} ORDER BY id'
                result = db.session.execute(text(query_sql), params)
                rows_raw = result.fetchall()
                results = [list(row)[1:] for row in rows_raw]
            except Exception as e:
                results = None
                flash(f"查询出错: {str(e)}", "danger")
        else:
            try:
                query_sql = f'SELECT * FROM "{dataset.table_name}" ORDER BY id'
                result = db.session.execute(text(query_sql))
                rows_raw = result.fetchall()
                results = [list(row)[1:] for row in rows_raw]
            except Exception:
                results = []

    return render_template(
        "param_query.html",
        datasets=datasets,
        dataset=dataset,
        columns=display_columns,
        results=results,
        selected=selected,
    )


@param_bp.route("/api/columns/<int:dataset_id>")
@login_required
def api_columns(dataset_id):
    """返回数据集的列名 JSON"""
    dataset = Dataset.query.get_or_404(dataset_id)
    columns = json.loads(dataset.column_names) if dataset.column_names else []
    return jsonify({"columns": columns})
