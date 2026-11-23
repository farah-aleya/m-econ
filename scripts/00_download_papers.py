"""
M-ECON | Download open-access papers that support the model choices.
Run from the project root:  python scripts/00_download_papers.py
Saves PDFs into papers/ and prints which ones need the UTP library.
"""
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "papers"
OUT.mkdir(exist_ok=True)
HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) M-ECON-datathon"}

PAPERS = [
    # (file name, why it matters, candidate URLs)
    ("01_Atkeson_Ohanian_2001_Phillips_curves_naive.pdf", "Model 1: naive benchmark",
     ["https://www.minneapolisfed.org/research/qr/qr2511.pdf"]),
    ("02_Stock_Watson_2003_Forecasting_output_inflation.pdf", "Model 2: lagged-predictor regression (NBER version)",
     ["https://www.nber.org/system/files/working_papers/w8180/w8180.pdf",
      "http://www.nber.org/papers/w8180.pdf"]),
    ("03_Medeiros_et_al_2021_ML_inflation_random_forest.pdf", "Model 3: random forest for inflation (working-paper version)",
     ["https://www.bcentral.cl/documents/33528/133326/DTBC_834.pdf"]),
    ("04_GouletCoulombe_et_al_2022_How_is_ML_useful.pdf", "Model 3: ML in data-poor macro settings (arXiv version)",
     ["https://arxiv.org/pdf/2008.12477"]),
    ("05_GouletCoulombe_2024_Macroeconomy_as_random_forest.pdf", "Model 3: random forest for macro (arXiv version)",
     ["https://arxiv.org/pdf/2006.12724"]),
    ("06_Breiman_2001_Random_forests.pdf", "Model 3: original random forest paper",
     ["https://www.stat.berkeley.edu/~breiman/randomforest2001.pdf"]),
    ("07_Cham_et_al_2024_ML_CPI_Malaysia.pdf", "Malaysia: ML for CPI forecasting (UKM JQMA)",
     ["https://ukm.my/jqma/wp-content/uploads/2024/11/Paper_14.pdf",
      "http://journalarticle.ukm.my/25186/1/199-214%20Paper.pdf"]),
    ("09_Majuca_2020_AMRO_oil_prices_Malaysia.pdf", "Malaysia: oil price effects (already cited)",
     ["https://amro-asia.org/wp-content/uploads/2020/04/Impact-of-Oil-Prices-on-Malaysia_final.pdf"]),
    # --- added 23 Nov: support for LASSO and forecast averaging (12 is reserved for Duasa 2010) ---
    ("13_Smeekes_Wijler_2018_Penalized_regression_macro_forecasting.pdf",
     "LASSO/Ridge: penalized regression for macro forecasting (accepted version)",
     ["https://cris.maastrichtuniversity.nl/ws/files/53572602/Smeekes_2018_Macroeconomic_forecasting_using_penalized_regression_methods.pdf",
      "https://cris.maastrichtuniversity.nl/ws/files/5783492/RM16039.pdf"]),
    ("14_Clemen_1989_Combining_forecasts_review.pdf",
     "Forecast averaging: review showing combining improves accuracy",
     ["https://people.duke.edu/~clemen/bio/Published%20Papers/13.CombiningReview-Clemen-IJOF-89.pdf"]),
    ("15_Tibshirani_1996_Lasso.pdf",
     "LASSO: original method paper",
     ["https://sites.stat.washington.edu/courses/stat527/s13/readings/j_royal_stat_soc_b1996.pdf",
      "https://ledaliang.github.io/journalclub/_static/tibshirani/tibshirani.pdf"]),
]

LIBRARY_ONLY = [
    ("Bates & Granger (1969). The combination of forecasts. Journal of the Operational Research Society, 20(4), 451-468. "
     "https://doi.org/10.1057/jors.1969.103", "Forecast averaging: original paper"),
    ("Stock & Watson (2004). Combination forecasts of output growth in a seven-country data set. "
     "Journal of Forecasting, 23(6), 405-430. https://doi.org/10.1002/for.928", "Forecast averaging for GDP growth"),
    ("LASSO Regression in Consumer Price Index Malaysia (UTHM). Record: https://libmast.utm.my/Record/uthm.eprints-2614",
     "LASSO, Malaysian CPI (check authors and year)"),
    ("Duasa, Ahmad, Ibrahim & Zainal (2010). Forecasting inflation in Malaysia. Journal of Forecasting, 29(6), 573-594.",
     "Model 2, Malaysian evidence"),
]

ok, failed = [], []
for name, why, urls in PAPERS:
    dest = OUT / name
    if dest.exists() or list(OUT.glob(name[:3] + "*")):   # already downloaded (or renamed)
        ok.append(name); continue
    for url in urls:
        try:
            r = requests.get(url, headers=HEAD, timeout=60, allow_redirects=True)
            if r.status_code == 200 and r.content[:4] == b"%PDF":
                dest.write_bytes(r.content)
                print(f"OK      {name}")
                ok.append(name)
                break
        except Exception:
            pass
    else:
        print(f"FAILED  {name}  -> open manually: {urls[0]}")
        failed.append((name, urls[0]))

print(f"\nDownloaded {len(ok)} of {len(PAPERS)} into {OUT}")
print("\nGet these through the UTP library (paywalled):")
for ref, why in LIBRARY_ONLY:
    print(f"  - {ref}  [{why}]")
