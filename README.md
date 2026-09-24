# Delivery & Logistics Performance Analytics Dashboard

**Author:** Hrishav Hari 
**Type:** Business / Data Analytics Internship Project  
**Domain:** Logistics & Supply Chain Operations

---

## Project Overview

This project transforms raw logistics delivery data into a complete business analytics solution — from raw data ingestion through cleaning, validation, feature engineering, KPI analysis, and interactive visualisation — culminating in a professional multi-page Streamlit dashboard and a consulting-style Word report.

The project demonstrates practical skills in Python, Pandas, NumPy, Plotly, Streamlit, and business analytics methodology, without the use of machine-learning models.

---

## Business Problem

A logistics and delivery company operating across five Indian regions with nine delivery partners wants to understand:

- Overall delivery performance and on-time rates
- Which partners, regions, and delivery modes perform differently
- Where delivery costs are concentrated and where efficiency can improve
- How customer satisfaction varies across dimensions
- What operational risks exist and what actions management should consider

---

## Objectives

1. Load, clean, and validate a 25,000-record logistics dataset
2. Engineer business-relevant derived features
3. Calculate verified KPIs
4. Analyse delivery performance, costs, and customer ratings by dimension
5. Identify measurable operational risks and opportunities
6. Present findings in an interactive Streamlit dashboard
7. Generate a professional Word report suitable for business presentation

---

## Dataset

**Source:** [Delivery Logistics Dataset — India Multi-Partner](https://www.kaggle.com/datasets/muhammadahmaddaar/delivery-logistics-dataset-india-multi-partner)  
**File:** `data/Delivery_Logistics.csv`  
**Records:** 25,000  
**Columns:** 15

### Dataset Description

| Column | Type | Description |
|---|---|---|
| delivery_id | float | Delivery reference (not a unique key) |
| delivery_partner | str | Logistics partner name (9 partners) |
| package_type | str | Category of package (9 types) |
| vehicle_type | str | Vehicle used (6 types) |
| delivery_mode | str | Delivery speed tier (4 modes) |
| region | str | Geographic region (5 regions) |
| weather_condition | str | Weather during delivery (6 conditions) |
| distance_km | float | Delivery distance in kilometres |
| package_weight_kg | float | Package weight in kilograms |
| delivery_time_hours | str* | Actual delivery time (hours, encoded) |
| expected_time_hours | str* | Expected delivery time (hours, encoded) |
| delayed | str | Whether delivery was delayed (yes/no) |
| delivery_status | str | Final status: delivered / delayed / failed |
| delivery_rating | int | Customer rating 1–5 |
| delivery_cost | float | Delivery cost in INR |

*Time columns are stored as nanosecond-epoch timestamp strings; the project decodes them to integer hours.

---

## Technologies Used

| Technology | Purpose |
|---|---|
| Python 3.8+ | Core language |
| Pandas | Data loading, cleaning, aggregation |
| NumPy | Numerical operations, feature engineering |
| Plotly | Interactive charts |
| Streamlit | Dashboard frontend |
| python-docx | Word report generation |
| Matplotlib | Static chart generation for report |

---

## Project Structure

```
HrishavHarino_DeliveryLogistics/
│
├── app.py                                          ← Main Streamlit application
├── generate_report.py                              ← Word report generator
├── data/
│   └── Delivery_Logistics.csv                     ← Source dataset
├── requirements.txt                                ← Python dependencies
├── README.md                                       ← This file
└── HrishavHarino_DeliveryLogistics_ProjectReport.docx  ← Professional report
```

---

## Data Processing Pipeline

```
Raw CSV (25,000 rows, 15 columns)
    │
    ├── Column standardisation
    ├── Nanosecond-epoch time decoding → integer hours
    ├── Categorical string normalisation
    ├── Numeric type enforcement
    ├── Range validation (cost, distance, weight, rating)
    └── Duplicate & missing value audit
         │
         ▼
    Clean DataFrame
         │
         ├── Feature Engineering
         │   ├── time_gap_hours = delivery_time_hours − expected_time_hours
         │   ├── cost_per_km = delivery_cost / distance_km
         │   ├── cost_per_kg = delivery_cost / package_weight_kg
         │   ├── distance_band (Short / Medium / Long)
         │   ├── weight_band (Light / Medium / Heavy)
         │   ├── performance_category (On-Time / Delayed / Failed)
         │   └── rating_band (Low / Medium / High)
         │
         └── KPI Calculation → Business Analysis → Dashboard / Report
```

---

## KPI Framework

| KPI | Formula |
|---|---|
| On-Time Delivery % | Delivered / Total × 100 |
| Delayed Delivery % | Delayed / Total × 100 |
| Failed Delivery % | Failed / Total × 100 |
| Avg Delivery Time | mean(delivery_time_hours) |
| Avg Delivery Cost | mean(delivery_cost) |
| Total Delivery Cost | sum(delivery_cost) |
| Avg Cost per KM | mean(delivery_cost / distance_km) |
| Avg Cost per KG | mean(delivery_cost / package_weight_kg) |
| Avg Customer Rating | mean(delivery_rating) |

---

## Dashboard Pages

| Page | Description |
|---|---|
| 🏠 Command Center | 3 headline KPIs, status distribution, partner overview, executive observations |
| 📊 Delivery Performance | On-time/delayed/failed by partner, region, mode, vehicle, weather |
| 💰 Cost & Efficiency | Cost by partner, region, mode, distance band, scatter analysis, heatmap |
| ⭐ Customer Experience | Rating distribution, by partner/region/mode/package/vehicle |
| ⚠️ Risk & Opportunities | Risk cards, opportunity cards, recommended actions, AI analyst |

All pages respond to **7 global sidebar filters**: Partner, Region, Delivery Mode, Vehicle Type, Weather, Package Type, Delivery Status.

---

## Key Insights

*(Derived from verified dataset metrics)*

- Overall on-time delivery rate: **~73.3%**
- Failed delivery rate: **~5.3%** of all records
- Average delivery cost: **₹864.94**
- Measurable performance variation observed across the 9 delivery partners
- Weather condition is associated with observable variation in delay rates
- Significant cost spread between highest- and lowest-cost delivery partners

---

## AI Executive Analyst

The project includes a **deterministic AI Executive Analyst** that:

- Receives only pre-calculated, verified metrics
- Produces 5 Key Findings, 3 Operational Risks, 3 Opportunities, and 5 Recommended Actions
- Does not fabricate numbers, invent trends, or claim unsupported causality
- Functions entirely offline — no API key required

---

## Installation

```bash
# 1. Clone / download the project folder
# 2. Install dependencies
pip install -r requirements.txt

# 3. Place the dataset
# Ensure Delivery_Logistics.csv is inside the data/ folder

# 4. Run the dashboard
streamlit run app.py

# 5. (Optional) Regenerate the Word report
python generate_report.py
```

---

## How to Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

The dashboard will open at `http://localhost:8501`.

---

## Screenshots / UI Preview

The dashboard uses an **"Ops Terminal"** visual identity:

- Deep navy (`#0B1E3D`) sidebar navigation
- Off-white (`#F5F7FA`) main canvas
- Electric teal (`#00C4CC`) accent colour
- KPI cards with status pills
- Dark insight panels with teal left-border
- Risk cards colour-coded by severity (red / amber / green)
- All-caps section headers with teal left-border separators

---

## Limitations

- **No calendar date column** — the dataset does not contain delivery dates, so monthly/quarterly trend analysis is not possible. The dataset is cross-sectional.
- `delivery_id` is not a true primary key — 498 values appear more than once.
- Time columns required custom nanosecond decoding; values represent integer hours.
- No city-level geographic data available in the dataset.

---

## Future Improvements

- Integrate live data feed for real-time operational monitoring
- Add city-level geographic analysis and map visualisations
- Incorporate date/time dimension for trend analysis when data becomes available
- Build partner SLA scorecard with configurable thresholds
- Add anomaly detection for unusual cost or delay spikes
- Connect to an LLM API for dynamic narrative generation

---

*Delivery & Logistics Performance Analytics Dashboard — HrishavHarino*
