"""
M-ECON | Step 6: unstructured data. Tone of BNM Monetary Policy Statements.
Run from the project root:  python scripts/06_text.py
Re-score only (no download): python scripts/06_text.py --offline

What it does
  1. Downloads each Monetary Policy Statement (MPS) from bnm.gov.my into raw/mpc/<yyyy-mm-dd>.html
     (skips files already saved). If a download fails, save the statement text by hand as
     raw/mpc/<yyyy-mm-dd>.txt and rerun; .txt files are used first.
  2. Extracts the statement text and scores its tone with a fixed word list:
       tone = (tightening phrases - easing phrases) / (tightening + easing), from -1 (easing) to +1 (tightening)
  3. Tests whether the tone leads the next OPR decision, and links tone with CPI inflation and GDP growth.
Outputs
  processed/mpc_statements.csv, processed/findings_text.txt
  outputs/powerbi_mpc_tone.csv, outputs/figures/fig_mpc_tone.png
"""
import re
import sys
import time
import html as htmllib
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw" / "mpc"; RAW.mkdir(parents=True, exist_ok=True)
PROC = ROOT / "processed"; PROC.mkdir(exist_ok=True)
OUT = ROOT / "outputs"; FIG = OUT / "figures"; FIG.mkdir(parents=True, exist_ok=True)
plt.rcParams["font.family"] = "Times New Roman"
OFFLINE = "--offline" in sys.argv
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/131.0.0.0 Safari/537.36",
           "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
           "Accept-Language": "en-US,en;q=0.9", "Referer": "https://www.bnm.gov.my/monetary-stability/opr-decisions"}
# bnm.gov.my blocks plain Python requests (HTTP 403). curl_cffi sends the same handshake as a real Chrome browser.
#   pip install curl_cffi
try:
    from curl_cffi import requests as creq
    SESSION = creq.Session(impersonate="chrome")
    CLIENT = "curl_cffi (Chrome)"
except ImportError:
    SESSION = requests.Session(); SESSION.headers.update(HEADERS)
    CLIENT = "requests (may get HTTP 403; run: pip install curl_cffi)"
BLOCKED = [0]
URL = "https://www.bnm.gov.my/-/monetary-policy-statement-{d:%d%m%Y}"

# MPC decisions from bnm.gov.my/monetary-stability/opr-decisions (date, change in OPR, new OPR), checked 23 Nov 2026
DECISIONS = """
2010-01-26 0 2.00|2010-03-04 0.25 2.25|2010-05-13 0.25 2.50|2010-07-08 0.25 2.75|2010-09-02 0 2.75|2010-11-12 0 2.75
2011-01-27 0 2.75|2011-03-11 0 2.75|2011-05-05 0.25 3.00|2011-07-07 0 3.00|2011-09-08 0 3.00|2011-11-11 0 3.00
2012-01-31 0 3.00|2012-03-09 0 3.00|2012-05-11 0 3.00|2012-07-05 0 3.00|2012-09-06 0 3.00|2012-11-08 0 3.00
2013-01-31 0 3.00|2013-03-07 0 3.00|2013-05-09 0 3.00|2013-07-11 0 3.00|2013-09-05 0 3.00|2013-11-07 0 3.00
2014-01-29 0 3.00|2014-03-06 0 3.00|2014-05-08 0 3.00|2014-07-10 0.25 3.25|2014-09-18 0 3.25|2014-11-06 0 3.25
2015-01-28 0 3.25|2015-03-05 0 3.25|2015-05-07 0 3.25|2015-07-09 0 3.25|2015-09-11 0 3.25|2015-11-05 0 3.25
2016-01-21 0 3.25|2016-03-09 0 3.25|2016-05-19 0 3.25|2016-07-13 -0.25 3.00|2016-09-07 0 3.00|2016-11-23 0 3.00
2017-01-19 0 3.00|2017-03-02 0 3.00|2017-05-12 0 3.00|2017-07-13 0 3.00|2017-09-07 0 3.00|2017-11-09 0 3.00
2018-01-25 0.25 3.25|2018-03-07 0 3.25|2018-05-10 0 3.25|2018-07-11 0 3.25|2018-09-05 0 3.25|2018-11-08 0 3.25
2019-01-24 0 3.25|2019-03-05 0 3.25|2019-05-07 -0.25 3.00|2019-07-09 0 3.00|2019-09-12 0 3.00|2019-11-05 0 3.00
2020-01-22 -0.25 2.75|2020-03-03 -0.25 2.50|2020-05-05 -0.50 2.00|2020-07-07 -0.25 1.75|2020-09-10 0 1.75|2020-11-03 0 1.75
2021-01-20 0 1.75|2021-03-04 0 1.75|2021-05-06 0 1.75|2021-07-08 0 1.75|2021-09-09 0 1.75|2021-11-03 0 1.75
2022-01-20 0 1.75|2022-03-03 0 1.75|2022-05-11 0.25 2.00|2022-07-06 0.25 2.25|2022-09-08 0.25 2.50|2022-11-03 0.25 2.75
2023-01-19 0 2.75|2023-03-09 0 2.75|2023-05-03 0.25 3.00|2023-07-06 0 3.00|2023-09-07 0 3.00|2023-11-02 0 3.00
2024-01-24 0 3.00|2024-03-07 0 3.00|2024-05-09 0 3.00|2024-07-11 0 3.00|2024-09-05 0 3.00|2024-11-06 0 3.00
2025-01-22 0 3.00|2025-03-06 0 3.00|2025-05-08 0 3.00|2025-07-09 -0.25 2.75|2025-09-04 0 2.75|2025-11-06 0 2.75
2026-01-22 0 2.75|2026-03-05 0 2.75|2026-05-07 0 2.75|2026-07-09 0 2.75|2026-09-03 0 2.75|2026-11-05 0 2.75
"""
rows = [x.split() for line in DECISIONS.strip().splitlines() for x in line.split("|")]
dec = pd.DataFrame(rows, columns=["date", "opr_change", "opr"])
dec["date"] = pd.to_datetime(dec["date"]); dec[["opr_change", "opr"]] = dec[["opr_change", "opr"]].astype(float)
dec = dec.sort_values("date").reset_index(drop=True)

# ---------- tone dictionary (fixed before scoring; phrases matched on lower-case text) ----------
# tightening (hawkish): pressure on prices, strong demand, removing stimulus
# matching is by word start, so "upside risk" also counts "upside risks"; each phrase is listed once
TIGHT = ["upside risk", "inflationary pressure", "price pressure", "cost pressure", "demand-driven",
         "demand driven", "higher inflation", "inflation to rise", "rising inflation", "elevated inflation",
         "inflation is expected to increase", "strong growth", "robust growth", "firm growth",
         "strong domestic demand", "financial imbalance", "excessive", "overheat", "normalis", "normaliz",
         "monetary accommodation", "tighten", "increase the opr", "raise the opr"]
# easing (dovish): weak growth, low inflation, support for the economy
EASE = ["downside risk", "weak", "slow", "moderat", "subdued", "benign", "contained", "lower inflation",
        "uncertaint", "headwind", "accommodative", "supportive", "support the economy", "support economic",
        "support growth", "support domestic", "pre-emptive", "preemptive", "reduce the opr", "lower the opr",
        "easing", "stimulus", "contraction", "recession", "softer", "soft patch", "challenging", "disruption",
        "pandemic"]

def count(text, phrases):
    return sum(len(re.findall(r"\b" + re.escape(p), text)) for p in phrases)

def html_to_text(raw):
    raw = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h\d>", "\n", raw)
    txt = htmllib.unescape(re.sub(r"<[^>]+>", " ", raw))
    txt = re.sub(r"[ \t\r\f\v]+", " ", txt)
    return re.sub(r"\n\s*\n+", "\n", txt)

def statement_body(txt):
    """keep the statement itself: from 'At its meeting' (or first MPC mention) to the closing 'Bank Negara Malaysia <date>'"""
    low = txt.lower()
    s = 0
    for k in ("at its meeting", "the monetary policy committee (mpc)", "embargo"):   # first anchor found, in this order
        if low.find(k) >= 0: s = low.find(k); break
    body = txt[s:]
    for stop in (r"Schedule of Monetary Policy", r"See also", r"Bank Negara Malaysia\s*\n?\s*\d{1,2}\s+\w+\s+\d{4}", r"©"):
        m = re.search(stop, body)
        if m and m.start() > 200: body = body[:m.start()]
    return body.strip()

def get(d):
    f_txt, f_html = RAW / f"{d:%Y-%m-%d}.txt", RAW / f"{d:%Y-%m-%d}.html"
    if f_txt.exists(): return f_txt.read_text(encoding="utf-8", errors="ignore"), "manual txt"
    if not f_html.exists() and not OFFLINE:
        try:
            r = SESSION.get(URL.format(d=d), headers=HEADERS, timeout=30)
            if r.status_code == 200 and "Monetary Policy" in r.text:
                f_html.write_text(r.text, encoding="utf-8"); time.sleep(1.5)
            else:
                print(f"   {d:%Y-%m-%d}: HTTP {r.status_code}, save it by hand as raw/mpc/{d:%Y-%m-%d}.txt")
                if r.status_code == 403:
                    BLOCKED[0] += 1
                    if BLOCKED[0] >= 3:
                        sys.exit("\n   bnm.gov.my is blocking downloads (HTTP 403). Run: pip install curl_cffi  then rerun.\n"
                                 "   If it still fails, save the statements by hand as raw/mpc/<yyyy-mm-dd>.txt")
        except Exception as e:
            print(f"   {d:%Y-%m-%d}: download failed ({type(e).__name__})")
    if f_html.exists(): return statement_body(html_to_text(f_html.read_text(encoding="utf-8", errors="ignore"))), "bnm.gov.my"
    return None, "missing"

print("Step 6: BNM Monetary Policy Statements")
if not OFFLINE: print(f"   download client: {CLIENT}")
if not OFFLINE and "requests" in CLIENT:
    try: SESSION.get("https://www.bnm.gov.my/monetary-stability/opr-decisions", timeout=30)  # pick up site cookies first
    except Exception: pass
recs = []; TEXTS = {}
for _, r in dec.iterrows():
    text, src = get(r["date"])
    if text: TEXTS[r["date"]] = text.lower()
    if not text: recs.append({**r, "source": src}); continue
    low = text.lower()
    h, e = count(low, TIGHT), count(low, EASE)
    recs.append({**r, "source": src, "words": len(low.split()), "tight": h, "ease": e,
                 "tone": (h - e) / (h + e) if h + e else 0.0})
df = pd.DataFrame(recs)
if "tone" not in df.columns:
    sys.exit("   No statements scored. Check raw/mpc/ (save statements as <yyyy-mm-dd>.txt) and rerun with --offline.")
df["next_change"] = df["opr_change"].shift(-1)
got = df.dropna(subset=["tone"]).copy()
print(f"   statements scored: {len(got)} of {len(df)} ({got['date'].min():%b %Y} to {got['date'].max():%b %Y})")
short = got[got["words"] < 150]
if len(short): print(f"   WARNING: {len(short)} statements under 150 words, check extraction: {', '.join(short['date'].dt.strftime('%Y-%m-%d'))}")
if len(got) < 10: sys.exit("   Too few statements. Check raw/mpc/ and rerun.")

# ---------- analysis ----------
lines = ["=== BNM MONETARY POLICY STATEMENT TONE ===",
         f"Statements scored: {len(got)} ({got['date'].min():%b %Y} to {got['date'].max():%b %Y}); "
         f"median length {got['words'].median():.0f} words",
         "Tone = (tightening - easing phrases) / total, from -1 (easing) to +1 (tightening)", ""]
lab = np.where(got["opr_change"] > 0, "hike", np.where(got["opr_change"] < 0, "cut", "hold"))
for k in ("hike", "hold", "cut"):
    s = got.loc[lab == k, "tone"]
    if len(s): lines.append(f"   Mean tone at {k:4s} meetings: {s.mean():+.2f} (n = {len(s)})")
# relative tone: the word list leans to easing words ("moderate", "weak"), so the raw score sits below zero.
# What matters is tone relative to BNM's usual wording. tone_rel uses only PAST statements (no look-ahead):
# (tone - mean of all earlier statements) / their std, from the 9th statement on.
got["tone_rel"] = (got["tone"] - got["tone"].expanding(8).mean().shift(1)) / got["tone"].expanding(8).std().shift(1)
got["tone_z"] = (got["tone"] - got["tone"].mean()) / got["tone"].std()
df = df.merge(got[["date", "tone_rel", "tone_z"]], on="date", how="left")
nx = got.dropna(subset=["next_change"])
lab2 = np.where(nx["next_change"] > 0, "hike", np.where(nx["next_change"] < 0, "cut", "hold"))
lines.append("")
for k in ("hike", "hold", "cut"):
    s = nx.loc[lab2 == k, "tone"]
    if len(s): lines.append(f"   Mean tone one meeting BEFORE a {k:4s}: {s.mean():+.2f} (n = {len(s)})")
rho, p = stats.spearmanr(nx["tone"], nx["next_change"])
lines.append(f"   Spearman correlation, tone vs next OPR change: {rho:+.2f} (p = {p:.3f}, n = {len(nx)})")
lines.append(f"   Raw tone: mean {got['tone'].mean():+.2f}, sd {got['tone'].std():.2f} (word list leans to easing words, so use relative tone)")
lines.append("")
lines.append("Relative tone (above or below BNM's average wording) before the next decision:")
for col, name in (("tone_z", "full-sample average"), ("tone_rel", "past statements only, real time")):
    z = nx.dropna(subset=[col]); up, dn = z[z[col] > 0], z[z[col] < 0]
    mv = z[z["next_change"] != 0]
    hit = (np.sign(mv[col]) == np.sign(mv["next_change"])).mean() * 100
    lines.append(f"   [{name}] direction right before {hit:.0f}% of {len(mv)} rate changes")
    lines.append(f"      above average ({len(up)}): next = {(up.next_change > 0).sum()} hikes, {(up.next_change == 0).sum()} holds, {(up.next_change < 0).sum()} cuts")
    lines.append(f"      below average ({len(dn)}): next = {(dn.next_change < 0).sum()} cuts, {(dn.next_change == 0).sum()} holds, {(dn.next_change > 0).sum()} hikes")
lines.append(f"   Base rate: {(nx.next_change == 0).mean() * 100:.0f}% of decisions are holds, so tone shows the direction of the next move, not its timing.")
# link with the macro data (monthly master from step 2, if present)
mm = PROC / "monthly_master.csv"; qm = PROC / "quarterly_master.csv"
monthly = pd.DataFrame({"date": pd.date_range(got["date"].min().to_period("M").to_timestamp(),
                                               pd.Timestamp.today().to_period("M").to_timestamp(), freq="MS")})
tm = got.assign(date=got["date"].dt.to_period("M").dt.to_timestamp())[["date", "tone", "opr"]]
monthly = pd.merge_asof(monthly, tm.sort_values("date"), on="date")  # tone carried until the next statement
if mm.exists():
    m = pd.read_csv(mm, parse_dates=["date"])
    if "cpi_yoy" in m.columns:
        monthly = monthly.merge(m[["date", "cpi_yoy"]], on="date", how="left")
        lines.append("")
        for h in (0, 3, 6):
            z = pd.DataFrame({"t": monthly["tone"], "c": monthly["cpi_yoy"].shift(-h)}).dropna()
            ex = z[~monthly.loc[z.index, "date"].between("2020-03-01", "2021-12-01")]
            r1, p1 = stats.pearsonr(ex["t"], ex["c"])
            lines.append(f"   Tone vs CPI inflation {h} months later (excl. 2020-21): r = {r1:+.2f} (p = {p1:.3f})")
if qm.exists():
    q = pd.read_csv(qm, parse_dates=["date"])
    if "gdp_yoy" in q.columns:
        tq = monthly.assign(date=monthly["date"].dt.to_period("Q").dt.to_timestamp()).groupby("date")["tone"].mean().reset_index()
        z = tq.merge(q[["date", "gdp_yoy"]], on="date").dropna()
        z = z[~z["date"].between("2020-01-01", "2021-12-31")]
        r2, p2 = stats.pearsonr(z["tone"], z["gdp_yoy"])
        lines.append(f"   Tone vs GDP growth, same quarter (excl. 2020-21): r = {r2:+.2f} (p = {p2:.3f})")
last = got.iloc[-1]
lines += ["", f"Latest statement ({last['date']:%d %b %Y}): tone {last['tone']:+.2f} (relative {got['tone_rel'].iloc[-1]:+.2f} sd), "
          f"{int(last['tight'])} tightening vs {int(last['ease'])} easing phrases; OPR {last['opr']:.2f}%"]
def top(words):
    n = {p: sum(count(t, [p]) for t in TEXTS.values()) for p in words}
    return ", ".join(f"{p} ({k})" for p, k in sorted(n.items(), key=lambda x: -x[1])[:6] if k)
lines += ["Most frequent tightening phrases: " + top(TIGHT), "Most frequent easing phrases: " + top(EASE)]

(PROC / "findings_text.txt").write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
df.to_csv(PROC / "mpc_statements.csv", index=False)
pb = got[["date", "opr_change", "opr", "tight", "ease", "tone", "tone_rel", "words"]].copy()
pb["stance"] = np.where(pb["tone_rel"] > 0.5, "More hawkish than usual",
                        np.where(pb["tone_rel"] < -0.5, "More dovish than usual", "Usual"))
pb["url"] = [URL.format(d=d) for d in pb["date"]]
pb.to_csv(OUT / "powerbi_mpc_tone.csv", index=False)

# ---------- figure ----------
fig, ax = plt.subplots(figsize=(10, 3.8))
g = got.dropna(subset=["tone_rel"])
ax.bar(g["date"], g["tone_rel"], width=40, color=np.where(g["tone_rel"] >= 0, "#C0561B", "#1F4E79"))
ax.axhline(0, color="black", lw=0.6); ax.set_ylabel("Tone vs BNM's past average (sd)")
for _, r in got[got["opr_change"] != 0].iterrows():
    ax.annotate("▲" if r["opr_change"] > 0 else "▼", (r["date"], 1.02), ha="center", fontsize=8,
                color="#C0561B" if r["opr_change"] > 0 else "#1F4E79", xycoords=("data", "axes fraction"))
ax2 = ax.twinx(); ax2.step(dec["date"], dec["opr"], where="post", color="black", lw=1.4, label="OPR (%)")
ax2.set_ylabel("OPR (%)"); ax2.set_ylim(0, 4)
lim = max(3, g["tone_rel"].abs().max() * 1.05); ax.set_ylim(-lim, lim); ax.spines["top"].set_visible(False); ax2.spines["top"].set_visible(False)
ax.set_title("Tone of BNM Monetary Policy Statements relative to past statements, and the OPR (▲ hike, ▼ cut)", pad=16)
fig.tight_layout(); fig.savefig(FIG / "fig_mpc_tone.png", dpi=200); plt.close(fig)
print("\nSaved processed/mpc_statements.csv, processed/findings_text.txt, outputs/powerbi_mpc_tone.csv, outputs/figures/fig_mpc_tone.png")
