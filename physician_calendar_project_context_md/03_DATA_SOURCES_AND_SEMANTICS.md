# Data Sources and Semantics

The project relies on three main information families. Exact export column names can vary and should be normalized before analysis.

## Calendar identity

A calendar under examination is one **קוד מתקן**, one **מספר משרה**, and one **ת"ז עובד**, as defined in `01_DOMAIN_GLOSSARY.md`.

The schedule, appointments, and visits files must agree on all three keys. Header names differ between raw exports and processed files; this pack does not list those aliases.

Appointment-to-visit matching, later in this file, is a separate check.

## 1. Schedule / לו"ז source

Purpose: establish the physician's recurring baseline working pattern.

Conceptually contains:
- the three calendar-identity keys;
- weekday;
- morning start/end;
- afternoon start/end when applicable;
- recurrence/frequency;
- metadata about creation/update.

Use it to determine the hard recurring working windows.

Do not infer the recurring schedule solely from appointment activity.

## 2. Appointments / calendar source

Purpose: represent the calendar at segment level, including booked appointments and calendar configuration.

Typical semantics include:
- the three calendar-identity keys;
- appointment date/time;
- member identity;
- appointment type (**סוג תור**);
- visit type (**סוג ביקור**);
- visit duration;
- actual visit-start field when available in the export;
- calendar source;
- calendar status;
- reason/preferred visit-type code;
- booking status;
- number of segments allocated to the appointment;
- booking timestamp;
- booking-center code;
- creation/update metadata.

### Critical rule: segment rows are not logical appointments

One logical appointment may occupy multiple segment rows.

Use the appointment's identifying fields and allocated-segment semantics to reconstruct a logical appointment before computing counts, rates, no-shows, visit-type distribution, urgent demand, etc.

### Calendar status / מעמד היומן

The appointment/calendar export can contain rows that represent configuration rather than a booked patient appointment.

Examples can include:
- closure;
- preference;
- open/free slot;
- reserve-related states;
- substitute physician contexts.

A row without a member identity may therefore still be meaningful calendar configuration.

### Calendar source / מקור היומן

This can indicate whether a segment originates from the recurring schedule or was inserted between two appointments without prior booking. Labels such as דחוף and נדחף in the appointments file are classifications of that same inserted appointment. Do not analyze them as separate phenomena.

## 3. Visits / ביקורים source

Purpose: represent activity that occurred in practice.

It is used to:
- determine whether scheduled appointments actualized;
- estimate no-show/non-actualization;
- measure actual workload;
- compare planned appointment time with actual visit start;
- inspect activity inside/outside the recurring schedule.

The project should match **appointments to visits**, not invert the analysis from visits to appointments. The appointment population is the denominator when asking what happened to scheduled demand.

## Appointment-to-visit matching

This check is separate from calendar identity. The three files already agree on facility code, job number, and employee ID.

Matching a scheduled appointment to a visit uses:
- member identity;
- date;
- compatible time/visit context.

Exact matching logic must tolerate known source behavior and should avoid double-matching one visit to multiple logical appointments.

A missing match can mean no-show, but can also mean imperfect data/matching. Keep data-quality warnings separate from business conclusions.

## Visit type dictionary

A separate visit-type reference file maps visit-type codes to human-readable descriptions. Use the business description in user-facing output.

Do not expose opaque visit-type codes when a resolved Hebrew name is available.

## Booking-center code

The booking-center/facility code can be used as a categorical data point to analyze where appointments were scheduled from. Do not invent the meaning of an unknown code without a validated lookup.

## Historical vs current calendar state

Some exports represent what currently remains in the calendar rather than a full historical event log. That means cancellations or overwritten states may not always be reconstructable from the calendar snapshot alone.

Do not claim cancellation history unless the source actually supports it.
