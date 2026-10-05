# Business Rules and Recommendation Constraints

## Primary recommendation boundary

The recommendation engine optimizes the **configuration of the existing recurring physician calendar**.

Unless an explicit business rule says otherwise:

- preserve existing working days;
- preserve total recurring working time;
- preserve recurrence/frequency;
- stay inside the physician's baseline working windows;
- do not convert exceptional extra work into required recurring hours;
- do not recommend reducing physician hours merely because some periods are underused.

The system can rearrange how capacity is configured **inside** those boundaries.

## Recurring recommendations only

The target output is a recurring calendar design, not a list of one-off date edits.

A recommendation should normally resolve to:
- weekday;
- recurring time window;
- business action;
- relevant visit type/activity where applicable;
- evidence/reason.

One-off absences or daily changes are context, not recurring optimization recommendations.

## Evidence over imitation

Do not simply reproduce current behavior.

Example: if digital/administrative activity currently happens at 10:00, that alone is not enough to recommend 10:00 as the dedicated administrative window.

A stronger recommendation should consider where allocating non-bookable digital/admin time causes the least harm to patient capacity, such as recurring periods with:
- higher no-show/non-actualization;
- recurring unused/free segments;
- lower clinic load;
- supporting evidence of digital/admin work.

## Preserve semantics of settings

- Patient capacity held for inserted appointments or a specific population => a named **עתודה** type (ת-עתודה, ט-עתודה, or עתודה מביטול).
- Non-patient administrative/digital time => **סגירה**.
- Visit-type placement restrictions => a named mechanism: **התאמה**, **הגבלה**, or **למעט**. If the rule covers more than one visit type in the same window, also say **העדפה מרובה** and name those visit types. Do not recommend an unspecified "העדפה", and do not treat מרובה as a visit type.
- Do not substitute one setting for another merely because both block general booking.

## Existing settings matter

Before recommending a new named preference type, named reserve type, or closure in a time window, inspect the existing configuration.

The correct action may be:
- preserve;
- adjust;
- remove/replace;
- flag conflict;
- leave unchanged.

Do not recommend a second overlapping reserve when an existing reserve already represents the same business need.

A well-performing existing setting can itself lead to a recommendation to **keep the current configuration**.

## Preference recommendations

Name the mechanism in every preference recommendation: **התאמה**, **הגבלה**, or **למעט**. When it covers several visit types, call it **העדפה מרובה** and name the visit types. Do not emit a standalone "review the existing preference" recommendation. Mention an existing preference only as context on a concrete action, and only when both the mechanism and the visit types are known.

A concentration pattern does not automatically justify **התאמה** (exclusive placement).

If evidence only supports that a visit type tends to perform well or cluster in an hour, phrase the recommendation as a concentration window (**הגבלה** only when the visit type must stay inside that window, or a non-exclusive concentration when other visit types may share it). Do not recommend **התאמה** unless the evidence supports exclusive placement.

Do not claim the entire hour must be exclusive if the evidence only supports concentration within that hour.

## Inserted appointments and reserve capacity

**תור דחוף** and **תור נדחף** are the same inserted appointment: placed between two appointments without prior booking, and labeled one way or the other in the appointments file.

Keep that appointment distinct from reserve capacity:
- the inserted appointment is observed demand that arrived without a pre-booked slot;
- **עתודה** (named by type: ת-עתודה, ט-עתודה, or עתודה מביטול) is configured capacity still intended for a patient.

## Specialties with external rules

For specialties whose calendars are governed by national/central policy (notably oncology and geriatrics in stakeholder discussions), do not freely optimize away mandated structures. Either:
- apply the known specialty rule; or
- require business validation / exclude from generic recommendations.

## Feasibility

Never recommend a configuration that cannot be represented in the scheduling system.

Recommendations must respect:
- segment granularity;
- visit durations;
- working windows;
- existing visit types;
- named preference mechanism (התאמה, הגבלה, למעט), and העדפה מרובה when that mechanism covers several visit types;
- reserve/closure semantics;
- known permissions/business constraints.

## User-facing communication

Recommendations should:
- be in clear Hebrew;
- avoid internal field names and implementation jargon;
- explain **what should change**, **where**, and **why**;
- distinguish a recommended change from a recommendation to preserve an effective existing setting;
- avoid exposing raw technical codes when a business label exists.
