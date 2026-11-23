# M-ECON Power BI build guide

Website-style dashboard: dark top menu, white rounded cards, teal (GDP), coral (inflation), amber and violet highlights, red/green alerts.

Files in this folder:
- `MECON_theme.json`: colours, fonts, card and table styles
- `backgrounds/bg_*.png`: one page background each (menu bar, cards, shadows already drawn)
- `previews/preview_*.png`: the same layout with every card labelled and its X, Y, W, H
- `MECON_measures.dax`: all measures and helper tables, ready to paste

Rule for every visual: **turn off its background and border** (the theme already does this), then set **X, Y, W, H** from the preview image (Format > General > Properties > Size and position). The visual then sits exactly inside its white card.

---

## Step 0. Prepare data (once)

1. Run `python scripts/07_powerbi_extras.py`. It adds 9 small CSV files to `outputs/`.
2. You now have 19 `powerbi_*.csv` files in `outputs/`.

## Step 1. New report, page size, theme

1. Power BI Desktop > Blank report. Save as `FOREFRONT_Datathon2026_dashboard.pbix`.
2. View > Themes > Browse for themes > `MECON_theme.json`.
3. Format page (click empty canvas) > Canvas settings: Type **16:9**, 1280 x 720. Vertical alignment **Top**.

## Step 2. Load the data

Home > Get data > Text/CSV, load each file, then **rename the table** (double-click in the Data pane):

| File | Table name |
|---|---|
| powerbi_monthly.csv | Monthly |
| powerbi_quarterly.csv | Quarterly |
| powerbi_variables.csv | Variables |
| powerbi_forecasts.csv | Forecasts |
| powerbi_predictions.csv | Predictions |
| powerbi_model_results.csv | ModelResults |
| powerbi_fan.csv | Fan |
| powerbi_importance.csv | Importance |
| powerbi_corr.csv | Corr |
| powerbi_top_predictors.csv | TopPredictors |
| powerbi_early_warning.csv | EarlyWarning |
| powerbi_ew_indicators.csv | EWIndicators |
| powerbi_ew_status.csv | EWStatus |
| powerbi_backtest.csv | Backtest |
| powerbi_events.csv | Events |
| powerbi_scenarios.csv | Scenarios |
| powerbi_scenario_slider.csv | ScenarioSlider |
| powerbi_state_inflation.csv | StateInflation |
| powerbi_mpc_tone.csv | MPCTone |

Checks in Power Query (Transform data) before Close & Apply:
- Every `date`, `origin`, `forecast_for`, `target_date`, `as_of` column = **Date** type.
- `Forecasts[selected]` = **True/False**.
- `EWIndicators[flag]`: blanks must stay blank (do not replace with 0).

## Step 3. Model

1. Home > Enter data > leave empty, name it `_Measures`. All measures go here.
2. Modeling > New table: paste **Calendar**, **Brent Shock**, **Ringgit Shock** from `MECON_measures.dax`.
3. Calendar: Table tools > Mark as date table > Date.
4. Model view, drag to create relationships (single direction, Calendar on the 1 side):
   - Calendar[Date] → Monthly[date], Quarterly[date], Events[date], MPCTone[date], EarlyWarning[date], EWIndicators[date], StateInflation[date]
   - Variables[variable] → Monthly[variable], Quarterly[variable]
5. Modeling > New measure: paste every measure from `MECON_measures.dax` (one at a time, select `_Measures` as home table).
6. Hide helper columns you will not use (right-click > Hide in report view) to keep the field list clean.

## Step 4. Six pages and the background

1. Create 6 pages, named exactly: **Home, GDP, Inflation, Drivers & States, Early Warning, Scenarios**.
2. On each page: Format page > Canvas background > Image > choose the matching `bg_*.png`, **Image fit: Fit**, **Transparency 0%**.
3. Page header text (all pages except Home): Insert > Text box at X 44, Y 88, W 400, H 34, page name in Segoe UI Bold 16, colour #1B2A41.

## Step 5. Top menu (on every page)

1. Insert > Buttons > Navigator > **Page navigator**. Position X 456, Y 14, W 800, H 36.
2. Format > Style:
   - Default: fill #0B1F3A, text #BEC8D7, Segoe UI 10, no border, shape **Pill**.
   - Hover: fill #16365F, text white.
   - Selected: fill #00A6A6, text white, bold.
3. Text box "M-ECON" at X 64, Y 18, W 160, H 30: white, Segoe UI Bold 16.
4. Copy the navigator and the M-ECON text box, then paste them on every page (Ctrl+C, Ctrl+V keeps the position).

## Step 6. KPI cards (the coloured-bar cards)

Use **Card (new)** visual for every KPI box. Settings:
- Callout value: measure (for example `GDP Forecast Text`), Segoe UI Semibold 28, colour = the card accent.
- Reference label: a subtitle measure (for example `GDP Subtitle`), font 9, colour #6B7A90.
- Category label: on, as the card title, font 10, #6B7A90.
- Card background and border: off. Turn off the visual header.

Status colours: Callout value > Color > fx > Format style **Field value** > the colour measure (for example `Cost Status Colour`). The card turns red when ON and green when OFF.

---

## Page 1. Home

Hero text (inside the dark band): text box X 48, Y 82, W 700, H 70.
- Line 1: "Malaysia Economic Pulse" white, Segoe UI Bold 20
- Line 2: "GDP and inflation forecasts, early warning and scenarios from official data" #C8E1E6, size 10.

| Card | Visual | Fields |
|---|---|---|
| K1 | Card (new) | Value `GDP Forecast Text`, reference `GDP Change Text`, label "GDP growth, " & period (use `GDP Forecast Period`) |
| K2 | Card (new) | Value `Inflation Forecast Text`, reference `Inside BNM Range` |
| K3 | Card (new) | Value `Cost Status`, colour `Cost Status Colour`, reference `Cost Detail` |
| K4 | Card (new) | Value `Growth Status`, colour `Growth Status Colour`, reference `Growth Detail` |
| C1 | Line and clustered column chart | X `Calendar[Date]` (Year > Quarter levels), Lines: `GDP Growth` (teal), `CPI Inflation Q` (coral); Columns: `Event Marker` (amber, 40% transparency); Tooltip: `Event Names`. Title "GDP growth and inflation, 2011 to 2026". Add a **slicer** for Calendar[Date] (Between style) inside the card at the bottom. |
| C2 | Table | `EWIndicators[signal]`, `EWIndicators[indicator]`, `Indicator Status`, `Indicator Month`. Conditional formatting > Font colour for `Indicator Status` = field value `Indicator Status Colour`. Title "Early-warning indicators" |
| C3 | Column chart | X `MPCTone[date]`, Y `MPCTone[tone_rel]`, column colour fx = `Tone Bar Colour`. Title from `Tone Subtitle` (Title > fx). Filter visual: date after 1 Jan 2022 |

Interaction: click K3 or K4 → go to Early Warning. Select the card > Format > Action: On, Type **Page navigation**, Destination Early Warning. Same for K1 → GDP, K2 → Inflation.

## Page 2. GDP

Header slicers (X 900, Y 86, W 340, H 38): **Tile slicer** on `Predictions[model]`, single select, filter the page to `Predictions[setup] = A2` (Filters pane > this page).

| Card | Visual | Fields |
|---|---|---|
| K1 | Card (new) | `GDP Forecast Text`, reference `GDP Forecast Period` |
| K2 | Card (new) | `GDP Range 80`, reference "95% range 4.3% to 8.7%" (text) |
| K3 | Card (new) | `GDP Model MAE` (format 0.00 "pp"), reference `GDP Model` |
| K4 | Card (new) | `GDP Gain Text`, reference "Target: at least 10% better than naive ✔" |
| C1 (view 1) | Line chart | X `Predictions[target_date]`, Y `Predictions[actual]` (navy, 3 px) and `Predictions[forecast]` (teal, markers on). Title fx = `Test Chart Title` |
| C1 (view 2) | Line chart | Table Fan, filter setup = A2. X `Fan[date]`, Y `actual` (navy) and `forecast` (teal, dashed). Analytics > Error bars on `forecast`: upper `hi80`, lower `lo80`, style **Band**, teal 80% transparency |
| C2 | Bar chart | Y `ModelResults[model]`, X `ModelResults[MAE]`, filter setup = A2, sort ascending. Bars fx = `Model Bar Colour`. Analytics: constant line at the Naive MAE 1.69, label "Naive" |
| C3 | Bar chart | Y `Importance[input]`, X `Importance[rf_permutation_importance]`, filter setup = A2, Top N 8 by value. Colour teal |

**Toggle between view 1 and view 2 (bookmarks):**
1. Place both C1 charts in the same position. View > Selection pane, Bookmarks pane.
2. Hide view 2, add bookmark "GDP test" (Data off, Display on, Current page). Hide view 1, show view 2, add bookmark "GDP forecast".
3. Insert > Buttons > Navigator > **Bookmark navigator** (only these two bookmarks; make a group in Bookmarks pane) at X 600, Y 270, W 220, H 28. Selected = teal, default = #EEF2F8.

## Page 3. Inflation

Copy the GDP page (right-click tab > Duplicate) and change:
- Page filter `Predictions[setup] = B`, `Fan[setup] = B`, `ModelResults[setup] = B`.
- K1 `Inflation Forecast Text`, K2 `Inflation Range 80`, K3 `Inflation Model MAE` (0.000 "pp"), K4 `Latest PPI CPI Gap Text` with label "Producer minus consumer prices".
- Colours: coral instead of teal.
- C2: Line chart, X `Calendar[Date]` (Month), `PPI Inflation` (amber) and `CPI Inflation` (coral). Title "Producer prices lead consumer prices".
- C3: Line chart, X `Calendar[Date]` (Month), `RON95 Price`, `RON95 BUDI95 Price`, `Diesel Price`; Columns `Event Marker` with tooltip `Event Names` (Line and clustered column chart). Filter date from 2017.

## Page 4. Drivers & States

| Card | Visual | Fields |
|---|---|---|
| C1 | **Azure map** (or Map) | Latitude `StateInflation[lat]`, Longitude `[lon]`, Size `State CPI Latest`, Legend none, Tooltips `state`, `State CPI Latest`, `State Food Latest`, `State Transport Latest`. Bubble colour: fx gradient teal (low) to coral (high). Title "Inflation by state, latest month" |
| C2 | Matrix | Rows `Corr[label]`, Columns `Corr[lag_label]`, Values `Corr[pearson_r]` (Average, 2 decimals). Filter `Corr[sample] = ex-COVID`. Background colour fx: Gradient, min -1 teal #00A6A6, center 0 white, max 1 coral #FF6B4A. Tile slicer `Corr[target]` above it (X 1060, Y 150, W 190, H 28) |
| C3 | Line and clustered column chart | X `MPCTone[date]`, Columns `MPCTone[tone_rel]` (colour fx `Tone Bar Colour`), Line `MPCTone[opr]` (navy, secondary axis). Title "BNM statement tone (bars) and the OPR (line)" |

Map tip: if the map is blank, File > Options > Security > tick "Use Map and Filled Map visuals".

State tooltip page (hover effect):
1. New page "State tip", Page information > **Allow use as tooltip** on, canvas Tooltip size.
2. Card `state` (first), small line chart of `StateInflation[cpi_yoy]` over `date` (coral).
3. On the map: Format > Tooltips > Type **Report page** > State tip. Hide the State tip page.

## Page 5. Early Warning

| Card | Visual | Fields |
|---|---|---|
| K1 | Card (new) | `Cost Status`, colour `Cost Status Colour`, reference `Cost Detail`, label "Cost pressure" |
| K2 | Card (new) | `Growth Status`, colour `Growth Status Colour`, reference `Growth Detail`, label "Growth slowdown" |
| C1 | Table | Same as Home C2 (copy it). Add a tile slicer on `EWIndicators[signal]` |
| C2 | Area chart | X `EarlyWarning[date]`, Y `Cost Count` (coral) and `Growth Count` (violet), 60% transparency. Analytics: constant line at **2**, red dashed, label "Signal ON". Title "How many indicators are flashing (0 to 3)" |
| C3 | Table | `Backtest[episode]`, `signal`, `first_signal`, `lead_time`, `hit`. Conditional icons on `hit` (green tick) |

## Page 6. Scenarios

| Card | Visual | Fields |
|---|---|---|
| C1 | 2 slicers + text | Slicer `'Brent Shock'[Value]` style **Single value slider** at X 44, Y 200, W 320, H 70, header "Oil price shock (%)". Slicer `'Ringgit Shock'[Value]` at X 44, Y 300, W 320, H 70, header "Ringgit weaker by (%)". Text box below: "Drag the sliders. Effects come from the fitted MLR models (Section 4.7 of the report)." |
| K1 | Card (new) | `GDP Effect Text`, colour fx `GDP Effect Colour`, reference `GDP After Shock Text` |
| K2 | Card (new) | `Inflation Effect Text`, colour fx `Inflation Effect Colour`, reference `Inflation After Shock Text` |
| C2 | Clustered bar chart | Y `Scenarios[scenario]`, X `Scenarios[effect_pp]`, Legend `Scenarios[setup]` (A2 teal, B coral). Analytics > Error bars: upper `hi95`, lower `lo95`. Title "Tested scenarios with 95% intervals (all include zero)" |
| C3 | Card (new) or text | `Scenario Sentence`, font 11, wrap on. Add a small amber label text "MODEL PROJECTION, NOT DATA" at the top |

---

## Step 7. Finishing touches (website feel)

- Visual header: off for KPI cards; on for charts (lets judges use Focus mode).
- Consistent titles: 12 pt Segoe UI Semibold, sentence case, no full stop.
- Number formats: one decimal for %, two for pp effects.
- Edit interactions (Format > Edit interactions): on Home, the date slicer filters C1 only.
- Sync slicers: View > Sync slicers, sync the date slicer across Home, Inflation and Drivers & States.
- Mobile layout (optional): View > Mobile layout, place the four Home KPIs and C1.

## Step 8. Export for submission

1. File > Export > **Export to PDF** → rename to `Data Product.pdf`.
2. Screenshot each page (Windows + Shift + S) and send them to Farah for the report (Figure 11 = Home).
3. Zip `FOREFRONT_Datathon2026_dashboard.zip` with: `Data Product.pdf`, the `.pbix`, the `outputs/powerbi_*.csv` files and `README.txt`.
