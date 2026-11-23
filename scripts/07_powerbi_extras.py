"""
M-ECON | Step 7: extra tables for the Power BI dashboard (run after steps 1 to 6).
Run from the project root:  python scripts/07_powerbi_extras.py
Writes outputs/powerbi_*.csv (variables, corr, top_predictors, importance, backtest, ew_indicators, ew_status,
fan, scenario_slider). Uses only files already produced by steps 2 to 6; no new data, no new modelling.
"""
from pathlib import Path
import re
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC, OUT = ROOT / "processed", ROOT / "outputs"

# 1. variable lookup (label, unit, group) for slicers and axis titles
VARS = [
    ("gdp_yoy", "Real GDP growth", "% YoY", "Target", "Domestic"),
    ("cpi_yoy", "CPI inflation", "% YoY", "Target", "Domestic"),
    ("core_yoy", "Core inflation", "% YoY", "Context", "Domestic"),
    ("ppi_yoy", "Producer prices (PPI)", "% YoY", "Predictor", "Domestic"),
    ("ppi_index_yoy", "Producer prices (PPI)", "% YoY", "Predictor", "Domestic"),
    ("ipi_yoy", "Industrial production", "% YoY", "Predictor", "Domestic"),
    ("ipi_index_yoy", "Industrial production", "% YoY", "Predictor", "Domestic"),
    ("u_rate", "Unemployment rate", "%", "Predictor", "Domestic"),
    ("opr", "Overnight Policy Rate", "%", "Predictor", "Domestic"),
    ("exports_rm_mil_yoy", "Exports", "% YoY", "Predictor", "Domestic"),
    ("imports_rm_mil_yoy", "Imports", "% YoY", "Predictor", "Domestic"),
    ("leading_index_yoy", "Leading Index", "% YoY", "Predictor", "Domestic"),
    ("coincident_index_yoy", "Coincident Index", "% YoY", "Predictor", "Domestic"),
    ("usdmyr", "USD/MYR", "RM per US$", "Predictor", "External"),
    ("usdmyr_yoy", "USD/MYR", "% YoY", "Predictor", "External"),
    ("neer_broad_yoy", "Ringgit NEER", "% YoY", "Predictor", "External"),
    ("brent_usd", "Brent crude", "US$ per barrel", "Predictor", "External"),
    ("brent_usd_yoy", "Brent crude", "% YoY", "Predictor", "External"),
    ("food_index_wb_yoy", "World food prices", "% YoY", "Predictor", "External"),
    ("fuel_ron95_market", "RON95 market price", "RM per litre", "Context", "Domestic"),
    ("fuel_ron95_budi95", "RON95 BUDI95 price", "RM per litre", "Context", "Domestic"),
    ("fuel_diesel_peninsular", "Diesel (Peninsular)", "RM per litre", "Context", "Domestic"),
    ("fuel_diesel_budi", "Diesel BUDI price", "RM per litre", "Context", "Domestic"),
]
pd.DataFrame(VARS, columns=["variable", "label", "unit", "role", "group"]).to_csv(OUT / "powerbi_variables.csv", index=False)

# 2. lagged correlations (heatmap) and top predictors
corr = []
for pipe, f in (("Inflation", "corr_lagged_inflation.csv"), ("GDP growth", "corr_lagged_gdp.csv")):
    c = pd.read_csv(PROC / f); c["target"] = pipe
    c["lag_label"] = c["lag"].astype(str) + (" m" if pipe == "Inflation" else " q")
    corr.append(c[["target", "sample", "label", "group", "lag", "lag_label", "n", "pearson_r", "pearson_p"]])
pd.concat(corr).to_csv(OUT / "powerbi_corr.csv", index=False)
tp = pd.read_csv(PROC / "top_predictors.csv")
tp["target"] = tp["pipeline"].map({"inflation": "Inflation", "gdp": "GDP growth"})
tp.to_csv(OUT / "powerbi_top_predictors.csv", index=False)

# 3. Random Forest importance with readable labels
NAMES = {"gdp_yoy": "GDP growth (own)", "cpi_yoy": "CPI inflation (own)", "ppi_yoy": "PPI", "ipi_yoy": "Industrial production",
         "ipi_index_yoy": "Industrial production", "opr": "OPR", "exports_rm_mil_yoy": "Exports",
         "neer_broad_yoy": "NEER", "coincident_index_yoy": "Coincident Index", "covid": "COVID dummy"}
def nice(f):
    m = re.match(r"(.+)_L(\d+)$", f)
    return f"{NAMES.get(m.group(1), m.group(1))} (lag {m.group(2)})" if m else NAMES.get(f, f)
imp = pd.read_csv(PROC / "feature_importance.csv")
imp["input"] = imp["feature"].map(nice)
imp["setup_label"] = imp["setup"].map({"A1": "GDP (with IPI)", "A2": "GDP (Coincident Index)", "B": "Inflation"})
imp.to_csv(OUT / "powerbi_importance.csv", index=False)

# 4. early-warning back-test and indicator flags (long format)
pd.read_csv(PROC / "early_warning_backtest.csv").to_csv(OUT / "powerbi_backtest.csv", index=False)
ew = pd.read_csv(OUT / "powerbi_early_warning.csv", parse_dates=["date"])
mon = pd.read_csv(OUT / "powerbi_monthly.csv", parse_dates=["date"])
IND = {"brent_high": ("Cost pressure", "Brent crude high", "brent_usd_yoy"),
       "ppi_high": ("Cost pressure", "Producer prices high", "ppi_yoy"),
       "usdmyr_high": ("Cost pressure", "Ringgit weak (USD/MYR high)", "usdmyr_yoy"),
       "ipi_low": ("Growth slowdown", "Industrial production low", "ipi_yoy"),
       "exports_low": ("Growth slowdown", "Exports low", "exports_rm_mil_yoy"),
       "leading_low": ("Growth slowdown", "Leading Index low", "leading_index_yoy")}
# an indicator counts only in months where its input is published (unpublished months are blank, not "normal")
long = ew.melt(id_vars="date", value_vars=list(IND), var_name="code", value_name="flag")
long["source"] = long["code"].map(lambda c: IND[c][2])
pub = mon.dropna(subset=["value"])[["date", "variable"]].assign(published=True)
long = long.merge(pub, left_on=["date", "source"], right_on=["date", "variable"], how="left").drop(columns="variable")
long.loc[long["published"] != True, "flag"] = pd.NA
long["signal"] = long["code"].map(lambda c: IND[c][0]); long["indicator"] = long["code"].map(lambda c: IND[c][1])
long["status"] = long["flag"].map({1: "Above usual range", 0: "Normal"}).fillna("Not yet published")
long.drop(columns=["published"]).to_csv(OUT / "powerbi_ew_indicators.csv", index=False)
# current status per signal: latest month with all three inputs published; ON when 2 or more of 3 flags are on
st = []
for sig in ("Cost pressure", "Growth slowdown"):
    g = long[long["signal"] == sig].pivot(index="date", columns="indicator", values="flag")
    full = g.dropna()
    d = full.index.max(); on = int(full.loc[d].sum())
    st.append({"signal": sig, "as_of": d.date(), "indicators_on": on, "status": "ON" if on >= 2 else "OFF",
               "rule": "ON when at least 2 of 3 indicators are outside their usual 5-year range"})
pd.DataFrame(st).to_csv(OUT / "powerbi_ew_status.csv", index=False)

# 5. forecast fan: recent history + next-period forecast with 80% and 95% bands
fc = pd.read_csv(OUT / "powerbi_forecasts.csv", parse_dates=["forecast_for", "origin"])
q = pd.read_csv(OUT / "powerbi_quarterly.csv", parse_dates=["date"])
m = pd.read_csv(OUT / "powerbi_monthly.csv", parse_dates=["date"])
fan = []
for setup, var, src, n in (("A2", "gdp_yoy", q, 16), ("A1", "gdp_yoy", q, 16), ("B", "cpi_yoy", m, 36)):
    sel = fc[(fc["setup"] == setup) & (fc["selected"])].iloc[0]
    h = src[src["variable"] == var].dropna(subset=["value"]).sort_values("date").tail(n)
    part = pd.DataFrame({"setup": setup, "target": sel["target"], "date": h["date"], "actual": h["value"]})
    # repeat the last actual in the forecast columns so the forecast line joins the history
    last = part.iloc[-1]
    join = {"setup": setup, "target": sel["target"], "date": last["date"], "forecast": last["actual"],
            "lo80": last["actual"], "hi80": last["actual"], "lo95": last["actual"], "hi95": last["actual"]}
    nxt = {"setup": setup, "target": sel["target"], "date": sel["forecast_for"], "forecast": sel["forecast"],
           "lo80": sel["lo80"], "hi80": sel["hi80"], "lo95": sel["lo95"], "hi95": sel["hi95"], "model": sel["model"]}
    fan.append(pd.concat([part, pd.DataFrame([join, nxt])]))
fan = pd.concat(fan)
fan = fan.groupby(["setup", "target", "date"], as_index=False).first()   # one row per date
fan.to_csv(OUT / "powerbi_fan.csv", index=False)

# 6. scenario slider: effect per 1% shock (the fitted effect is linear in the shock size)
sc = pd.read_csv(OUT / "powerbi_scenarios.csv")
rows = []
for setup, g in sc.groupby("setup"):
    b = g[g["scenario"] == "Brent +20%"].iloc[0]; fx = g[g["scenario"].str.startswith("Ringgit")].iloc[0]
    rows.append({"setup": setup, "target": b["target"], "brent_effect_per_1pct": b["effect_pp"] / 20,
                 "ringgit_effect_per_1pct": fx["effect_pp"] / 10, "brent_p": b["brent_p"], "usdmyr_p": b["usdmyr_p"]})
pd.DataFrame(rows).to_csv(OUT / "powerbi_scenario_slider.csv", index=False)

print("Saved outputs/powerbi_variables, corr, top_predictors, importance, backtest, ew_indicators, ew_status, fan, scenario_slider (.csv)")
