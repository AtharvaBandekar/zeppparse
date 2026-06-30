import pandas as pd
from pathlib import Path

# Paths
PROCESSED_DIR = Path("data/processed")

# Loaders
def load_all():
    """Load all parquet files and normalize local_date to datetime."""
    hr = pd.read_parquet(PROCESSED_DIR / "hr.parquet")
    sleep = pd.read_parquet(PROCESSED_DIR / "sleep.parquet")
    activity_min = pd.read_parquet(PROCESSED_DIR / "activity_minute.parquet")
    activity_stage = pd.read_parquet(PROCESSED_DIR / "activity_stage.parquet")

    # Normalize local_date to proper datetime across all dataframes
    for df in [hr, sleep, activity_min, activity_stage]:
        df["local_date"] = pd.to_datetime(df["local_date"])

    return hr, sleep, activity_min, activity_stage

# Resting HR
def compute_resting_hr(hr: pd.DataFrame) -> pd.DataFrame:
    """
    Compute daily resting HR as the 5th percentile of HR readings
    between midnight and 6am local time. This window captures true
    resting state — asleep, minimal activity, no food or exercise effect.
    """
    # Isolate overnight window
    overnight = hr[hr["local_timestamp"].dt.hour < 6].copy()

    # 5th percentile per day — more robust than minimum which catches artifacts
    resting = (
        overnight.groupby("local_date")["heart_rate"]
        .quantile(0.05)
        .reset_index()
        .rename(columns={"heart_rate": "resting_hr"})
    )

    # 7-day and 28-day rolling mean and std
    resting = resting.sort_values("local_date")
    resting["resting_hr_7d_mean"] = (
        resting["resting_hr"].rolling(7, min_periods=3).mean()
    )
    resting["resting_hr_7d_std"] = (
        resting["resting_hr"].rolling(7, min_periods=3).std()
    )
    resting["resting_hr_28d_mean"] = (
        resting["resting_hr"].rolling(28, min_periods=14).mean()
    )
    resting["resting_hr_28d_std"] = (
        resting["resting_hr"].rolling(28, min_periods=14).std()
    )

    return resting.reset_index(drop=True)

# Sleep Features
def compute_sleep_features(sleep: pd.DataFrame) -> pd.DataFrame:
    """
    Compute sleep efficiency and rolling baselines.
    Efficiency = total sleep / time in bed as a percentage.
    Time in bed derived from start_local and stop_local.
    """
    df = sleep.copy()

    # Time in bed in minutes
    df["time_in_bed_min"] = (
        (df["stop_local"] - df["start_local"])
        .dt.total_seconds() / 60
    )

    # Sleep efficiency — capped at 100% to handle any edge cases
    df["sleep_efficiency"] = (
        (df["total_sleep_min"] / df["time_in_bed_min"]) * 100
    ).clip(upper=100).round(1)

    # Rolling baselines
    df = df.sort_values("local_date")
    df["total_sleep_7d_mean"] = (
        df["total_sleep_min"].rolling(7, min_periods=3).mean()
    )
    df["sleep_efficiency_7d_mean"] = (
        df["sleep_efficiency"].rolling(7, min_periods=3).mean()
    )

    return df[[
        "local_date", "timezone",
        "total_sleep_min", "time_in_bed_min", "sleep_efficiency",
        "deep_sleep_min", "rem_sleep_min", "wake_min",
        "total_sleep_7d_mean", "sleep_efficiency_7d_mean"
    ]].reset_index(drop=True)

# Daily Steps
def compute_daily_steps(activity_min: pd.DataFrame) -> pd.DataFrame:
    """
    Compute total daily steps and 7-day rolling baseline
    from minute-level activity data.
    """
    df = (
        activity_min.groupby("local_date")["steps"]
        .sum()
        .reset_index()
        .rename(columns={"steps": "daily_steps"})
    )

    df = df.sort_values("local_date")
    df["daily_steps_7d_mean"] = (
        df["daily_steps"].rolling(7, min_periods=3).mean()
    )
    df["daily_steps_7d_std"] = (
        df["daily_steps"].rolling(7, min_periods=3).std()
    )

    return df.reset_index(drop=True)

# Daily Summary
def compute_daily_summary(
    resting_hr: pd.DataFrame,
    sleep_features: pd.DataFrame,
    daily_steps: pd.DataFrame
) -> pd.DataFrame:
    """
    Join all feature streams into one row per day.
    Flag days with unreliable data.
    """
    # Merge on local_date
    df = resting_hr.merge(sleep_features, on="local_date", how="outer")
    df = df.merge(daily_steps, on="local_date", how="outer")

    df = df.sort_values("local_date").reset_index(drop=True)

    # Flag unreliable days
    df["unreliable"] = (
        df["daily_steps"] < 500        # likely unworn day
    ) | (
        df["total_sleep_min"] < 120    # likely tracking failure
    ) | (
        df["resting_hr"].isna()        # no overnight HR data
    )

    return df


if __name__ == "__main__":
    hr, sleep, activity_min, activity_stage = load_all()

    resting_hr = compute_resting_hr(hr)
    sleep_features = compute_sleep_features(sleep)
    daily_steps = compute_daily_steps(activity_min)
    summary = compute_daily_summary(resting_hr, sleep_features, daily_steps)
    summary.to_parquet(PROCESSED_DIR / "daily_summary.parquet", index=False)
    print(f"\nSaved daily_summary.parquet ({summary.shape[0]} rows)")

    print("── Daily Summary ────────────────────")
    print(summary.head(10))
    print(f"\nShape: {summary.shape}")
    print(f"Unreliable days flagged: {summary['unreliable'].sum()}")
    print(f"\nReliable days only:")
    reliable = summary[~summary["unreliable"]]
    print(f"  Mean resting HR:       {reliable['resting_hr'].mean():.1f} bpm")
    print(f"  Mean sleep duration:   {reliable['total_sleep_min'].mean():.0f} min")
    print(f"  Mean daily steps:      {reliable['daily_steps'].mean():.0f}")
