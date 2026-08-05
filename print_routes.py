# -*- coding: utf-8 -*-
# print_routes.py - 3D打印工艺参数计算器

import math
from flask import Blueprint, render_template, request
from flask_login import login_required

print_bp = Blueprint("print_params", __name__, url_prefix="/print")


# 材料数据库
MATERIALS = {
    "PLA": {
        "density": 1.24,           # g/cm³
        "cost_per_kg": 25,          # ¥/kg
        "nozzle_temp": 200,         # °C
        "bed_temp": 60,             # °C
        "color": "#4CAF50",
        "desc": "易打印，环保可降解，适合初学者",
    },
    "ABS": {
        "density": 1.04,
        "cost_per_kg": 22,
        "nozzle_temp": 240,
        "bed_temp": 100,
        "color": "#FF9800",
        "desc": "强度高，耐热好，需要热床和封闭环境",
    },
    "PETG": {
        "density": 1.27,
        "cost_per_kg": 28,
        "nozzle_temp": 235,
        "bed_temp": 80,
        "color": "#2196F3",
        "desc": "兼顾强度和易用性，耐化学腐蚀",
    },
    "TPU": {
        "density": 1.20,
        "cost_per_kg": 35,
        "nozzle_temp": 225,
        "bed_temp": 60,
        "color": "#9C27B0",
        "desc": "柔性材料，弹性好，耐磨",
    },
    "Nylon": {
        "density": 1.14,
        "cost_per_kg": 40,
        "nozzle_temp": 260,
        "bed_temp": 100,
        "color": "#607D8B",
        "desc": "高强度，高韧性，需干燥保存",
    },
    "PC": {
        "density": 1.20,
        "cost_per_kg": 45,
        "nozzle_temp": 275,
        "bed_temp": 110,
        "color": "#E91E63",
        "desc": "极高强度和耐热，打印难度大",
    },
    "树脂": {
        "density": 1.10,
        "cost_per_kg": 50,
        "nozzle_temp": 25,
        "bed_temp": 0,
        "color": "#00BCD4",
        "desc": "光固化树脂，精度极高，表面光滑",
    },
}


def calc_results(material, layer_height, infill, speed, wall_thickness, part_volume, nozzle_dia=0.4):
    """根据参数计算打印结果"""
    mat = MATERIALS.get(material, MATERIALS["PLA"])

    # 材料重量 (g) = 体积 (cm³) × 密度 (g/cm³) × 填充率
    solid_volume = part_volume * (infill / 100.0)

    # 考虑壁厚：简单近似 (外壁占比约 15% 完全填充)
    wall_ratio = min(0.3, wall_thickness / nozzle_dia * 0.1)
    effective_solid = solid_volume + (part_volume - solid_volume) * wall_ratio

    material_weight = part_volume * mat["density"] * effective_solid / part_volume

    # 打印时间 (分钟)
    # 简化公式: 时间 ∝ 体积 / (层高 × 喷嘴直径 × 速度)
    # 基准: 8cm³ / (0.2mm * 0.4mm * 50mm/s) ≈ 约 50 分钟
    base_time = 50.0
    time_factor = (layer_height * nozzle_dia * speed) / (0.2 * 0.4 * 50.0)
    if time_factor < 0.01:
        time_factor = 0.01
    print_time = base_time * (part_volume / 8.0) / time_factor

    # 成本 (¥)
    material_cost = material_weight * mat["cost_per_kg"] / 1000.0
    electricity_cost = print_time / 60.0 * 0.5  # 0.5 ¥/小时
    total_cost = round(material_cost + electricity_cost, 2)

    # 表面质量评分 (1-10)
    quality = 10 - (layer_height - 0.05) / (0.3 - 0.05) * 8
    quality = max(1, min(10, round(quality, 1)))

    # 强度评分 (1-10)
    strength_base = {"PLA": 6, "ABS": 7, "PETG": 7, "TPU": 3, "Nylon": 9, "PC": 10, "树脂": 8}
    strength = strength_base.get(material, 6) * (0.4 + 0.6 * infill / 100.0)
    strength = max(1, min(10, round(strength, 1)))

    return {
        "print_time": round(print_time, 1),
        "material_weight": round(material_weight, 2),
        "total_cost": total_cost,
        "surface_quality": quality,
        "strength": strength,
        "nozzle_temp": mat["nozzle_temp"],
        "bed_temp": mat["bed_temp"],
    }


@print_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    """3D打印参数计算器"""
    results = None
    compare_data = []
    params = {
        "material": "PLA",
        "layer_height": 0.2,
        "infill": 20,
        "speed": 50,
        "wall_thickness": 1.2,
        "part_volume": 8.0,
        "nozzle_dia": 0.4,
    }

    if request.method == "POST":
        params["material"] = request.form.get("material", "PLA")
        params["layer_height"] = float(request.form.get("layer_height", 0.2))
        params["infill"] = int(request.form.get("infill", 20))
        params["speed"] = int(request.form.get("speed", 50))
        params["wall_thickness"] = float(request.form.get("wall_thickness", 1.2))
        params["part_volume"] = float(request.form.get("part_volume", 8.0))
        params["nozzle_dia"] = float(request.form.get("nozzle_dia", 0.4))

        results = calc_results(
            material=params["material"],
            layer_height=params["layer_height"],
            infill=params["infill"],
            speed=params["speed"],
            wall_thickness=params["wall_thickness"],
            part_volume=params["part_volume"],
            nozzle_dia=params["nozzle_dia"],
        )

        # 生成对比数据：同一参数下不同填充率的对比
        for inf in [10, 20, 30, 50, 80, 100]:
            r = calc_results(
                material=params["material"],
                layer_height=params["layer_height"],
                infill=inf,
                speed=params["speed"],
                wall_thickness=params["wall_thickness"],
                part_volume=params["part_volume"],
                nozzle_dia=params["nozzle_dia"],
            )
            compare_data.append({
                "infill": inf,
                "time": r["print_time"],
                "weight": r["material_weight"],
                "cost": r["total_cost"],
                "strength": r["strength"],
            })

    return render_template(
        "print_params.html",
        materials=MATERIALS,
        params=params,
        results=results,
        compare_data=compare_data,
    )
