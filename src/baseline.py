import pandas as pd
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
PROCESSED_DIR = Path("data/processed")

# ── Thresholds ────────────────────────────────────────────────────────────────
# Deviation threshold: 1.5 SD from personal 7-day rolling mean
# Grounded in intra-individual baseline methodology per:
# Pichot et al. (2000) Med Sci Sports Exerc 32:1729-1736
# Buchheit (2014) Front Physiol 5:73
SD_THRESHOLD = 1.5
RHR_HARD_FLOOR_BPM = 5

# Readiness score weights (must sum to 10)
WEIGHT_RHR    = 4   # strongest available signal without HRV
WEIGHT_SLEEP  = 4   # sleep duration + efficiency composite
WEIGHT_STRAIN = 2   # activity load, lower weight — lags recovery signal

# ── Loader ────────────────────────────────────────────────────────────────────
def load_summary() -> pd.DataFrame:
    df = pd.read_parquet(PROCESSED_DIR / "daily_summary.parquet")
    df["local_date"] = pd.to_datetime(df["local_date"])
    return df

# ── Recovery State Classifier ─────────────────────────────────────────────────
def classify_recovery(row: pd.Series) -> dict:
    """
    Classify recovery state from resting HR and sleep signals.
    Deviation logic per Pichot et al. (2000) and Buchheit (2014):
    flag when today's value exceeds personal 7-day mean by SD_THRESHOLD SDs.
    Returns individual signal flags and composite recovery state.
    """
    result = {
        "rhr_elevated": False,
        "sleep_degraded": False,
        "recovery_state": "normal"
    }

    # Skip unreliable days entirely
    if row["unreliable"]:
        result["recovery_state"] = "unreliable"
        return result

    # RHR flag — elevated means above baseline by SD_THRESHOLD SDs
    if pd.notna(row["resting_hr_7d_mean"]) and pd.notna(row["resting_hr_28d_std"]):
        rhr_upper_sd = row["resting_hr_7d_mean"] + SD_THRESHOLD * row["resting_hr_28d_std"]
        rhr_upper_hard = row["resting_hr_7d_mean"] + RHR_HARD_FLOOR_BPM
        if row["resting_hr"] > rhr_upper_sd or row["resting_hr"] > rhr_upper_hard:
            result["rhr_elevated"] = True

    # Sleep flag — degraded means below baseline by SD_THRESHOLD SDs
    if pd.notna(row["total_sleep_7d_mean"]) and pd.notna(row["total_sleep_7d_std"]):
        sleep_lower = row["total_sleep_7d_mean"] - SD_THRESHOLD * row["total_sleep_7d_std"]
        if row["total_sleep_min"] < sleep_lower:
            result["sleep_degraded"] = True

    # Composite recovery state
    if result["rhr_elevated"] and result["sleep_degraded"]:
        result["recovery_state"] = "poor"
    elif result["rhr_elevated"] or result["sleep_degraded"]:
        result["recovery_state"] = "reduced"
    else:
        result["recovery_state"] = "normal"

    return result


# ── Strain State Classifier ───────────────────────────────────────────────────
def classify_strain(row: pd.Series) -> dict:
    """
    Classify strain state from daily steps relative to personal baseline.
    High strain = steps exceed 7-day mean by SD_THRESHOLD SDs.
    Low strain = steps below 7-day mean by SD_THRESHOLD SDs.
    """
    result = {"strain_state": "normal"}

    if row["unreliable"]:
        result["strain_state"] = "unreliable"
        return result

    if pd.notna(row["daily_steps_7d_mean"]) and pd.notna(row["daily_steps_7d_std"]):
        upper = row["daily_steps_7d_mean"] + SD_THRESHOLD * row["daily_steps_7d_std"]
        lower = row["daily_steps_7d_mean"] - SD_THRESHOLD * row["daily_steps_7d_std"]

        if row["daily_steps"] > upper:
            result["strain_state"] = "high"
        elif row["daily_steps"] < lower:
            result["strain_state"] = "low"

    return result


# ── Readiness Score ───────────────────────────────────────────────────────────
def compute_readiness_score(recovery: dict, strain: dict) -> int:
    """
    Compute integer readiness score 1-10 from recovery and strain states.
    Weights: RHR=4, Sleep=4, Strain=2. Fully inspectable rule-based logic.
    No model. No inference. Every deduction is explicitly documented.
    """
    if recovery["recovery_state"] == "unreliable":
        return -1  # sentinel value — not a real score

    score = 10

    # RHR component (max deduction: 4)
    if recovery["rhr_elevated"]:
        score -= 4

    # Sleep component (max deduction: 4)
    if recovery["sleep_degraded"]:
        score -= 4

    # Strain component (max deduction: 2)
    # High prior strain reduces readiness; low strain is neutral or positive
    if strain["strain_state"] == "high":
        score -= 2
    elif strain["strain_state"] == "low":
        score += 1  # low strain slightly boosts readiness — active rest

    return max(1, min(10, score))  # clamp to 1-10

if __name__ == "__main__":
    summary = load_summary()

    # Apply classifiers row by row
    recovery_results = summary.apply(classify_recovery, axis=1, result_type="expand")
    strain_results = summary.apply(classify_strain, axis=1, result_type="expand")

    summary = pd.concat([summary, recovery_results, strain_results], axis=1)

    # Compute readiness score
    summary["readiness_score"] = summary.apply(
        lambda r: compute_readiness_score(
            {"rhr_elevated": r["rhr_elevated"],
             "sleep_degraded": r["sleep_degraded"],
             "recovery_state": r["recovery_state"]},
            {"strain_state": r["strain_state"]}
        ), axis=1
    )
    
    # Save classifier output
    output_cols = [
        "local_date", "resting_hr", "resting_hr_7d_mean",
        "total_sleep_min", "total_sleep_7d_mean",
        "daily_steps", "daily_steps_7d_mean",
        "recovery_state", "strain_state", "readiness_score", "unreliable"
    ]
    output = summary[output_cols]
    output.to_parquet(PROCESSED_DIR / "baseline_output.parquet", index=False)
    print(f"Saved baseline_output.parquet ({output.shape[0]} rows)")

    # Today's readiness — the actual user-facing output
    today = output[output["readiness_score"] > 0].iloc[-1]
    from datetime import date
    latest_date = today['local_date'].date()
    days_stale = (date.today() - latest_date).days

    print("\n── Latest Readiness ─────────────────")
    if days_stale > 2:
        print(f"  ⚠ Data is {days_stale} days old — re-export from Zepp before trusting this score")
    print(f"  Date:            {latest_date}")
    print(f"  Resting HR:      {today['resting_hr']:.0f} bpm (7d mean: {today['resting_hr_7d_mean']:.1f})")
    print(f"  Sleep:           {today['total_sleep_min']:.0f} min (7d mean: {today['total_sleep_7d_mean']:.1f})")
    print(f"  Steps yesterday: {today['daily_steps']:.0f} (7d mean: {today['daily_steps_7d_mean']:.1f})")
    print(f"  Recovery state:  {today['recovery_state'].upper()}")
    print(f"  Strain state:    {today['strain_state'].upper()}")
    print(f"  Readiness score: {today['readiness_score']}/10")

