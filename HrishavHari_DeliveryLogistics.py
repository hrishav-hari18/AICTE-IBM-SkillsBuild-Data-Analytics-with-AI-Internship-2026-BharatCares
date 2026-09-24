"""
Delivery & Logistics Performance Analytics Dashboard
Author: HrishavHarino
Dataset: Delivery Logistics Dataset — India Multi-Partner
"""

import re
import warnings
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# CONSTANTS & THEME
# ─────────────────────────────────────────────
DATA_PATH = "data/Delivery_Logistics.csv"

PALETTE = {
    "teal":  "#00C4CC",
    "amber": "#F59E0B",
    "red":   "#EF4444",
    "green": "#22C55E",
    "navy":  "#0B1E3D",
    "slate": "#1E3A5F",
    "muted": "#64748B",
    "bg":    "#F5F7FA",
    "white": "#FFFFFF",
}

# Consistent color sequences for charts
COLOR_SEQ = [
    "#00C4CC", "#F59E0B", "#3B82F6", "#8B5CF6",
    "#22C55E", "#EF4444", "#F97316", "#EC4899", "#14B8A6",
]

PARTNER_COLORS = {
    "amazon logistics": "#FF9900",
    "blue dart":        "#003087",
    "delhivery":        "#E63946",
    "dhl":              "#FFCC00",
    "ecom express":     "#1D3461",
    "ekart":            "#2196F3",
    "fedex":            "#4D148C",
    "shadowfax":        "#00BCD4",
    "xpressbees":       "#FF5722",
}


# ─────────────────────────────────────────────
# STAGE 2 — DATA LOADING & CLEANING
# ─────────────────────────────────────────────
@st.cache_data(show_spinner="Loading & cleaning data…")
def load_and_clean_data():
    """Load raw CSV, decode special columns, clean, and return clean DataFrame."""
    import os
    base = os.path.dirname(__file__)
    path = os.path.join(base, DATA_PATH)

    if not os.path.exists(path):
        st.error(f"Dataset not found at: {path}\nPlease place Delivery_Logistics.csv inside the data/ folder.")
        st.stop()

    raw = pd.read_csv(path)
    quality_log = []

    # ── Raw snapshot ──────────────────────────────────────
    raw_rows, raw_cols = raw.shape
    quality_log.append({"check": "Raw rows", "value": raw_rows, "status": "INFO"})
    quality_log.append({"check": "Raw columns", "value": raw_cols, "status": "INFO"})

    # ── Duplicate check ───────────────────────────────────
    dup_count = raw.duplicated().sum()
    quality_log.append({"check": "Exact duplicates", "value": dup_count, "status": "PASS" if dup_count == 0 else "WARN"})

    # ── Missing values ─────────────────────────────────────
    missing_total = raw.isnull().sum().sum()
    quality_log.append({"check": "Missing values", "value": missing_total, "status": "PASS" if missing_total == 0 else "WARN"})

    df = raw.copy()

    # ── Standardise column names ───────────────────────────
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # ── Standardise string categoricals ───────────────────
    str_cols = ["delivery_partner", "package_type", "vehicle_type",
                "delivery_mode", "region", "weather_condition",
                "delayed", "delivery_status"]
    for c in str_cols:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip().str.lower()

    # ── Decode nanosecond-epoch time columns ───────────────
    # Values look like '1970-01-01 00:00:00.000000008' — fractional nanoseconds
    def decode_ns_to_hours(series):
        def _extract(s):
            m = re.search(r"\.(\d+)$", str(s))
            if m:
                return int(m.group(1))   # nanoseconds = integer hours in this dataset
            return np.nan
        return series.apply(_extract)

    df["delivery_time_hours"] = decode_ns_to_hours(df["delivery_time_hours"])
    df["expected_time_hours"] = decode_ns_to_hours(df["expected_time_hours"])

    # Validate decoded ranges
    inv_delivery = ((df["delivery_time_hours"] < 0) | (df["delivery_time_hours"] > 72)).sum()
    inv_expected = ((df["expected_time_hours"] < 0) | (df["expected_time_hours"] > 72)).sum()
    quality_log.append({"check": "Invalid delivery_time_hours", "value": inv_delivery, "status": "PASS" if inv_delivery == 0 else "WARN"})
    quality_log.append({"check": "Invalid expected_time_hours", "value": inv_expected, "status": "PASS" if inv_expected == 0 else "WARN"})

    # ── Ensure numeric columns are numeric ─────────────────
    for c in ["distance_km", "package_weight_kg", "delivery_cost", "delivery_rating"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # ── Validate numeric ranges ────────────────────────────
    neg_cost = (df["delivery_cost"] <= 0).sum()
    neg_dist = (df["distance_km"] <= 0).sum()
    neg_wt   = (df["package_weight_kg"] <= 0).sum()
    bad_rat  = (~df["delivery_rating"].between(1, 5)).sum()
    quality_log.append({"check": "Invalid delivery_cost (<=0)", "value": neg_cost, "status": "PASS" if neg_cost == 0 else "WARN"})
    quality_log.append({"check": "Invalid distance_km (<=0)", "value": neg_dist, "status": "PASS" if neg_dist == 0 else "WARN"})
    quality_log.append({"check": "Invalid package_weight_kg (<=0)", "value": neg_wt, "status": "PASS" if neg_wt == 0 else "WARN"})
    quality_log.append({"check": "Invalid delivery_rating (out 1-5)", "value": bad_rat, "status": "PASS" if bad_rat == 0 else "WARN"})

    # ── delivery_id note ───────────────────────────────────
    dup_ids = raw_rows - df["delivery_id"].nunique()
    quality_log.append({"check": "Non-unique delivery_id rows", "value": dup_ids, "status": "INFO"})

    clean_rows = len(df)
    quality_log.append({"check": "Clean rows (final)", "value": clean_rows, "status": "INFO"})

    overall = "PASS" if all(q["status"] in ("PASS", "INFO") for q in quality_log) else "WARN"
    quality_log.append({"check": "Overall Data Quality", "value": overall, "status": overall})

    return df, pd.DataFrame(quality_log)


# ─────────────────────────────────────────────
# STAGE 3 — FEATURE ENGINEERING & KPIs
# ─────────────────────────────────────────────
def create_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived business columns to the clean DataFrame."""
    df = df.copy()

    # Time gap: actual − expected (negative = arrived early, positive = late)
    df["time_gap_hours"] = df["delivery_time_hours"] - df["expected_time_hours"]

    # Binary flags
    df["is_delayed"] = (df["delayed"] == "yes").astype(int)
    df["is_failed"]  = (df["delivery_status"] == "failed").astype(int)
    df["is_on_time"] = (df["delivery_status"] == "delivered").astype(int)

    # Cost efficiency
    df["cost_per_km"] = df["delivery_cost"] / df["distance_km"].replace(0, np.nan)
    df["cost_per_kg"] = df["delivery_cost"] / df["package_weight_kg"].replace(0, np.nan)

    # Distance bands
    df["distance_band"] = pd.cut(
        df["distance_km"],
        bins=[0, 100, 200, 300],
        labels=["Short (0-100 km)", "Medium (100-200 km)", "Long (200-300 km)"],
    )

    # Weight bands
    df["weight_band"] = pd.cut(
        df["package_weight_kg"],
        bins=[0, 17, 33, 51],
        labels=["Light (0-17 kg)", "Medium (17-33 kg)", "Heavy (33-51 kg)"],
    )

    # Performance category (human-readable)
    def perf_cat(row):
        if row["delivery_status"] == "delivered":
            return "On-Time"
        elif row["delivery_status"] == "delayed":
            return "Delayed"
        else:
            return "Failed"

    df["performance_category"] = df.apply(perf_cat, axis=1)

    # Rating band
    df["rating_band"] = pd.cut(
        df["delivery_rating"],
        bins=[0, 2, 3, 5],
        labels=["Low (1-2)", "Medium (3)", "High (4-5)"],
    )

    return df


def calculate_kpis(df: pd.DataFrame) -> dict:
    """Calculate all headline business KPIs. Returns a dictionary of verified metrics."""
    total = len(df)
    on_time   = (df["delivery_status"] == "delivered").sum()
    delayed   = (df["delivery_status"] == "delayed").sum()
    failed    = (df["delivery_status"] == "failed").sum()

    kpis = {
        # Volume
        "total_deliveries":       int(total),
        "on_time_deliveries":     int(on_time),
        "delayed_deliveries":     int(delayed),
        "failed_deliveries":      int(failed),

        # Rates
        "on_time_pct":            round(on_time / total * 100, 1),
        "delayed_pct":            round(delayed / total * 100, 1),
        "failed_pct":             round(failed / total * 100, 1),

        # Time
        "avg_delivery_time":      round(df["delivery_time_hours"].mean(), 2),
        "avg_expected_time":      round(df["expected_time_hours"].mean(), 2),
        "avg_time_gap":           round(df["time_gap_hours"].mean(), 2),

        # Cost
        "avg_delivery_cost":      round(df["delivery_cost"].mean(), 2),
        "total_delivery_cost":    round(df["delivery_cost"].sum(), 2),
        "avg_cost_per_km":        round(df["cost_per_km"].mean(), 2),
        "avg_cost_per_kg":        round(df["cost_per_kg"].mean(), 2),

        # Rating
        "avg_rating":             round(df["delivery_rating"].mean(), 2),
    }
    return kpis


# ─────────────────────────────────────────────
# STAGE 4 — BUSINESS ANALYSIS FUNCTIONS
# ─────────────────────────────────────────────
def analyze_by_dimension(df: pd.DataFrame, dim: str) -> pd.DataFrame:
    """Generic aggregation by a categorical dimension."""
    grp = df.groupby(dim, observed=True).agg(
        total_deliveries    = ("delivery_status", "count"),
        on_time             = ("is_on_time",  "sum"),
        delayed_count       = ("is_delayed",  "sum"),
        failed_count        = ("is_failed",   "sum"),
        avg_delivery_time   = ("delivery_time_hours", "mean"),
        avg_expected_time   = ("expected_time_hours", "mean"),
        avg_cost            = ("delivery_cost", "mean"),
        total_cost          = ("delivery_cost", "sum"),
        avg_rating          = ("delivery_rating", "mean"),
        avg_cost_per_km     = ("cost_per_km", "mean"),
        avg_cost_per_kg     = ("cost_per_kg", "mean"),
        avg_distance        = ("distance_km", "mean"),
    ).reset_index()

    grp["on_time_pct"]  = (grp["on_time"] / grp["total_deliveries"] * 100).round(1)
    grp["delayed_pct"]  = (grp["delayed_count"] / grp["total_deliveries"] * 100).round(1)
    grp["failed_pct"]   = (grp["failed_count"] / grp["total_deliveries"] * 100).round(1)
    grp["avg_delivery_time"]  = grp["avg_delivery_time"].round(2)
    grp["avg_cost"]           = grp["avg_cost"].round(2)
    grp["avg_rating"]         = grp["avg_rating"].round(2)
    grp["avg_cost_per_km"]    = grp["avg_cost_per_km"].round(2)
    grp["avg_cost_per_kg"]    = grp["avg_cost_per_kg"].round(2)
    return grp


def analyze_partners(df):      return analyze_by_dimension(df, "delivery_partner")
def analyze_regions(df):       return analyze_by_dimension(df, "region")
def analyze_modes(df):         return analyze_by_dimension(df, "delivery_mode")
def analyze_vehicles(df):      return analyze_by_dimension(df, "vehicle_type")
def analyze_weather(df):       return analyze_by_dimension(df, "weather_condition")
def analyze_package_types(df): return analyze_by_dimension(df, "package_type")
def analyze_distance_bands(df):return analyze_by_dimension(df, "distance_band")
def analyze_weight_bands(df):  return analyze_by_dimension(df, "weight_band")


# ─────────────────────────────────────────────
# STAGE 7 — DETERMINISTIC AI EXECUTIVE ANALYST
# ─────────────────────────────────────────────
def generate_executive_insights(kpis: dict, df: pd.DataFrame) -> dict:
    """
    Deterministic AI Executive Analyst.
    Interprets ONLY pre-calculated verified metrics.
    No fabrication — every statement traces to a real number.
    """
    partners = analyze_partners(df)
    regions  = analyze_regions(df)
    modes    = analyze_modes(df)
    vehicles = analyze_vehicles(df)
    weather  = analyze_weather(df)

    # Best / worst performers
    best_partner_ot  = partners.loc[partners["on_time_pct"].idxmax(), "delivery_partner"].title()
    worst_partner_ot = partners.loc[partners["on_time_pct"].idxmin(), "delivery_partner"].title()
    best_partner_ot_val  = partners["on_time_pct"].max()
    worst_partner_ot_val = partners["on_time_pct"].min()

    highest_cost_partner = partners.loc[partners["avg_cost"].idxmax(), "delivery_partner"].title()
    lowest_cost_partner  = partners.loc[partners["avg_cost"].idxmin(), "delivery_partner"].title()
    highest_cost_val     = partners["avg_cost"].max()
    lowest_cost_val      = partners["avg_cost"].min()

    worst_region = regions.loc[regions["delayed_pct"].idxmax(), "region"].title()
    best_region  = regions.loc[regions["delayed_pct"].idxmin(), "region"].title()
    worst_region_delay_val = regions["delayed_pct"].max()
    best_region_delay_val  = regions["delayed_pct"].min()

    worst_weather = weather.loc[weather["delayed_pct"].idxmax(), "weather_condition"].title()
    worst_weather_val = weather["delayed_pct"].max()
    best_weather  = weather.loc[weather["delayed_pct"].idxmin(), "weather_condition"].title()

    worst_vehicle_time = vehicles.loc[vehicles["avg_delivery_time"].idxmax(), "vehicle_type"].title()
    worst_vehicle_val  = vehicles["avg_delivery_time"].max()

    best_rated_mode = modes.loc[modes["avg_rating"].idxmax(), "delivery_mode"].title()
    best_rated_mode_val = modes["avg_rating"].max()

    highest_cost_mode = modes.loc[modes["avg_cost"].idxmax(), "delivery_mode"].title()
    highest_cost_mode_val = modes["avg_cost"].max()

    findings = [
        f"The network processed {kpis['total_deliveries']:,} deliveries with an overall on-time delivery rate of "
        f"{kpis['on_time_pct']}%, while {kpis['delayed_pct']}% were delayed and {kpis['failed_pct']}% failed.",

        f"Among logistics partners, {best_partner_ot} recorded the highest on-time delivery rate at "
        f"{best_partner_ot_val:.1f}%, compared to {worst_partner_ot} at {worst_partner_ot_val:.1f}%, "
        f"indicating measurable performance variation across the partner network.",

        f"The {worst_region} region observed the highest delay concentration at {worst_region_delay_val:.1f}%, "
        f"while the {best_region} region performed best at {best_region_delay_val:.1f}% delay rate.",

        f"Deliveries associated with {worst_weather} weather conditions recorded a higher delay rate "
        f"({worst_weather_val:.1f}%) compared to {best_weather} conditions, suggesting weather as an "
        f"observable factor in delivery variability.",

        f"The average delivery cost across the network stood at ₹{kpis['avg_delivery_cost']:,.2f}, "
        f"with {highest_cost_partner} averaging the highest cost (₹{highest_cost_val:,.2f}) and "
        f"{lowest_cost_partner} the lowest (₹{lowest_cost_val:,.2f}).",
    ]

    risks = [
        f"CONCENTRATION RISK: With {kpis['failed_pct']}% of deliveries failing outright, "
        f"the {worst_region} region warrants priority monitoring given its {worst_region_delay_val:.1f}% delay rate.",

        f"PARTNER PERFORMANCE RISK: The performance gap between best ({best_partner_ot}: {best_partner_ot_val:.1f}% on-time) "
        f"and worst ({worst_partner_ot}: {worst_partner_ot_val:.1f}% on-time) partner represents a "
        f"{best_partner_ot_val - worst_partner_ot_val:.1f} percentage-point spread — a significant operational risk "
        f"if volume is concentrated in lower-performing partners.",

        f"WEATHER EXPOSURE RISK: {worst_weather} weather is associated with a delay rate of {worst_weather_val:.1f}%. "
        f"Without contingency routing or proactive rescheduling, adverse weather periods may disproportionately "
        f"impact service levels.",
    ]

    opportunities = [
        f"PARTNER BENCHMARKING: The {best_partner_ot_val - worst_partner_ot_val:.1f} percentage-point gap in on-time "
        f"performance between top and bottom partners suggests that sharing operational practices from "
        f"{best_partner_ot} could materially lift network-wide on-time rates.",

        f"COST OPTIMIZATION: The cost spread between the highest-cost partner (₹{highest_cost_val:,.2f}) and "
        f"lowest-cost partner (₹{lowest_cost_val:,.2f}) presents a renegotiation or reallocation opportunity "
        f"that could reduce average delivery cost meaningfully.",

        f"REGIONAL FOCUS: Targeted operational review of the {worst_region} region — which accounts for "
        f"a disproportionate share of delays — could improve the overall network on-time rate without requiring "
        f"broad infrastructure changes.",
    ]

    actions = [
        f"Review allocation of delivery volume to {worst_partner_ot} and consider implementing a performance "
        f"improvement plan with measurable on-time delivery targets.",

        f"Conduct a root-cause investigation into the elevated delay and failure rates observed in the "
        f"{worst_region} region, evaluating partner assignment, route planning, and capacity.",

        f"Develop weather-contingency protocols for {worst_weather} conditions, including pre-emptive "
        f"customer communications and delivery rescheduling workflows.",

        f"Benchmark the operational practices of {best_partner_ot} (on-time: {best_partner_ot_val:.1f}%) "
        f"and evaluate whether those practices can be extended to lower-performing network partners.",

        f"Prioritize cost-per-km and cost-per-kg analysis for the {highest_cost_mode} delivery mode "
        f"(avg cost ₹{highest_cost_mode_val:,.2f}) to identify route or pricing inefficiencies.",
    ]

    return {
        "findings":     findings,
        "risks":        risks,
        "opportunities":opportunities,
        "actions":      actions,
    }


# ─────────────────────────────────────────────
# STAGE 5 — PLOTLY CHART HELPERS
# ─────────────────────────────────────────────
CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, Segoe UI, sans-serif", size=12, color="#1E293B"),
    margin=dict(l=20, r=20, t=40, b=20),
    legend=dict(bgcolor="rgba(0,0,0,0)", borderwidth=0),
)


def bar_chart(data, x, y, color_col=None, title="", orientation="v",
              color_map=None, text_col=None, color_seq=None):
    if color_seq is None:
        color_seq = COLOR_SEQ
    kwargs = dict(
        data_frame=data, x=x, y=y, title=title,
        color_discrete_sequence=color_seq,
        orientation=orientation,
    )
    if color_col:
        kwargs["color"] = color_col
        if color_map:
            kwargs["color_discrete_map"] = color_map
    if text_col:
        kwargs["text"] = text_col
    fig = px.bar(**kwargs)
    fig.update_layout(**CHART_LAYOUT)
    fig.update_traces(marker_line_width=0)
    return fig


def donut_chart(labels, values, title="", colors=None):
    if colors is None:
        colors = COLOR_SEQ
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.55,
        marker=dict(colors=colors[:len(labels)], line=dict(color="#fff", width=2)),
        textinfo="label+percent",
        hovertemplate="%{label}: %{value:,} (%{percent})<extra></extra>",
    ))
    fig.update_layout(title_text=title, **CHART_LAYOUT)
    return fig


def heatmap_chart(data, x, y, z, title=""):
    pivot = data.pivot_table(index=y, columns=x, values=z, aggfunc="mean")
    fig = px.imshow(
        pivot, text_auto=".1f", aspect="auto",
        color_continuous_scale=["#EFF6FF", "#3B82F6", "#1E3A5F"],
        title=title,
    )
    fig.update_layout(**CHART_LAYOUT)
    return fig


def scatter_chart(data, x, y, color=None, title="", trendline=None):
    kwargs = dict(data_frame=data, x=x, y=y, title=title,
                  color_discrete_sequence=COLOR_SEQ, opacity=0.5)
    if color:
        kwargs["color"] = color
    if trendline:
        kwargs["trendline"] = trendline
    fig = px.scatter(**kwargs)
    fig.update_layout(**CHART_LAYOUT)
    return fig


def grouped_bar(data, x, y_list, names, title=""):
    fig = go.Figure()
    for y, name, color in zip(y_list, names, COLOR_SEQ):
        fig.add_trace(go.Bar(name=name, x=data[x], y=data[y],
                             marker_color=color))
    fig.update_layout(barmode="group", title_text=title, **CHART_LAYOUT)
    return fig


def horizontal_bar(data, x, y, title="", color=None):
    c = color or PALETTE["teal"]
    fig = go.Figure(go.Bar(
        x=data[x], y=data[y], orientation="h",
        marker_color=c,
        text=data[x].round(1),
        textposition="outside",
    ))
    fig.update_layout(title_text=title, yaxis=dict(autorange="reversed"), **CHART_LAYOUT)
    return fig


# ─────────────────────────────────────────────
# STAGE 6 — STREAMLIT DASHBOARD
# ─────────────────────────────────────────────
def apply_css():
    st.markdown("""
    <style>
    /* ── Global ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', 'Segoe UI', sans-serif; }

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] {
        background: #0B1E3D !important;
    }
    section[data-testid="stSidebar"] * { color: #E2E8F0 !important; }
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stMultiSelect label { color: #94A3B8 !important; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }

    /* ── Main background ── */
    .main .block-container { background: #F5F7FA; padding: 1.5rem 2rem; max-width: 1400px; }

    /* ── Section headers ── */
    .section-header {
        border-left: 4px solid #00C4CC;
        padding: 4px 0 4px 14px;
        margin: 1.5rem 0 0.75rem;
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #64748B;
    }

    /* ── KPI cards ── */
    .kpi-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 20px 24px;
        margin-bottom: 0.5rem;
    }
    .kpi-label { font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: #64748B; margin-bottom: 4px; }
    .kpi-value { font-size: 2rem; font-weight: 700; color: #0B1E3D; line-height: 1.1; font-variant-numeric: tabular-nums; }
    .kpi-sub   { font-size: 0.75rem; color: #94A3B8; margin-top: 4px; }
    .kpi-pill-green { display: inline-block; background: #D1FAE5; color: #065F46; padding: 2px 8px; border-radius: 20px; font-size: 0.65rem; font-weight: 600; }
    .kpi-pill-red   { display: inline-block; background: #FEE2E2; color: #991B1B; padding: 2px 8px; border-radius: 20px; font-size: 0.65rem; font-weight: 600; }
    .kpi-pill-amber { display: inline-block; background: #FEF3C7; color: #92400E; padding: 2px 8px; border-radius: 20px; font-size: 0.65rem; font-weight: 600; }

    /* ── Insight panels ── */
    .insight-panel {
        background: #0B1E3D;
        color: #E2E8F0;
        border-left: 3px solid #00C4CC;
        border-radius: 6px;
        padding: 14px 18px;
        margin-bottom: 0.5rem;
        font-size: 0.82rem;
        line-height: 1.6;
    }

    /* ── Risk cards ── */
    /* High-contrast risk cards — dark background so text is always readable */
    .risk-card-red   { background:#2D0A0A; border-left: 5px solid #EF4444; border-radius:8px; padding:14px 18px; margin-bottom:0.6rem; font-size:0.83rem; color:#F8D7D7 !important; line-height:1.65; }
    .risk-card-amber { background:#2D1E00; border-left: 5px solid #F59E0B; border-radius:8px; padding:14px 18px; margin-bottom:0.6rem; font-size:0.83rem; color:#FDE8B0 !important; line-height:1.65; }
    .risk-card-green { background:#002D12; border-left: 5px solid #22C55E; border-radius:8px; padding:14px 18px; margin-bottom:0.6rem; font-size:0.83rem; color:#BBF7D0 !important; line-height:1.65; }
    .risk-card-blue  { background:#001A2D; border-left: 5px solid #3B82F6; border-radius:8px; padding:14px 18px; margin-bottom:0.6rem; font-size:0.83rem; color:#BFDBFE !important; line-height:1.65; }
    /* Force text color on all children of risk cards */
    .risk-card-red *, .risk-card-amber *, .risk-card-green *, .risk-card-blue * { color: inherit !important; }

    /* ── Data quality badge ── */
    .dq-pass { background:#D1FAE5; color:#065F46; padding:4px 12px; border-radius:20px; font-size:0.75rem; font-weight:700; }
    .dq-warn { background:#FEF3C7; color:#92400E; padding:4px 12px; border-radius:20px; font-size:0.75rem; font-weight:700; }

    /* ── Page title ── */
    .page-title { font-size:1.6rem; font-weight:700; color:#0B1E3D; margin-bottom:0; }
    .page-subtitle { font-size:0.85rem; color:#64748B; margin-top:2px; margin-bottom:1rem; }

    /* ── Chart containers ── */
    .chart-card { background:#FFFFFF; border:1px solid #E2E8F0; border-radius:10px; padding:12px; }

    /* hide streamlit branding */
    footer { visibility: hidden; }
    </style>
    """, unsafe_allow_html=True)


def kpi_card(label, value, sub="", pill=None, pill_type="green"):
    pill_html = ""
    if pill:
        pill_html = f'<div class="kpi-pill-{pill_type}">{pill}</div>'
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub">{sub} {pill_html}</div>
    </div>
    """, unsafe_allow_html=True)


def section_header(text):
    st.markdown(f'<div class="section-header">{text}</div>', unsafe_allow_html=True)


def insight_panel(text):
    st.markdown(f'<div class="insight-panel">💡 {text}</div>', unsafe_allow_html=True)


def risk_card(text, level="red"):
    st.markdown(f'<div class="risk-card-{level}">{text}</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
# PAGE 1 — OPERATIONS COMMAND CENTER
# ─────────────────────────────────────────────
def page_command_center(df, kpis):
    st.markdown('<p class="page-title">OPERATIONS COMMAND CENTER</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Real-time operational health across all delivery partners, regions, and modes.</p>', unsafe_allow_html=True)

    section_header("Primary KPIs")
    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("On-Time Delivery Rate", f"{kpis['on_time_pct']}%",
                 sub=f"{kpis['on_time_deliveries']:,} of {kpis['total_deliveries']:,} deliveries",
                 pill="▲ Target: >80%", pill_type="green" if kpis['on_time_pct'] >= 70 else "amber")
    with c2:
        kpi_card("Avg. Delivery Time", f"{kpis['avg_delivery_time']} hrs",
                 sub=f"Expected avg: {kpis['avg_expected_time']} hrs",
                 pill=f"Gap: {abs(kpis['avg_time_gap']):.1f} hrs early", pill_type="green")
    with c3:
        kpi_card("Avg. Delivery Cost", f"₹{kpis['avg_delivery_cost']:,.0f}",
                 sub=f"Total: ₹{kpis['total_delivery_cost']:,.0f}",
                 pill=f"₹{kpis['avg_cost_per_km']:.2f}/km", pill_type="amber")

    section_header("Supporting Metrics")
    c4, c5, c6, c7 = st.columns(4)
    with c4:
        kpi_card("Total Deliveries", f"{kpis['total_deliveries']:,}", sub="All statuses")
    with c5:
        kpi_card("Delayed Rate", f"{kpis['delayed_pct']}%",
                 sub=f"{kpis['delayed_deliveries']:,} delayed",
                 pill_type="red")
    with c6:
        kpi_card("Failed Rate", f"{kpis['failed_pct']}%",
                 sub=f"{kpis['failed_deliveries']:,} failed",
                 pill_type="red")
    with c7:
        kpi_card("Avg. Customer Rating", f"{kpis['avg_rating']}/5",
                 sub="Across all delivered orders", pill="★", pill_type="amber")

    section_header("Delivery Status Distribution")
    c_left, c_right = st.columns([1, 2])
    with c_left:
        status_counts = df["delivery_status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Count"]
        fig_donut = donut_chart(
            status_counts["Status"].str.title(),
            status_counts["Count"],
            title="Status Split",
            colors=[PALETTE["green"], PALETTE["amber"], PALETTE["red"]],
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    with c_right:
        partners = analyze_partners(df).sort_values("on_time_pct", ascending=True)
        fig_partner = go.Figure()
        fig_partner.add_trace(go.Bar(
            name="On-Time %", x=partners["on_time_pct"], y=partners["delivery_partner"].str.title(),
            orientation="h", marker_color=PALETTE["teal"],
            text=partners["on_time_pct"].apply(lambda x: f"{x:.1f}%"), textposition="outside",
        ))
        fig_partner.add_trace(go.Bar(
            name="Delayed %", x=partners["delayed_pct"], y=partners["delivery_partner"].str.title(),
            orientation="h", marker_color=PALETTE["amber"],
        ))
        fig_partner.update_layout(
            barmode="stack", title_text="On-Time vs Delayed % by Partner",
            yaxis=dict(autorange="reversed"), **CHART_LAYOUT,
        )
        st.plotly_chart(fig_partner, use_container_width=True)

    section_header("Delivery Mode & Region Overview")
    c8, c9 = st.columns(2)
    with c8:
        modes = analyze_modes(df)
        fig_mode = bar_chart(modes, x="delivery_mode", y="on_time_pct",
                             title="On-Time % by Delivery Mode",
                             color_seq=[PALETTE["teal"], PALETTE["slate"], PALETTE["amber"], PALETTE["green"]])
        fig_mode.update_traces(text=modes["on_time_pct"].apply(lambda x: f"{x:.1f}%"), textposition="outside")
        st.plotly_chart(fig_mode, use_container_width=True)
    with c9:
        regions = analyze_regions(df)
        fig_reg = bar_chart(regions, x="region", y="total_deliveries",
                            title="Total Deliveries by Region",
                            color_seq=COLOR_SEQ)
        st.plotly_chart(fig_reg, use_container_width=True)

    section_header("Executive Observations")
    insights = generate_executive_insights(kpis, df)
    for f in insights["findings"][:3]:
        insight_panel(f)


# ─────────────────────────────────────────────
# PAGE 2 — DELIVERY PERFORMANCE
# ─────────────────────────────────────────────
def page_delivery_performance(df, kpis):
    st.markdown('<p class="page-title">DELIVERY PERFORMANCE</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">On-time, delayed, and failed delivery analysis across all operational dimensions.</p>', unsafe_allow_html=True)

    section_header("Performance Overview")
    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("On-Time Delivery %", f"{kpis['on_time_pct']}%", sub=f"{kpis['on_time_deliveries']:,} deliveries")
    with c2:
        kpi_card("Delayed %", f"{kpis['delayed_pct']}%", sub=f"{kpis['delayed_deliveries']:,} deliveries")
    with c3:
        kpi_card("Failed %", f"{kpis['failed_pct']}%", sub=f"{kpis['failed_deliveries']:,} deliveries")

    section_header("Partner Performance")
    partners = analyze_partners(df).sort_values("on_time_pct", ascending=False)
    fig_p = grouped_bar(
        partners, x="delivery_partner",
        y_list=["on_time_pct", "delayed_pct", "failed_pct"],
        names=["On-Time %", "Delayed %", "Failed %"],
        title="Delivery Status % by Partner",
    )
    fig_p.update_layout(xaxis_tickangle=-20)
    st.plotly_chart(fig_p, use_container_width=True)

    section_header("Avg Delivery Time by Partner")
    fig_time = horizontal_bar(
        partners.sort_values("avg_delivery_time"),
        x="avg_delivery_time", y="delivery_partner",
        title="Average Delivery Time (hours) by Partner",
        color=PALETTE["slate"],
    )
    st.plotly_chart(fig_time, use_container_width=True)

    section_header("Regional Performance")
    c4, c5 = st.columns(2)
    with c4:
        regions = analyze_regions(df).sort_values("on_time_pct", ascending=False)
        fig_r = bar_chart(regions, x="region", y="on_time_pct",
                          title="On-Time % by Region", color_seq=COLOR_SEQ)
        fig_r.update_traces(text=regions["on_time_pct"].apply(lambda x: f"{x:.1f}%"), textposition="outside")
        st.plotly_chart(fig_r, use_container_width=True)
    with c5:
        fig_rfail = bar_chart(regions, x="region", y="failed_pct",
                              title="Failed Delivery % by Region",
                              color_seq=[PALETTE["red"]])
        st.plotly_chart(fig_rfail, use_container_width=True)

    section_header("Vehicle Type Performance")
    vehicles = analyze_vehicles(df).sort_values("on_time_pct", ascending=False)
    c6, c7 = st.columns(2)
    with c6:
        fig_v = bar_chart(vehicles, x="vehicle_type", y="on_time_pct",
                          title="On-Time % by Vehicle Type", color_seq=COLOR_SEQ)
        st.plotly_chart(fig_v, use_container_width=True)
    with c7:
        fig_vt = bar_chart(vehicles, x="vehicle_type", y="avg_delivery_time",
                           title="Avg Delivery Time by Vehicle Type",
                           color_seq=[PALETTE["slate"]])
        st.plotly_chart(fig_vt, use_container_width=True)

    section_header("Weather Impact on Delays")
    weather = analyze_weather(df).sort_values("delayed_pct", ascending=False)
    fig_w = bar_chart(weather, x="weather_condition", y="delayed_pct",
                      title="Delayed % by Weather Condition",
                      color_seq=[PALETTE["amber"]])
    fig_w.update_traces(text=weather["delayed_pct"].apply(lambda x: f"{x:.1f}%"), textposition="outside")
    st.plotly_chart(fig_w, use_container_width=True)

    section_header("Delivery Mode Performance")
    modes = analyze_modes(df)
    fig_m = grouped_bar(
        modes, x="delivery_mode",
        y_list=["on_time_pct", "delayed_pct", "failed_pct"],
        names=["On-Time %", "Delayed %", "Failed %"],
        title="Performance % by Delivery Mode",
    )
    st.plotly_chart(fig_m, use_container_width=True)


# ─────────────────────────────────────────────
# PAGE 3 — COST & EFFICIENCY
# ─────────────────────────────────────────────
def page_cost_efficiency(df, kpis):
    st.markdown('<p class="page-title">COST & EFFICIENCY</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Delivery cost analysis across partners, regions, modes, and distance/weight bands.</p>', unsafe_allow_html=True)

    section_header("Cost KPIs")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Avg. Delivery Cost", f"₹{kpis['avg_delivery_cost']:,.0f}", sub="Per delivery")
    with c2:
        kpi_card("Total Delivery Cost", f"₹{kpis['total_delivery_cost']/1e6:.2f}M", sub="All deliveries")
    with c3:
        kpi_card("Avg. Cost per KM", f"₹{kpis['avg_cost_per_km']:.2f}", sub="Per kilometre")
    with c4:
        kpi_card("Avg. Cost per KG", f"₹{kpis['avg_cost_per_kg']:.2f}", sub="Per kilogram")

    section_header("Cost by Partner")
    partners = analyze_partners(df).sort_values("avg_cost", ascending=True)
    c5, c6 = st.columns(2)
    with c5:
        fig_cp = horizontal_bar(partners, x="avg_cost", y="delivery_partner",
                                title="Avg. Delivery Cost by Partner (₹)", color=PALETTE["teal"])
        st.plotly_chart(fig_cp, use_container_width=True)
    with c6:
        fig_ckm = horizontal_bar(partners.sort_values("avg_cost_per_km"),
                                 x="avg_cost_per_km", y="delivery_partner",
                                 title="Avg. Cost per KM by Partner (₹)", color=PALETTE["slate"])
        st.plotly_chart(fig_ckm, use_container_width=True)

    section_header("Cost by Delivery Mode & Region")
    c7, c8 = st.columns(2)
    with c7:
        modes = analyze_modes(df)
        fig_cm = bar_chart(modes, x="delivery_mode", y="avg_cost",
                           title="Avg. Cost by Delivery Mode (₹)", color_seq=COLOR_SEQ)
        st.plotly_chart(fig_cm, use_container_width=True)
    with c8:
        regions = analyze_regions(df)
        fig_cr = bar_chart(regions, x="region", y="avg_cost",
                           title="Avg. Cost by Region (₹)", color_seq=COLOR_SEQ)
        st.plotly_chart(fig_cr, use_container_width=True)

    section_header("Cost vs Distance Analysis")
    c9, c10 = st.columns(2)
    with c9:
        dbands = analyze_distance_bands(df)
        fig_db = bar_chart(dbands, x="distance_band", y="avg_cost",
                           title="Avg. Cost by Distance Band (₹)", color_seq=[PALETTE["teal"], PALETTE["amber"], PALETTE["red"]])
        st.plotly_chart(fig_db, use_container_width=True)
    with c10:
        sample = df.sample(min(2000, len(df)), random_state=42)
        fig_sc = scatter_chart(sample, x="distance_km", y="delivery_cost",
                               color="delivery_mode",
                               title="Delivery Cost vs Distance (sample 2,000)")
        st.plotly_chart(fig_sc, use_container_width=True)

    section_header("Cost by Weight Band")
    wbands = analyze_weight_bands(df)
    fig_wb = bar_chart(wbands, x="weight_band", y="avg_cost",
                       title="Avg. Cost by Weight Band (₹)",
                       color_seq=[PALETTE["green"], PALETTE["amber"], PALETTE["red"]])
    st.plotly_chart(fig_wb, use_container_width=True)

    section_header("Cost Heatmap — Partner × Delivery Mode")
    heat_data = df.groupby(["delivery_partner", "delivery_mode"], observed=True)["delivery_cost"].mean().reset_index()
    fig_heat = heatmap_chart(heat_data, x="delivery_mode", y="delivery_partner",
                             z="delivery_cost", title="Avg. Delivery Cost (₹) — Partner × Mode")
    st.plotly_chart(fig_heat, use_container_width=True)


# ─────────────────────────────────────────────
# PAGE 4 — CUSTOMER EXPERIENCE
# ─────────────────────────────────────────────
def page_customer_experience(df, kpis):
    st.markdown('<p class="page-title">CUSTOMER EXPERIENCE</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Customer satisfaction ratings across delivery dimensions.</p>', unsafe_allow_html=True)

    section_header("Rating KPIs")
    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("Avg. Customer Rating", f"{kpis['avg_rating']}/5", sub="Overall network")
    with c2:
        high_rat = (df["delivery_rating"] >= 4).sum()
        kpi_card("High-Rating Deliveries (4-5★)", f"{high_rat:,}",
                 sub=f"{high_rat/kpis['total_deliveries']*100:.1f}% of total")
    with c3:
        low_rat = (df["delivery_rating"] <= 2).sum()
        kpi_card("Low-Rating Deliveries (1-2★)", f"{low_rat:,}",
                 sub=f"{low_rat/kpis['total_deliveries']*100:.1f}% of total")

    section_header("Rating Distribution")
    c4, c5 = st.columns([1, 2])
    with c4:
        rat_cnt = df["delivery_rating"].value_counts().sort_index()
        fig_rat = donut_chart(
            [f"{i}★" for i in rat_cnt.index],
            rat_cnt.values,
            title="Rating Distribution",
            colors=[PALETTE["red"], PALETTE["amber"], "#FCD34D", PALETTE["teal"], PALETTE["green"]],
        )
        st.plotly_chart(fig_rat, use_container_width=True)
    with c5:
        rat_bar = rat_cnt.reset_index()
        rat_bar.columns = ["Rating", "Count"]
        rat_bar["Rating"] = rat_bar["Rating"].apply(lambda x: f"{x}★")
        fig_rb = bar_chart(rat_bar, x="Rating", y="Count",
                           title="Rating Frequency",
                           color_seq=[PALETTE["red"], PALETTE["amber"], "#FCD34D", PALETTE["teal"], PALETTE["green"]])
        st.plotly_chart(fig_rb, use_container_width=True)

    section_header("Rating by Partner & Region")
    c6, c7 = st.columns(2)
    with c6:
        partners = analyze_partners(df).sort_values("avg_rating", ascending=False)
        fig_rp = horizontal_bar(partners, x="avg_rating", y="delivery_partner",
                                title="Avg. Rating by Partner", color=PALETTE["teal"])
        st.plotly_chart(fig_rp, use_container_width=True)
    with c7:
        regions = analyze_regions(df).sort_values("avg_rating", ascending=False)
        fig_rr = bar_chart(regions, x="region", y="avg_rating",
                           title="Avg. Rating by Region", color_seq=COLOR_SEQ)
        st.plotly_chart(fig_rr, use_container_width=True)

    section_header("Rating by Delivery Mode & Package Type")
    c8, c9 = st.columns(2)
    with c8:
        modes = analyze_modes(df).sort_values("avg_rating", ascending=False)
        fig_rm = bar_chart(modes, x="delivery_mode", y="avg_rating",
                           title="Avg. Rating by Delivery Mode", color_seq=COLOR_SEQ)
        st.plotly_chart(fig_rm, use_container_width=True)
    with c9:
        pkgs = analyze_package_types(df).sort_values("avg_rating", ascending=False)
        fig_rpkg = bar_chart(pkgs, x="package_type", y="avg_rating",
                             title="Avg. Rating by Package Type", color_seq=COLOR_SEQ)
        fig_rpkg.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig_rpkg, use_container_width=True)

    section_header("Rating vs Delivery Performance")
    perf_rat = df.groupby("performance_category", observed=True)["delivery_rating"].mean().reset_index()
    perf_rat.columns = ["Performance", "Avg Rating"]
    fig_prp = bar_chart(perf_rat, x="Performance", y="Avg Rating",
                        title="Avg. Rating by Delivery Performance Category",
                        color_seq=[PALETTE["green"], PALETTE["amber"], PALETTE["red"]])
    st.plotly_chart(fig_prp, use_container_width=True)

    section_header("Rating by Vehicle Type")
    vehicles = analyze_vehicles(df).sort_values("avg_rating", ascending=False)
    fig_rv = bar_chart(vehicles, x="vehicle_type", y="avg_rating",
                       title="Avg. Rating by Vehicle Type", color_seq=COLOR_SEQ)
    st.plotly_chart(fig_rv, use_container_width=True)


# ─────────────────────────────────────────────
# PAGE 5 — RISK & OPPORTUNITIES + AI ANALYST
# ─────────────────────────────────────────────
def page_risk_opportunities(df, kpis):
    st.markdown('<p class="page-title">RISK & OPPORTUNITIES</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Measurable operational risks, growth opportunities, and AI-assisted executive recommendations.</p>', unsafe_allow_html=True)

    insights = generate_executive_insights(kpis, df)

    # ── Operational Risks ─────────────────────
    section_header("Operational Risks")
    partners = analyze_partners(df)
    regions  = analyze_regions(df)
    weather  = analyze_weather(df)

    worst_region = regions.loc[regions["delayed_pct"].idxmax(), "region"].title()
    worst_region_val = regions["delayed_pct"].max()
    worst_partner = partners.loc[partners["on_time_pct"].idxmin(), "delivery_partner"].title()
    worst_partner_val = partners["on_time_pct"].min()
    worst_weather = weather.loc[weather["delayed_pct"].idxmax(), "weather_condition"].title()
    worst_weather_val = weather["delayed_pct"].max()
    high_cost_partner = partners.loc[partners["avg_cost"].idxmax(), "delivery_partner"].title()
    high_cost_val = partners["avg_cost"].max()
    fail_pct = kpis["failed_pct"]

    risk_card(f"🔴 HIGH DELAY REGION — {worst_region} region records a {worst_region_val:.1f}% delay rate, "
              f"above the network average of {kpis['delayed_pct']}%. Concentration of delays in this region "
              f"may indicate infrastructure or capacity constraints.", "red")

    risk_card(f"🟠 PARTNER PERFORMANCE GAP — {worst_partner} has the lowest on-time delivery rate at "
              f"{worst_partner_val:.1f}%, versus a network average of {kpis['on_time_pct']}%. "
              f"If delivery volume is concentrated here, service-level risk increases.", "amber")

    risk_card(f"🟠 WEATHER SENSITIVITY — {worst_weather} conditions are associated with a {worst_weather_val:.1f}% "
              f"delay rate. Without contingency protocols, adverse weather events pose a recurring service risk.", "amber")

    risk_card(f"🔴 FAILED DELIVERY RATE — {fail_pct}% of all deliveries fail outright "
              f"({kpis['failed_deliveries']:,} records). Failed deliveries represent lost revenue and potential "
              f"customer churn risk that warrants investigation.", "red")

    risk_card(f"🟡 COST CONCENTRATION — {high_cost_partner} averages ₹{high_cost_val:,.0f} per delivery, "
              f"significantly above the network average of ₹{kpis['avg_delivery_cost']:,.0f}. "
              f"If this partner handles high-volume routes, overall cost efficiency is constrained.", "amber")

    # ── Opportunities ─────────────────────────
    section_header("Opportunities")
    best_partner = partners.loc[partners["on_time_pct"].idxmax(), "delivery_partner"].title()
    best_partner_val = partners["on_time_pct"].max()
    gap = best_partner_val - worst_partner_val

    risk_card(f"✅ PARTNER BENCHMARKING — The {gap:.1f} pp on-time rate gap between top ({best_partner}: "
              f"{best_partner_val:.1f}%) and bottom ({worst_partner}: {worst_partner_val:.1f}%) partner "
              f"presents a clear opportunity to transfer best practices across the network.", "green")

    low_cost_partner = partners.loc[partners["avg_cost"].idxmin(), "delivery_partner"].title()
    low_cost_val = partners["avg_cost"].min()
    cost_opp = high_cost_val - low_cost_val
    risk_card(f"✅ COST REDUCTION — The ₹{cost_opp:,.0f} cost spread between highest ({high_cost_partner}: "
              f"₹{high_cost_val:,.0f}) and lowest ({low_cost_partner}: ₹{low_cost_val:,.0f}) cost partners "
              f"indicates a renegotiation or reallocation opportunity.", "green")

    best_region = regions.loc[regions["on_time_pct"].idxmax(), "region"].title()
    best_region_val = regions["on_time_pct"].max()
    risk_card(f"✅ REGIONAL BEST PRACTICE — The {best_region} region achieves {best_region_val:.1f}% on-time rate. "
              f"Investigating what operational conditions contribute to this performance could inform "
              f"targeted improvements in lower-performing regions.", "green")

    modes = analyze_modes(df)
    best_mode_rat = modes.loc[modes["avg_rating"].idxmax(), "delivery_mode"].title()
    best_mode_rat_val = modes["avg_rating"].max()
    risk_card(f"✅ CUSTOMER SATISFACTION — The {best_mode_rat} mode achieves the highest avg. customer rating "
              f"({best_mode_rat_val:.2f}/5). Promoting this mode for applicable routes may improve "
              f"overall network satisfaction scores.", "blue")

    # ── Recommended Actions ───────────────────
    section_header("Recommended Actions")
    for i, action in enumerate(insights["actions"], 1):
        st.markdown(f"""
        <div style="background:#0F2744;border:1px solid #1E3A5F;border-radius:8px;
                    padding:14px 18px;margin-bottom:0.5rem;display:flex;gap:14px;align-items:flex-start;">
            <div style="background:#00C4CC;color:#0B1E3D;border-radius:50%;width:28px;height:28px;
                        display:flex;align-items:center;justify-content:center;font-weight:800;
                        font-size:0.82rem;flex-shrink:0;">{i}</div>
            <div style="font-size:0.83rem;color:#E2E8F0;line-height:1.65;">{action}</div>
        </div>
        """, unsafe_allow_html=True)

    # ── AI Executive Summary ──────────────────
    section_header("AI Executive Analyst Summary")
    st.markdown("""
    <div style="background:#0B1E3D;border-radius:10px;padding:20px 24px;color:#E2E8F0;margin-bottom:1rem;">
        <div style="font-size:0.65rem;text-transform:uppercase;letter-spacing:0.12em;color:#00C4CC;margin-bottom:8px;">
            ▶ DETERMINISTIC AI EXECUTIVE ANALYST — Based on verified metrics only
        </div>
    """, unsafe_allow_html=True)

    st.markdown('<div style="color:#00C4CC;font-size:0.7rem;font-weight:600;letter-spacing:0.08em;margin-bottom:6px;">KEY FINDINGS</div>', unsafe_allow_html=True)
    for f in insights["findings"]:
        st.markdown(f'<div style="background:#1E3A5F;border-left:3px solid #00C4CC;border-radius:4px;padding:10px 14px;margin-bottom:6px;font-size:0.82rem;line-height:1.6;color:#E2E8F0;">{f}</div>', unsafe_allow_html=True)

    col_r, col_o = st.columns(2)
    with col_r:
        st.markdown('<div style="color:#EF4444;font-size:0.7rem;font-weight:600;letter-spacing:0.08em;margin:12px 0 6px;">OPERATIONAL RISKS</div>', unsafe_allow_html=True)
        for r in insights["risks"]:
            st.markdown(f'<div style="background:#2D0A0A;border-left:3px solid #EF4444;border-radius:4px;padding:10px 14px;margin-bottom:6px;font-size:0.82rem;line-height:1.6;color:#F8D7D7;">{r}</div>', unsafe_allow_html=True)
    with col_o:
        st.markdown('<div style="color:#22C55E;font-size:0.7rem;font-weight:600;letter-spacing:0.08em;margin:12px 0 6px;">OPPORTUNITIES</div>', unsafe_allow_html=True)
        for o in insights["opportunities"]:
            st.markdown(f'<div style="background:#002D12;border-left:3px solid #22C55E;border-radius:4px;padding:10px 14px;margin-bottom:6px;font-size:0.82rem;line-height:1.6;color:#BBF7D0;">{o}</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Data Quality Status ───────────────────
    section_header("Data Quality Status")
    _, quality_df = load_and_clean_data()
    overall = quality_df[quality_df["check"] == "Overall Data Quality"]["value"].values[0]
    badge = f'<span class="dq-pass">✔ {overall}</span>' if overall == "PASS" else f'<span class="dq-warn">⚠ {overall}</span>'
    st.markdown(f'<p style="margin-bottom:8px;">Data Quality: {badge}</p>', unsafe_allow_html=True)
    st.dataframe(quality_df[quality_df["check"] != "Overall Data Quality"], use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────
# MAIN APP ENTRY POINT
# ─────────────────────────────────────────────
def main():
    st.set_page_config(
        page_title="Delivery Logistics Dashboard | HrishavHarino",
        page_icon="📦",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    apply_css()

    # Load & clean data
    df_raw, quality_df = load_and_clean_data()
    df = create_features(df_raw)

    # ── SIDEBAR ──────────────────────────────────
    with st.sidebar:
        st.markdown("""
        <div style="padding:16px 0 8px;">
            <div style="font-size:0.6rem;text-transform:uppercase;letter-spacing:0.15em;color:#64748B;margin-bottom:2px;">ANALYTICS PLATFORM</div>
            <div style="font-size:1.1rem;font-weight:700;color:#FFFFFF;">📦 DeliveryOps</div>
            <div style="font-size:0.7rem;color:#64748B;">Logistics Intelligence Dashboard</div>
        </div>
        <hr style="border-color:#1E3A5F;margin:8px 0 16px;">
        """, unsafe_allow_html=True)

        page = st.radio(
            "NAVIGATION",
            ["🏠 Command Center", "📊 Delivery Performance", "💰 Cost & Efficiency",
             "⭐ Customer Experience", "⚠️ Risk & Opportunities"],
            label_visibility="visible",
        )

        st.markdown("<hr style='border-color:#1E3A5F;margin:16px 0;'>", unsafe_allow_html=True)
        st.markdown('<div style="font-size:0.65rem;text-transform:uppercase;letter-spacing:0.1em;color:#64748B;margin-bottom:8px;">GLOBAL FILTERS</div>', unsafe_allow_html=True)

        # Filters
        all_partners = sorted(df["delivery_partner"].str.title().unique())
        sel_partners = st.multiselect("Delivery Partner", all_partners, default=all_partners, key="f_partner")

        all_regions = sorted(df["region"].str.title().unique())
        sel_regions = st.multiselect("Region", all_regions, default=all_regions, key="f_region")

        all_modes = sorted(df["delivery_mode"].str.title().unique())
        sel_modes = st.multiselect("Delivery Mode", all_modes, default=all_modes, key="f_mode")

        all_vehicles = sorted(df["vehicle_type"].str.title().unique())
        sel_vehicles = st.multiselect("Vehicle Type", all_vehicles, default=all_vehicles, key="f_vehicle")

        all_weather = sorted(df["weather_condition"].str.title().unique())
        sel_weather = st.multiselect("Weather Condition", all_weather, default=all_weather, key="f_weather")

        all_pkg = sorted(df["package_type"].str.title().unique())
        sel_pkg = st.multiselect("Package Type", all_pkg, default=all_pkg, key="f_pkg")

        all_status = sorted(df["delivery_status"].str.title().unique())
        sel_status = st.multiselect("Delivery Status", all_status, default=all_status, key="f_status")

        st.markdown("<hr style='border-color:#1E3A5F;margin:16px 0;'>", unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:0.65rem;color:#64748B;">Author: HrishavHarino<br>Dataset: India Multi-Partner<br>Records: {len(df):,}</div>', unsafe_allow_html=True)

    # ── APPLY FILTERS ─────────────────────────
    mask = (
        df["delivery_partner"].str.title().isin(sel_partners) &
        df["region"].str.title().isin(sel_regions) &
        df["delivery_mode"].str.title().isin(sel_modes) &
        df["vehicle_type"].str.title().isin(sel_vehicles) &
        df["weather_condition"].str.title().isin(sel_weather) &
        df["package_type"].str.title().isin(sel_pkg) &
        df["delivery_status"].str.title().isin(sel_status)
    )
    df_filtered = df[mask]

    if df_filtered.empty:
        st.warning("No data matches the selected filters. Please adjust the sidebar filters.")
        return

    kpis = calculate_kpis(df_filtered)

    # ── RENDER PAGE ───────────────────────────
    if page == "🏠 Command Center":
        page_command_center(df_filtered, kpis)
    elif page == "📊 Delivery Performance":
        page_delivery_performance(df_filtered, kpis)
    elif page == "💰 Cost & Efficiency":
        page_cost_efficiency(df_filtered, kpis)
    elif page == "⭐ Customer Experience":
        page_customer_experience(df_filtered, kpis)
    elif page == "⚠️ Risk & Opportunities":
        page_risk_opportunities(df_filtered, kpis)


if __name__ == "__main__":
    main()
