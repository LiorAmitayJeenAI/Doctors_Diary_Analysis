# Data Quality and Edge Cases

## 1. Do not confuse rows with appointments

The largest structural trap is segment duplication. A 20-minute appointment in a 10-minute-segment calendar may appear as two rows.

Always calculate appointment metrics on logical appointments unless the metric is explicitly segment-based.

## 2. דחוף and נדחף are the same appointment

The definition is in `01_DOMAIN_GLOSSARY.md`: דחוף and נדחף are two labels for one inserted appointment.

Do not build separate urgent-demand and pushed-demand metrics. Reconcile the labels into one inserted-appointment population before counting.

## 3. Visit record uncertainty

Stakeholders noted that documentation behavior can sometimes create a visit record that does not perfectly reflect a normal real-world encounter.

Until a validated clinical rule exists:
- treat the supplied visits export as operational truth;
- do not claim certainty beyond the data;
- allow data-quality warnings where visit semantics materially affect a recommendation.

## 4. Snapshot vs event history

A current calendar export may not preserve all canceled appointments or prior states.

Therefore:
- do not infer historical cancellation rate from a snapshot unless cancellation history exists;
- distinguish "currently free" from "was never booked";
- do not fabricate booking-state transitions.

## 5. Matching failures

An appointment without a matched visit is not automatically a patient no-show if:
- member identity is missing/changed;
- time fields are inconsistent;
- visit data coverage differs from appointment coverage;
- one source has an extraction gap.

Track unmatched rates and surface suspicious coverage problems.

## 6. Date-range alignment

Compare sources over aligned analysis periods.

If appointments cover dates not present in the visit export, those dates must not silently inflate no-show rates.

## 7. One-off schedule changes

Absences, daily changes, and exceptional openings should not be learned as the recurring baseline.

## 8. Specialty policy

The recommendation constraint for oncology, geriatrics, and other centrally governed specialties is in `04_BUSINESS_RULES_AND_CONSTRAINTS.md`. Do not optimize those calendars from local behavior alone.

## 9. Preference-type overrides

A booked appointment that differs from the configured mechanism (התאמה, הגבלה, or למעט), including when that mechanism is an העדפה מרובה over several visit types, does not necessarily mean corrupted data. Authorized clinic users may override practical placement.

Analyze the configured mechanism, the visit types in the group, and observed behavior separately. Do not compare the word מרובה to a visit-type name and record the mismatch as 0% compliance.

## 10. Unknown categorical codes

Facility codes, booking-center codes, statuses, or reason codes should remain opaque categories unless a validated mapping is available.

Never guess their meaning from the numeric/code value.

## 11. Sparse data

Do not create precise recurring recommendations from a tiny number of observations.

When evidence is weak, prefer:
- no recommendation;
- an insight;
- a business-validation flag;
- a broader/non-exclusive suggestion.

## 12. Conflicting evidence

When sources disagree in a way that changes the recommendation, do not hide the contradiction. Route it to validation or downgrade confidence.

## 13. Data anonymization

Member identifiers used for analysis may be replaced with stable synthetic identifiers. Referential consistency across appointments and visits is more important than preserving the real identifier.

Anonymization must preserve the ability to match the same member across relevant sources.
