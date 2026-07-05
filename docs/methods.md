# Baseline: Methods Note

## Overview

Baseline is a deterministic physiological state classifier that produces a daily readiness score from consumer wearable data. It operates exclusively on intra-individual deviation logic — every threshold is derived from the user's own historical baseline, not population norms. No machine learning is used at any stage. Every output is fully back-calculable from the raw input values.

---

## Signal Selection

### Resting Heart Rate

Resting heart rate (RHR) was selected as the primary recovery signal. It is computed as the 5th percentile of minute-level heart rate readings recorded between 00:00 and 06:00 local time — a window that captures true physiological rest, minimizing confounding from postural changes, meal timing, and physical activity.

RHR is a validated marker of autonomic nervous system state. Pichot et al. (2000) demonstrated that nocturnal heart rate increased progressively under accumulated training load in middle-distance runners, reaching statistical significance at week 3, and decreased significantly during a subsequent recovery week. Buchheit (2014) established RHR monitoring as a practical, low-cost tool for tracking training status when beat-to-beat HRV data is unavailable.

### Heart Rate Variability — Excluded

HRV (specifically RMSSD) was not included despite being the superior autonomic recovery marker. The Amazfit Helio exports heart rate as a per-minute average, which destroys the beat-to-beat interval information required to compute RMSSD. A per-minute BPM average mathematically represents only the total frequency of heartbeats over a 60-second window, completely lacking the precise millisecond-level temporal spacing between individual beats. Because RMSSD strictly requires calculating the variance between these successive, adjacent beat intervals, attempting to reconstruct it from an aggregated average is mathematically invalid since the required beat-to-beat variation has been permanently erased. RHR was retained as the best available signal given the data constraints.

### Sleep

Total sleep duration and sleep efficiency were included as secondary signals. Training load and match schedule have been shown to negatively correlate with sleep duration in high-level athletes (Costa et al., 2021, Front Physiol). Sleep efficiency was computed as total sleep time divided by time in bed, derived from Zepp's reported sleep onset and wake timestamps. Note: consumer wearable sleep efficiency values run systematically higher than clinical polysomnography norms and should be interpreted relative to personal baseline only.

### Activity (Strain)

Daily step count from minute-level activity data was used as a proxy for physical strain load. Steps were chosen over distance or calories due to lower sensor uncertainty. Strain is classified relative to the user's own 7-day rolling baseline.

---

## Threshold Logic

### Deviation-Based Classification

All classifiers use intra-individual deviation thresholds rather than population-derived cutoffs. The primary threshold is 1.5 standard deviations from the personal 7-day rolling mean, consistent with the individualized baseline methodology described in Buchheit (2014).

### Hybrid RHR Threshold

Pure SD-based thresholds for RHR were found to be insufficiently sensitive during periods following anomalous events. A single RHR spike inflates the rolling standard deviation, widening the detection threshold and reducing sensitivity to subsequent elevations — a structural flaw in SD-only approaches on small personal datasets.

A hybrid threshold was implemented: RHR is flagged as elevated if it exceeds the 7-day mean by either 1.5 × 28-day rolling SD (stable long-term variance estimate) or a hard absolute floor of 5 bpm above the 7-day mean, whichever is lower. The 5 bpm floor is grounded in Pichot et al. (2000), who observed nocturnal HR increases of 3.74 bpm reaching statistical significance under accumulated load — establishing 5 bpm above personal recent mean as a physiologically meaningful deviation threshold.

---

## Readiness Score

The readiness score is an integer from 1 to 10 computed from weighted rule-based logic:

| Signal     | Weight | Deduction condition                      |
| ---------- | ------ | ---------------------------------------- |
| Resting HR | 4      | Elevated above hybrid threshold          |
| Sleep      | 4      | Total sleep below 7d mean by 1.5 × 7d SD |
| Strain     | 2      | Daily steps above 7d mean by 1.5 × 7d SD |

RHR and sleep carry equal weight (4 points each) because both reflect autonomic recovery state directly. Strain carries lower weight (2 points) because it reflects prior load rather than current recovery, and its relationship to next-day readiness is less immediate. A low-strain day adds 1 point as an active rest signal.

---

## Limitations

**N=1 validation.** This system has been developed and validated on a single individual's data. The threshold logic has not been tested across populations, age groups, fitness levels, or device types. Findings cannot be generalized.

**Consumer wearable accuracy.** Amazfit Helio HR data is derived from photoplethysmography (PPG), which is subject to motion artifact, skin tone variation, and sensor fit. Minute-level HR averages are less precise than ECG-derived measurements. All downstream computations inherit this uncertainty.

**No HRV.** The absence of RMSSD data is the single largest signal gap in this system. RHR is a weaker and less sensitive autonomic marker than HRV. Users with access to beat-to-beat interval data should extend this system accordingly.

**Manual export dependency.** Data must be manually exported from the Zepp application. There is no automated sync pipeline. Stale data will produce misleading readiness scores; the CLI issues a warning when the latest data point is more than 2 days old.

---

## References

- Pichot V, Roche F, Gaspoz JM, et al. Relation between heart rate variability and training load in middle-distance runners. _Med Sci Sports Exerc._ 2000;32(9):1729–1736.
- Buchheit M. Monitoring training status with HR measures: do all roads lead to Rome? _Front Physiol._ 2014;5:73.
- Costa JA, Figueiredo P, Nakamura FY, Rebelo A, Brito J. Monitoring individual sleep and nocturnal heart rate variability indices: the impact of training and match schedule and load in high-level female soccer players. _Front Physiol._ 2021;12:678462.
