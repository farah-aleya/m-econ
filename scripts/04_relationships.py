"""
M-ECON | Step 4: relationship analysis (Objectives 1 and 2, report Sections 4.4 and 5.2).
Run from the project root:  python scripts/04_relationships.py
Inputs : processed/monthly_master.csv, processed/quarterly_master.csv
Outputs: processed/corr_lagged_inflation.csv, processed/corr_lagged_gdp.csv
         processed/granger.csv, processed/vif.csv, processed/top_predictors.csv
         outputs/figures/fig3_gdp_cpi.png        (Figure 3, updated to 2026 Q3)
         outputs/figures/fig4_quadrant.png       (Figure 4)
         outputs/figures/fig5_heatmap.png        (Figure 5)
         outputs/figures/fig6_peak_lags.png      (Figure 6)
         processed/findings_relationships.txt    (plain-language summary for Section 5.2)

Notes
-----
* "Lag k" means the predictor k periods BEFORE the target (predictor leads).
* Correlations are reported with p-values; they are associations, not causes.
* Granger tests ask whether past values of a predictor help predict the target beyond the
  target's own past. They show predictive precedence only.
* Results are also computed without 2020-2021 so the COVID swing does not drive the ranking.
"""
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from statsmodels.tsa.stattools import grangercausalitytests
from statsmodels.stats.outliers_influence import variance_inflation_factor

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
PROC, FIG = ROOT / "processed", ROOT / "outputs" / "figures"
FIG.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"],
                     "font.size": 11, "axes.spines.top": False, "axes.spines.right": False})
BLUE, ORANGE, LIGHT = "#1F4E79", "#C55A11", "#9DC3E6"

M = pd.read_csv(PROC / "monthly_master.csv", parse_dates=["date"], index_col="date")
Q = pd.read_csv(PROC / "quarterly_master.csv", parse_dates=["date"], index_col="date")
TXT = []

# predictor -> (label, group)
PRED_M = {
    "ppi_yoy": ("PPI", "Domestic"), "ipi_yoy": ("Industrial production", "Domestic"),
    "u_rate": ("Unemployment rate", "Domestic"), "opr": ("OPR", "Domestic"),
    "leading_index_yoy": ("Leading Index", "Domestic"), "exports_rm_mil_yoy": ("Exports", "Domestic"),
    "imports_rm_mil_yoy": ("Imports", "Domestic"), "usdmyr_yoy": ("USD/MYR", "External"),
    "neer_broad_yoy": ("NEER (broad)", "External"), "brent_usd_yoy": ("Brent crude", "External"),
    "food_index_wb_yoy": ("World food prices", "External"),
}
PRED_Q = {
    "cpi_yoy": ("CPI inflation", "Domestic"), "ppi_index_yoy": ("PPI", "Domestic"),
    "ipi_index_yoy": ("Industrial production", "Domestic"), "u_rate": ("Unemployment rate", "Domestic"),
    "opr": ("OPR", "Domestic"), "leading_index_yoy": ("Leading Index", "Domestic"),
    "exports_rm_mil_yoy": ("Exports", "Domestic"), "imports_rm_mil_yoy": ("Imports", "Domestic"),
    "usdmyr_yoy": ("USD/MYR", "External"), "neer_broad_yoy": ("NEER (broad)", "External"),
    "brent_usd_yoy": ("Brent crude", "External"), "food_index_wb_yoy": ("World food prices", "External"),
}
LAGS = {"inflation": [0, 1, 3, 6, 12], "gdp": [0, 1, 2, 3, 4]}

def lagged_corr(df, target, preds, lags, pipeline, excl_covid):
    rows = []
    for p, (label, group) in preds.items():
        for k in lags:
            pair = pd.concat([df[target], df[p].shift(k)], axis=1).dropna()
            if excl_covid:
                pair = pair[(pair.index < "2020-01-01") | (pair.index > "2021-12-31")]
            if len(pair) < 12:
                continue
            r, pr = stats.pearsonr(pair.iloc[:, 0], pair.iloc[:, 1])
            s, ps = stats.spearmanr(pair.iloc[:, 0], pair.iloc[:, 1])
            rows.append({"pipeline": pipeline, "sample": "ex-COVID" if excl_covid else "full",
                         "predictor": p, "label": label, "group": group, "lag": k, "n": len(pair),
                         "pearson_r": round(r, 3), "pearson_p": round(pr, 4),
                         "spearman_rho": round(s, 3), "spearman_p": round(ps, 4)})
    return pd.DataFrame(rows)

def granger(df, target, preds, maxlag, pipeline):
    rows = []
    for p, (label, group) in preds.items():
        pair = df[[target, p]].dropna()
        pair = pair.diff().dropna()          # first differences: guards against non-stationarity
        try:
            res = grangercausalitytests(pair, maxlag=maxlag)
        except Exception:
            continue
        pv = {L: res[L][0]["ssr_ftest"][1] for L in res}
        best = min(pv, key=pv.get)
        rows.append({"pipeline": pipeline, "predictor": p, "label": label, "group": group,
                     "best_lag": int(best), "min_p": round(pv[best], 4), "n": len(pair),
                     **{f"p_lag{int(L)}": round(v, 4) for L, v in pv.items()}})
    return pd.DataFrame(rows)

def vif(df, preds, pipeline):
    X = df[list(preds)].dropna()
    X = (X - X.mean()) / X.std()
    X.insert(0, "const", 1.0)
    return pd.DataFrame([{"pipeline": pipeline, "predictor": c, "label": preds[c][0],
                          "vif": round(variance_inflation_factor(X.values, i), 2)}
                         for i, c in enumerate(X.columns) if c != "const"])

# ---------------------------------------------------------------- run analyses
ci = pd.concat([lagged_corr(M, "cpi_yoy", PRED_M, LAGS["inflation"], "inflation", x) for x in (False, True)])
cg = pd.concat([lagged_corr(Q, "gdp_yoy", PRED_Q, LAGS["gdp"], "gdp", x) for x in (False, True)])
ci.to_csv(PROC / "corr_lagged_inflation.csv", index=False)
cg.to_csv(PROC / "corr_lagged_gdp.csv", index=False)

gr = pd.concat([granger(M, "cpi_yoy", PRED_M, 12, "inflation"), granger(Q, "gdp_yoy", PRED_Q, 4, "gdp")])
gr.to_csv(PROC / "granger.csv", index=False)

vf = pd.concat([vif(M, PRED_M, "inflation"), vif(Q, PRED_Q, "gdp")])
vf.to_csv(PROC / "vif.csv", index=False)

# ---------------------------------------------------------------- ranking (Objective 2)
def rank(corr, gr_p, pipeline):
    full = corr[(corr["sample"] == "full")]
    exc = corr[(corr["sample"] == "ex-COVID")]
    peak = full.loc[full.groupby("predictor")["pearson_r"].apply(lambda s: s.abs().idxmax())]
    peak_ex = exc.loc[exc.groupby("predictor")["pearson_r"].apply(lambda s: s.abs().idxmax())].set_index("predictor")
    out = peak[["predictor", "label", "group", "lag", "pearson_r", "pearson_p"]].rename(
        columns={"lag": "peak_lag", "pearson_r": "peak_r", "pearson_p": "peak_p"}).set_index("predictor")
    out["peak_r_exCOVID"] = peak_ex["pearson_r"]
    g = gr_p[gr_p.pipeline == pipeline].set_index("predictor")[["min_p", "best_lag"]]
    out = out.join(g.rename(columns={"min_p": "granger_p", "best_lag": "granger_lag"}))
    # score: rank by |r| (ex-COVID, so the pandemic does not dominate) and by Granger p; average ranks
    out["rank_corr"] = out["peak_r_exCOVID"].abs().rank(ascending=False)
    out["rank_granger"] = out["granger_p"].rank(ascending=True)
    out["score"] = (out["rank_corr"] + out["rank_granger"]) / 2
    out = out.sort_values("score")
    out.insert(0, "pipeline", pipeline)
    out["significant_corr"] = out["peak_p"] < 0.05
    out["significant_granger"] = out["granger_p"] < 0.05
    return out.reset_index()

top = pd.concat([rank(ci, gr, "inflation"), rank(cg, gr, "gdp")])
top.to_csv(PROC / "top_predictors.csv", index=False)

# ---------------------------------------------------------------- figures
# Figure 3 (updated): GDP growth bars + quarterly mean CPI
fig, ax = plt.subplots(figsize=(9, 4.2))
ax.bar(Q.index, Q["gdp_yoy"], width=60, color=LIGHT, label="Real GDP growth (YoY, %)")
ax.plot(Q.index, Q["cpi_yoy"], color=BLUE, marker="o", ms=3.5, lw=2, label="CPI inflation, quarterly mean (YoY, %)")
ax.axhline(0, color="grey", lw=0.8); ax.set_ylabel("% year-on-year")
ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.12), ncol=2, frameon=False)
fig.tight_layout(); fig.savefig(FIG / "fig3_gdp_cpi.png", dpi=200); plt.close(fig)

# Figure 4: growth-inflation quadrant (deviation from 2016-2019 average, ex-COVID quarters greyed)
base = Q.loc["2016-01-01":"2019-12-31"]
gx = Q["gdp_yoy"] - base["gdp_yoy"].mean(); iy = Q["cpi_yoy"] - base["cpi_yoy"].mean()
covid = (Q.index >= "2020-01-01") & (Q.index <= "2021-12-31")
fig, ax = plt.subplots(figsize=(7.5, 5.5))
ax.axhline(0, color="grey", lw=0.8); ax.axvline(0, color="grey", lw=0.8)
ax.scatter(gx[~covid], iy[~covid], color=BLUE, s=28, zorder=3, label="Quarter")
ax.scatter(gx[covid], iy[covid], color="lightgrey", s=28, zorder=2, label="2020-2021 (COVID)")
for d in Q.index[-4:]:
    ax.annotate(f"{d.year} Q{(d.month - 1)//3 + 1}", (gx[d], iy[d]), fontsize=8, xytext=(4, 4), textcoords="offset points")
ax.set_xlim(-6, 6); ax.set_ylim(-3.5, 3.5)
for (x, y, t) in [(3, 3, "Overheating"), (3, -3, "Strong growth,\nlow inflation"), (-5.5, 3, "Stagflation"), (-5.5, -3, "Slowdown")]:
    ax.text(x, y, t, fontsize=9, color="dimgrey", va="center")
ax.set_xlabel("GDP growth minus 2016-2019 average (pp)"); ax.set_ylabel("CPI inflation minus 2016-2019 average (pp)")
ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=2, fontsize=8)
fig.tight_layout(); fig.savefig(FIG / "fig4_quadrant.png", dpi=200); plt.close(fig)

# Figure 5: heatmap of correlation at peak lag, one panel per target (ex-COVID)
fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.2), gridspec_kw={"width_ratios": [1, 1], "wspace": 0.55})
for ax, (corr, lags, title) in zip(axes, [(ci, LAGS["inflation"], "Inflation (CPI YoY), lag in months"),
                                          (cg, LAGS["gdp"], "GDP growth (YoY), lag in quarters")]):
    t = corr[corr["sample"] == "ex-COVID"].pivot(index="label", columns="lag", values="pearson_r")[lags]
    im = ax.imshow(t.values, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(len(lags))); ax.set_xticklabels(lags); ax.set_yticks(range(len(t))); ax.set_yticklabels(t.index, fontsize=9)
    for i in range(t.shape[0]):
        for j in range(t.shape[1]):
            v = t.values[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7.5, color="white" if abs(v) > 0.55 else "black")
    ax.set_title(title, fontsize=10); ax.spines[:].set_visible(False)
fig.colorbar(im, ax=axes, shrink=0.7, label="Pearson r (excluding 2020-2021)")
fig.savefig(FIG / "fig5_heatmap.png", dpi=200, bbox_inches="tight"); plt.close(fig)

# Figure 6: peak lag and strength per indicator
fig, axes = plt.subplots(1, 2, figsize=(10, 4.6))
for ax, (pl, unit) in zip(axes, [("inflation", "months"), ("gdp", "quarters")]):
    t = top[top.pipeline == pl].sort_values("peak_r_exCOVID")
    colors = [ORANGE if g == "External" else BLUE for g in t["group"]]
    ax.barh(t["label"], t["peak_r_exCOVID"], color=colors)
    for y, (r, L) in enumerate(zip(t["peak_r_exCOVID"], t["peak_lag"])):
        ax.text(r + (0.02 if r >= 0 else -0.02), y, f"lag {L}", va="center", ha="left" if r >= 0 else "right", fontsize=8)
    ax.axvline(0, color="grey", lw=0.8); ax.set_xlim(-1, 1)
    ax.set_title(f"{'Inflation' if pl == 'inflation' else 'GDP growth'}: strongest r and its lag ({unit})", fontsize=10)
    ax.tick_params(axis="y", labelsize=9)
from matplotlib.patches import Patch
fig.legend(handles=[Patch(color=BLUE, label="Domestic"), Patch(color=ORANGE, label="External")],
           loc="lower center", ncol=2, frameon=False)
fig.tight_layout(rect=(0, 0.06, 1, 1)); fig.savefig(FIG / "fig6_peak_lags.png", dpi=200); plt.close(fig)

# ---------------------------------------------------------------- plain-language summary
for pl, name in [("inflation", "INFLATION (monthly)"), ("gdp", "GDP GROWTH (quarterly)")]:
    t = top[top.pipeline == pl]
    TXT.append(f"\n=== {name} ===")
    TXT.append(t[["label", "group", "peak_lag", "peak_r", "peak_p", "peak_r_exCOVID", "granger_lag", "granger_p"]].to_string(index=False))
    TXT.append("Top 3 (combined rank): " + ", ".join(t["label"].head(3)))
    for g in ["Domestic", "External"]:
        sub = t[t.group == g]
        TXT.append(f"{g}: mean |r| ex-COVID = {sub['peak_r_exCOVID'].abs().mean():.2f}, "
                   f"median peak lag = {sub['peak_lag'].median():.0f}")
TXT.append("\n=== VIF (values above 10 mean strong overlap) ===")
TXT.append(vf.to_string(index=False))
(PROC / "findings_relationships.txt").write_text("\n".join(TXT), encoding="utf-8")
print("\n".join(TXT))
print("\nDone. Figures in outputs/figures/, tables in processed/.")
