BEGIN;

CREATE TABLE schedules (
    schedule_id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doctor_calendar_id    BIGINT NOT NULL REFERENCES doctor_calendars (doctor_calendar_id),
    source_national_id    VARCHAR NOT NULL,
    source_facility_code  VARCHAR NOT NULL,
    source_role_code      VARCHAR NOT NULL,
    activity_weekday      VARCHAR,
    morning_from_time     VARCHAR,
    morning_to_time       VARCHAR,
    afternoon_from_time   VARCHAR,
    afternoon_to_time     VARCHAR,
    frequency             VARCHAR,
    note_number           VARCHAR,
    user_name             VARCHAR,
    program_name          VARCHAR,
    created_date          VARCHAR,
    created_time          VARCHAR,
    record_status         VARCHAR,
    receiving_district    VARCHAR,
    last_change_date      VARCHAR
);

COMMENT ON TABLE schedules IS
    'שורות לו״ז מקובץ המקור. ערכי תעודת זהות, מתקן ותפקיד נשמרים גם כאן לצורך traceability.';

COMMENT ON COLUMN schedules.schedule_id IS 'מפתח פנימי של שורת הלו״ז.';
COMMENT ON COLUMN schedules.doctor_calendar_id IS 'FK אל doctor_calendars.doctor_calendar_id.';
COMMENT ON COLUMN schedules.source_national_id IS 'תעודת זהות רופא כפי שהגיעה מקובץ המקור.';
COMMENT ON COLUMN schedules.source_facility_code IS 'קוד מתקן כפי שהגיע מקובץ המקור.';
COMMENT ON COLUMN schedules.source_role_code IS 'קוד תפקיד רופא כפי שהגיע מקובץ המקור.';
COMMENT ON COLUMN schedules.activity_weekday IS 'מרפאת רופא — יום פעילות.';
COMMENT ON COLUMN schedules.morning_from_time IS
    'לפנה"צ משעה. פורמט מקור לא ודאי (ערכים ארוזים כגון 800, 1330); נשמר כ-VARCHAR.';
COMMENT ON COLUMN schedules.morning_to_time IS
    'לפנה"צ עד שעה. פורמט מקור לא ודאי; נשמר כ-VARCHAR.';
COMMENT ON COLUMN schedules.afternoon_from_time IS
    'אחה"צ משעה. פורמט מקור לא ודאי; נשמר כ-VARCHAR.';
COMMENT ON COLUMN schedules.afternoon_to_time IS
    'אחה"צ עד שעה. פורמט מקור לא ודאי; נשמר כ-VARCHAR.';
COMMENT ON COLUMN schedules.user_name IS 'משתמש.';
COMMENT ON COLUMN schedules.program_name IS 'תוכנית.';
COMMENT ON COLUMN schedules.created_date IS
    'יצירה תאריך. פורמט מקור לא ודאי (ערכים ארוזים כגון 1250420); נשמר כ-VARCHAR.';
COMMENT ON COLUMN schedules.created_time IS
    'שעת יצירה. פורמט מקור לא ודאי (ערכים ארוזים כגון 40022); נשמר כ-VARCHAR.';
COMMENT ON COLUMN schedules.record_status IS 'רשומה סטטוס.';
COMMENT ON COLUMN schedules.receiving_district IS 'מחוז קולט.';
COMMENT ON COLUMN schedules.last_change_date IS
    'תאריך שינוי אחרון. פורמט מקור לא ודאי; נשמר כ-VARCHAR.';

COMMIT;
