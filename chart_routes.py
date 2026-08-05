# -*- coding: utf-8 -*-
# chart_routes.py - 图表保存与独立展示

import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import text

from models import db, Dataset, SavedChart

chart_bp = Blueprint("chart", __name__, url_prefix="/chart")


@chart_bp.route("/save", methods=["POST"])
@login_required
def save():
    """保存当前图表配置"""
    dataset_id = request.form.get("dataset_id", type=int)
    chart_type = request.form.get("chart_type", "").strip()
    x_column = request.form.get("x_column", "").strip()
    y_column = request.form.get("y_column", "").strip()
    name = request.form.get("name", "").strip()

    if not all([dataset_id, chart_type, x_column, y_column]):
        flash("缺少图表配置参数", "danger")
        return redirect(url_for("chart.list_charts"))

    dataset = Dataset.query.get(dataset_id)
    if not dataset:
        flash("数据集不存在", "danger")
        return redirect(url_for("chart.list_charts"))

    if not name:
        name = f"{dataset.name} - {chart_type}"

    chart = SavedChart(
        name=name,
        dataset_id=dataset_id,
        chart_type=chart_type,
        x_column=x_column,
        y_column=y_column,
        user_id=current_user.id,
    )
    db.session.add(chart)
    db.session.commit()
    flash("图表已保存", "success")
    return redirect(url_for("chart.list_charts"))


@chart_bp.route("/charts")
@login_required
def list_charts():
    """已保存图表列表"""
    charts = SavedChart.query.order_by(SavedChart.created_at.desc()).all()
    return render_template("charts.html", charts=charts)


@chart_bp.route("/chart/<int:chart_id>")
@login_required
def view_chart(chart_id):
    """独立查看某个已保存的图表"""
    chart = SavedChart.query.get_or_404(chart_id)
    dataset = Dataset.query.get(chart.dataset_id)
    if not dataset:
        flash("关联的数据集已被删除", "warning")
        return redirect(url_for("chart.list_charts"))

    columns = json.loads(dataset.column_names) if dataset.column_names else []

    # 查找列索引
    try:
        x_idx = columns.index(chart.x_column)
        y_idx = columns.index(chart.y_column)
    except ValueError:
        flash("图表配置中的列已不存在", "warning")
        return redirect(url_for("chart.list_charts"))

    # 查询数据
    try:
        query = f'SELECT * FROM "{dataset.table_name}" ORDER BY id'
        result = db.session.execute(text(query))
        rows_raw = result.fetchall()
        data_rows = [list(row)[1:] for row in rows_raw]
    except Exception:
        data_rows = []

    return render_template(
        "view_chart.html",
        chart=chart,
        dataset=dataset,
        columns=columns,
        data_rows=data_rows,
        x_idx=x_idx,
        y_idx=y_idx,
    )


@chart_bp.route("/chart/<int:chart_id>/delete", methods=["POST"])
@login_required
def delete_chart(chart_id):
    chart = SavedChart.query.get_or_404(chart_id)
    db.session.delete(chart)
    db.session.commit()
    flash("图表已删除", "success")
    return redirect(url_for("chart.list_charts"))
