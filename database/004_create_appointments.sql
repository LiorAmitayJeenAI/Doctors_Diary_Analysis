BEGIN;

CREATE TABLE appointments (
    appointment_id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doctor_calendar_id             BIGINT NOT NULL REFERENCES doctor_calendars (doctor_calendar_id),
    source_national_id             VARCHAR NOT NULL,
    source_facility_code           VARCHAR NOT NULL,
    source_role_code               VARCHAR NOT NULL,
    appointment_date               VARCHAR,
    appointment_time               VARCHAR,
    member_identity_code           VARCHAR,
    member_id                      VARCHAR,
    appointment_type_code          VARCHAR,
    visit_type_code                VARCHAR,
    visit_duration                 INTEGER,
    actual_visit_time              VARCHAR,
    calendar_source                VARCHAR,
    calendar_status                VARCHAR,
    reason_or_preferred_visit_type VARCHAR,
    reason_description             VARCHAR,
    booking_status                 VARCHAR,
    allocated_segments             INTEGER,
    booked_date                    VARCHAR,
    booked_time                    VARCHAR,
    booking_center_code            VARCHAR,
    created_date                   VARCHAR,
    created_time                   VARCHAR,
    record_status                  VARCHAR,
    last_change_date               VARCHAR
);

COMMENT ON TABLE appointments IS
    'נתוני זימון תורים / יומן. כל 24 שדות המקור נשמרים בנפרד, כולל מזהי מקור לצורך traceability.';

COMMENT ON COLUMN appointments.appointment_id IS 'מפתח פנימי של התור.';
COMMENT ON COLUMN appointments.doctor_calendar_id IS 'FK אל doctor_calendars.doctor_calendar_id.';
COMMENT ON COLUMN appointments.source_national_id IS 'ת.ז רופא כפי שהגיעה מקובץ המקור.';
COMMENT ON COLUMN appointments.source_facility_code IS 'מתקן כפי שהגיע מקובץ המקור.';
COMMENT ON COLUMN appointments.source_role_code IS 'תפקיד כפי שהגיע מקובץ המקור.';
COMMENT ON COLUMN appointments.appointment_date IS
    'תאריך התור. פורמט מקור לא ודאי (ערכים ארוזים כגון 1260104); נשמר כ-VARCHAR.';
COMMENT ON COLUMN appointments.appointment_time IS
    'שעת התור. פורמט מקור לא ודאי (ערכים ארוזים כגון 1035); נשמר כ-VARCHAR.';
COMMENT ON COLUMN appointments.member_identity_code IS 'ק.זהות חבר.';
COMMENT ON COLUMN appointments.member_id IS 'ת.ז. חבר.';
COMMENT ON COLUMN appointments.appointment_type_code IS 'סוג תור.';
COMMENT ON COLUMN appointments.visit_type_code IS 'סוג ביקור.';
COMMENT ON COLUMN appointments.visit_duration IS 'משך ביקור בדקות.';
COMMENT ON COLUMN appointments.actual_visit_time IS
    'שעת ביקור בפועל (os). פורמט מקור לא ודאי; נשמר כ-VARCHAR.';
COMMENT ON COLUMN appointments.calendar_source IS 'מקור היומן.';
COMMENT ON COLUMN appointments.calendar_status IS 'מעמד היומן.';
COMMENT ON COLUMN appointments.reason_or_preferred_visit_type IS 'קוד סיבה / סוג ביקור מועדף.';
COMMENT ON COLUMN appointments.reason_description IS 'תאור סיבה.';
COMMENT ON COLUMN appointments.booking_status IS 'סטטוס זימון.';
COMMENT ON COLUMN appointments.allocated_segments IS 'segments — סה"כ הוקצו לתור.';
COMMENT ON COLUMN appointments.booked_date IS
    'תאריך שיבוץ התור. פורמט מקור לא ודאי; נשמר כ-VARCHAR.';
COMMENT ON COLUMN appointments.booked_time IS
    'שעת שיבוץ התור. פורמט מקור לא ודאי; נשמר כ-VARCHAR.';
COMMENT ON COLUMN appointments.booking_center_code IS 'קוד מתקן מוקד זימון.';
COMMENT ON COLUMN appointments.created_date IS
    'יצירה תאריך. פורמט מקור לא ודאי; נשמר כ-VARCHAR.';
COMMENT ON COLUMN appointments.created_time IS
    'שעת יצירה (עמודת שעה השנייה בקובץ המקור). פורמט מקור לא ודאי; נשמר כ-VARCHAR.';
COMMENT ON COLUMN appointments.record_status IS 'רשומה סטטוס.';
COMMENT ON COLUMN appointments.last_change_date IS
    'תאריך שינוי אחרון. פורמט מקור לא ודאי; נשמר כ-VARCHAR.';

COMMIT;
