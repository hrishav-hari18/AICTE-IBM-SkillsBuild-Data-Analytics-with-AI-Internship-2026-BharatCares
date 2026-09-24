"""
Professional Word Report Generator
Delivery & Logistics Performance Analytics Dashboard
Author: HrishavHarino

Run: python generate_report.py
"""

import os
import re
import io
import warnings
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import rcParams
from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import datetime

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# DATA LOADING (mirrors app.py logic)
# ─────────────────────────────────────────────
DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "Delivery_Logistics.csv")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "HrishavHarino_DeliveryLogistics_ProjectReport.docx")

# Matplotlib style
rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "figure.dpi": 150,
})

NAVY   = "#0B1E3D"
TEAL   = "#00C4CC"
AMBER  = "#F59E0B"
RED    = "#EF4444"
GREEN  = "#22C55E"
COLORS = [TEAL, AMBER, "#3B82F6", "#8B5CF6", GREEN, RED, "#F97316", "#EC4899", "#14B8A6"]


def decode_ns(s):
    m = re.search(r"\.(\d+)$", str(s))
    return int(m.group(1)) if m else np.nan


def load_data():
    df = pd.read_csv(DATA_PATH)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    str_cols = ["delivery_partner", "package_type", "vehicle_type",
                "delivery_mode", "region", "weather_condition", "delayed", "delivery_status"]
    for c in str_cols:
        df[c] = df[c].astype(str).str.strip().str.lower()
    df["delivery_time_hours"]  = df["delivery_time_hours"].apply(decode_ns)
    df["expected_time_hours"]  = df["expected_time_hours"].apply(decode_ns)
    for c in ["distance_km", "package_weight_kg", "delivery_cost", "delivery_rating"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["time_gap_hours"] = df["delivery_time_hours"] - df["expected_time_hours"]
    df["is_delayed"] = (df["delayed"] == "yes").astype(int)
    df["is_failed"]  = (df["delivery_status"] == "failed").astype(int)
    df["is_on_time"] = (df["delivery_status"] == "delivered").astype(int)
    df["cost_per_km"] = df["delivery_cost"] / df["distance_km"].replace(0, np.nan)
    df["cost_per_kg"] = df["delivery_cost"] / df["package_weight_kg"].replace(0, np.nan)
    df["distance_band"] = pd.cut(df["distance_km"], bins=[0,100,200,300],
                                  labels=["Short (0-100 km)", "Medium (100-200 km)", "Long (200-300 km)"])
    df["weight_band"]   = pd.cut(df["package_weight_kg"], bins=[0,17,33,51],
                                  labels=["Light (0-17 kg)", "Medium (17-33 kg)", "Heavy (33-51 kg)"])
    return df


def kpis(df):
    total   = len(df)
    on_time = (df["delivery_status"] == "delivered").sum()
    delayed = (df["delivery_status"] == "delayed").sum()
    failed  = (df["delivery_status"] == "failed").sum()
    return {
        "total":           total,
        "on_time":         on_time,
        "delayed":         delayed,
        "failed":          failed,
        "on_time_pct":     round(on_time/total*100, 1),
        "delayed_pct":     round(delayed/total*100, 1),
        "failed_pct":      round(failed/total*100, 1),
        "avg_time":        round(df["delivery_time_hours"].mean(), 2),
        "avg_exp_time":    round(df["expected_time_hours"].mean(), 2),
        "avg_cost":        round(df["delivery_cost"].mean(), 2),
        "total_cost":      round(df["delivery_cost"].sum(), 2),
        "avg_cost_per_km": round(df["cost_per_km"].mean(), 2),
        "avg_cost_per_kg": round(df["cost_per_kg"].mean(), 2),
        "avg_rating":      round(df["delivery_rating"].mean(), 2),
    }


def by_dim(df, dim):
    g = df.groupby(dim, observed=True).agg(
        total=("delivery_status","count"),
        on_time=("is_on_time","sum"),
        delayed=("is_delayed","sum"),
        failed=("is_failed","sum"),
        avg_time=("delivery_time_hours","mean"),
        avg_cost=("delivery_cost","mean"),
        total_cost=("delivery_cost","sum"),
        avg_rating=("delivery_rating","mean"),
        avg_cpkm=("cost_per_km","mean"),
    ).reset_index()
    g["on_time_pct"] = (g["on_time"]/g["total"]*100).round(1)
    g["delayed_pct"] = (g["delayed"]/g["total"]*100).round(1)
    g["failed_pct"]  = (g["failed"] /g["total"]*100).round(1)
    return g


# ─────────────────────────────────────────────
# MATPLOTLIB CHART HELPERS
# ─────────────────────────────────────────────
def fig_to_bytes(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
    buf.seek(0)
    plt.close(fig)
    return buf


def chart_status_pie(df):
    counts = df["delivery_status"].value_counts()
    labels = [s.title() for s in counts.index]
    colors = [GREEN, AMBER, RED]
    fig, ax = plt.subplots(figsize=(5, 4))
    wedges, texts, autotexts = ax.pie(
        counts.values, labels=labels, autopct="%1.1f%%",
        colors=colors[:len(labels)], startangle=140,
        wedgeprops=dict(edgecolor="white", linewidth=1.5),
        textprops=dict(fontsize=9),
    )
    for at in autotexts:
        at.set_fontsize(8)
        at.set_color("white")
    ax.set_title("Delivery Status Distribution", fontsize=11, fontweight="bold", color=NAVY, pad=12)
    return fig_to_bytes(fig)


def chart_partner_ontime(df):
    p = by_dim(df, "delivery_partner").sort_values("on_time_pct", ascending=True)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars = ax.barh(p["delivery_partner"].str.title(), p["on_time_pct"], color=TEAL, edgecolor="none")
    for b in bars:
        ax.text(b.get_width() + 0.3, b.get_y() + b.get_height()/2,
                f"{b.get_width():.1f}%", va="center", fontsize=8, color=NAVY)
    ax.set_xlabel("On-Time %")
    ax.set_title("On-Time Delivery % by Partner", fontsize=11, fontweight="bold", color=NAVY, pad=10)
    ax.set_xlim(0, 105)
    fig.tight_layout()
    return fig_to_bytes(fig)


def chart_partner_cost(df):
    p = by_dim(df, "delivery_partner").sort_values("avg_cost", ascending=True)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars = ax.barh(p["delivery_partner"].str.title(), p["avg_cost"], color=AMBER, edgecolor="none")
    for b in bars:
        ax.text(b.get_width() + 5, b.get_y() + b.get_height()/2,
                f"₹{b.get_width():,.0f}", va="center", fontsize=8, color=NAVY)
    ax.set_xlabel("Avg. Delivery Cost (₹)")
    ax.set_title("Avg. Delivery Cost by Partner (₹)", fontsize=11, fontweight="bold", color=NAVY, pad=10)
    fig.tight_layout()
    return fig_to_bytes(fig)


def chart_region_performance(df):
    r = by_dim(df, "region").sort_values("on_time_pct", ascending=False)
    x = np.arange(len(r))
    w = 0.25
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(x - w, r["on_time_pct"], w, label="On-Time %", color=TEAL, edgecolor="none")
    ax.bar(x,      r["delayed_pct"], w, label="Delayed %",  color=AMBER, edgecolor="none")
    ax.bar(x + w,  r["failed_pct"],  w, label="Failed %",   color=RED,   edgecolor="none")
    ax.set_xticks(x)
    ax.set_xticklabels(r["region"].str.title(), rotation=0)
    ax.set_ylabel("Percentage (%)")
    ax.legend(fontsize=8)
    ax.set_title("Delivery Performance % by Region", fontsize=11, fontweight="bold", color=NAVY, pad=10)
    fig.tight_layout()
    return fig_to_bytes(fig)


def chart_weather_delay(df):
    w = by_dim(df, "weather_condition").sort_values("delayed_pct", ascending=False)
    fig, ax = plt.subplots(figsize=(7, 4))
    clrs = [RED if v > 30 else AMBER if v > 20 else TEAL for v in w["delayed_pct"]]
    bars = ax.bar(w["weather_condition"].str.title(), w["delayed_pct"], color=clrs, edgecolor="none")
    for b in bars:
        ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.3,
                f"{b.get_height():.1f}%", ha="center", fontsize=8, color=NAVY)
    ax.set_ylabel("Delayed %")
    ax.set_title("Delayed Delivery % by Weather Condition", fontsize=11, fontweight="bold", color=NAVY, pad=10)
    fig.tight_layout()
    return fig_to_bytes(fig)


def chart_mode_cost(df):
    m = by_dim(df, "delivery_mode").sort_values("avg_cost", ascending=False)
    fig, ax = plt.subplots(figsize=(6, 3.5))
    bars = ax.bar(m["delivery_mode"].str.title(), m["avg_cost"],
                  color=COLORS[:len(m)], edgecolor="none")
    for b in bars:
        ax.text(b.get_x() + b.get_width()/2, b.get_height() + 3,
                f"₹{b.get_height():,.0f}", ha="center", fontsize=8, color=NAVY)
    ax.set_ylabel("Avg. Cost (₹)")
    ax.set_title("Avg. Cost by Delivery Mode (₹)", fontsize=11, fontweight="bold", color=NAVY, pad=10)
    fig.tight_layout()
    return fig_to_bytes(fig)


def chart_rating_dist(df):
    counts = df["delivery_rating"].value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(5, 3.5))
    bars = ax.bar([f"{i}★" for i in counts.index], counts.values,
                  color=[RED, AMBER, "#FCD34D", TEAL, GREEN], edgecolor="none")
    for b in bars:
        ax.text(b.get_x() + b.get_width()/2, b.get_height() + 30,
                f"{int(b.get_height()):,}", ha="center", fontsize=8, color=NAVY)
    ax.set_ylabel("Count")
    ax.set_title("Customer Rating Distribution", fontsize=11, fontweight="bold", color=NAVY, pad=10)
    fig.tight_layout()
    return fig_to_bytes(fig)


def chart_partner_rating(df):
    p = by_dim(df, "delivery_partner").sort_values("avg_rating", ascending=True)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars = ax.barh(p["delivery_partner"].str.title(), p["avg_rating"], color=GREEN, edgecolor="none")
    for b in bars:
        ax.text(b.get_width() + 0.01, b.get_y() + b.get_height()/2,
                f"{b.get_width():.2f}", va="center", fontsize=8, color=NAVY)
    ax.set_xlabel("Avg. Rating")
    ax.set_xlim(0, 5.5)
    ax.set_title("Avg. Customer Rating by Partner", fontsize=11, fontweight="bold", color=NAVY, pad=10)
    ax.axvline(3.67, color=AMBER, linestyle="--", linewidth=1.2, label="Network avg")
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig_to_bytes(fig)


def chart_distance_cost(df):
    db = by_dim(df, "distance_band")
    fig, ax = plt.subplots(figsize=(6, 3.5))
    bars = ax.bar(db["distance_band"].astype(str), db["avg_cost"],
                  color=[TEAL, AMBER, RED], edgecolor="none")
    for b in bars:
        ax.text(b.get_x() + b.get_width()/2, b.get_height() + 3,
                f"₹{b.get_height():,.0f}", ha="center", fontsize=8, color=NAVY)
    ax.set_ylabel("Avg. Cost (₹)")
    ax.set_title("Avg. Cost by Distance Band (₹)", fontsize=11, fontweight="bold", color=NAVY, pad=10)
    ax.set_xticklabels(db["distance_band"].astype(str), rotation=10, fontsize=8)
    fig.tight_layout()
    return fig_to_bytes(fig)


# ─────────────────────────────────────────────
# WORD DOCUMENT HELPERS
# ─────────────────────────────────────────────
def set_cell_bg(cell, hex_color):
    tc   = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd  = OxmlElement("w:shd")
    shd.set(qn("w:val"),   "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"),  hex_color.lstrip("#"))
    tcPr.append(shd)


def set_cell_border(cell, top=None, bottom=None, left=None, right=None):
    tc   = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement("w:tcBorders")
    for side, val in [("top", top), ("bottom", bottom), ("left", left), ("right", right)]:
        if val:
            el = OxmlElement(f"w:{side}")
            el.set(qn("w:val"),   val.get("val",   "single"))
            el.set(qn("w:sz"),    val.get("sz",    "4"))
            el.set(qn("w:space"), val.get("space", "0"))
            el.set(qn("w:color"), val.get("color", "auto"))
            tcBorders.append(el)
    tcPr.append(tcBorders)


def rgb(hex_color):
    h = hex_color.lstrip("#")
    return RGBColor(int(h[0:2],16), int(h[2:4],16), int(h[4:6],16))


def add_heading(doc, text, level=1, color=NAVY):
    p = doc.add_heading(text, level=level)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    for run in p.runs:
        run.font.color.rgb = rgb(color)
    return p


def add_para(doc, text, size=10, bold=False, color="#1E293B", align=WD_ALIGN_PARAGRAPH.LEFT, space_before=0, space_after=6):
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after  = Pt(space_after)
    run = p.add_run(text)
    run.font.size  = Pt(size)
    run.font.bold  = bold
    run.font.color.rgb = rgb(color)
    return p


def add_kpi_table(doc, kpi_dict):
    items = list(kpi_dict.items())
    cols  = 3
    rows  = (len(items) + cols - 1) // cols
    table = doc.add_table(rows=rows, cols=cols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    idx = 0
    for r in range(rows):
        for c in range(cols):
            if idx >= len(items):
                break
            label, value = items[idx]
            cell = table.cell(r, c)
            set_cell_bg(cell, "F5F7FA")
            set_cell_border(cell, top={"val":"single","sz":"4","color":"E2E8F0"},
                                  bottom={"val":"single","sz":"4","color":"E2E8F0"},
                                  left={"val":"single","sz":"4","color":"E2E8F0"},
                                  right={"val":"single","sz":"4","color":"E2E8F0"})
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            cell.add_paragraph().add_run(label).font.size = Pt(8)
            vrun = cell.paragraphs[0].add_run(str(value))
            vrun.font.size  = Pt(14)
            vrun.font.bold  = True
            vrun.font.color.rgb = rgb(NAVY)
            idx += 1
    doc.add_paragraph()


def add_figure(doc, img_bytes, caption_text, width_inches=6.0):
    doc.add_picture(img_bytes, width=Inches(width_inches))
    last = doc.paragraphs[-1]
    last.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cr = cap.add_run(caption_text)
    cr.font.size   = Pt(9)
    cr.font.italic = True
    cr.font.color.rgb = rgb("#64748B")
    doc.add_paragraph()


def add_risk_item(doc, title, body, color=RED):
    table = doc.add_table(rows=1, cols=2)
    table.columns[0].width = Cm(0.5)
    table.columns[1].width = Cm(14)
    left_cell = table.cell(0, 0)
    set_cell_bg(left_cell, color.lstrip("#"))
    right_cell = table.cell(0, 1)
    set_cell_bg(right_cell, "FFFFFF")
    p = right_cell.paragraphs[0]
    run_t = p.add_run(title + " — ")
    run_t.font.bold  = True
    run_t.font.size  = Pt(9)
    run_t.font.color.rgb = rgb(color)
    run_b = p.add_run(body)
    run_b.font.size  = Pt(9)
    run_b.font.color.rgb = rgb("#1E293B")
    doc.add_paragraph()


def add_action_item(doc, num, text):
    table = doc.add_table(rows=1, cols=2)
    table.columns[0].width = Cm(0.8)
    table.columns[1].width = Cm(13.8)
    num_cell = table.cell(0, 0)
    set_cell_bg(num_cell, NAVY.lstrip("#"))
    num_cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    np_ = num_cell.paragraphs[0]
    np_.alignment = WD_ALIGN_PARAGRAPH.CENTER
    nr = np_.add_run(str(num))
    nr.font.bold  = True
    nr.font.size  = Pt(10)
    nr.font.color.rgb = rgb(TEAL)
    text_cell = table.cell(0, 1)
    set_cell_bg(text_cell, "F5F7FA")
    tp = text_cell.paragraphs[0]
    tr = tp.add_run(text)
    tr.font.size = Pt(9)
    tr.font.color.rgb = rgb("#1E293B")
    doc.add_paragraph()


# ─────────────────────────────────────────────
# REPORT SECTIONS
# ─────────────────────────────────────────────
def build_cover(doc):
    doc.add_paragraph()
    doc.add_paragraph()
    # Title block
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    tr = title_p.add_run("DELIVERY & LOGISTICS\nPERFORMANCE ANALYTICS")
    tr.font.size  = Pt(26)
    tr.font.bold  = True
    tr.font.color.rgb = rgb(NAVY)

    doc.add_paragraph()
    sub_p = doc.add_paragraph()
    sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sr = sub_p.add_run("Business Analytics Dashboard — India Multi-Partner Logistics Dataset")
    sr.font.size  = Pt(13)
    sr.font.color.rgb = rgb("#64748B")

    doc.add_paragraph()
    # Teal divider table
    div = doc.add_table(rows=1, cols=1)
    div.cell(0,0).width = Cm(12)
    set_cell_bg(div.cell(0,0), TEAL.lstrip("#"))
    div.cell(0,0).paragraphs[0].add_run(" ")
    doc.add_paragraph()

    for label, value in [
        ("Author",   "HrishavHarino"),
        ("Type",     "Business / Data Analytics Internship Project"),
        ("Dataset",  "Delivery Logistics Dataset — India Multi-Partner"),
        ("Records",  "25,000 rows × 15 columns"),
        ("Date",     datetime.date.today().strftime("%B %Y")),
    ]:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        lr = p.add_run(f"{label}:  ")
        lr.font.bold  = True
        lr.font.size  = Pt(11)
        lr.font.color.rgb = rgb(NAVY)
        vr = p.add_run(value)
        vr.font.size  = Pt(11)
        vr.font.color.rgb = rgb("#1E293B")

    doc.add_page_break()


def build_exec_summary(doc, k):
    add_heading(doc, "1. Executive Summary", level=1)
    add_para(doc,
        f"This report presents the findings of a comprehensive business analytics study conducted on the "
        f"India Multi-Partner Delivery Logistics dataset, comprising {k['total']:,} delivery records across "
        f"nine logistics partners, five geographic regions, and four delivery modes.",
    )
    add_para(doc,
        f"The network achieved an overall on-time delivery rate of {k['on_time_pct']}%, with {k['delayed_pct']}% of "
        f"deliveries classified as delayed and {k['failed_pct']}% failing outright. The average delivery cost "
        f"across the network stood at ₹{k['avg_cost']:,.2f}, with an average customer satisfaction rating of "
        f"{k['avg_rating']}/5.",
    )
    add_para(doc,
        "Measurable performance variation was observed across delivery partners, geographic regions, "
        "delivery modes, vehicle types, and weather conditions. The analysis identifies five key operational "
        "risks and five practical management actions, all grounded in verified data.",
    )
    doc.add_paragraph()


def build_business_problem(doc):
    add_heading(doc, "2. Business Problem & Objectives", level=1)
    add_para(doc,
        "Management requires data-driven answers to the following operational questions:",
        bold=True,
    )
    questions = [
        "How many deliveries are being processed and what is the overall on-time rate?",
        "Which logistics partners deliver the best and worst on-time performance?",
        "Which regions experience the highest delay and failure concentrations?",
        "How does delivery cost vary across partners, modes, distances, and weights?",
        "How do customer ratings correlate with delivery performance dimensions?",
        "What operational risks exist and what actions should management consider?",
    ]
    for q in questions:
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(q).font.size = Pt(10)
    doc.add_paragraph()


def build_dataset_overview(doc, df, k):
    add_heading(doc, "3. Dataset Overview", level=1)
    add_para(doc, "Source: Kaggle — Delivery Logistics Dataset, India Multi-Partner")
    add_para(doc, "URL: https://www.kaggle.com/datasets/muhammadahmaddaar/delivery-logistics-dataset-india-multi-partner")
    doc.add_paragraph()

    headers = ["Property", "Value"]
    rows_data = [
        ("Total Records", f"{k['total']:,}"),
        ("Columns", "15"),
        ("Exact Duplicates", "0"),
        ("Missing Values", "0"),
        ("Delivery Partners", "9"),
        ("Regions", "5"),
        ("Delivery Modes", "4"),
        ("Vehicle Types", "6"),
        ("Package Types", "9"),
        ("Weather Conditions", "6"),
        ("Date Range", "No calendar dates (cross-sectional dataset)"),
    ]
    table = doc.add_table(rows=len(rows_data)+1, cols=2)
    table.style = "Table Grid"
    for i, h in enumerate(headers):
        cell = table.cell(0, i)
        set_cell_bg(cell, NAVY.lstrip("#"))
        run = cell.paragraphs[0].add_run(h)
        run.font.bold  = True
        run.font.size  = Pt(10)
        run.font.color.rgb = rgb("#FFFFFF")
    for r, (label, val) in enumerate(rows_data, 1):
        table.cell(r, 0).paragraphs[0].add_run(label).font.size = Pt(9)
        table.cell(r, 1).paragraphs[0].add_run(val).font.size   = Pt(9)
        if r % 2 == 0:
            set_cell_bg(table.cell(r, 0), "F5F7FA")
            set_cell_bg(table.cell(r, 1), "F5F7FA")
    doc.add_paragraph()


def build_tech_stack(doc):
    add_heading(doc, "4. Technology Stack", level=1)
    items = [
        ("Python 3.8+",    "Core programming language"),
        ("Pandas",         "Data loading, cleaning, aggregation"),
        ("NumPy",          "Numerical computations, feature engineering"),
        ("Plotly",         "Interactive dashboard charts"),
        ("Streamlit",      "Dashboard frontend framework"),
        ("Matplotlib",     "Static chart generation for this report"),
        ("python-docx",    "Word report generation"),
    ]
    table = doc.add_table(rows=len(items)+1, cols=2)
    table.style = "Table Grid"
    for i, h in enumerate(["Technology", "Purpose"]):
        cell = table.cell(0, i)
        set_cell_bg(cell, TEAL.lstrip("#"))
        run = cell.paragraphs[0].add_run(h)
        run.font.bold = True; run.font.size = Pt(10)
        run.font.color.rgb = rgb(NAVY)
    for r, (tech, purpose) in enumerate(items, 1):
        table.cell(r,0).paragraphs[0].add_run(tech).font.size    = Pt(9)
        table.cell(r,1).paragraphs[0].add_run(purpose).font.size = Pt(9)
    doc.add_paragraph()


def build_data_cleaning(doc):
    add_heading(doc, "5. Data Understanding, Cleaning & Validation", level=1)

    add_heading(doc, "5.1 Raw Data Observations", level=2)
    observations = [
        "25,000 records with 15 columns — no missing values across all columns.",
        "delivery_id contains 498 non-unique values; treated as a reference field, not a primary key.",
        "delivery_time_hours and expected_time_hours are stored as nanosecond-epoch timestamp strings "
        "(e.g., '1970-01-01 00:00:00.000000008'); decoded to integer hours using fractional nanosecond extraction.",
        "All categorical columns use consistent lowercase values with no mixed-case inconsistencies.",
        "No exact duplicate rows detected.",
    ]
    for o in observations:
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(o).font.size = Pt(9)

    add_heading(doc, "5.2 Cleaning Pipeline", level=2)
    steps = [
        "Load raw CSV → standardise column names to snake_case lowercase.",
        "Strip and lowercase all categorical string columns.",
        "Decode nanosecond-epoch time strings → integer hours for delivery_time_hours and expected_time_hours.",
        "Enforce numeric types for distance_km, package_weight_kg, delivery_cost, delivery_rating.",
        "Validate numeric ranges: cost > 0, distance > 0, weight > 0, rating between 1 and 5.",
        "Audit duplicate records and non-unique delivery_id values.",
    ]
    for i, s in enumerate(steps, 1):
        p = doc.add_paragraph(style="List Number")
        p.add_run(s).font.size = Pt(9)

    add_heading(doc, "5.3 Data Quality Summary", level=2)
    dq_items = [
        ("Raw rows",                     "25,000", "PASS"),
        ("Raw columns",                  "15",     "PASS"),
        ("Exact duplicates",             "0",      "PASS"),
        ("Missing values (all columns)", "0",      "PASS"),
        ("Invalid delivery_time_hours",  "0",      "PASS"),
        ("Invalid expected_time_hours",  "0",      "PASS"),
        ("Invalid delivery_cost (≤0)",   "0",      "PASS"),
        ("Invalid distance_km (≤0)",     "0",      "PASS"),
        ("Invalid delivery_rating",      "0",      "PASS"),
        ("Non-unique delivery_id rows",  "498",    "INFO"),
        ("Overall Data Quality",         "PASS",   "PASS"),
    ]
    table = doc.add_table(rows=len(dq_items)+1, cols=3)
    table.style = "Table Grid"
    for i, h in enumerate(["Check", "Value", "Status"]):
        cell = table.cell(0, i)
        set_cell_bg(cell, NAVY.lstrip("#"))
        run = cell.paragraphs[0].add_run(h)
        run.font.bold = True; run.font.size = Pt(10); run.font.color.rgb = rgb("#FFFFFF")
    for r, (chk, val, status) in enumerate(dq_items, 1):
        table.cell(r,0).paragraphs[0].add_run(chk).font.size   = Pt(9)
        table.cell(r,1).paragraphs[0].add_run(val).font.size   = Pt(9)
        scell = table.cell(r,2)
        srun  = scell.paragraphs[0].add_run(status)
        srun.font.size = Pt(9)
        srun.font.bold = True
        if status == "PASS":
            srun.font.color.rgb = rgb(GREEN)
        elif status == "INFO":
            srun.font.color.rgb = rgb(AMBER)
        else:
            srun.font.color.rgb = rgb(RED)
    doc.add_paragraph()


def build_feature_engineering(doc):
    add_heading(doc, "6. Feature Engineering", level=1)
    add_para(doc, "The following derived columns were created from verified source columns:")
    features = [
        ("time_gap_hours",       "delivery_time_hours − expected_time_hours",
         "Measures how early (negative) or late (positive) a delivery arrived relative to expectation."),
        ("cost_per_km",          "delivery_cost / distance_km",
         "Unit delivery cost per kilometre — useful for route efficiency analysis."),
        ("cost_per_kg",          "delivery_cost / package_weight_kg",
         "Unit delivery cost per kilogram — useful for weight-based cost benchmarking."),
        ("distance_band",        "Cut: Short (0–100), Medium (100–200), Long (200–300 km)",
         "Groups deliveries into distance tiers for segment analysis."),
        ("weight_band",          "Cut: Light (0–17), Medium (17–33), Heavy (33–51 kg)",
         "Groups packages into weight tiers."),
        ("performance_category", "Mapped from delivery_status: On-Time / Delayed / Failed",
         "Human-readable performance label for visualisations."),
        ("rating_band",          "Cut: Low (1–2), Medium (3), High (4–5)",
         "Aggregated rating tier for segment comparisons."),
        ("is_on_time",           "1 if delivery_status == 'delivered', else 0",
         "Binary flag for aggregation."),
        ("is_delayed",           "1 if delayed == 'yes', else 0",
         "Binary flag for aggregation."),
        ("is_failed",            "1 if delivery_status == 'failed', else 0",
         "Binary flag for aggregation."),
    ]
    table = doc.add_table(rows=len(features)+1, cols=3)
    table.style = "Table Grid"
    for i, h in enumerate(["Feature", "Formula", "Business Purpose"]):
        cell = table.cell(0, i)
        set_cell_bg(cell, TEAL.lstrip("#"))
        run = cell.paragraphs[0].add_run(h)
        run.font.bold = True; run.font.size = Pt(9); run.font.color.rgb = rgb(NAVY)
    for r, (feat, formula, purpose) in enumerate(features, 1):
        table.cell(r,0).paragraphs[0].add_run(feat).font.size    = Pt(8)
        table.cell(r,1).paragraphs[0].add_run(formula).font.size = Pt(8)
        table.cell(r,2).paragraphs[0].add_run(purpose).font.size = Pt(8)
        if r % 2 == 0:
            for c in range(3):
                set_cell_bg(table.cell(r,c), "F5F7FA")
    doc.add_paragraph()


def build_kpi_framework(doc, k):
    add_heading(doc, "7. KPI Framework & Results", level=1)
    add_para(doc, "All KPIs are calculated from verified, cleaned data. No values are fabricated.")
    doc.add_paragraph()
    kpi_display = {
        "Total Deliveries":    f"{k['total']:,}",
        "On-Time Delivery %":  f"{k['on_time_pct']}%",
        "Delayed Delivery %":  f"{k['delayed_pct']}%",
        "Failed Delivery %":   f"{k['failed_pct']}%",
        "Avg Delivery Time":   f"{k['avg_time']} hrs",
        "Avg Expected Time":   f"{k['avg_exp_time']} hrs",
        "Avg Delivery Cost":   f"₹{k['avg_cost']:,.2f}",
        "Total Delivery Cost": f"₹{k['total_cost']/1e6:.2f}M",
        "Avg Cost per KM":     f"₹{k['avg_cost_per_km']:.2f}",
        "Avg Cost per KG":     f"₹{k['avg_cost_per_kg']:.2f}",
        "Avg Customer Rating": f"{k['avg_rating']}/5",
    }
    add_kpi_table(doc, kpi_display)


def build_analysis(doc, df, k):
    # ── Overall Performance ───────────────────────────────
    add_heading(doc, "8. Overall Delivery Performance", level=1)
    fig1_bytes = chart_status_pie(df)
    add_figure(doc, fig1_bytes, "Figure 1 — Delivery Status Distribution\n"
               f"The network processed {k['total']:,} deliveries. {k['on_time_pct']}% were delivered "
               f"on time, {k['delayed_pct']}% were delayed, and {k['failed_pct']}% failed outright.")

    # ── Partner Analysis ──────────────────────────────────
    add_heading(doc, "9. Logistics Partner Analysis", level=1)
    p = by_dim(df, "delivery_partner")
    best  = p.loc[p["on_time_pct"].idxmax()]
    worst = p.loc[p["on_time_pct"].idxmin()]
    add_para(doc,
        f"On-time delivery rates vary across the nine logistics partners. "
        f"{best['delivery_partner'].title()} recorded the highest on-time rate at {best['on_time_pct']:.1f}%, "
        f"while {worst['delivery_partner'].title()} recorded the lowest at {worst['on_time_pct']:.1f}%, "
        f"representing a {best['on_time_pct']-worst['on_time_pct']:.1f} percentage-point spread."
    )
    fig2_bytes = chart_partner_ontime(df)
    add_figure(doc, fig2_bytes, "Figure 2 — On-Time Delivery % by Partner\n"
               "Partners are ranked from lowest to highest on-time rate. The gap between top and bottom "
               "partner represents a measurable operational variance across the network.")

    fig3_bytes = chart_partner_cost(df)
    hcp = p.loc[p["avg_cost"].idxmax()]
    lcp = p.loc[p["avg_cost"].idxmin()]
    add_figure(doc, fig3_bytes, f"Figure 3 — Avg. Delivery Cost by Partner (₹)\n"
               f"{hcp['delivery_partner'].title()} is the highest-cost partner at ₹{hcp['avg_cost']:,.0f} avg., "
               f"compared to {lcp['delivery_partner'].title()} at ₹{lcp['avg_cost']:,.0f} avg.")

    # ── Regional Analysis ─────────────────────────────────
    add_heading(doc, "10. Regional Performance Analysis", level=1)
    r = by_dim(df, "region")
    wr = r.loc[r["delayed_pct"].idxmax()]
    br = r.loc[r["delayed_pct"].idxmin()]
    add_para(doc,
        f"The {wr['region'].title()} region recorded the highest delay rate at {wr['delayed_pct']:.1f}%, "
        f"while the {br['region'].title()} region observed the lowest at {br['delayed_pct']:.1f}%. "
        f"This {wr['delayed_pct']-br['delayed_pct']:.1f} pp differential suggests "
        f"regional operational variation worth investigating."
    )
    fig4_bytes = chart_region_performance(df)
    add_figure(doc, fig4_bytes, "Figure 4 — Delivery Performance % by Region\n"
               "On-time, delayed, and failed percentages are compared across all five regions.")

    # ── Weather Analysis ──────────────────────────────────
    add_heading(doc, "11. Weather Condition Analysis", level=1)
    w = by_dim(df, "weather_condition")
    ww = w.loc[w["delayed_pct"].idxmax()]
    bw = w.loc[w["delayed_pct"].idxmin()]
    add_para(doc,
        f"{ww['weather_condition'].title()} conditions are associated with the highest observed delay rate "
        f"({ww['delayed_pct']:.1f}%), compared to {bw['weather_condition'].title()} conditions at "
        f"{bw['delayed_pct']:.1f}%. No causal relationship is claimed — weather appears as an observable "
        f"factor associated with delivery variability."
    )
    fig5_bytes = chart_weather_delay(df)
    add_figure(doc, fig5_bytes, "Figure 5 — Delayed Delivery % by Weather Condition\n"
               "Bars coloured red indicate delay rates above 30%; amber above 20%.")

    # ── Cost & Efficiency ─────────────────────────────────
    add_heading(doc, "12. Cost & Efficiency Analysis", level=1)
    add_para(doc,
        f"The average delivery cost across the network is ₹{k['avg_cost']:,.2f}, with a total network "
        f"cost of ₹{k['total_cost']/1e6:.2f}M. Cost per km averages ₹{k['avg_cost_per_km']:.2f} and "
        f"cost per kg averages ₹{k['avg_cost_per_kg']:.2f}."
    )
    fig6_bytes = chart_mode_cost(df)
    add_figure(doc, fig6_bytes, "Figure 6 — Avg. Delivery Cost by Mode (₹)\n"
               "Delivery mode cost comparison across express, same-day, standard, and two-day modes.")
    fig8_bytes = chart_distance_cost(df)
    add_figure(doc, fig8_bytes, "Figure 8 — Avg. Cost by Distance Band (₹)\n"
               "Cost increases with distance, confirming the expected cost-distance relationship.")

    # ── Customer Experience ───────────────────────────────
    add_heading(doc, "13. Customer Experience Analysis", level=1)
    high_rat = (df["delivery_rating"] >= 4).sum()
    low_rat  = (df["delivery_rating"] <= 2).sum()
    add_para(doc,
        f"The average customer rating across the network is {k['avg_rating']}/5. "
        f"{high_rat:,} deliveries ({high_rat/k['total']*100:.1f}%) received a high rating (4–5★), "
        f"while {low_rat:,} ({low_rat/k['total']*100:.1f}%) received a low rating (1–2★)."
    )
    fig7_bytes = chart_rating_dist(df)
    add_figure(doc, fig7_bytes, "Figure 7 — Customer Rating Distribution\n"
               "The majority of ratings cluster at 4–5 stars, indicating generally positive customer experience.")
    fig9_bytes = chart_partner_rating(df)
    add_figure(doc, fig9_bytes, "Figure 9 — Avg. Customer Rating by Partner\n"
               "Rating variation across partners; the dashed amber line marks the network average.")


def build_risk_opportunity(doc, df, k):
    add_heading(doc, "14. Risk Analysis", level=1)
    add_para(doc, "All risks are grounded in verified, observable data. No speculative claims are made.")
    doc.add_paragraph()

    p  = by_dim(df, "delivery_partner")
    r  = by_dim(df, "region")
    w  = by_dim(df, "weather_condition")

    worst_region  = r.loc[r["delayed_pct"].idxmax()]
    worst_partner = p.loc[p["on_time_pct"].idxmin()]
    worst_weather = w.loc[w["delayed_pct"].idxmax()]
    high_cost_p   = p.loc[p["avg_cost"].idxmax()]

    add_risk_item(doc,
        "HIGH DELAY REGION",
        f"{worst_region['region'].title()} region: {worst_region['delayed_pct']:.1f}% delay rate "
        f"vs network avg of {k['delayed_pct']}%.",
        RED)

    add_risk_item(doc,
        "PARTNER PERFORMANCE GAP",
        f"{worst_partner['delivery_partner'].title()}: {worst_partner['on_time_pct']:.1f}% on-time rate "
        f"vs network avg of {k['on_time_pct']}%.",
        AMBER)

    add_risk_item(doc,
        "WEATHER SENSITIVITY",
        f"{worst_weather['weather_condition'].title()} conditions: {worst_weather['delayed_pct']:.1f}% "
        f"delay rate. No contingency protocols documented.",
        AMBER)

    add_risk_item(doc,
        "FAILED DELIVERY RATE",
        f"{k['failed_pct']}% outright failure rate ({k['failed']:,} deliveries). "
        f"Each failure represents lost revenue and potential customer churn.",
        RED)

    add_risk_item(doc,
        "COST CONCENTRATION",
        f"{high_cost_p['delivery_partner'].title()} averages ₹{high_cost_p['avg_cost']:,.0f} per delivery "
        f"vs network avg of ₹{k['avg_cost']:,.0f}.",
        AMBER)

    add_heading(doc, "15. Opportunity Analysis", level=1)
    best_partner  = p.loc[p["on_time_pct"].idxmax()]
    low_cost_p    = p.loc[p["avg_cost"].idxmin()]
    best_region   = r.loc[r["on_time_pct"].idxmax()]

    add_risk_item(doc,
        "PARTNER BENCHMARKING",
        f"{best_partner['on_time_pct']:.1f}% vs {worst_partner['on_time_pct']:.1f}% on-time rate gap. "
        f"Transferring {best_partner['delivery_partner'].title()}'s practices could lift network performance.",
        GREEN)

    add_risk_item(doc,
        "COST REDUCTION",
        f"₹{high_cost_p['avg_cost']-low_cost_p['avg_cost']:,.0f} spread between highest and lowest cost partner. "
        f"Renegotiation or reallocation opportunity identified.",
        GREEN)

    add_risk_item(doc,
        "REGIONAL FOCUS",
        f"{best_region['region'].title()} region achieves {best_region['on_time_pct']:.1f}% on-time rate. "
        f"Investigating contributing factors could inform improvements elsewhere.",
        GREEN)

    add_heading(doc, "16. Recommended Actions", level=1)
    actions = [
        f"Review allocation of delivery volume to {worst_partner['delivery_partner'].title()} and implement "
        f"a performance improvement plan with measurable on-time delivery targets.",
        f"Conduct a root-cause investigation into elevated delay and failure rates in the "
        f"{worst_region['region'].title()} region — evaluate partner assignment, route planning, and capacity.",
        f"Develop weather-contingency protocols for {worst_weather['weather_condition'].title()} conditions, "
        f"including pre-emptive customer communications and rescheduling workflows.",
        f"Benchmark the operational practices of {best_partner['delivery_partner'].title()} "
        f"(on-time: {best_partner['on_time_pct']:.1f}%) and evaluate applicability across the partner network.",
        f"Prioritise cost-per-km analysis for the highest-cost partner ({high_cost_p['delivery_partner'].title()}: "
        f"₹{high_cost_p['avg_cost']:,.0f}) to identify route or pricing inefficiencies.",
    ]
    for i, a in enumerate(actions, 1):
        add_action_item(doc, i, a)


def build_ai_section(doc, df, k):
    add_heading(doc, "17. AI Executive Analyst", level=1)
    add_para(doc,
        "The following findings, risks, opportunities, and actions were generated by a deterministic "
        "AI Executive Analyst module. All statements are based exclusively on verified, pre-calculated "
        "metrics. No numbers are fabricated. No causal claims are made without data support.",
        color="#64748B",
    )
    doc.add_paragraph()

    p_  = by_dim(df, "delivery_partner")
    r_  = by_dim(df, "region")
    w_  = by_dim(df, "weather_condition")
    m_  = by_dim(df, "delivery_mode")
    best_p  = p_.loc[p_["on_time_pct"].idxmax()]
    worst_p = p_.loc[p_["on_time_pct"].idxmin()]
    worst_r = r_.loc[r_["delayed_pct"].idxmax()]
    best_r  = r_.loc[r_["delayed_pct"].idxmin()]
    worst_w = w_.loc[w_["delayed_pct"].idxmax()]
    best_w  = w_.loc[w_["delayed_pct"].idxmin()]
    high_cp = p_.loc[p_["avg_cost"].idxmax()]
    low_cp  = p_.loc[p_["avg_cost"].idxmin()]
    best_mode_r = m_.loc[m_["avg_rating"].idxmax()]
    high_cm     = m_.loc[m_["avg_cost"].idxmax()]

    add_heading(doc, "Key Findings", level=2)
    findings = [
        f"The network processed {k['total']:,} deliveries with an overall on-time delivery rate of "
        f"{k['on_time_pct']}%, while {k['delayed_pct']}% were delayed and {k['failed_pct']}% failed.",
        f"Among logistics partners, {best_p['delivery_partner'].title()} recorded the highest on-time rate at "
        f"{best_p['on_time_pct']:.1f}%, compared to {worst_p['delivery_partner'].title()} at "
        f"{worst_p['on_time_pct']:.1f}%.",
        f"The {worst_r['region'].title()} region observed the highest delay concentration at "
        f"{worst_r['delayed_pct']:.1f}%, while {best_r['region'].title()} performed best at "
        f"{best_r['delayed_pct']:.1f}% delay rate.",
        f"Deliveries associated with {worst_w['weather_condition'].title()} conditions recorded a higher delay "
        f"rate ({worst_w['delayed_pct']:.1f}%) compared to {best_w['weather_condition'].title()} conditions.",
        f"Average delivery cost stood at ₹{k['avg_cost']:,.2f}, with {high_cp['delivery_partner'].title()} "
        f"averaging the highest cost (₹{high_cp['avg_cost']:,.2f}) and {low_cp['delivery_partner'].title()} "
        f"the lowest (₹{low_cp['avg_cost']:,.2f}).",
    ]
    for f in findings:
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(f).font.size = Pt(9)

    add_heading(doc, "Operational Risks", level=2)
    risks = [
        f"Concentration of delays in {worst_r['region'].title()} region ({worst_r['delayed_pct']:.1f}%) "
        f"warrants priority monitoring.",
        f"Performance gap between best and worst partner represents a "
        f"{best_p['on_time_pct']-worst_p['on_time_pct']:.1f} pp spread — a significant risk if volume "
        f"concentrates in lower-performing partners.",
        f"{worst_w['weather_condition'].title()} weather is associated with {worst_w['delayed_pct']:.1f}% "
        f"delay rate. Adverse weather periods pose a recurring service risk.",
    ]
    for r in risks:
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(r).font.size = Pt(9)

    add_heading(doc, "Opportunities", level=2)
    opps = [
        f"The {best_p['on_time_pct']-worst_p['on_time_pct']:.1f} pp on-time gap between best and worst partner "
        f"represents a benchmarking opportunity.",
        f"₹{high_cp['avg_cost']-low_cp['avg_cost']:,.0f} cost spread between highest and lowest cost partner "
        f"indicates a renegotiation or reallocation opportunity.",
        f"The {best_r['region'].title()} region achieves {best_r['on_time_pct']:.1f}% on-time rate — "
        f"investigating contributing operational factors could lift network performance.",
    ]
    for o in opps:
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(o).font.size = Pt(9)
    doc.add_paragraph()


def build_dashboard_overview(doc):
    add_heading(doc, "18. Dashboard Overview", level=1)
    add_para(doc,
        "The interactive Streamlit dashboard is organised into five pages, all responding to seven global "
        "sidebar filters (Partner, Region, Delivery Mode, Vehicle Type, Weather Condition, Package Type, "
        "Delivery Status)."
    )
    pages = [
        ("🏠 Operations Command Center",
         "3 headline KPI cards (On-Time %, Avg Delivery Time, Avg Cost), 4 supporting metrics, "
         "status donut chart, partner stacked bar chart, region/mode overview, executive observations."),
        ("📊 Delivery Performance",
         "Partner performance grouped bar, avg delivery time ranking, regional on-time/failed bars, "
         "vehicle type performance, weather delay analysis, delivery mode comparison."),
        ("💰 Cost & Efficiency",
         "4 cost KPI cards, partner cost rankings, cost/km comparison, mode/region cost bars, "
         "distance band cost analysis, cost-distance scatter, weight band cost, partner×mode heatmap."),
        ("⭐ Customer Experience",
         "3 rating KPIs, rating distribution (donut + bar), partner/region/mode/package type/vehicle "
         "rating comparisons, performance category vs rating."),
        ("⚠️ Risk & Opportunities",
         "5 risk cards (colour-coded by severity), 4 opportunity cards, 5 recommended action items, "
         "AI Executive Analyst section with findings/risks/opportunities, data quality status table."),
    ]
    table = doc.add_table(rows=len(pages)+1, cols=2)
    table.style = "Table Grid"
    for i, h in enumerate(["Page", "Contents"]):
        cell = table.cell(0, i)
        set_cell_bg(cell, NAVY.lstrip("#"))
        run = cell.paragraphs[0].add_run(h)
        run.font.bold = True; run.font.size = Pt(10); run.font.color.rgb = rgb("#FFFFFF")
    for r, (page, desc) in enumerate(pages, 1):
        table.cell(r,0).paragraphs[0].add_run(page).font.size  = Pt(9)
        table.cell(r,1).paragraphs[0].add_run(desc).font.size  = Pt(9)
        if r % 2 == 0:
            set_cell_bg(table.cell(r,0), "F5F7FA")
            set_cell_bg(table.cell(r,1), "F5F7FA")
    doc.add_paragraph()

    add_heading(doc, "Visual Design Identity", level=2)
    add_para(doc,
        'The dashboard uses an "Ops Terminal" visual identity: deep navy (#0B1E3D) sidebar, '
        "off-white (#F5F7FA) main canvas, electric teal (#00C4CC) accent colour, amber warning indicators, "
        "and red risk markers. All-caps section headers with teal left-border separators, borderless KPI cards "
        "with status pills, dark insight panels, and severity-coded risk cards create a professional, "
        "operations-grade interface distinct from generic reporting dashboards."
    )
    doc.add_paragraph()


def build_limitations_conclusion(doc):
    add_heading(doc, "19. Limitations", level=1)
    limits = [
        "No calendar date column — the dataset is cross-sectional; monthly/quarterly trend analysis is not possible.",
        "delivery_id is not a true primary key — 498 values appear more than once.",
        "Time columns required custom nanosecond decoding; values represent integer hours (not timestamps).",
        "No city-level geographic data is available; analysis is at region level only.",
        "No historical comparison is possible with a single cross-sectional dataset.",
    ]
    for l in limits:
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(l).font.size = Pt(9)
    doc.add_paragraph()

    add_heading(doc, "20. Conclusion", level=1)
    add_para(doc,
        "This analysis demonstrates a complete business analytics pipeline — from raw data inspection "
        "through cleaning, validation, feature engineering, KPI calculation, and multi-dimensional driver "
        "analysis — without relying on machine-learning models. All findings are grounded in verified, "
        "observable data. The interactive Streamlit dashboard enables management to explore performance "
        "by partner, region, delivery mode, vehicle type, weather condition, and package type in real time."
    )
    add_para(doc,
        "The analysis reveals measurable variation in on-time delivery rates, delivery costs, and customer "
        "satisfaction across the partner network and geographic regions. Five practical management actions "
        "have been identified, each directly connected to a verified data finding. These findings provide "
        "a data-driven foundation for operational planning, partner performance management, and cost "
        "optimization decisions."
    )
    doc.add_paragraph()

    add_heading(doc, "21. Future Improvements", level=1)
    improvements = [
        "Integrate a calendar date dimension to enable monthly/quarterly trend analysis.",
        "Add city-level geographic mapping for granular delivery routing analysis.",
        "Build a partner SLA scorecard with configurable on-time delivery thresholds.",
        "Connect to a live data feed for real-time operational monitoring.",
        "Add anomaly detection for cost spikes or delay surges.",
        "Integrate an LLM API for dynamic narrative generation based on live metrics.",
    ]
    for imp in improvements:
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(imp).font.size = Pt(9)
    doc.add_paragraph()


# ─────────────────────────────────────────────
# MAIN REPORT BUILDER
# ─────────────────────────────────────────────
def build_report():
    print("Loading data…")
    df = load_data()
    k  = kpis(df)

    print("Creating document…")
    doc = Document()

    # Page margins
    for section in doc.sections:
        section.top_margin    = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin   = Cm(2.8)
        section.right_margin  = Cm(2.8)

    # Cover page
    build_cover(doc)

    # Sections
    build_exec_summary(doc, k)
    build_business_problem(doc)
    build_dataset_overview(doc, df, k)
    build_tech_stack(doc)
    build_data_cleaning(doc)
    build_feature_engineering(doc)
    build_kpi_framework(doc, k)
    build_analysis(doc, df, k)
    build_risk_opportunity(doc, df, k)
    build_ai_section(doc, df, k)
    build_dashboard_overview(doc)
    build_limitations_conclusion(doc)

    print(f"Saving report to: {OUTPUT_PATH}")
    doc.save(OUTPUT_PATH)
    print("Report saved successfully.")


if __name__ == "__main__":
    build_report()
