# ZeppParse

Deterministic ETL pipeline for Amazfit/Zepp wearable data. Parses raw HR, sleep, and activity exports into normalized, timezone-correct Parquet files, then computes daily physiological features with rolling personal baselines.

No predictive models. No black-box scoring. Every output is a direct, inspectable computation on your own historical data.

## What it does

- Parses HEARTRATE_AUTO, SLEEP, ACTIVITY_MINUTE, and ACTIVITY_STAGE exports from Zepp
- Normalizes all timestamps to local time using a configurable timezone-by-date-range map (handles travel across timezones correctly)
- Computes daily resting HR (5th percentile, midnight-6am window) with 7-day and 28-day rolling baselines
- Computes sleep duration and efficiency with 7-day rolling baselines
- Computes daily step totals with 7-day rolling baselines
- Joins everything into a single daily summary, flagging unreliable days (low steps, low sleep, missing HR) so they don't corrupt baseline calculations

## Pipeline

```
data/raw/*.csv -> src/ingest.py -> data/processed/*.parquet -> src/features.py -> data/processed/daily_summary.parquet
```

## Setup

```bash
conda create -n zeppparse python=3.13
conda activate zeppparse
pip install pandas pyarrow
```

## Usage

1. Export HEARTRATE_AUTO, SLEEP, ACTIVITY_MINUTE, ACTIVITY_STAGE CSVs from the Zepp app
2. Place them in their respective `data/raw/<STREAM>/` directories
3. Update the `TIMEZONE_PERIODS` list in `src/ingest.py` to reflect your travel history
4. Run:

```bash
python src/ingest.py
python src/features.py
```

5. Output: `data/processed/daily_summary.parquet` - one row per day, with resting HR, sleep, and activity features plus rolling baselines

## Baseline: Readiness Scoring

Baseline reads from ZeppParse's processed output and applies deterministic classifiers to produce a daily readiness score (1–10).

**Classifiers:**

- Recovery state: resting HR and sleep deviation from personal 7-day baseline
- Strain state: daily steps deviation from personal 7-day baseline
- Readiness score: weighted composite of recovery and strain states

**Run the full pipeline:**

```bash
python src/ingest.py
python src/features.py
python src/baseline.py
```

**Launch the Streamlit app:**

```bash
streamlit run src/app.py
```

The app runs in demo mode if no processed data is found, using a synthetic 14-day sample that demonstrates all classifier states.

See `docs/methods.md` for threshold logic, citations, and limitations.

## Sample output

See `output/sample/daily_summary_sample.csv` for an anonymized 14-day sample of the daily summary schema.

## Known limitations

- Sleep efficiency is computed from Zepp's reported sleep onset/wake timestamps, not true time-in-bed - values run higher than clinical sleep efficiency norms and should be interpreted as relative to your own baseline, not compared to population benchmarks
- Body fat and body circumference exports are intentionally excluded - wrist-worn bioimpedance estimates are not reliable enough to build deterministic logic on
- Timezone handling requires manually maintaining the `TIMEZONE_PERIODS` map; it does not auto-detect travel from the data

## Updating your data

1. Open Zepp → Profile → My Data → Export each stream
2. Replace files in data/raw/`<STREAM>`/
3. For new workouts, export TCX individually → data/raw/workouts/
4. Run:
   python src/ingest.py
   python src/features.py
   python src/baseline.py
