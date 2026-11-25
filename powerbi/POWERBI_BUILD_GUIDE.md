# M-ECON Power BI build guide (from scratch)

Website-style dashboard: dark top menu, white rounded cards, teal = GDP, coral = inflation, amber = selected or highlight, violet = models, red/green = alerts.

Time needed: about 4 to 5 hours. Save often (Ctrl+S).

## Files you need

| File | What it is |
|---|---|
| `outputs/powerbi_*.csv` (19 files) | All dashboard data |
| `powerbi/MECON_theme.json` | Colours and fonts |
| `powerbi/backgrounds/bg_*.png` | One page background each (menu bar, cards and shadows already drawn) |
| `powerbi/previews/preview_*.png` | Same layouts with every card labelled with X, Y, W, H |
| `powerbi/MECON_measures.dax` | All measures, one per line |

**Golden rule for every visual:** turn its background and border off, then type its X, Y, W, H from the preview image in **Format > General > Properties > Size / Position**. It then sits exactly inside its white card.

---

## Part A. New file, page size, theme

1. Power BI Desktop > **Blank report**. Save as `FOREFRONT_Datathon2026_dashboard.pbix` in the project folder.
2. **View > Themes** > small down arrow > **Browse for themes** > `powerbi/MECON_theme.json`.
3. Click empty canvas > **Format page** (Visualizations pane, 2nd icon) > **Canvas settings**: Type **16:9** (1280 × 720), Vertical alignment **Top**.

## Part B. Load the 19 CSV files

1. **Home > Get data > Text/CSV**, load each file in `outputs/`.
2. Rename each table (double-click it in the Data pane):

| File | Table name | | File | Table name |
|---|---|---|---|---|
| powerbi_monthly.csv | Monthly | | powerbi_early_warning.csv | EarlyWarning |
| powerbi_quarterly.csv | Quarterly | | powerbi_ew_indicators.csv | EWIndicators |
| powerbi_variables.csv | Variables | | powerbi_ew_status.csv | EWStatus |
| powerbi_forecasts.csv | Forecasts | | powerbi_backtest.csv | Backtest |
| powerbi_predictions.csv | Predictions | | powerbi_events.csv | Events |
| powerbi_model_results.csv | ModelResults | | powerbi_scenarios.csv | Scenarios |
| powerbi_fan.csv | Fan | | powerbi_scenario_slider.csv | ScenarioSlider |
| powerbi_importance.csv | Importance | | powerbi_state_inflation.csv | StateInflation |
| powerbi_corr.csv | Corr | | powerbi_mpc_tone.csv | MPCTone |
| powerbi_top_predictors.csv | TopPredictors | | | |

### Fix: Variables table header
Power BI loads its header row as data (columns show as Column1 to Column5).
1. **Home > Transform data**. Click **Variables** on the left.
2. If **Applied steps** shows "Changed Type", click the **X** next to it.
3. **Transform** tab > **Use First Row as Headers**. Columns become variable, label, unit, role, group.
4. **Home > Close & Apply**.

### Check data types (Table view, the grid icon on the left)
Click each column below > **Column tools > Data type**:
- **Date:** `date` in Monthly, Quarterly, Events, MPCTone, EarlyWarning, EWIndicators, StateInflation, Fan; `origin` and `forecast_for` in Forecasts; `origin` and `target_date` in Predictions; `as_of` in EWStatus; `origin` in Scenarios.
- **True/False:** `selected` in Forecasts.
- **Whole number:** `flag` in EWIndicators. Its blanks must stay blank (October 2026 PPI shows blank "Not yet published", not 0).

### Sort the heatmap lags correctly
Corr table > click `lag_label` > **Column tools > Sort by column > lag**. Otherwise "12 m" sorts before "2 m".

## Part C. Model

### C1. Helper tables
1. **Home > Enter data**, leave empty, name it `_Measures`, **Load**.
2. **Modeling > New table**, paste each and press Enter (the first 3 lines of `MECON_measures.dax`):
   - `Calendar = ...`
   - `Brent Shock = GENERATESERIES ( -30, 30, 5 )`
   - `Ringgit Shock = GENERATESERIES ( -10, 10, 1 )`
3. Click **Calendar** > **Table tools > Mark as date table** > turn the toggle **On** > choose **Date** > **Save**.

### C2. Relationships (Model view, 3rd icon on the left)
1. **First delete Power BI's automatic links.** Click each line and press Delete, keeping only Variables → Monthly and Variables → Quarterly. Typical wrong ones: ScenarioSlider to Fan, Forecasts, ModelResults and Scenarios; EWStatus to EWIndicators and Backtest.
2. Drag `Calendar[Date]` onto `date` in each of: **Monthly, Quarterly, Events, MPCTone, EarlyWarning, EWIndicators, StateInflation**.
3. In every window set **Cardinality: One to many (1:\*)** and **Cross-filter: Single**. EarlyWarning, Events and MPCTone open as One to one / Both: change them.
4. If missing, drag `Variables[variable]` onto `Monthly[variable]` and `Quarterly[variable]`.
5. Check: **9 lines** in total. `_Measures`, Brent Shock and Ringgit Shock have **no** lines.

### C3. Measures
1. Report view > click `_Measures` > **Modeling > New measure**.
2. Paste **one line** from `MECON_measures.dax` (each measure is one line), press Enter.
3. Repeat for all measures. Check the **Home table** box says `_Measures`.
4. When done: right-click `Column1` in `_Measures` > **Delete from model**.
5. A red underline under `Calendar` means it needs quotes: `'Calendar'` (already fixed in the file).

## Part D. Pages, backgrounds, menu

### D1. Pages
1. Rename Page 1 to **Home**.
2. For the others: right-click **Home** > **Duplicate page**, rename: **GDP, Inflation, Drivers & States, Early Warning, Scenarios**.
3. On each page: click empty canvas > **Format page > Canvas background** > Image **X** (remove old) > **Browse** > matching `bg_*.png`, **Image fit: Fill**, **Transparency: 0%**. (Fill or Fit both work; **Normal** shows only a corner.)

### D2. Top menu (build on Home, then copy)
1. **Insert > Buttons > Navigator > Page navigator.** General: Height **40**, Width **800**, Horizontal **456**, Vertical **12**.
2. Visual > **Shape: Pill**.
3. Visual > **Style** > Apply settings to **Default**: Text Segoe UI 10 colour `#BEC8D7`; Fill On `#0B1F3A`; Border Off.
4. Apply settings to **Selected**: Text white, bold; Fill `#00A6A6`.
5. **Insert > Text box** "M-ECON": Segoe UI Bold 16, white; Height 30, Width 160, Horizontal 64, Vertical 18; Background Off.
6. Select both (Ctrl+click) > Ctrl+C > paste (Ctrl+V) on every other page.

### D3. Page titles (all pages except Home)
Text box at Horizontal 44, Vertical 88, Width 400, Height 34. Segoe UI Bold 16, colour `#1B2A41`, Background Off.

## Part E. KPI card recipe (used on every page)

1. **Card** visual (the "123" icon). Drag one measure into **Value**.
2. General: size and position from the preview; **Background Off**, **Border Off**, **Header icons Off**.
3. Visual > **Callout > Values**: Segoe UI Semibold, size 28 (24 if the box is 100 tall), colour = the card's bar colour.
4. Visual > **Cards > Background Off** (removes the inner white box).
5. Label: Build visual > right-click the field > **Rename for this visual** > type the label.
6. Status colour (red/green): Callout > Values > colour **fx** > **Field value** > the colour measure.
7. **Do not use Reference labels**: they squeeze the card. The New Card has no Action, so cards are not clickable (the top menu covers navigation).
8. Fastest: build one card, then Ctrl+C / Ctrl+V and change field, label, colour and Horizontal.

---

## Page 1. Home

- **Hero text** (text box): line 1 "Malaysia Economic Pulse" Segoe UI Bold 20 white; line 2 "GDP and inflation forecasts, early warning and scenarios from official data" size 10 colour `#C8E1E6`. Height 70, Width 700, Horizontal 48, Vertical 82, Background Off.

| Card | Measure | Label | Colour | H / W / X / Y |
|---|---|---|---|---|
| K1 | GDP Forecast Text | GDP growth, next quarter | `#00A6A6` | 110 / 296 / 24 / 166 |
| K2 | Inflation Forecast Text | Inflation, next month | `#FF6B4A` | 110 / 296 / 336 / 166 |
| K3 | Cost Status | Cost-pressure signal | fx Cost Status Colour | 110 / 296 / 648 / 166 |
| K4 | Growth Status | Growth-slowdown signal | fx Growth Status Colour | 110 / 296 / 960 / 166 |

**C1 main chart:** Line and clustered column chart (2nd row, last icon). H 404, W 808, X 24, Y 292.
- X-axis `Calendar[Date]` (choose Date, not hierarchy); Visual > X-axis > **Type: Continuous** (Quarter causes a scrollbar).
- Column y-axis `Event Marker`, renamed "Policy event": colour `#F5B700`, transparency 50%.
- Line y-axis `GDP Growth` (renamed "GDP growth", `#00A6A6`) and `CPI Inflation Q` (renamed "CPI inflation", `#FF6B4A`), width 2.5.
- Tooltips `Event Names`.
- Y-axis Off (and its title Off); secondary y-axis title Off.
- Title "GDP growth and inflation (% YoY), 2011 to 2026", left.

**C2 table:** Table visual. H 196, W 408, X 848, Y 292.
- Columns `EWIndicators[indicator]` (Indicator), `Indicator Status` (Status), `Indicator Month` (Month).
- Totals Off; Values and Column headers font 10; Grid row padding 5.
- Status > Conditional formatting > Font colour > Field value > `Indicator Status Colour`.
- Title "Early-warning indicators (latest month)".

**C3 tone chart:** Clustered column chart. H 196, W 408, X 848, Y 500.
- X `MPCTone[date]`, Y `MPCTone[tone_rel]` (Average).
- Visual filter: date on or after 1/1/2022.
- Columns colour fx > Field value > `Tone Bar Colour`. Axis titles Off.
- Title fx > Field value > `Tone Subtitle`.

## Page 2. GDP

- **Page filters** (Filters pane > Filters on this page): `Predictions[setup]`, `ModelResults[setup]`, `Importance[setup]`, each = **A2**.
- **Title:** "GDP growth forecast".
- **Model dropdown:** Slicer on `Predictions[model]`. Style Dropdown, Single select On, header Off. H 34, W 300, X 940, Y 88. Select **Average (MLR+RF)**.

| Card | Measure | Label | Colour / format | X (Y 146, H 100, W 296) |
|---|---|---|---|---|
| K1 | GDP Forecast Text | Forecast, 2026 Q4 | `#00A6A6`, size 24 | 24 |
| K2 | GDP Range 80 | 80% forecast range | `#00A6A6`, size 20 | 336 |
| K3 | GDP Model MAE | Test error (MAE, pp), Avg model | `#6C5CE7`, units None, 2 decimals | 648 |
| K4 | GDP Gain Text | Better than naive (target 10%) | `#F5B700` | 960 |

**C1:** Line chart. H 434, W 808, X 24, Y 262.
- X `Predictions[target_date]` (date, not hierarchy). Y `actual` and `forecast` (both Average), renamed Actual and Forecast.
- Lines: Actual `#0B1F3A` width 3; Forecast `#00A6A6` width 2.5; Markers On size 4. Axis titles Off.
- Title fx > Field value > `Test Chart Title`.

**C2:** Clustered bar chart. H 212, W 408, X 848, Y 262.
- Y `ModelResults[model]`, X `MAE` (Average). Sort axis by Average of MAE, ascending.
- Y-axis font 8, title Off; X-axis Off; Inner padding 10%; Data labels On, 2 decimals.
- Bars colour fx > Field value > `Model Bar Colour`.
- Title "Test error by model (MAE, lower is better)".

**C3:** Clustered bar chart. H 206, W 408, X 848, Y 490.
- Y `Importance[input]`, X `rf_permutation_importance` (Sum).
- Visual filter on input: Top N, Top 5, by value rf_permutation_importance. Sort descending.
- X-axis Off; Y-axis max width 45%; Data labels 3 decimals; colour `#00A6A6`.
- Title "Top 5 drivers (Random Forest importance)".

## Page 3. Inflation (copy of GDP)

1. On Inflation, delete its navigator and M-ECON text.
2. On GDP: Ctrl+A, Ctrl+C. On Inflation: Ctrl+V. When asked **Sync visuals**, choose **Don't sync**.
3. Page filters: the three setup filters = **B**.
4. Dropdown: pick **AR(1)**. Title: "Inflation forecast".
5. Cards:

| Card | Measure | Label | Format |
|---|---|---|---|
| K1 | Inflation Forecast Text | Forecast, Nov 2026 | `#FF6B4A` |
| K2 | Inflation Range 80 | 80% forecast range | `#FF6B4A` |
| K3 | Inflation Model MAE | Test error (MAE, pp), AR(1) | 3 decimals |
| K4 | Inflation Gain Text | Better than naive (target 10%, not met) | `#F5B700` |

6. Optional: Forecast line and driver bars `#FF6B4A`.

## Page 4. Drivers & States

Title "Drivers and state inflation".

**C1 state map:** Map (or Azure map). H 550, W 616, X 24, Y 146.
- Location `StateInflation[state]`, Latitude `lat` (Average), Longitude `lon` (Average), Bubble size `State CPI Latest`.
- Tooltips `State CPI Latest`, `State Food Latest`, `State Transport Latest`.
- Bubble colour fx: gradient by `State CPI Latest`, low `#00A6A6`, high `#FF6B4A`.
- Title "Inflation by state, latest month".
- If the map is blank: File > Options and settings > Options > Security > tick "Use Map and Filled Map visuals".

**C2 correlation heatmap:** Matrix. H 270, W 600, X 656, Y 146.
- Rows `Corr[label]`, Columns `Corr[lag_label]`, Values `pearson_r` (Average, 2 decimals).
- Visual filter `Corr[sample]` = **ex-COVID**.
- Tile slicer on `Corr[target]` (single select) at H 28, W 190, X 1060, Y 150.
- Cell elements > Background colour fx > Gradient, add a middle colour: min -1 `#00A6A6`, center 0 white, max 1 `#FF6B4A`.
- Totals Off. Title "Correlation with the target, by lag".

**C3 tone vs OPR:** Line and clustered column chart. H 264, W 600, X 656, Y 432.
- X `MPCTone[date]` (Continuous). Column `tone_rel` (Average), colour fx `Tone Bar Colour`. Line `opr` (Average), `#0B1F3A`.
- Title "BNM statement tone (bars) and the OPR (line)".

## Page 5. Early Warning

Title "Early warning".

| Card | Measure | Label | Colour | H / W / X / Y |
|---|---|---|---|---|
| K1 | Cost Status | Cost pressure | fx Cost Status Colour | 150 / 400 / 24 / 146 |
| K2 | Growth Status | Growth slowdown | fx Growth Status Colour | 150 / 400 / 24 / 312 |

Optional: small text cards under each with `Cost Detail` / `Growth Detail` (size 10, grey).

**C1:** Copy the Home indicator table. H 218, W 400, X 24, Y 478.

**C2 timeline:** Area chart. H 330, W 816, X 440, Y 146.
- X `EarlyWarning[date]` (Continuous). Y `Cost Count` (`#FF6B4A`) and `Growth Count` (`#6C5CE7`), transparency 60%.
- Analytics (magnifying glass icon) > **Constant line** value **2**, red, dashed, label "Signal ON".
- Title "How many indicators are flashing (0 to 3)".

**C3 back-test:** Table. H 204, W 816, X 440, Y 492.
- Columns `Backtest[episode]`, `signal`, `first_signal`, `lead_time`, `false_alarm_rate_pct`.
- Title "Back-test: five past episodes (all flagged)".

## Page 6. Scenarios

Title "Scenarios".

**C1 control panel:**
- Slicer on `'Brent Shock'[Value]`. Slicer settings > Style **Single value** (slider), header "Oil price shock (%)". H 70, W 320, X 44, Y 200.
- Slicer on `'Ringgit Shock'[Value]`, Single value, header "Ringgit weaker by (%)". H 70, W 320, X 44, Y 300.
- Text box below: "Drag the sliders. Effects come from the fitted regression models (report Section 4.7)."

| Card | Measure | Label | Colour | H / W / X / Y |
|---|---|---|---|---|
| K1 | GDP Effect Text | Effect on GDP growth, next quarter | fx GDP Effect Colour | 150 / 420 / 400 / 146 |
| K2 | Inflation Effect Text | Effect on inflation, next month | fx Inflation Effect Colour | 150 / 420 / 836 / 146 |

**C2 tested scenarios:** Clustered bar chart. H 250, W 856, X 400, Y 312.
- Y `Scenarios[scenario]`, X `effect_pp` (Sum), Legend `setup` (A2 `#00A6A6`, B `#FF6B4A`).
- Analytics > **Error bars**: Upper `hi95`, Lower `lo95` (Sum).
- Title "Tested scenarios with 95% intervals (all include zero)".

**C3 plain language:** Card with `Scenario Sentence`, callout size 11, wrap on. H 118, W 856, X 400, Y 578. Add a small amber text box "MODEL PROJECTION, NOT DATA" at the top of the card.

---

## Part F. Finishing and export

1. Click every page in reading mode (Ctrl+click on the menu) and check that nothing is cut off.
2. Save. **File > Export > Export to PDF** → rename `Data Product.pdf`.
3. Screenshot each page (Windows + Shift + S). Home = report Figure 11.
4. Write `README.txt`: purpose, pages, data sources, how to refresh (run scripts 01 to 07, then Power BI > Refresh), and this line: "Page backgrounds (menu bar and card layout) were designed by the team as PNG images; all visuals are live Power BI visuals."
5. Zip `FOREFRONT_Datathon2026_dashboard.zip`: `Data Product.pdf`, the `.pbix`, the `powerbi_*.csv` files and `README.txt`.
