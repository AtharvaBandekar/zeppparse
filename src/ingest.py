# Imports
import pandas as pd
from zoneinfo import ZoneInfo
from pathlib import Path

# Timezone Map
TIMEZONE_PERIODS = [
    ("2026-02-20", "2026-05-01", "America/New_York"),
    ("2026-05-02", "2026-05-31", "Asia/Dubai"),
    ("2026-06-01", None,         "America/New_York"),
]

def get_timezone(date_str: str) -> ZoneInfo:
    """Return the local timezone for a given date string (YYYY-MM-DD)."""
    for start, end, tz in TIMEZONE_PERIODS:
        if date_str >= start and (end is None or date_str <= end):
            return ZoneInfo(tz)
    raise ValueError(f"No timezone defined for date: {date_str}")

# Paths
RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
HR_FILE = RAW_DIR / "HEARTRATE_AUTO" / "HEARTRATE_AUTO_1780695191057.csv"
SLEEP_FILE = RAW_DIR / "SLEEP" / "SLEEP_1780695190291.csv"
ACTIVITY_MINUTE_FILE = RAW_DIR / "ACTIVITY_MINUTE" / "ACTIVITY_MINUTE_1780695190225.csv"
ACTIVITY_STAGE_FILE = RAW_DIR / "ACTIVITY_STAGE" / "ACTIVITY_STAGE_1780695190155.csv"

# HR Parser
def parse_hr(filepath: Path) -> pd.DataFrame:
    """Parse HEARTRATE_AUTO CSV into standardized format."""
    df = pd.read_csv(filepath)
    
    # Combine date and time into a single local timestamp
    df["local_timestamp"] = pd.to_datetime(df["date"] + " " + df["time"])
    
    # Assign timezone and derive local_date
    df["timezone"] = df["date"].apply(lambda d: str(get_timezone(d)))
    df["local_date"] = df["local_timestamp"].dt.date
    
    # Drop original columns, reorder
    df = df.drop(columns=["date", "time"])
    df = df[["local_timestamp", "local_date", "timezone", "heartRate"]]
    df = df.rename(columns={"heartRate": "heart_rate"})
    
    # Deduplicate
    df = df.drop_duplicates(subset=["local_timestamp"])
    
    return df.sort_values("local_timestamp").reset_index(drop=True)

# Sleep Parser
def parse_sleep(filepath: Path) -> pd.DataFrame:
    """Parse SLEEP CSV into standardized format."""
    df = pd.read_csv(filepath, usecols=["date", "deepSleepTime", "shallowSleepTime", "wakeTime", "start", "stop", "REMTime"])

    # Convert UTC timestamps to local time
    df["start_utc"] = pd.to_datetime(df["start"], utc=True)
    df["stop_utc"] = pd.to_datetime(df["stop"], utc=True)

    # Assign timezone based on date column
    df["timezone"] = df["date"].apply(lambda d: str(get_timezone(d)))

    # Convert to local time
    df["start_local"] = df.apply(
        lambda r: r["start_utc"].astimezone(ZoneInfo(r["timezone"])), axis=1
    )
    df["stop_local"] = df.apply(
        lambda r: r["stop_utc"].astimezone(ZoneInfo(r["timezone"])), axis=1
    )

    # Use date column as local_date
    df["local_date"] = pd.to_datetime(df["date"]).dt.date

    # Rename sleep stage columns
    df = df.rename(columns={
        "deepSleepTime": "deep_sleep_min",
        "shallowSleepTime": "shallow_sleep_min",
        "wakeTime": "wake_min",
        "REMTime": "rem_sleep_min"
    })

    # Total sleep duration in minutes
    df["total_sleep_min"] = (
        df["deep_sleep_min"] + df["shallow_sleep_min"] + df["rem_sleep_min"]
    )

    df = df[[
        "local_date", "timezone",
        "start_local", "stop_local",
        "deep_sleep_min", "shallow_sleep_min",
        "rem_sleep_min", "wake_min",
        "total_sleep_min"
    ]]

    return df.sort_values("local_date").reset_index(drop=True)

# Activity Minute Parser
def parse_activity_minute(filepath: Path) -> pd.DataFrame:
    """Parse ACTIVITY_MINUTE CSV into standardized format."""
    df = pd.read_csv(filepath)

    # Combine date and time into local timestamp
    df["local_timestamp"] = pd.to_datetime(df["date"] + " " + df["time"])

    # Assign timezone and local date
    df["timezone"] = df["date"].apply(lambda d: str(get_timezone(d)))
    df["local_date"] = df["local_timestamp"].dt.date

    df = df.drop(columns=["date", "time"])
    df = df[["local_timestamp", "local_date", "timezone", "steps"]]

    # Deduplicate
    df = df.drop_duplicates(subset=["local_timestamp"])

    return df.sort_values("local_timestamp").reset_index(drop=True)

# Activity Stage Parser
def parse_activity_stage(filepath: Path) -> pd.DataFrame:
    """Parse ACTIVITY_STAGE CSV into standardized format."""
    df = pd.read_csv(filepath)

    # Combine date and start time into local timestamp
    df["start_local"] = pd.to_datetime(df["date"] + " " + df["start"])
    df["stop_local"] = pd.to_datetime(df["date"] + " " + df["stop"])

    # Assign timezone and local date
    df["timezone"] = df["date"].apply(lambda d: str(get_timezone(d)))
    df["local_date"] = pd.to_datetime(df["date"]).dt.date

    df = df.drop(columns=["date", "start", "stop"])
    df = df[["local_date", "timezone", "start_local", "stop_local",
             "distance", "calories", "steps"]]

    return df.sort_values("start_local").reset_index(drop=True)

# Write to Parquet
def save_all(hr, sleep, activity_min, activity_stage):
    """Write all parsed dataframes to processed directory."""
    hr.to_parquet(PROCESSED_DIR / "hr.parquet", index=False)
    sleep.to_parquet(PROCESSED_DIR / "sleep.parquet", index=False)
    activity_min.to_parquet(PROCESSED_DIR / "activity_minute.parquet", index=False)
    activity_stage.to_parquet(PROCESSED_DIR / "activity_stage.parquet", index=False)
    print("\n── Saved to data/processed/ ─────────")
    print(f"  hr.parquet              {hr.shape[0]} rows")
    print(f"  sleep.parquet           {sleep.shape[0]} rows")
    print(f"  activity_minute.parquet {activity_min.shape[0]} rows")
    print(f"  activity_stage.parquet  {activity_stage.shape[0]} rows")

# Execution Block
if __name__ == "__main__":
    hr = parse_hr(HR_FILE)
    print("── HR ───────────────────────────────")
    print(hr.head(5))
    print(f"Shape: {hr.shape}")
    print(f"Date range: {hr['local_date'].min()} → {hr['local_date'].max()}")
    print(f"Missing HR values: {hr['heart_rate'].isna().sum()}")

    print("\n── Sleep ────────────────────────────")
    sleep = parse_sleep(SLEEP_FILE)
    print(sleep.head(5))
    print(f"Shape: {sleep.shape}")
    print(f"Date range: {sleep['local_date'].min()} → {sleep['local_date'].max()}")
    print(f"Missing total sleep: {sleep['total_sleep_min'].isna().sum()}")

    print("\n── Activity Minute ──────────────────")
    activity_min = parse_activity_minute(ACTIVITY_MINUTE_FILE)
    print(activity_min.head(5))
    print(f"Shape: {activity_min.shape}")
    print(f"Date range: {activity_min['local_date'].min()} → {activity_min['local_date'].max()}")
    print(f"Missing steps: {activity_min['steps'].isna().sum()}")

    print("\n── Activity Stage ───────────────────")
    activity_stage = parse_activity_stage(ACTIVITY_STAGE_FILE)
    print(activity_stage.head(5))
    print(f"Shape: {activity_stage.shape}")
    print(f"Date range: {activity_stage['local_date'].min()} → {activity_stage['local_date'].max()}")
    print(f"Missing calories: {activity_stage['calories'].isna().sum()}")

    save_all(hr, sleep, activity_min, activity_stage)

