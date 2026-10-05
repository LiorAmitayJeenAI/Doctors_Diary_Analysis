# Calendar Settings and Their Semantics

## סגירה

A **closure** blocks calendar segments that are not intended for member appointment booking.

Typical uses:
- partial absence;
- administrative work;
- digital prescription handling;
- team meeting;
- break;
- telephone consultation work that is not a bookable member appointment;
- machine-calendar operational closure.

Key distinction: a closure represents time **not intended for a patient appointment**.

## עתודה

A **reserve** keeps appointment capacity for restricted use, mainly by a medical center/clinic/authorized operational unit and often for demand that arrives without a pre-booked slot.

A reserve is not a closure. The slot is still intended for a patient. Name the reserve type whenever the setting is discussed or recommended. The types in this project are:

- **ת-עתודה** — after cancellation, the slot becomes a normal open slot.
- **ט-עתודה** — after cancellation, the slot returns to reserve.
- **עתודה מביטול** — a canceled slot retained as reserve capacity.

**ס-סגירה** is not one of these types. It is a closure. See below.

Reserved slots are still intended for patient care, but are not exposed like ordinary open slots to all booking channels.

### ת-עתודה

After a patient is booked into a ת-עתודה slot and later cancels, the slot becomes a normal open slot and can become available to broader booking channels.

### ט-עתודה

After cancellation, the slot returns to its original reserve state.

This can create utilization risk when cancellation occurs close to the appointment time because the slot may remain restricted and go unused.

Access to ט-עתודה can be configured for particular operational centers.

### עתודה מביטול

A canceled appointment slot can be converted/retained as reserve capacity for clinic use, subject to the relevant provider/visit-type settings.

### ס-סגירה

Technically behaves similarly to reserve mechanics in some system contexts but is intended as a rapid way to close open scheduling slots. Business meaning remains closure, not patient reserve.

## עתודה vs סגירה

Use a named **עתודה** type when the slot is still intended for a member/patient, including demand that arrives as an inserted appointment (דחוף/נדחף).

Use **סגירה** when the slot is not intended for a member appointment.

This distinction is fundamental. Do not recommend "reserve" for administrative work.

## העדפה

A **preference** constrains where selected visit types can be booked. Always name the type. "העדפה" alone is not a recommendation.

Only use or recommend a named mechanism when the calendar has more than one visit type and the operational requirement is understood across the relevant days/hours.

The placement mechanisms are **התאמה**, **הגבלה**, and **למעט**. Do not mix mechanisms casually in the same calendar. **העדפה מרובה** is not a fourth mechanism.

### התאמה

Inside the preference window, only the selected visit type(s) may be booked.

The selected visit type(s) also cannot be booked outside that defined preference window.

This is the strongest/exclusive placement model.

Typical use: precisely controlling the number/location of new-patient appointments.

### הגבלה

The selected visit type(s) may be booked only inside the preference window, but other calendar visit types may also be booked inside that window.

The selected visit type(s) cannot be booked outside the preference window.

### למעט

Inside the preference window, all associated visit types may be booked **except** the excluded selected visit type(s).

Outside the window, the excluded visit type(s) can be booked normally.

## העדפה מרובה

**העדפה מרובה** means one preference applies to more than one visit type in the same time window, instead of to a single visit type.

It is not another kind of preference. The group still uses one placement mechanism: **התאמה**, **הגבלה**, or **למעט**. The only difference from an ordinary preference is that the same rule covers several visit types together.

Example: a calendar has ביקור רגיל, תור טלפוני, תור וידאו, and ביקור ראשון. To reserve 09:00–10:00 for both תור טלפוני and תור וידאו, define one multiple preference for those two visit types in that window rather than two separate preferences.

- Multiple preference with **התאמה** for תור טלפוני + תור וידאו at 09:00–10:00: only those two visit types may be booked inside the window, and those two visit types also cannot be booked outside it.
- Multiple preference with **הגבלה** for the same pair: those two visit types must be booked inside 09:00–10:00, but other visit types may still be booked inside that window.

A label of **מרובה** by itself is not a visit type and is not enough to judge compliance or to recommend a change. Compliance is judged against the visit types in the group, under the named mechanism. If the source only says מרובה and does not identify the mechanism and the visit types, do not treat that as 0% compliance and do not emit a preference recommendation.

## Important override behavior

Operational users with sufficient authority may sometimes place an appointment that does not follow the apparent preference pattern. Therefore:
- a configured preference type describes calendar policy;
- actual booked mix describes observed behavior;
- non-compliance is analytically meaningful but does not necessarily prove the setting is technically broken.

## שינוי יומי

A one-time change to the physician/provider's recurring schedule, used when a specific day's working hours are shortened or extended.

When defining a daily change, the relevant range represents the full working hours for that day, not merely the delta.

A one-time daily change is not a recurring recommendation.

## היעדרות

A full or partial absence.

Full-day absence is normally represented through the appropriate absence mechanism rather than merely closing all slots, because proper absence can affect system indication and service-directory visibility.

Partial absence can be represented through closure or daily change according to the business case.

## גודל יומן בשבועות

How many weeks forward the calendar is opened.

The business recommendation is commonly around **20 weeks**, but the appropriate value depends on appointment availability and operational needs. A larger horizon can make calendar refresh heavier.

## ריענון יומן

Calendar configuration changes require refresh before they are reflected operationally. Refresh is an implementation/operations concern; recommendations should describe the desired business configuration rather than pretending the change is active before refresh.
