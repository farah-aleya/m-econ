"""
M-ECON | Step 1: download raw data and write an inspection report.
Run from the project root:  python scripts/01_download.py
Outputs: raw/<dataset>.parquet  and  raw/inspect_report.txt
"""
import io
import datetime as dt
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw"
RAW.mkdir(exist_ok=True)

# dataset id -> candidate direct-download URLs (first one that works is used)
DATASETS = {
    "gdp_qtr_real": ["https://storage.dosm.gov.my/gdp/gdp_qtr_real.parquet"],
    "cpi_headline_inflation": ["https://storage.dosm.gov.my/cpi/cpi_headline_inflation.parquet"],
    "cpi_core_inflation": ["https://storage.dosm.gov.my/cpi/cpi_core_inflation.parquet"],
    "ppi": ["https://storage.dosm.gov.my/ppi/ppi.parquet"],
    "ipi": ["https://storage.dosm.gov.my/ipi/ipi.parquet"],
    "lfs_month": ["https://storage.dosm.gov.my/labour/lfs_month.parquet"],
    "exchangerates": ["https://storage.data.gov.my/finsector/exchangerates.parquet"],
    "economic_indicators": ["https://storage.dosm.gov.my/mei/economic_indicators.parquet",
                            "https://storage.dosm.gov.my/economic/economic_indicators.parquet"],
    "trade_sitc_1d": ["https://storage.dosm.gov.my/trade/trade_sitc_1d.parquet"],
    "interestrates": ["https://storage.data.gov.my/finsector/interestrates.parquet"],
}

API = "https://api.data.gov.my/data-catalogue"
HEADERS = {"User-Agent": "M-ECON-datathon/1.0"}


def try_parquet(urls):
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
            if r.status_code == 200 and r.content[:4] == b"PAR1":
                return pd.read_parquet(io.BytesIO(r.content)), url
        except Exception:
            pass
    return None, None


def try_api(ds_id):
    try:
        r = requests.get(API, params={"id": ds_id, "limit": 1_000_000}, headers=HEADERS, timeout=120)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and data:
                return pd.DataFrame(data), f"{API}?id={ds_id}"
    except Exception:
        pass
    return None, None


def describe(name, df, source):
    lines = [f"\n{'=' * 70}", f"{name}", f"source: {source}", f"rows: {len(df)}  cols: {list(df.columns)}"]
    lines.append(f"dtypes: {df.dtypes.astype(str).to_dict()}")
    if "date" in df.columns:
        d = pd.to_datetime(df["date"], errors="coerce")
        lines.append(f"date range: {d.min().date()} to {d.max().date()}")
    for c in df.columns:
        if df[c].dtype == object and c != "date":
            u = df[c].dropna().unique()
            shown = list(u[:40])
            lines.append(f"  {c}: {len(u)} unique -> {shown}{' ...' if len(u) > 40 else ''}")
    lines.append("head:\n" + df.head(3).to_string())
    lines.append("tail:\n" + df.tail(3).to_string())
    return "\n".join(lines)


def main():
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    report = [f"M-ECON raw data inspection report  |  retrieved {stamp}"]
    for name, urls in DATASETS.items():
        df, src = try_parquet(urls)
        if df is None:
            df, src = try_api(name)
        if df is None:
            msg = f"\n!! {name}: FAILED to download. Get it manually from https://open.dosm.gov.my/data-catalogue/{name}"
            print(msg); report.append(msg)
            continue
        df.to_parquet(RAW / f"{name}.parquet", index=False)
        print(f"OK  {name:24s} {len(df):>7} rows  <- {src}")
        report.append(describe(name, df, src))

    # manual files: just confirm presence
    for f in ["pinksheet_monthly.xlsx", "bis_neer_malaysia.csv", "opr_decisions.csv"]:
        p = RAW / f
        report.append(f"\nmanual file {f}: {'FOUND' if p.exists() else 'not found yet'}")
        if p.exists() and p.suffix == ".csv":
            report.append(pd.read_csv(p).head(5).to_string())
        if p.exists() and p.suffix == ".xlsx":
            xl = pd.ExcelFile(p)
            report.append(f"sheets: {xl.sheet_names}")

    (RAW / "inspect_report.txt").write_text("\n".join(report), encoding="utf-8")
    print(f"\nReport written to {RAW / 'inspect_report.txt'}")


if __name__ == "__main__":
    main()
