BEGIN;

CREATE TABLE visits (
    visit_id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doctor_calendar_id         BIGINT NOT NULL REFERENCES doctor_calendars (doctor_calendar_id),
    emp_name                   VARCHAR,
    position_code              VARCHAR,
    org_unit_facility_desc     VARCHAR,
    customer_id                VARCHAR,
    payment_group_desc         VARCHAR,
    weekday_name               VARCHAR,
    encounter_date             DATE,
    encounter_start_datetime   TIMESTAMP,
    hr_emp_key_pk              VARCHAR
);

COMMENT ON TABLE visits IS
    'ביקורים מקובץ המקור. משויכים ליומן (doctor_calendar_id) ולא ישירות לרופא.';

COMMENT ON COLUMN visits.visit_id IS 'מפתח פנימי של הביקור.';
COMMENT ON COLUMN visits.doctor_calendar_id IS 'FK אל doctor_calendars.doctor_calendar_id.';
COMMENT ON COLUMN visits.emp_name IS 'EMP_NAME — שם הרופא בקובץ הביקורים.';
COMMENT ON COLUMN visits.position_code IS
    'POSITION_CODE — קוד תפקיד/משרה בקובץ הביקורים. אינו זהה ל-role_code בלו״ז ובתורים.';
COMMENT ON COLUMN visits.org_unit_facility_desc IS 'ORG_UNIT_FACILITY_DESC — תיאור מתקן.';
COMMENT ON COLUMN visits.customer_id IS 'CUSTOMER_ID — מזהה מטופל.';
COMMENT ON COLUMN visits.payment_group_desc IS 'PAYMENT_GROUP_DESC — קבוצת תשלום / סוג מפגש.';
COMMENT ON COLUMN visits.weekday_name IS 'יום בשבוע.';
COMMENT ON COLUMN visits.encounter_date IS
    'ENCOUNTER_DATE. בקובץ המקור ערכי Excel datetime תקינים; נשמר כ-DATE.';
COMMENT ON COLUMN visits.encounter_start_datetime IS
    'ENCOUNTER_START_DATETIME. בקובץ המקור ערכי Excel datetime תקינים; נשמר כ-TIMESTAMP ללא אזור זמן.';
COMMENT ON COLUMN visits.hr_emp_key_pk IS 'HR_EMP_KEY_PK — מפתח עובד במערכת HR.';

COMMIT;
