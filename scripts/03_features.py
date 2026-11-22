"""
M-ECON | Step 6: publication-lag alignment and lag features (no data leakage).
Run from the project root:  python scripts/03_features.py
Inputs : processed/monthly_master.csv, processed/quarterly_master.csv
Outputs: processed/features_monthly.csv    (inflation pipeline, target = next month's CPI YoY)
         processed/features_quarterly.csv  (GDP pipeline, target = next quarter's GDP YoY)
         processed/publication_lags.csv    (table for the report, Section 4.3)

Logic
-----
A forecast is made at "origin" t for the target at t+1. A predictor may only be used if it would
already have been published by then. DOSM releases some series later than others, so each
predictor is first shifted by its publication delay (in periods), then lagged further.
Delays are typical DOSM / BNM / BIS / World Bank release gaps; check against the release calendars.
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "processed"

monthly = pd.read_csv(PROC / "monthly_master.csv", parse_dates=["date"], index_col="date")
quarterly = pd.read_csv(PROC / "quarterly_master.csv", parse_dates=["date"], index_col="date")

# ---------------------------------------------------------------- publication delays (months)
# value for month m is treated as usable from origin m + delay
PUB_DELAY_M = {
    "cpi_yoy": 0,            # CPI(m) released ~3-4 weeks after m; known when forecasting m+1
    "core_yoy": 0,
    "ppi_yoy": 0,            # released ~4 weeks after m
    "exports_rm_mil_yoy": 0, "imports_rm_mil_yoy": 0,   # ~3 weeks after m
    "brent_usd_yoy": 0, "food_index_wb_yoy": 0,          # market prices / Pink Sheet early next month
    "usdmyr_yoy": 0, "neer_broad_yoy": 0,                # daily market data
    "opr": 0, "opr_change_12m": 0,                       # policy decisions, real time
    "ipi_yoy": 1,            # released ~6 weeks after m
    "u_rate": 1,             # released ~6 weeks after m
    "leading_index_yoy": 2, "coincident_index_yoy": 2,   # released ~2 months after m
}
LAGS_M = [0, 1, 3, 6, 12]

def build_monthly():
    f = pd.DataFrame(index=monthly.index)
    f["target_cpi_yoy_next"] = monthly["cpi_yoy"].shift(-1)          # what we forecast
    for col, delay in PUB_DELAY_M.items():
        if col not in monthly:
            continue
        avail = monthly[col].shift(delay)
        for L in LAGS_M:
            f[f"{col}_L{L + delay}"] = avail.shift(L)                # name shows total months back
    f["month"] = f.index.month                                       # seasonality dummy source
    f["covid"] = ((f.index >= "2020-03-01") & (f.index <= "2021-12-01")).astype(int)
    return f

# ---------------------------------------------------------------- quarterly (quarters)
PUB_DELAY_Q = {
    "gdp_yoy": 0,             # GDP(q) advance estimate ~3 weeks after q
    "cpi_yoy": 0, "ppi_index_yoy": 0, "exports_rm_mil_yoy": 0, "imports_rm_mil_yoy": 0,
    "brent_usd_yoy": 0, "food_index_wb_yoy": 0, "usdmyr_yoy": 0, "neer_broad_yoy": 0, "opr": 0,
    "ipi_index_yoy": 0,       # last month of q released ~6 weeks after q end, before GDP preliminary
    "u_rate": 0,
    "leading_index_yoy": 1, "coincident_index_yoy": 1,   # last month of q released ~2 months later
}
LAGS_Q = [0, 1, 2, 4]

def build_quarterly():
    f = pd.DataFrame(index=quarterly.index)
    f["target_gdp_yoy_next"] = quarterly["gdp_yoy"].shift(-1)
    for col, delay in PUB_DELAY_Q.items():
        if col not in quarterly:
            continue
        avail = quarterly[col].shift(delay)
        for L in LAGS_Q:
            f[f"{col}_L{L + delay}"] = avail.shift(L)
    f["quarter"] = f.index.quarter
    f["covid"] = quarterly["covid_dummy"]
    return f

fm, fq = build_monthly(), build_quarterly()
fm.round(4).to_csv(PROC / "features_monthly.csv")
fq.round(4).to_csv(PROC / "features_quarterly.csv")

rows = [{"variable": k, "pipeline": "inflation (monthly)", "publication_delay": f"{v} month(s)"} for k, v in PUB_DELAY_M.items()]
rows += [{"variable": k, "pipeline": "GDP (quarterly)", "publication_delay": f"{v} quarter(s)"} for k, v in PUB_DELAY_Q.items()]
pd.DataFrame(rows).to_csv(PROC / "publication_lags.csv", index=False)

def summary(f, tgt):
    usable = f.dropna(subset=[tgt])
    full = usable.dropna()
    print(f"{tgt}: {f.shape[1]-1} features | rows with target {len(usable)} "
          f"({usable.index.min().date()} to {usable.index.max().date()}) | complete rows {len(full)}")
summary(fm, "target_cpi_yoy_next")
summary(fq, "target_gdp_yoy_next")
print("Latest origin rows (used for the live forecast):")
print("  monthly :", fm.index.max().date(), "  quarterly:", fq.index.max().date())
print("Done. See processed/features_*.csv and processed/publication_lags.csv")
