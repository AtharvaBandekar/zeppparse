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