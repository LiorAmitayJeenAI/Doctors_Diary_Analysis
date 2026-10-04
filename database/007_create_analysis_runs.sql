BEGIN;

CREATE TABLE analysis_runs (
    analysis_run_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doctor_calendar_id   BIGINT NOT NULL REFERENCES doctor_calendars (doctor_calendar_id),
    analysis_period_from DATE,
    analysis_period_to   DATE,
    status               VARCHAR(40) NOT NULL,
    created_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at         TIMESTAMP
);

COMMENT ON TABLE analysis_runs IS
    'הרצת ניתוח אחת: העלאת לו״ז, תורים וביקורים עבור יומן מסוים.';

COMMENT ON COLUMN analysis_runs.analysis_run_id IS 'מפתח פנימי של הרצת הניתוח.';
COMMENT ON COLUMN analysis_runs.doctor_calendar_id IS 'FK אל doctor_calendars.doctor_calendar_id.';
COMMENT ON COLUMN analysis_runs.analysis_period_from IS
    'תחילת תקופת הניתוח. יכול להיות NULL עד שהתקופה מחושבת.';
COMMENT ON COLUMN analysis_runs.analysis_period_to IS
    'סוף תקופת הניתוח. יכול להיות NULL עד שהתקופה מחושבת.';
COMMENT ON COLUMN analysis_runs.status IS
    'סטטוס הרצה ברמת האפליקציה, למשל VALIDATING, LOADING, ANALYZING, GENERATING_RECOMMENDATIONS, COMPLETED, FAILED. אין CHECK קשיח.';
COMMENT ON COLUMN analysis_runs.created_at IS 'מועד יצירת ההרצה.';
COMMENT ON COLUMN analysis_runs.completed_at IS 'מועד סיום ההרצה. NULL כל עוד לא הושלמה.';

COMMIT;
