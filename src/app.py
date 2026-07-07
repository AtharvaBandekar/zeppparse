import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import date

# Paths
PROCESSED_DIR = Path("data/processed")
SAMPLE_DIR = Path("output/sample")

# Page config
st.set_page_config(page_title="Baseline", layout="centered")

# Data Loader
@st.cache_data
def load_data() -> tuple[pd.DataFrame, bool]:
    real_path = PROCESSED_DIR / "baseline_output.parquet"
    sample_path = SAMPLE_DIR / "baseline_output_sample.parquet"
    if real_path.exists():
        return pd.read_parquet(real_path), False
    elif sample_path.exists():
        return pd.read_parquet(sample_path), True
    else:
        return None, True

# Load data
df, is_sample = load_data()

st.title("Baseline")
st.caption("Deterministic physiological readiness scoring from wearable data.")

if df is None:
    st.error("No data found. Run ingest.py and features.py first, or add sample data to output/sample/.")
    st.stop()

if is_sample:
    st.warning("Demo mode — showing sample data. Run the pipeline on your own Zepp export to see real scores.")

df["local_date"] = pd.to_datetime(df["local_date"])

# Latest Readiness
latest = df[df["readiness_score"] > 0].iloc[-1]
days_stale = (date.today() - pd.Timestamp(latest["local_date"]).date()).days

st.divider()

if not is_sample and days_stale > 2:
    st.warning(f"⚠ Data is {days_stale} days old — re-export from Zepp for an accurate score.")

# Readiness score
score = int(latest["readiness_score"])
if score >= 8:
    color = "green"
elif score >= 5:
    color = "orange"
else:
    color = "red"

st.markdown(f"## Readiness: <span style='color:{color}'>{score}/10</span>", unsafe_allow_html=True)

# Metrics
col1, col2, col3 = st.columns(3)
col1.metric("Resting HR", f"{latest['resting_hr']:.0f} bpm",
            delta=f"{latest['resting_hr'] - latest['resting_hr_7d_mean']:.1f} vs 7d mean",
            delta_color="inverse")
col2.metric("Sleep", f"{latest['total_sleep_min']:.0f} min",
            delta=f"{latest['total_sleep_min'] - latest['total_sleep_7d_mean']:.0f} vs 7d mean")
col3.metric("Steps", f"{latest['daily_steps']:,.0f}",
            delta=f"{latest['daily_steps'] - latest['daily_steps_7d_mean']:,.0f} vs 7d mean")

st.markdown(f"**Recovery:** {latest['recovery_state'].upper()} &nbsp;&nbsp; **Strain:** {latest['strain_state'].upper()}")

st.divider()

# 14-day trend
st.subheader("14-day Readiness Trend")
chart_data = df[df["readiness_score"] > 0].tail(14)[["local_date", "readiness_score"]].set_index("local_date")
st.line_chart(chart_data)

st.caption("RHR flagged as elevated only when >5 bpm above 7-day mean. Sleep flagged when >1.5 SD below 7-day mean.")