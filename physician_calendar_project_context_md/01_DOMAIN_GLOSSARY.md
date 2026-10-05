# Domain Glossary

## מערכת זימון תורים

The Maccabi appointment scheduling system in which providers/services are represented and appointments can be scheduled when the provider has a Maccabi calendar or participates through supported calendar-sharing mechanisms.

## ערוצי זימון

Common scheduling/cancellation channels include:

- **מל"ה** — appointments handled by Maccabi's central service representatives.
- **מרכז רפואי / סניף** — scheduling by staff at medical centers/branches.
- **מרפאת רופא** — scheduling by the physician or clinic secretary.
- **דיגיטל – עם סיסמא** — member self-service through authenticated web/mobile channels.
- **IVR** — automated voice scheduling.
- **בוט** — automated bot/robot scheduling.

The booking channel can matter analytically, but a channel is not itself a visit type.

## יומן

A provider calendar based on the physician/provider position defined in SAP and associated with a profession group or institute.

A calendar under examination is identified by three keys, and every source file must carry the same values:

- **קוד מתקן** — facility code;
- **מספר משרה** — job number;
- **ת"ז עובד** — employee ID.

These three keys are the canonical calendar identity. **תפקיד** (role) is not a matching key. Other files in this pack refer here instead of restating the keys.

## יומן מכונה

A calendar created directly in the appointment system, typically under an institute. It is used when a normal provider calendar is not suitable or an additional operational calendar is required. Some provider attributes normally sourced from SAP may not appear.

## לו"ז

The recurring definition of the physician's actual working days and working hours.

Important:
- A physician may not work every week; recurrence/frequency can therefore be part of the schedule.
- The recurring schedule is the baseline boundary for recommendations.
- A future recurring schedule can be defined, but the project should not invent a new employment pattern merely because historical exceptions exist.

## סגמנט

The smallest time slot in the calendar.

Segment size is derived from the common denominator of visit-type durations in the calendar. A logical appointment can consume multiple consecutive segments.

Example: if the segment is 10 minutes and a visit type lasts 20 minutes, one appointment occupies two segments. Analysis must avoid counting those two rows as two appointments.

## סוג ביקור

The business/clinical appointment purpose or appointment name that is booked.

Examples include:
- ביקור רגיל
- ביקור ראשון
- תור טלפוני
- תור וידאו
- many specialty-specific visit types

A label such as תור דחוף in a visit-type field is not a separate concept from **תור נדחף**. See below.

Important:
- A visit type can have calendar-specific duration.
- Different visit types may have different durations.
- The same named visit type can have different durations in different calendars.
- First/return and telephone/video are visit-type semantics/settings, not interchangeable with appointment structural type.

## סוג תור

A structural/operational appointment classification. Keep this separate from **סוג ביקור**.

### תור רגיל
An appointment placed in the normal configured calendar.

### תור נדחף / תור דחוף
The same appointment. It is inserted between two existing appointments without prior booking, and the appointments file classifies it under one of these labels.

Do not treat **דחוף** and **נדחף** as two dimensions. A difference in the column or code is a classification difference for this inserted appointment, not evidence of a different clinical or structural event.

### תור מתווסף
An additional appointment outside the normal fixed schedule that can be exposed automatically to central scheduling/digital channels according to configured logic, commonly when no appointment exists in a defined near-term window.

### תור רציף
Up to several consecutive appointments on the same day.

### תור סדרתי
A series of appointments created at a fixed interval.

### קבוצה
A group appointment in which multiple patients may be associated with the same time slot; may involve one or more providers.

## ביקור

A record of activity that occurred in the clinical system.

For project analysis, visit data is used to understand actualization/completion and actual activity. However, stakeholders noted that documentation practices may occasionally create misleading visit records. Treat the supplied visits source as the operational source of truth unless a stronger validated rule is provided.

## No-show / אי הגעה

A scheduled logical appointment for which there is no matching completed visit under the project's matching rules.

Do not equate every missing match with patient behavior until matching/data-quality issues have been excluded.

## פעילות דיגיטלית / אדמיניסטרטיבית

Work performed by the physician that is not intended to be a patient-bookable appointment slot, such as handling digital prescriptions or other administrative work.

When calendar time is intentionally reserved for this work, the appropriate business concept is generally **סגירה**, not **עתודה**.

## שעות פעילות בפועל מול לו"ז

Historical activity outside the recurring schedule can be informative about pressure or behavior, but it must not automatically redefine the physician's recurring working commitment.
