# Analysis and Recommendation Logic

Canonical recommendation boundaries are in `04_BUSINESS_RULES_AND_CONSTRAINTS.md`. This document describes the reasoning the project should support, not a specific implementation.

## Baseline first

Before calculating recommendations, establish:
- active weekdays;
- working windows per weekday;
- recurrence/frequency;
- segment size;
- associated visit types and durations;
- existing preferences (mechanism התאמה, הגבלה, or למעט; העדפה מרובה when several visit types share that mechanism), reserve types (ת-עתודה, ט-עתודה, עתודה מביטול), and closures.

All later analysis should be interpreted relative to this baseline.

## Logical appointment reconstruction

Calendar exports are segment-level.

Before appointment KPIs:
1. identify rows belonging to the same logical appointment;
2. collapse them into one appointment;
3. retain the total occupied duration/segments;
4. preserve visit type, appointment type, member, date/time, and relevant settings.

Failure to do this inflates counts for longer appointments.

## Actualization

For each logical scheduled appointment, determine whether a compatible visit occurred.

Useful outputs:
- scheduled appointments;
- matched/completed visits;
- no-show/non-actualization rate;
- actualization by weekday/hour;
- actualization by visit type;
- actualization for inserted appointments (דחוף/נדחף labels) and for each reserve type;
- delay from planned appointment time to actual visit start when valid.

## Capacity and free time

Analyze recurring capacity by weekday/time:
- total available segments;
- booked segments;
- unused/free segments;
- closure/admin segments;
- reserve segments;
- utilization rate.

Recurring unused capacity is more actionable than a single quiet date.

## Visit-type allocation

Look for stable patterns in which particular visit types:
- are repeatedly booked in certain weekday/time windows;
- actualize well in those windows;
- fit operationally within the segment structure;
- can be concentrated without violating existing settings.

The goal is not necessarily exclusivity. Often the right recommendation is to give a visit type **priority/concentration** in a window while leaving the clinic flexibility over the exact segment split.

## Telephone/video activity

Telephone/video modality can overlap conceptually with a named visit type such as **תור טלפוני**.

Do not create duplicate client-facing recommendations for the same practical action in the same time window. Combine supporting evidence when the business intent is the same.

## Digital/administrative allocation

When recommending non-bookable time for digital/admin work, evaluate:
- historical digital/admin activity;
- recurring free capacity;
- no-show patterns;
- relative workload;
- patient-demand opportunity cost.

The best window is not automatically the window with the most historical digital work.

## Inserted appointments and reserve capacity

Treat דחוף and נדחף as one inserted-appointment population. Analyze:
- how often these appointments are inserted between booked appointments, by weekday and time;
- current reserve capacity by reserve type (ת-עתודה, ט-עתודה, עתודה מביטול);
- reserve utilization and whether those slots actualize;
- recurring hours where inserted demand exceeds the existing reserve.

Potential recommendation:
- preserve an effective reserve of a named type;
- adjust the location or amount of an existing reserve of that type;
- introduce a named reserve type only when evidence supports a recurring need and no equivalent reserve already overlaps.

## Existing preference performance

For each preference window, name the mechanism first (התאמה, הגבלה, or למעט). If several visit types share it, call it העדפה מרובה and list those visit types. Then:
- resolve the configured visit type(s);
- inspect the actual booked visit-type mix;
- assess compliance against those visit types under that mechanism;
- assess utilization/actualization;
- determine whether that setting is helping.

A label of מרובה without a mechanism and without visit types is not a compliance measurement. Do not turn it into a recommendation. If the same preference covers every working hour of a weekday, describe it once for that day, not once per hour.

If that setting is fully followed and works well, a concrete recommendation may say to preserve it. Do not restate the recommendation as a generic preference, and do not emit a standalone review of the preference.

## Trend and recurrence

Recommendations should rely on recurring evidence, not isolated anomalies.

Prefer patterns that:
- appear across multiple weeks;
- are consistent by weekday/time;
- have enough observations to be meaningful;
- are not explained solely by absences or temporary schedule changes.

## Planning horizon

The project commonly plans roughly **20 weeks forward**. Historical evidence can cover around six months, with emphasis on the most recent relevant data when business rules require it.

The recommendation is a recurring template for the future horizon, not a prediction of exact patient arrivals.
