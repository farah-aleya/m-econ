# M-ECON: Malaysia Economic Forecasting & Early Warning System

Team FOREFRONT entry for the **MDIT Global Challenge 2026** (Malaysia Data Innovation Talent Datathon, UiTM).
Theme: SDG 8, Decent Work and Economic Growth.

M-ECON uses official Malaysian and global data to:

- forecast **quarterly real GDP growth** and **monthly headline CPI inflation**
- identify which indicators move with, and help predict, growth and inflation
- raise **early-warning signals** for cost pressure and growth slowdowns
- project **scenarios** for oil price (Brent ±20%) and ringgit (USD/MYR ±10%) shocks

All results feed a Power BI dashboard.

## Team
1. Nur Farah Aleya 
2. Ilhan Zikri 
3. Anuar Afiq 
4. Siti Zafirah

Advisor: Dr. Ganesh Kumar, Department of Computing, Universiti Teknologi PETRONAS.

## Pipeline

| Step | Script | What it does | Status |
|---|---|---|---|
| 1 | `scripts/01_download.py` | Downloads raw data into `raw/` | Done |
| 2 | `scripts/02_clean.py` | Cleans and aligns data into monthly and quarterly master tables; missing-value audit; ADF/KPSS stationarity tests; Power BI CSVs | Done |
| 3 | `scripts/03_features.py` | Builds model-ready tables: next-period targets, lag features, publication-delay shifts (no data leakage) | Done |
| 4 | `scripts/04_relationships.py` | Lagged Pearson/Spearman correlations (with and without COVID), Granger causality, VIF, top-predictor ranking, figures | To run |
| 5 | `05_models.py` | Naive baseline, multiple linear regression with lags, Random Forest; rolling-origin validation; early-warning back-test; scenarios | In progress |

`scripts/00_download_papers.py` downloads the open-access papers used in the literature review. The PDFs are not stored in this repo.

## Data sources

| Source | Series |
|---|---|
| OpenDOSM / data.gov.my | Real GDP (`gdp_qtr_real`), headline and core CPI inflation, PPI, IPI, unemployment rate (`lfs_month`), leading and coincident indexes, exports and imports (`trade_sitc_1d`), USD/MYR (`exchangerates_daily_1200`, middle rate) |
| Bank Negara Malaysia | Overnight Policy Rate decisions (`raw/opr_decisions.csv`) |
| World Bank Pink Sheet | Brent crude oil price, food price index |
| BIS | Nominal effective exchange rate, broad (Malaysia) |

Only real official data is used. No synthetic data is generated.

## Folder structure

```
raw/          downloaded source files (parquet, csv, xlsx)
processed/    master tables, features, audits, data dictionary
outputs/      Power BI CSVs and figures
scripts/      pipeline scripts, run in order
```

## How to run

Requires Python 3.10 or later.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt

python scripts/01_download.py
python scripts/02_clean.py
python scripts/03_features.py
python scripts/04_relationships.py
```

Each script prints a short summary and writes its outputs to `processed/` or `outputs/`.

## Key outputs

| File | Contents |
|---|---|
| `processed/monthly_master.csv` | 202 months (Jan 2010 to Oct 2026), 25 columns |
| `processed/quarterly_master.csv` | 43 quarters (2016 Q1 to 2026 Q3) |
| `processed/features_monthly.csv` | Inflation model table: target and lagged features |
| `processed/features_quarterly.csv` | GDP model table: target and lagged features |
| `processed/publication_lags.csv` | Publication delay applied to each input |
| `processed/data_dictionary.csv` | Variable definitions and sources |
| `outputs/powerbi_monthly.csv`, `outputs/powerbi_quarterly.csv` | Long-format data for the dashboard |

## Method notes

- Forecasts use only data published by the forecast date (publication-lag alignment).
- Models are evaluated in time order with expanding-window rolling-origin cross-validation; observations are never shuffled.
- Relationships are reported as correlation or predictive precedence, not causation.
- Scenario results are model projections, not forecasts of what will happen.
