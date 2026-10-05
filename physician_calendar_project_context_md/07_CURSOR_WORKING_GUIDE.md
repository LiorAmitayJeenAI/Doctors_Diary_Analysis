# Cursor Working Guide

Use this file as behavioral guidance when modifying the project.

## Understand the domain before changing calculations

Before changing a metric, identify whether it operates on:
- segments;
- logical appointments;
- visits;
- recurring schedule windows;
- calendar settings.

Do not mix denominators.

## Preserve canonical distinctions

The pairs that must stay separate are defined in `01_DOMAIN_GLOSSARY.md` and `06_DATA_QUALITY_AND_EDGE_CASES.md`. Calendar-setting names are in `02_CALENDAR_SETTINGS.md`. Do not collapse those distinctions, and do not restate them here.

## Recommendation invariant

The canonical boundaries are in `04_BUSINESS_RULES_AND_CONSTRAINTS.md`: reorganize the recurring calendar inside the existing working schedule. If a requested code change violates that invariant, flag it rather than silently implementing it.

## Use deterministic business logic where possible

The model/LLM should explain and phrase recommendations, but core eligibility should be based on computed evidence and business constraints whenever feasible.

Examples of deterministic checks:
- recommendation window is inside baseline schedule;
- no working-hour change;
- enough recurring evidence;
- no duplicate practical recommendation;
- no overlapping duplicate reserve;
- logical appointments are deduplicated;
- configured setting is resolved before suggesting a conflicting setting.

## Existing settings are first-class context

A recommendation is not generated in an empty calendar.

For every proposed window, ask:
1. Is there already a preference, which mechanism (התאמה, הגבלה, or למעט), and which visit types? If there are several visit types, it is העדפה מרובה.
2. Is there already a reserve, and which type (ת-עתודה, ט-עתודה, or עתודה מביטול)?
3. Is there a closure?
4. What visit type is configured?
5. What actually happened in that window?
6. Should the action preserve, adjust, replace, or conflict with the setting?

## Prefer business labels

User-facing Hebrew should say things such as:
- "עתודה"
- "סגירה"
- "העדפה"
- "תור טלפוני"
- "ביקור רגיל"

Avoid exposing internal enum names, database column names, or opaque codes.

## Recommendation phrasing

Good:
- "מומלץ לתת עדיפות לריכוז תורים טלפוניים ביום שני בין 09:00–10:00, תוך שמירה על גמישות בשאר המשבצות."

Too strong without evidence:
- "יש להקדיש את כל 09:00–10:00 לתורים טלפוניים."

Good for an existing effective setting:
- "מומלץ להשאיר את ההתאמה הקיימת ללא שינוי." Name the actual mechanism and, for העדפה מרובה, the visit types.

## Digital/admin recommendations

Do not merely mirror where digital work currently happens. Choose a window based on opportunity cost and recurring capacity signals.

Administrative/digital time that is not patient-bookable should map to **closure semantics**.

## Tests worth having

At minimum, regression tests should cover:
- multi-segment appointment counted once;
- דחוף and נדחף labels collapse to one inserted-appointment count;
- appointment-to-visit matching does not double-match;
- source date ranges are aligned;
- recommendation never leaves baseline working window;
- total recurring working time is unchanged;
- overlapping existing reserve is adjusted rather than duplicated;
- a fully effective existing preference can produce "keep" rather than "change", and the wording names the mechanism and visit types; a standalone preference review is not a recommendation;
- telephone modality + telephone visit type in the same window are not duplicated in final presentation;
- a one-off absence does not become a recurring recommendation.

## When requirements are ambiguous

Prefer domain safety over aggressive optimization.

If a business term is unclear, consult `01_DOMAIN_GLOSSARY.md` rather than guessing from field names or current sample values.

## What this context pack does not define

Files `00` through `07` deliberately do not document:
- Langflow node graphs;
- component IDs;
- JSON workflow structure;
- API wiring;
- database implementation details.

Files `08` through `11` describe the four live flows at component level. Those descriptions can change when the graphs change, without changing the domain model in `00` through `07`.
