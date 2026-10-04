BEGIN;

CREATE TABLE doctor_calendars (
    doctor_calendar_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doctor_id          BIGINT NOT NULL REFERENCES doctors (doctor_id),
    facility_code      VARCHAR NOT NULL,
    role_code          VARCHAR NOT NULL,
    CONSTRAINT doctor_calendars_doctor_facility_role_key
        UNIQUE (doctor_id, facility_code, role_code)
);

COMMENT ON TABLE doctor_calendars IS
    'יומן של רופא במתקן ובתפקיד מסוימים. אותו רופא יכול להיות בעל יותר מיומן אחד.';

COMMENT ON COLUMN doctor_calendars.doctor_calendar_id IS 'מפתח פנימי של היומן.';
COMMENT ON COLUMN doctor_calendars.doctor_id IS 'FK אל doctors.doctor_id.';
COMMENT ON COLUMN doctor_calendars.facility_code IS 'קוד מתקן.';
COMMENT ON COLUMN doctor_calendars.role_code IS 'קוד תפקיד.';

COMMIT;
