# Physician Calendar Analysis — Project Context

This folder is a context pack for Cursor and other coding agents working on the **ניתוח יומני רופאים** project.

## What the project does

The system analyzes a physician's historical calendar behavior and produces evidence-based recommendations for how the physician's **existing recurring calendar configuration** can be organized more effectively for the coming planning horizon.

The intended business objective is to improve calendar utilization and completed patient care within the physician's existing working framework. The system is not intended to renegotiate a physician's employment agreement or arbitrarily change working days/hours.

Historical data is used to understand:
- the physician's recurring working schedule;
- configured calendar settings;
- appointments that were scheduled;
- visits that actually occurred;
- unused capacity and no-shows;
- appointments inserted between two existing appointments without prior booking (דחוף and נדחף, as defined in `01_DOMAIN_GLOSSARY.md`);
- use of reserves (by reserve type) and preferences (by mechanism, and by the visit types when the preference is multiple);
- recurring patterns by weekday and time;
- digital/administrative activity.

The typical analysis looks backward over roughly half a year of available history and creates a forward-looking recurring recommendation, commonly around **20 weeks**.

## Core mental model

Do not treat every row as one appointment. The scheduling system is **segment based**. One logical appointment may occupy several calendar segments.

Keep these concepts separate:

1. **Schedule / לו"ז** — the recurring days and working windows.
2. **Calendar segment / סגמנט** — the smallest time unit in the calendar.
3. **Calendar setting** — a named preference mechanism (העדפה מרובה when it covers several visit types), a named reserve type, closure, etc.
4. **Appointment / תור** — something scheduled for a member.
5. **Visit / ביקור** — evidence that clinical activity actually occurred.
6. **Recommendation** — a proposed recurring calendar configuration supported by historical evidence.

## Hard business principle

Recommendations reorganize capacity inside the existing physician schedule. The canonical boundaries — working days, total recurring hours, and working windows — are in `04_BUSINESS_RULES_AND_CONSTRAINTS.md`.

## Source-of-truth caution

Treat the visits export as operational visit evidence, and do not invent a stronger definition of a true visit than the source supports. The canonical caution is in `06_DATA_QUALITY_AND_EDGE_CASES.md`, under visit record uncertainty.

## Specialty caution

Oncology and geriatrics may follow central calendar rules. The canonical constraint is in `04_BUSINESS_RULES_AND_CONSTRAINTS.md`, under specialties with external rules.

## Where each rule lives

Each rule is written once:

- terms and calendar identity — `01_DOMAIN_GLOSSARY.md`;
- calendar settings — `02_CALENDAR_SETTINGS.md`;
- source files and appointment-to-visit matching — `03_DATA_SOURCES_AND_SEMANTICS.md`;
- recommendation prohibitions — `04_BUSINESS_RULES_AND_CONSTRAINTS.md`;
- how analysis should reason — `05_ANALYSIS_AND_RECOMMENDATION_LOGIC.md`;
- data traps — `06_DATA_QUALITY_AND_EDGE_CASES.md`.

## Language

Business-facing output should be in clear Hebrew and should use the business terminology in this context pack. Internal code can use English identifiers.

## Files in this pack

- `01_DOMAIN_GLOSSARY.md` — canonical business terminology and calendar identity.
- `02_CALENDAR_SETTINGS.md` — calendar configuration semantics.
- `03_DATA_SOURCES_AND_SEMANTICS.md` — what the input datasets mean.
- `04_BUSINESS_RULES_AND_CONSTRAINTS.md` — non-negotiable recommendation rules.
- `05_ANALYSIS_AND_RECOMMENDATION_LOGIC.md` — what good analysis should reason about.
- `06_DATA_QUALITY_AND_EDGE_CASES.md` — traps, ambiguities, and validation rules.
- `07_CURSOR_WORKING_GUIDE.md` — instructions for an AI coding agent working in this repository.
- `08_FLOW_ORCHESTRATOR.md` — live flow `analyzes doctor's schedules`.
- `09_FLOW_INGESTION.md` — live flow `ingestion`.
- `10_FLOW_ANALYTICS.md` — live flow `analytics`.
- `11_FLOW_RECOMMENDATION.md` — live flow `recommendation (1)`.

Files `08` through `11` describe those four live Langflow flows in Hebrew, at component level. They are not a dump of the JSON graph. Files `00` through `07` remain the domain model.
