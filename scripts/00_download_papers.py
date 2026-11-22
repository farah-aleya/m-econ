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
    ("08_Jasni_et_al_2022_DOSM_nowcasting_GDP_ML.pdf", "Malaysia: DOSM ML nowcasting poster",
     ["https://v1.dosm.gov.my/v1/uploads/files/4_Portal%20Content/2_%20Statistics/MyStats/2022/Poster/SITI%20KHADIJAH%20JASNI_CORE%20TEAM_DOSM.pdf"]),
    ("09_Majuca_2020_AMRO_oil_prices_Malaysia.pdf", "Malaysia: oil price effects (already cited)",
     ["https://amro-asia.org/wp-content/uploads/2020/04/Impact-of-Oil-Prices-on-Malaysia_final.pdf"]),
]

LIBRARY_ONLY = [
    ("Duasa, Ahmad, Ibrahim & Zainal (2010). Forecasting inflation in Malaysia. Journal of Forecasting, 29(6), 573-594.",
     "Model 2, Malaysian evidence"),
    ("Bergmeir & Benitez (2012). On the use of cross-validation for time series predictor evaluation. "
     "Information Sciences, 191, 192-213. https://doi.org/10.1016/j.ins.2011.12.028", "Time-ordered validation"),
    ("Baharumshah, Soon & Wohar (2017). International Review of Economics & Finance, 51, 245-257.", "Already cited"),
    ("Ahmed & Wadud (2011). Energy Policy, 39(12), 8062-8069.", "Already cited"),
]

ok, failed = [], []
for name, why, urls in PAPERS:
    dest = OUT / name
    if dest.exists():
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
