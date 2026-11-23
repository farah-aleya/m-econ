"""
M-ECON | Step 2-5 + 7: clean raw data, build master tables, audit, stationarity, data dictionary.
Run from the project root:  python scripts/02_clean.py
Inputs : raw/  (from 01_download.py + manual files)
Outputs: processed/monthly_master.csv, processed/quarterly_master.csv,
         processed/missing_audit.csv, processed/stationarity.csv,
         processed/data_dictionary.csv, processed/run_log.txt
         processed/fuel_monthly.csv (context only, not a model input)
         outputs/powerbi_monthly.csv, outputs/powerbi_quarterly.csv, outputs/powerbi_events.csv
"""
import io
import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import requests

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
RAW, PROC, OUT = ROOT / "raw", ROOT / "processed", ROOT / "outputs"
PROC.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True)

START, END = "2010-01-01", "2026-10-01"      # monthly window kept in the master table
LOG = []
def log(msg):
    print(msg); LOG.append(str(msg))

def ms(s):
    """to month-start timestamp"""
    return pd.to_datetime(s).dt.to_period("M").dt.to_timestamp()

def rp(name):
    return pd.read_parquet(RAW / f"{name}.parquet")

# ------------------------------------------------------------------ OPR decisions
# Source: BNM, OPR Decisions & Statements (https://www.bnm.gov.my/monetary-stability/opr-decisions).
# Only the meetings where the OPR level CHANGED are needed. Spot-check against the BNM page.
OPR_FILE = RAW / "opr_decisions.csv"
if not OPR_FILE.exists():
    pd.DataFrame([
        ("2009-02-24", 2.00), ("2010-03-04", 2.25), ("2010-05-13", 2.50), ("2010-07-08", 2.75),
        ("2011-05-05", 3.00), ("2014-07-10", 3.25), ("2016-07-13", 3.00), ("2018-01-25", 3.25),
        ("2019-05-07", 3.00), ("2020-01-22", 2.75), ("2020-03-03", 2.50), ("2020-05-05", 2.00),
        ("2020-07-07", 1.75), ("2022-05-11", 2.00), ("2022-07-06", 2.25), ("2022-09-08", 2.50),
        ("2022-11-03", 2.75), ("2023-05-03", 3.00), ("2025-07-09", 2.75),
    ], columns=["date", "opr"]).to_csv(OPR_FILE, index=False)
    log("Created raw/opr_decisions.csv (pre-filled from BNM; please spot-check)")

# ------------------------------------------------------------------ monthly series
m = {}

# CPI headline and core (overall), YoY already computed by DOSM
cpi = rp("cpi_headline_inflation"); cpi = cpi[cpi.division == "overall"].copy()
cpi["date"] = ms(cpi["date"]); m["cpi_yoy"] = cpi.set_index("date")["inflation_yoy"]
core = rp("cpi_core_inflation"); core = core[core.division == "overall"].copy()
core["date"] = ms(core["date"]); m["core_yoy"] = core.set_index("date")["inflation_yoy"]

# PPI and IPI: index level (abs) + YoY published by DOSM
for name in ["ppi", "ipi"]:
    df = rp(name); df["date"] = ms(df["date"])
    m[f"{name}_index"] = df[df.series == "abs"].set_index("date")["index"]
    m[f"{name}_yoy"] = df[df.series == "growth_yoy"].set_index("date")["index"]

# Unemployment rate
lfs = rp("lfs_month"); lfs["date"] = ms(lfs["date"]); m["u_rate"] = lfs.set_index("date")["u_rate"]

# Leading and coincident indexes
ei = rp("economic_indicators"); ei["date"] = ms(ei["date"]); ei = ei.set_index("date")
m["leading_index"] = ei["leading"]; m["coincident_index"] = ei["coincident"]

# Trade (overall), RM million
tr = rp("trade_sitc_1d"); tr = tr[tr.section == "overall"].copy(); tr["date"] = ms(tr["date"])
tr = tr.set_index("date")
m["exports_rm_mil"] = tr["exports"] / 1e6; m["imports_rm_mil"] = tr["imports"] / 1e6

# USD/MYR (ringgit per US dollar), monthly average of daily 1200 rates
def get_usdmyr():
    f = RAW / "exchangerates_daily_1200.parquet"
    if not f.exists():
        try:
            r = requests.get("https://storage.data.gov.my/finsector/exr/daily_1200.parquet", timeout=120)
            if r.status_code == 200 and r.content[:4] == b"PAR1":
                f.write_bytes(r.content); log("Downloaded exchangerates_daily_1200.parquet")
        except Exception as e:
            log(f"daily_1200 download failed: {e}")
    if f.exists():
        df = pd.read_parquet(f)
        log(f"daily_1200 columns: {list(df.columns)[:12]}")
        if "rate_type" in df.columns:                     # buying / middle / selling -> keep middle
            df = df[df["rate_type"] == "middle"]
        if "currency" in df.columns:                      # long layout
            df = df[df["currency"].str.lower() == "usd"]
            vcol = [c for c in df.columns if df[c].dtype.kind == "f"][0]
            s = df.set_index(pd.to_datetime(df["date"]))[vcol]
        else:                                             # wide layout
            col = next(c for c in df.columns if c.lower() in ("usd", "myr_usd"))
            s = df.set_index(pd.to_datetime(df["date"]))[col]
        src = "data.gov.my exchangerates_daily_1200"
    else:
        df = rp("exchangerates")
        s = df.set_index(pd.to_datetime(df["date"]))["myr_usd"]
        src = "data.gov.my exchangerates (legacy file, ends Jan 2026)"
        log("WARNING: using legacy exchange-rate file that ends Jan 2026")
    s = s.astype(float)
    if s.median() < 1:            # quoted as USD per MYR -> invert to MYR per USD
        s = 1 / s
    out = s.resample("MS").mean()
    log(f"USD/MYR source: {src}; last month {out.dropna().index.max().date()}")
    return out
m["usdmyr"] = get_usdmyr()

# BIS nominal effective exchange rate, broad (2020 = 100); a rise = ringgit stronger
with open(RAW / "bis_neer_malaysia.csv", encoding="utf-8-sig") as fh:
    lines = fh.read().splitlines()
hdr = next(i for i, l in enumerate(lines) if l.startswith("KEY:"))
bis = pd.read_csv(io.StringIO("\n".join(lines[hdr:])))
bis["date"] = ms(bis["TIME_PERIOD:Period"]); m["neer_broad"] = bis.set_index("date")["OBS_VALUE:Value"]

# World Bank Pink Sheet: Brent (US$/bbl) and Food price index (2010 = 100)
def pink(sheet, find_col):
    x = pd.read_excel(RAW / "CMO-Historical-Data-Monthly.xlsx", sheet_name=sheet, header=None)
    col = find_col(x)
    rows = x[x[0].astype(str).str.match(r"^\d{4}M\d{2}$")]
    dates = pd.to_datetime(rows[0].str.replace("M", "-") + "-01")
    return pd.Series(pd.to_numeric(rows[col], errors="coerce").values, index=dates)
def brent_col(x):
    return next(c for c in x.columns if str(x.iloc[4, c]).strip() == "Crude oil, Brent")
def food_col(x):
    return next(c for c in x.columns if any(str(v).strip().startswith("Food") for v in x.iloc[4:9, c]))
m["brent_usd"] = pink("Monthly Prices", brent_col)
m["food_index_wb"] = pink("Monthly Indices", food_col)

# OPR: monthly level at end of month
opr = pd.read_csv(OPR_FILE, parse_dates=["date"]).sort_values("date")
grid = pd.date_range("2009-01-01", END, freq="MS")
month_end = grid + pd.offsets.MonthEnd(0)
m["opr"] = pd.Series(
    [opr.loc[opr.date <= d, "opr"].iloc[-1] if (opr.date <= d).any() else np.nan for d in month_end], index=grid)

# ------------------------------------------------------------------ monthly master
monthly = pd.DataFrame(m).sort_index()
# derived YoY growth for level series
for c in ["usdmyr", "neer_broad", "brent_usd", "food_index_wb", "leading_index", "coincident_index",
          "exports_rm_mil", "imports_rm_mil"]:
    monthly[f"{c}_yoy"] = monthly[c].pct_change(12, fill_method=None) * 100
monthly["opr_change_12m"] = monthly["opr"].diff(12)
monthly = monthly.loc[START:END]
monthly.index.name = "date"
monthly.round(4).to_csv(PROC / "monthly_master.csv")
log(f"monthly_master: {monthly.shape}, {monthly.index.min().date()} to {monthly.index.max().date()}")

# ------------------------------------------------------------------ fuel prices (context only)
# Source: data.gov.my fuelprice (weekly, from 30 Mar 2017). Kept OUT of monthly_master so it never
# enters the models (it would cut the inflation sample to 2018+). Used for the dashboard and report.
FUEL_FILE = RAW / "fuelprice.csv"
fuel_m = None
if FUEL_FILE.exists():
    fp = pd.read_csv(FUEL_FILE, parse_dates=["date"])
    fp = fp[fp["series_type"] == "level"].drop(columns="series_type").set_index("date").sort_index()
    fuel_cols = {"ron95": "fuel_ron95_market", "ron97": "fuel_ron97", "diesel": "fuel_diesel_peninsular",
                 "diesel_eastmsia": "fuel_diesel_east", "ron95_budi95": "fuel_ron95_budi95",
                 "ron95_skps": "fuel_ron95_skps", "diesel_skds": "fuel_diesel_skds", "diesel_budi": "fuel_diesel_budi"}
    fp = fp[[c for c in fuel_cols if c in fp.columns]].rename(columns=fuel_cols).astype(float)
    fuel_m = fp.resample("MS").mean().loc["2017-04-01":END]   # Mar 2017 has one week only, so start Apr
    fuel_m["fuel_ron95_market_yoy"] = fuel_m["fuel_ron95_market"].pct_change(12, fill_method=None) * 100
    fuel_m["fuel_diesel_peninsular_yoy"] = fuel_m["fuel_diesel_peninsular"].pct_change(12, fill_method=None) * 100
    fuel_m.index.name = "date"
    fuel_m.round(4).to_csv(PROC / "fuel_monthly.csv")
    log(f"fuel_monthly: {fuel_m.shape}, {fuel_m.index.min().date()} to {fuel_m.index.max().date()} (context only)")
else:
    log("raw/fuelprice.csv not found: fuel prices skipped")

# ------------------------------------------------------------------ quarterly master
gdp = rp("gdp_qtr_real"); gdp["date"] = ms(gdp["date"])
q = pd.DataFrame({
    "gdp_real_rm_mil": gdp[gdp.series == "abs"].set_index("date")["value"],
    "gdp_yoy": gdp[gdp.series == "growth_yoy"].set_index("date")["value"],
})
full = pd.DataFrame(m).sort_index()
mean_cols = ["cpi_yoy", "core_yoy", "ppi_index", "ipi_index", "u_rate", "leading_index", "coincident_index",
             "usdmyr", "neer_broad", "brent_usd", "food_index_wb", "opr"]
sum_cols = ["exports_rm_mil", "imports_rm_mil"]
qm = full[mean_cols].resample("QS").mean().join(full[sum_cols].resample("QS").sum(min_count=3))
for c in ["ppi_index", "ipi_index", "leading_index", "coincident_index", "usdmyr", "neer_broad",
          "brent_usd", "food_index_wb", "exports_rm_mil", "imports_rm_mil"]:
    qm[f"{c}_yoy"] = qm[c].pct_change(4, fill_method=None) * 100
quarterly = q.join(qm, how="left").loc["2016-01-01":]
quarterly.index.name = "date"
quarterly["covid_dummy"] = ((quarterly.index >= "2020-01-01") & (quarterly.index <= "2021-12-01")).astype(int)
quarterly.round(4).to_csv(PROC / "quarterly_master.csv")
log(f"quarterly_master: {quarterly.shape}, {quarterly.index.min().date()} to {quarterly.index.max().date()}")
log("GDP YoY last 3 quarters: " + quarterly["gdp_yoy"].tail(3).to_string().replace("\n", " | "))

# ------------------------------------------------------------------ missing-value audit
rows = []
for name, df in [("monthly", monthly), ("quarterly", quarterly)]:
    for c in df.columns:
        s = df[c]; nn = s.dropna()
        first, last = (nn.index.min(), nn.index.max()) if len(nn) else (None, None)
        inner_gaps = int(s.loc[first:last].isna().sum()) if first is not None else None
        rows.append({"table": name, "variable": c, "first": first.date() if first is not None else None,
                     "last": last.date() if last is not None else None, "n_obs": len(nn),
                     "missing_in_window": int(s.isna().sum()), "internal_gaps": inner_gaps})
audit = pd.DataFrame(rows); audit.to_csv(PROC / "missing_audit.csv", index=False)
log("Variables with internal gaps: " + ", ".join(audit.loc[audit.internal_gaps > 0, "variable"]) if
    (audit.internal_gaps > 0).any() else "No internal gaps in any series")

# ------------------------------------------------------------------ stationarity (ADF + KPSS)
from statsmodels.tsa.stattools import adfuller, kpss
warnings.filterwarnings("ignore")
st_rows = []
targets = {"monthly": [c for c in monthly.columns if c.endswith("_yoy") or c in ("u_rate", "opr", "opr_change_12m")],
           "quarterly": ["gdp_yoy", "cpi_yoy", "u_rate", "opr"] + [c for c in quarterly.columns if c.endswith("_yoy") and c != "gdp_yoy" and c != "cpi_yoy" and c != "core_yoy"]}
for tname, cols in targets.items():
    df = monthly if tname == "monthly" else quarterly
    for c in cols:
        s = df[c].dropna()
        if len(s) < 20:
            continue
        try:
            adf_p = adfuller(s, autolag="AIC")[1]
            kpss_p = kpss(s, regression="c", nlags="auto")[1]
        except Exception as e:
            adf_p = kpss_p = np.nan
        verdict = ("stationary" if adf_p < 0.05 and kpss_p > 0.05 else
                   "non-stationary" if adf_p >= 0.05 and kpss_p <= 0.05 else "mixed")
        st_rows.append({"table": tname, "variable": c, "n": len(s), "adf_p": round(adf_p, 4),
                        "kpss_p": round(kpss_p, 4), "verdict": verdict})
stat = pd.DataFrame(st_rows); stat.to_csv(PROC / "stationarity.csv", index=False)
log("Stationarity verdicts: " + stat.verdict.value_counts().to_dict().__str__())

# ------------------------------------------------------------------ data dictionary
DD = [
 ("cpi_yoy", "Headline CPI inflation, YoY %", "OpenDOSM cpi_headline_inflation (division = overall)", "M", "Inflation target"),
 ("core_yoy", "Core CPI inflation, YoY %", "OpenDOSM cpi_core_inflation (overall)", "M", "Supporting"),
 ("ppi_index / ppi_yoy", "Producer Price Index (2010 = 100) and YoY %", "OpenDOSM ppi", "M", "Inflation predictor"),
 ("ipi_index / ipi_yoy", "Industrial Production Index (2015 = 100) and YoY %", "OpenDOSM ipi", "M", "GDP predictor"),
 ("u_rate", "Unemployment rate, %", "OpenDOSM lfs_month", "M", "Both"),
 ("leading_index / coincident_index", "Leading and Coincident Indexes", "OpenDOSM economic_indicators", "M", "GDP predictor"),
 ("exports_rm_mil / imports_rm_mil", "Total exports and imports, RM million", "OpenDOSM trade_sitc_1d (overall)", "M", "GDP predictor"),
 ("usdmyr", "Ringgit per US dollar, monthly average of daily 1200 rate (rise = ringgit weaker)", "data.gov.my exchangerates_daily_1200 (BNM)", "M", "Both; scenario input"),
 ("neer_broad", "Nominal effective exchange rate, broad, 2020 = 100 (rise = ringgit stronger)", "BIS WS_EER M.N.B.MY", "M", "Both"),
 ("brent_usd", "Brent crude oil, US$/bbl", "World Bank Pink Sheet, Monthly Prices", "M", "Both; scenario input"),
 ("food_index_wb", "World Bank food price index, 2010 = 100", "World Bank Pink Sheet, Monthly Indices", "M", "Inflation predictor"),
 ("opr", "Overnight Policy Rate, level at month end, %", "BNM OPR Decisions & Statements", "M (from events)", "Both"),
 ("*_yoy (derived)", "Year-on-year % change computed by the team", "Derived", "M / Q", "Model input"),
 ("gdp_real_rm_mil / gdp_yoy", "Real GDP at constant 2015 prices and YoY %", "OpenDOSM gdp_qtr_real", "Q", "GDP target"),
 ("covid_dummy", "1 for 2020 Q1 to 2021 Q4", "Derived", "Q", "Structural break control"),
 ("fuel_ron95_market / fuel_ron97 / fuel_diesel_peninsular / fuel_diesel_east", "Pump prices, RM per litre, monthly average of weekly prices (RON95 market price is the unsubsidised price from 30 Sep 2025)", "data.gov.my fuelprice", "M (from weekly)", "Context only, not a model input"),
 ("fuel_ron95_budi95 / fuel_ron95_skps / fuel_diesel_skds / fuel_diesel_budi", "Subsidised pump prices under BUDI95, SKPS, SKDS and BUDI Diesel, RM per litre", "data.gov.my fuelprice", "M (from weekly)", "Context only, not a model input"),
]
pd.DataFrame(DD, columns=["variable", "description", "source", "frequency", "role"]).to_csv(PROC / "data_dictionary.csv", index=False)

# ------------------------------------------------------------------ Power BI exports (long format)
def to_long(df, freq):
    out = df.reset_index().melt(id_vars="date", var_name="variable", value_name="value").dropna()
    out["frequency"] = freq
    return out
pbi_m = monthly.join(fuel_m, how="left") if fuel_m is not None else monthly
to_long(pbi_m, "M").to_csv(OUT / "powerbi_monthly.csv", index=False)
to_long(quarterly, "Q").to_csv(OUT / "powerbi_quarterly.csv", index=False)

# policy and shock events for dashboard annotations
EVENTS = [
 ("2014-07-01", "Oil price fall begins (Brent from US$112 in Jun 2014)", "Global shock"),
 ("2015-04-01", "GST introduced at 6%", "Tax"),
 ("2017-03-30", "Weekly fuel pricing data begins", "Fuel"),
 ("2018-06-01", "GST set to 0% (replaced by SST from 1 Sep 2018)", "Tax"),
 ("2018-09-01", "SST introduced", "Tax"),
 ("2020-03-18", "Movement Control Order (COVID-19)", "COVID"),
 ("2024-06-10", "Diesel subsidy rationalisation (Peninsular)", "Fuel"),
 ("2025-07-01", "SST expansion", "Tax"),
 ("2025-09-30", "RON95 targeted subsidy (BUDI95) begins", "Fuel"),
 ("2026-07-01", "Subsidised diesel for individuals (BUDI Diesel, RM2.10/litre) begins", "Fuel"),
]
pd.DataFrame(EVENTS, columns=["date", "event", "category"]).to_csv(OUT / "powerbi_events.csv", index=False)

(PROC / "run_log.txt").write_text("\n".join(LOG), encoding="utf-8")
print("\nDone. See processed/ and outputs/.")
