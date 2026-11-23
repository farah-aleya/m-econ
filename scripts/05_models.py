"""
M-ECON | Step 5: forecasting models, rolling-origin evaluation, early warning and scenarios.
Run from the project root:  python scripts/05_models.py      (takes about 1 to 3 minutes)

Inputs : processed/features_monthly.csv, processed/features_quarterly.csv, processed/monthly_master.csv,
         processed/quarterly_master.csv
Outputs: processed/model_results.csv          accuracy table (Table 5 in the report)
         processed/model_predictions.csv      every out-of-sample forecast
         processed/latest_forecasts.csv       next-period forecasts with intervals (Table 6)
         processed/mlr_summary_<setup>.txt    MLR steps from FFM2063 Ch 2 (equation, t, F, assumptions)
         processed/feature_importance.csv     RF permutation importance, LASSO and MLR coefficients
         processed/early_warning_signals.csv  monthly signals; processed/early_warning_backtest.csv (Table 7)
         processed/scenarios.csv              Brent and USD/MYR scenarios (Table 8)
         processed/findings_models.txt        plain-text summary of all results
         outputs/figures/fig8_actual_vs_forecast_gdp.png, fig9_actual_vs_forecast_cpi.png,
         fig10_importance.png, fig_tree_inflation.png, fig_mlr_diagnostics.png
         outputs/powerbi_model_results.csv, powerbi_predictions.csv, powerbi_forecasts.csv,
         powerbi_early_warning.csv, powerbi_scenarios.csv

Setups (each runs the same 7 models)
  A1  GDP growth, activity input = IPI              (from 2017, ~38 quarters)
  A2  GDP growth, activity input = Coincident Index (from 2012, ~58 quarters)
  B   CPI inflation, monthly                        (from 2017, ~115 months)
Models
  1 Naive  2 AR(1)  3 MLR with backward elimination  4 LASSO  5 Regression tree (pruned)
  6 Random Forest  7 Average of MLR and RF
Validation: expanding-window rolling origin; at each origin every model is refitted on data
available up to that origin and makes a one-step-ahead forecast. Nothing is shuffled.
"""
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import statsmodels.api as sm
    from statsmodels.stats.outliers_influence import variance_inflation_factor
    from statsmodels.stats.stattools import durbin_watson
    from statsmodels.stats.diagnostic import het_breuschpagan
    from scipy import stats
    from sklearn.linear_model import LassoCV
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    from sklearn.tree import DecisionTreeRegressor, plot_tree
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.inspection import permutation_importance
except ImportError as e:
    raise SystemExit(f"Missing package ({e}). Run:  pip install -r requirements.txt")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
PROC, OUT = ROOT / "processed", ROOT / "outputs"
FIG = OUT / "figures"; FIG.mkdir(parents=True, exist_ok=True)
plt.rcParams["font.family"] = "Times New Roman"
SEED = 42
TXT = []
def say(s=""):
    print(s); TXT.append(str(s))

fm = pd.read_csv(PROC / "features_monthly.csv", parse_dates=["date"], index_col="date")
fq = pd.read_csv(PROC / "features_quarterly.csv", parse_dates=["date"], index_col="date")
M = pd.read_csv(PROC / "monthly_master.csv", parse_dates=["date"], index_col="date")
Q = pd.read_csv(PROC / "quarterly_master.csv", parse_dates=["date"], index_col="date")

# ------------------------------------------------------------------ setups
# Candidate inputs = own latest value + the top predictors from step 04 at short lags + COVID dummy.
# Lag numbers already include each series' publication delay (see 03_features.py).
SETUPS = {
    "A1": dict(name="GDP growth (with IPI)", data=fq, target="target_gdp_yoy_next", own="gdp_yoy_L0",
               pool=["gdp_yoy_L0", "gdp_yoy_L1", "ipi_index_yoy_L0", "ipi_index_yoy_L1", "ipi_index_yoy_L2",
                     "opr_L0", "opr_L1", "opr_L2", "exports_rm_mil_yoy_L0", "exports_rm_mil_yoy_L1",
                     "exports_rm_mil_yoy_L2", "covid"],
               test_from="2022-01-01", max_vars=4, depth=3, freq="Q"),
    "A2": dict(name="GDP growth (with Coincident Index)", data=fq, target="target_gdp_yoy_next", own="gdp_yoy_L0",
               pool=["gdp_yoy_L0", "gdp_yoy_L1", "coincident_index_yoy_L1", "coincident_index_yoy_L2",
                     "coincident_index_yoy_L3", "opr_L0", "opr_L1", "opr_L2", "exports_rm_mil_yoy_L0",
                     "exports_rm_mil_yoy_L1", "exports_rm_mil_yoy_L2", "covid"],
               test_from="2022-01-01", max_vars=4, depth=3, freq="Q"),
    "B": dict(name="CPI inflation", data=fm, target="target_cpi_yoy_next", own="cpi_yoy_L0",
              pool=["cpi_yoy_L0", "cpi_yoy_L1", "ppi_yoy_L0", "ppi_yoy_L1", "ppi_yoy_L3", "neer_broad_yoy_L0",
                    "neer_broad_yoy_L1", "neer_broad_yoy_L3", "ipi_yoy_L1", "ipi_yoy_L2", "ipi_yoy_L4", "covid"],
              test_from="2022-01-01", max_vars=6, depth=5, freq="M"),
}
MODELS = ["Naive", "AR(1)", "MLR", "LASSO", "Regression tree", "Random Forest", "Average (MLR+RF)"]

# ------------------------------------------------------------------ model helpers
def n_splits(n):
    return max(2, min(5, n // 10))

def backward_mlr(X, y, max_vars, keep_log=False):
    """FFM2063 Ch 2: drop the least significant input one at a time (p > 0.05), then any VIF > 10,
    then trim to max_vars. Returns fitted OLS, chosen columns and the elimination log."""
    cols = list(X.columns); log = []
    while True:
        res = sm.OLS(y, sm.add_constant(X[cols], has_constant="add")).fit()
        p = res.pvalues.drop("const")
        reason = None
        if len(cols) > 1 and p.max() > 0.05:
            drop, reason = p.idxmax(), f"p = {p.max():.3f}"
        elif len(cols) > 1:
            vif = pd.Series([variance_inflation_factor(sm.add_constant(X[cols]).values, i + 1)
                             for i in range(len(cols))], index=cols)
            if vif.max() > 10:
                drop, reason = vif.idxmax(), f"VIF = {vif.max():.1f}"
            elif len(cols) > max_vars:
                drop, reason = p.idxmax(), f"limit of {max_vars} inputs"
        if reason is None:
            return res, cols, log
        if keep_log:
            log.append(f"removed {drop} ({reason}); R2 before = {res.rsquared:.3f}")
        cols.remove(drop)

def make_lasso(cv):
    try:                                   # newer scikit-learn: alphas=<int>
        return LassoCV(cv=cv, alphas=60, max_iter=50000, random_state=SEED)
    except TypeError:
        return LassoCV(cv=cv, n_alphas=60, max_iter=50000, random_state=SEED)

def fit_lasso(X, y):
    las = make_lasso(TimeSeriesSplit(n_splits(len(y))))
    try:
        return make_pipeline(StandardScaler(), las).fit(X, y)
    except (TypeError, ValueError):        # older scikit-learn rejects alphas=<int> at fit time
        las = LassoCV(cv=TimeSeriesSplit(n_splits(len(y))), n_alphas=60, max_iter=50000, random_state=SEED)
        return make_pipeline(StandardScaler(), las).fit(X, y)

def fit_tree(X, y):
    """Ch 6: grow a large tree, then cost-complexity pruning with alpha chosen by time-ordered CV."""
    base = DecisionTreeRegressor(min_samples_leaf=3, random_state=SEED)
    alphas = np.unique(base.cost_complexity_pruning_path(X, y).ccp_alphas)
    alphas = alphas[alphas >= 0]
    if len(alphas) > 25:
        alphas = np.quantile(alphas, np.linspace(0, 1, 25))
    best, best_err = 0.0, np.inf
    for a in alphas:
        errs = []
        for tr, va in TimeSeriesSplit(n_splits(len(y))).split(X):
            t = DecisionTreeRegressor(min_samples_leaf=3, ccp_alpha=a, random_state=SEED).fit(X.iloc[tr], y.iloc[tr])
            errs.append(np.mean((t.predict(X.iloc[va]) - y.iloc[va]) ** 2))
        if np.mean(errs) < best_err:
            best, best_err = a, np.mean(errs)
    return DecisionTreeRegressor(min_samples_leaf=3, ccp_alpha=best, random_state=SEED).fit(X, y)

def fit_rf(X, y, depth):
    """Pre-pruned forest: fixed settings, not tuned on the test data."""
    return RandomForestRegressor(n_estimators=500, max_depth=depth, min_samples_leaf=3, max_features=0.33,
                                 random_state=SEED, n_jobs=-1).fit(X, y)

def fit_all(X, y, cfg):
    own = cfg["own"]
    out = {}
    out["AR(1)"] = sm.OLS(y, sm.add_constant(X[[own]])).fit()
    out["MLR"] = backward_mlr(X, y, cfg["max_vars"])
    out["LASSO"] = fit_lasso(X, y)
    out["Regression tree"] = fit_tree(X, y)
    out["Random Forest"] = fit_rf(X, y, cfg["depth"])
    return out

def predict_all(fits, x, cfg):
    own = cfg["own"]
    p = {"Naive": float(x[own].iloc[0]),
         "AR(1)": float(fits["AR(1)"].predict(sm.add_constant(x[[own]], has_constant="add")).iloc[0])}
    res, cols, _ = fits["MLR"]
    p["MLR"] = float(res.predict(sm.add_constant(x[cols], has_constant="add")).iloc[0])
    p["LASSO"] = float(fits["LASSO"].predict(x)[0])
    p["Regression tree"] = float(fits["Regression tree"].predict(x)[0])
    p["Random Forest"] = float(fits["Random Forest"].predict(x)[0])
    p["Average (MLR+RF)"] = (p["MLR"] + p["Random Forest"]) / 2
    return p

# ------------------------------------------------------------------ rolling-origin evaluation
pred_rows, res_rows, final = [], [], {}
say("=== ROLLING-ORIGIN EVALUATION (one-step-ahead, expanding window) ===")
for key, cfg in SETUPS.items():
    D = cfg["data"]
    df = D[cfg["pool"] + [cfg["target"]]].dropna()
    origins = df.index[df.index >= cfg["test_from"]]
    for t in origins:
        train = df[df.index < t]
        X, y = train[cfg["pool"]], train[cfg["target"]]
        fits = fit_all(X, y, cfg)
        p = predict_all(fits, df.loc[[t], cfg["pool"]], cfg)
        step = pd.DateOffset(months=3 if cfg["freq"] == "Q" else 1)
        for mname, v in p.items():
            pred_rows.append(dict(setup=key, model=mname, origin=t, target_date=t + step,
                                  actual=df.at[t, cfg["target"]], last_value=df.at[t, cfg["own"]], forecast=v,
                                  n_train=len(train)))
    P = pd.DataFrame([r for r in pred_rows if r["setup"] == key])
    naive_mae = (P[P.model == "Naive"].actual - P[P.model == "Naive"].forecast).abs().mean()
    say(f"\n{key}: {cfg['name']} | sample {df.index.min():%Y-%m} to {df.index.max():%Y-%m} ({len(df)} rows) | "
        f"test origins {origins.min():%Y-%m} to {origins.max():%Y-%m} ({len(origins)} forecasts)")
    for mname in MODELS:
        s = P[P.model == mname]
        e = s.actual - s.forecast
        mae, rmse = e.abs().mean(), np.sqrt((e ** 2).mean())
        if mname == "Naive":
            da = np.nan
        else:
            da = (np.sign(s.forecast - s.last_value) == np.sign(s.actual - s.last_value)).mean() * 100
        skill = (1 - mae / naive_mae) * 100
        res_rows.append(dict(setup=key, target=cfg["name"], model=mname, n_test=len(s), MAE=mae, RMSE=rmse,
                             directional_accuracy=da, mae_vs_naive_pct=skill,
                             beats_naive_10pct=("n/a" if mname == "Naive" else ("Yes" if skill >= 10 else "No"))))
        say(f"   {mname:18s} MAE {mae:5.2f}  RMSE {rmse:5.2f}  DA {'  n/a' if np.isnan(da) else f'{da:4.0f}%'}  "
            f"vs Naive {skill:+5.1f}%")
    # final fit on all rows with a known target (used for forecasts, importance, MLR report)
    X, y = df[cfg["pool"]], df[cfg["target"]]
    final[key] = dict(fits=fit_all(X, y, cfg), X=X, y=y, df=df)

R = pd.DataFrame(res_rows); P = pd.DataFrame(pred_rows)
R.round(3).to_csv(PROC / "model_results.csv", index=False)
P.round(3).to_csv(PROC / "model_predictions.csv", index=False)
best = R[R.model != "Naive"].sort_values("MAE").groupby("setup").head(1).set_index("setup")
say("\nBest model by test MAE:")
for k, r in best.iterrows():
    say(f"   {k}: {r.model} (MAE {r.MAE:.2f}, {r.mae_vs_naive_pct:+.1f}% vs Naive) -> "
        f"Objective 3 target (>= 10%) {'MET' if r.mae_vs_naive_pct >= 10 else 'NOT met'}")

# overfitting check for tree models: training MAE (final fit) vs test MAE
say("\nOverfitting check (train MAE on final fit vs test MAE):")
for k, f in final.items():
    for mname in ["Regression tree", "Random Forest"]:
        tr = np.mean(np.abs(f["fits"][mname].predict(f["X"]) - f["y"]))
        te = R[(R.setup == k) & (R.model == mname)].MAE.iloc[0]
        say(f"   {k} {mname:16s} train {tr:.2f}  test {te:.2f}")

# ------------------------------------------------------------------ MLR report (FFM2063 Ch 2)
def mlr_report(key):
    cfg, f = SETUPS[key], final[key]
    res, cols, log = backward_mlr(f["X"], f["y"], cfg["max_vars"], keep_log=True)
    n, k = int(res.nobs), len(cols)
    tcrit = stats.t.ppf(0.975, n - k - 1); fcrit = stats.f.ppf(0.95, k, n - k - 1)
    resid = res.resid
    sw = stats.shapiro(resid); bp = het_breuschpagan(resid, res.model.exog)
    vif = ([variance_inflation_factor(res.model.exog, i + 1) for i in range(k)] if k > 1 else [1.0])
    std_res = resid / resid.std()
    eq = f"{cfg['target'].replace('target_', '').replace('_next', '')}(t+1) = {res.params['const']:.3f}" + "".join(
        f" {'+' if res.params[c] >= 0 else '-'} {abs(res.params[c]):.3f} {c}" for c in cols)
    lines = [f"MLR for setup {key}: {cfg['name']}", "=" * 70,
             "Step 1-2. Candidate inputs: " + ", ".join(cfg["pool"]),
             "Backward elimination (least significant first):"] + [f"   {l}" for l in log] + [
             f"Final inputs ({k}): {', '.join(cols)}", "", "Step 3. Estimated equation (least squares):", "   " + eq, "",
             f"Step 4. Standard error of estimate = {np.sqrt(res.mse_resid):.3f}",
             f"        R2 = {res.rsquared:.3f}, adjusted R2 = {res.rsquared_adj:.3f}, n = {n}", "",
             f"Step 5. t-tests (alpha = 0.05, critical |t| = t(0.025, {n - k - 1}) = {tcrit:.3f}):"]
    for c in cols:
        lines.append(f"   {c:26s} coef {res.params[c]:8.3f}  t = {res.tvalues[c]:7.2f}  p = {res.pvalues[c]:.4f}  "
                     f"{'significant' if abs(res.tvalues[c]) > tcrit else 'not significant'}")
    lines += [f"Step 6. F-test: F = {res.fvalue:.2f} vs critical F(0.05, {k}, {n - k - 1}) = {fcrit:.2f} -> "
              f"{'reject H0: the model is significant' if res.fvalue > fcrit else 'cannot reject H0'}", "",
              "Step 7. Assumption checks:",
              f"   Multicollinearity: max VIF = {max(vif):.2f} (rule: < 10)",
              f"   Independence of residuals: Durbin-Watson = {durbin_watson(resid):.2f} (about 2 means no autocorrelation)",
              f"   Normality of residuals: Shapiro-Wilk p = {sw.pvalue:.3f} ({'normal' if sw.pvalue > 0.05 else 'not normal'} at 5%)",
              f"   Constant variance: Breusch-Pagan p = {bp[1]:.3f} ({'constant' if bp[1] > 0.05 else 'not constant'} at 5%)",
              f"   Outliers: {int((std_res.abs() > 3).sum())} standardised residuals above 3 "
              f"({', '.join(f'{d:%Y-%m}' for d in std_res.index[std_res.abs() > 3]) or 'none'}); kept, not deleted",
              "   Linearity: see residual plot in outputs/figures/fig_mlr_diagnostics.png"]
    (PROC / f"mlr_summary_{key}.txt").write_text("\n".join(lines), encoding="utf-8")
    return res, cols
mlr_final = {k: mlr_report(k) for k in SETUPS}
say("\nMLR final equations (full sample): see processed/mlr_summary_<setup>.txt")
for k, (res, cols) in mlr_final.items():
    say(f"   {k}: inputs {cols}, adj R2 {res.rsquared_adj:.2f}, F p = {res.f_pvalue:.4f}")

# diagnostics figure (A2 and B)
fig, axes = plt.subplots(2, 2, figsize=(9, 7))
for row, k in enumerate(["A2", "B"]):
    res, _ = mlr_final[k]
    axes[row, 0].scatter(res.fittedvalues, res.resid, s=12, color="#1f4e79")
    axes[row, 0].axhline(0, color="grey", lw=0.8)
    axes[row, 0].set_title(f"{SETUPS[k]['name']}: residuals vs fitted", fontsize=10)
    axes[row, 0].set_xlabel("Fitted"); axes[row, 0].set_ylabel("Residual")
    sm.qqplot(res.resid, line="s", ax=axes[row, 1], markersize=3)
    axes[row, 1].set_title(f"{SETUPS[k]['name']}: normal Q-Q plot", fontsize=10)
fig.tight_layout(); fig.savefig(FIG / "fig_mlr_diagnostics.png", dpi=200); plt.close(fig)

# ------------------------------------------------------------------ importance
imp_rows = []
for k, f in final.items():
    pi = permutation_importance(f["fits"]["Random Forest"], f["X"], f["y"], n_repeats=30, random_state=SEED)
    lasso = f["fits"]["LASSO"][-1]
    res, cols = mlr_final[k]
    sd = f["X"].std()
    for i, c in enumerate(f["X"].columns):
        imp_rows.append(dict(setup=k, feature=c, rf_permutation_importance=pi.importances_mean[i],
                             lasso_coef_standardised=lasso.coef_[i],
                             mlr_coef_standardised=(res.params[c] * sd[c] / f["y"].std()) if c in cols else 0.0))
I = pd.DataFrame(imp_rows); I.round(4).to_csv(PROC / "feature_importance.csv", index=False)
LABEL = {"gdp_yoy": "GDP growth (own)", "cpi_yoy": "CPI inflation (own)", "ipi_index_yoy": "Industrial production",
         "ipi_yoy": "Industrial production", "coincident_index_yoy": "Coincident Index", "opr": "OPR",
         "exports_rm_mil_yoy": "Exports", "ppi_yoy": "PPI", "neer_broad_yoy": "NEER", "covid": "COVID dummy"}
def lab(c):
    base, _, lag = c.rpartition("_L")
    return f"{LABEL.get(base, LABEL.get(c, c))} (lag {lag})" if base else LABEL.get(c, c)
fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
for ax, k in zip(axes, ["A2", "B"]):
    s = I[I.setup == k].set_index("feature")["rf_permutation_importance"].sort_values().tail(8)
    ax.barh([lab(c) for c in s.index], s.values, color="#1f4e79")
    ax.set_title(f"{SETUPS[k]['name']}: Random Forest importance", fontsize=10)
    ax.set_xlabel("Permutation importance (drop in R²)")
    ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout(); fig.savefig(FIG / "fig10_importance.png", dpi=200); plt.close(fig)
say("\nTop 3 inputs by Random Forest importance:")
for k in SETUPS:
    s = I[I.setup == k].set_index("feature")["rf_permutation_importance"].sort_values(ascending=False).head(3)
    say(f"   {k}: " + ", ".join(f"{lab(c)} {v:.2f}" for c, v in s.items()))
say("LASSO inputs kept (non-zero):")
for k in SETUPS:
    s = I[(I.setup == k) & (I.lasso_coef_standardised.abs() > 1e-6)].feature.tolist()
    say(f"   {k}: {', '.join(lab(c) for c in s) or 'none (intercept only)'}")

# pruned tree figure (inflation)
tB = final["B"]["fits"]["Regression tree"]
fig, ax = plt.subplots(figsize=(11, 5.5))
plot_tree(tB, feature_names=[lab(c) for c in final["B"]["X"].columns], filled=True, rounded=True,
          precision=1, fontsize=7, ax=ax, impurity=False)
ax.set_title(f"Pruned regression tree for next-month CPI inflation ({tB.get_n_leaves()} leaves)", fontsize=10)
fig.tight_layout(); fig.savefig(FIG / "fig_tree_inflation.png", dpi=200); plt.close(fig)

# ------------------------------------------------------------------ actual vs forecast figures
def avf(keys, fname, title, ylabel):
    fig, ax = plt.subplots(figsize=(9, 4.2))
    first = P[P.setup == keys[0]]
    act = first[first.model == "Naive"].set_index("target_date")["actual"]
    hist_src = SETUPS[keys[0]]["data"]
    hist = hist_src[SETUPS[keys[0]]["own"]]
    hist.index = hist.index  # value at origin date
    start = act.index.min() - pd.DateOffset(years=3)
    ax.plot(hist[hist.index >= start].index, hist[hist.index >= start].values, color="black", lw=1.6, label="Actual")
    styles = [("-", "#c55a11"), ("--", "#1f4e79")]
    for (k, (ls, col)) in zip(keys, styles):
        m = best.loc[k, "model"]
        s = P[(P.setup == k) & (P.model == m)].set_index("target_date")["forecast"]
        ax.plot(s.index, s.values, ls=ls, color=col, lw=1.4, marker="o", ms=3,
                label=f"{m}, {SETUPS[k]['name'].split('(')[-1].rstrip(')') if '(' in SETUPS[k]['name'] else 'forecast'}")
    nv = P[(P.setup == keys[0]) & (P.model == "Naive")].set_index("target_date")["forecast"]
    ax.plot(nv.index, nv.values, ls=":", color="grey", lw=1.2, label="Naive")
    ax.axvline(act.index.min(), color="grey", lw=0.8); ax.text(act.index.min(), ax.get_ylim()[1], " test period", va="top", fontsize=8)
    ax.set_ylabel(ylabel); ax.set_title(title, fontsize=10); ax.legend(frameon=False, fontsize=8, ncol=2)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(FIG / fname, dpi=200); plt.close(fig)
avf(["A2", "A1"], "fig8_actual_vs_forecast_gdp.png", "Real GDP growth: actual and one-quarter-ahead forecasts", "% YoY")
avf(["B"], "fig9_actual_vs_forecast_cpi.png", "CPI inflation: actual and one-month-ahead forecasts", "% YoY")

# ------------------------------------------------------------------ latest forecasts with intervals
fc_rows = []
say("\n=== LATEST FORECASTS ===")
for k, cfg in SETUPS.items():
    D = cfg["data"]
    last = D[cfg["own"]].dropna().index.max()                 # newest period with a published value
    avail = [c for c in cfg["pool"] if pd.notna(D.at[last, c])]
    missing = [c for c in cfg["pool"] if c not in avail]
    if missing:   # some inputs not yet published for the newest period: refit without them
        cfg_l = dict(cfg, pool=avail)
        df_l = D[avail + [cfg["target"]]].dropna()
        fits_l = fit_all(df_l[avail], df_l[cfg["target"]], cfg_l)
        say(f"   {k}: inputs not yet published for {last:%b %Y} ({', '.join(missing)}); models refitted without them")
    else:
        cfg_l, fits_l = cfg, final[k]["fits"]
    x = D.loc[[last], cfg_l["pool"]]
    p = predict_all(fits_l, x, cfg_l)
    step = pd.DateOffset(months=3 if cfg["freq"] == "Q" else 1)
    res, cols, _ = fits_l["MLR"]
    pr = res.get_prediction(sm.add_constant(x[cols], has_constant="add"))
    for mname, v in p.items():
        e = P[(P.setup == k) & (P.model == mname)]; err = (e.actual - e.forecast).abs()
        if mname == "MLR":
            lo80, hi80 = pr.conf_int(obs=True, alpha=0.2)[0]; lo95, hi95 = pr.conf_int(obs=True, alpha=0.05)[0]
        else:
            q80, q95 = err.quantile(0.8), err.quantile(0.95)
            lo80, hi80, lo95, hi95 = v - q80, v + q80, v - q95, v + q95
        fc_rows.append(dict(setup=k, target=cfg["name"], model=mname, origin=last, forecast_for=last + step,
                            forecast=v, lo80=lo80, hi80=hi80, lo95=lo95, hi95=hi95,
                            selected=(mname == best.loc[k, "model"]),
                            latest_actual=float(D.loc[last, cfg["own"]])))
    b = [r for r in fc_rows if r["setup"] == k and r["selected"]][0]
    per = f"{b['forecast_for'].year} Q{(b['forecast_for'].month - 1) // 3 + 1}" if cfg["freq"] == "Q" else f"{b['forecast_for']:%b %Y}"
    say(f"   {k} {cfg['name']}: {per} = {b['forecast']:.1f}% (80%: {b['lo80']:.1f} to {b['hi80']:.1f}; "
        f"95%: {b['lo95']:.1f} to {b['hi95']:.1f}) by {b['model']}; latest actual {b['latest_actual']:.1f}%")
F = pd.DataFrame(fc_rows); F.round(3).to_csv(PROC / "latest_forecasts.csv", index=False)

# ------------------------------------------------------------------ scenarios (MLR + shocked input)
say("\n=== SCENARIOS (effect on the next-period forecast, MLR with the shocked input added) ===")
SHOCK_COLS = {"Q": {"brent": "brent_usd_yoy_L0", "fx": "usdmyr_yoy_L0"},
              "M": {"brent": "brent_usd_yoy_L0", "fx": "usdmyr_yoy_L0"}}
sc_rows = []
for k in ["A2", "B"]:
    cfg = SETUPS[k]; D = cfg["data"]; res, cols = mlr_final[k]
    sc = SHOCK_COLS[cfg["freq"]]
    use = list(dict.fromkeys(cols + [sc["brent"], sc["fx"]]))
    dfx = D[use + [cfg["target"]]].dropna()
    r2 = sm.OLS(dfx[cfg["target"]], sm.add_constant(dfx[use])).fit()
    last = D[use].dropna().index.max()
    g_b, g_f = D.at[last, sc["brent"]], D.at[last, sc["fx"]]
    for label, sb, sf in [("Brent +20%", 0.20, 0), ("Brent -20%", -0.20, 0),
                          ("Ringgit 10% weaker (USD/MYR +10%)", 0, 0.10),
                          ("Brent +20% and ringgit 10% weaker", 0.20, 0.10)]:
        d_b = sb * (100 + g_b); d_f = sf * (100 + g_f)        # change in the YoY input, percentage points
        eff = r2.params[sc["brent"]] * d_b + r2.params[sc["fx"]] * d_f
        var = (d_b ** 2) * r2.bse[sc["brent"]] ** 2 + (d_f ** 2) * r2.bse[sc["fx"]] ** 2 \
            + 2 * d_b * d_f * r2.cov_params().loc[sc["brent"], sc["fx"]]
        se = np.sqrt(var)
        sc_rows.append(dict(setup=k, target=cfg["name"], scenario=label, effect_pp=eff, lo95=eff - 1.96 * se,
                            hi95=eff + 1.96 * se, brent_coef=r2.params[sc["brent"]], brent_p=r2.pvalues[sc["brent"]],
                            usdmyr_coef=r2.params[sc["fx"]], usdmyr_p=r2.pvalues[sc["fx"]], origin=last))
    say(f"   {k} {cfg['name']}: Brent coef {r2.params[sc['brent']]:.4f} (p = {r2.pvalues[sc['brent']]:.3f}), "
        f"USD/MYR coef {r2.params[sc['fx']]:.4f} (p = {r2.pvalues[sc['fx']]:.3f})")
    for r in [r for r in sc_rows if r["setup"] == k]:
        say(f"      {r['scenario']:36s} {r['effect_pp']:+.2f} pp (95%: {r['lo95']:+.2f} to {r['hi95']:+.2f})")
S = pd.DataFrame(sc_rows); S.round(4).to_csv(PROC / "scenarios.csv", index=False)
say("   Benchmark: Majuca (2020) finds a 1% Brent rise lifts the level of real GDP by about 0.042% and "
    "consumer prices by about 0.014%.")

# ------------------------------------------------------------------ early-warning signals and back-test
say("\n=== EARLY WARNING ===")
WIN, MINP = 60, 36
def high(s): return s > s.shift(1).rolling(WIN, min_periods=MINP).quantile(0.9)
def low(s):  return s < s.shift(1).rolling(WIN, min_periods=MINP).quantile(0.1)
EW = pd.DataFrame(index=M.index)
EW["brent_high"] = high(M["brent_usd_yoy"]); EW["ppi_high"] = high(M["ppi_yoy"]); EW["usdmyr_high"] = high(M["usdmyr_yoy"])
EW["ipi_low"] = low(M["ipi_yoy"]); EW["exports_low"] = low(M["exports_rm_mil_yoy"]); EW["leading_low"] = low(M["leading_index_yoy"])
cost_in = M[["brent_usd_yoy", "ppi_yoy", "usdmyr_yoy"]].notna().sum(axis=1)
grow_in = M[["ipi_yoy", "exports_rm_mil_yoy", "leading_index_yoy"]].notna().sum(axis=1)
EW["cost_count"] = EW[["brent_high", "ppi_high", "usdmyr_high"]].sum(axis=1)
EW["growth_count"] = EW[["ipi_low", "exports_low", "leading_low"]].sum(axis=1)
EW["cost_pressure"] = (EW["cost_count"] >= 2) & (cost_in >= 2)
EW["growth_slowdown"] = (EW["growth_count"] >= 2) & (grow_in >= 2)
valid_from = M["ppi_yoy"].dropna().index.min() + pd.DateOffset(months=MINP)
EW = EW[EW.index >= valid_from]
EW.astype(int).to_csv(PROC / "early_warning_signals.csv")
EPISODES = [("2014 to 2015 oil fall", "2014-07-01", "2015-12-01", "growth_slowdown"),
            ("2017 producer price spike", "2016-12-01", "2017-06-01", "cost_pressure"),
            ("2020 to 2021 COVID-19", "2020-03-01", "2020-12-01", "growth_slowdown"),
            ("2021 to 2022 commodity surge", "2021-06-01", "2022-09-01", "cost_pressure"),
            ("2026 oil shock", "2026-03-01", "2026-10-01", "cost_pressure")]
LEAD = 6
mask_ep = pd.Series(False, index=EW.index)
bt = []
for name, a, b, sig in EPISODES:
    a, b = pd.Timestamp(a), pd.Timestamp(b)
    win = EW.loc[a - pd.DateOffset(months=LEAD):b, sig]
    mask_ep |= (EW.index >= a - pd.DateOffset(months=LEAD)) & (EW.index <= b)
    on = win[win]
    covered = (a - pd.DateOffset(months=LEAD)) >= EW.index.min()
    if len(on):
        first = on.index.min()
        lead = (a.year - first.year) * 12 + (a.month - first.month)
        lead_txt = f"{lead} months before" if lead > 0 else ("at start" if lead == 0 else f"{-lead} months after start")
    else:
        lead_txt = "n/a"
    bt.append(dict(episode=name, signal=sig.replace("_", " "), window=f"{a:%b %Y} to {b:%b %Y}",
                   hit=("Yes" if len(on) else "No") + ("" if covered else " (partial data)"),
                   first_signal=(on.index.min().strftime("%b %Y") if len(on) else "none"), lead_time=lead_txt,
                   months_on=int(win.sum()), months_in_window=int(len(win))))
calm = EW[~mask_ep]
for sig in ["cost_pressure", "growth_slowdown"]:
    fa = calm[sig].mean() * 100
    say(f"   False alarm rate, {sig.replace('_', ' ')}: {fa:.1f}% of {len(calm)} calm months")
    for r in bt:
        if r["signal"] == sig.replace("_", " "):
            r["false_alarm_rate_pct"] = round(fa, 1)
BT = pd.DataFrame(bt); BT.to_csv(PROC / "early_warning_backtest.csv", index=False)
for r in bt:
    say(f"   {r['episode']:30s} {r['signal']:16s} hit {r['hit']:4s} first {r['first_signal']:9s} lead {r['lead_time']}")
lc = EW.index[cost_in.reindex(EW.index) == 3].max(); lg = EW.index[grow_in.reindex(EW.index) == 3].max()
say(f"   Current status: cost pressure {'ON' if EW.at[lc, 'cost_pressure'] else 'off'} in {lc:%b %Y} "
    f"({int(EW.at[lc, 'cost_count'])}/3 indicators); growth slowdown {'ON' if EW.at[lg, 'growth_slowdown'] else 'off'} "
    f"in {lg:%b %Y} ({int(EW.at[lg, 'growth_count'])}/3). Months shown are the latest with all three inputs published.")

# ------------------------------------------------------------------ Power BI exports
R.round(3).to_csv(OUT / "powerbi_model_results.csv", index=False)
P.round(3).to_csv(OUT / "powerbi_predictions.csv", index=False)
F.round(3).to_csv(OUT / "powerbi_forecasts.csv", index=False)
EW.reset_index().astype({c: int for c in EW.columns}).to_csv(OUT / "powerbi_early_warning.csv", index=False)
S.round(4).to_csv(OUT / "powerbi_scenarios.csv", index=False)
(PROC / "findings_models.txt").write_text("\n".join(TXT), encoding="utf-8")
print("\nDone. Tables in processed/, figures in outputs/figures/, Power BI files in outputs/.")
