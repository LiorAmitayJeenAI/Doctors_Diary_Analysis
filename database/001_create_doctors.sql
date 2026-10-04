BEGIN;

CREATE TABLE doctors (
    doctor_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    national_id VARCHAR(9) NOT NULL UNIQUE,
    doctor_name VARCHAR(150) NOT NULL
);

COMMENT ON TABLE doctors IS 'רופאים. מפתח עסקי: תעודת זהות.';

COMMENT ON COLUMN doctors.doctor_id IS 'מפתח פנימי של הרופא.';
COMMENT ON COLUMN doctors.national_id IS 'תעודת זהות רופא.';
COMMENT ON COLUMN doctors.doctor_name IS 'שם הרופא.';

COMMIT;
