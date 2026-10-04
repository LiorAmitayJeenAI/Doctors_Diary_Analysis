BEGIN;

ALTER TABLE schedules
    ADD COLUMN analysis_run_id BIGINT REFERENCES analysis_runs (analysis_run_id);

ALTER TABLE appointments
    ADD COLUMN analysis_run_id BIGINT REFERENCES analysis_runs (analysis_run_id);

ALTER TABLE visits
    ADD COLUMN analysis_run_id BIGINT REFERENCES analysis_runs (analysis_run_id);

COMMENT ON COLUMN schedules.analysis_run_id IS
    'FK אל analysis_runs.analysis_run_id. Nullable עד ל-backfill של שורות קיימות.';
COMMENT ON COLUMN appointments.analysis_run_id IS
    'FK אל analysis_runs.analysis_run_id. Nullable עד ל-backfill של שורות קיימות.';
COMMENT ON COLUMN visits.analysis_run_id IS
    'FK אל analysis_runs.analysis_run_id. Nullable עד ל-backfill של שורות קיימות.';

COMMIT;

-- analysis_run_id is nullable because existing source rows may have no run.
-- After every row is assigned a run, a later migration can:
--   ALTER TABLE schedules    ALTER COLUMN analysis_run_id SET NOT NULL;
--   ALTER TABLE appointments ALTER COLUMN analysis_run_id SET NOT NULL;
--   ALTER TABLE visits       ALTER COLUMN analysis_run_id SET NOT NULL;
--
-- Example backfill (only if there is already source data):
--   1. INSERT INTO analysis_runs (doctor_calendar_id, status)
--      SELECT DISTINCT doctor_calendar_id, 'COMPLETED'
--      FROM (
--          SELECT doctor_calendar_id FROM schedules
--          UNION
--          SELECT doctor_calendar_id FROM appointments
--          UNION
--          SELECT doctor_calendar_id FROM visits
--      ) existing;
--   2. UPDATE schedules s
--      SET analysis_run_id = r.analysis_run_id
--      FROM analysis_runs r
--      WHERE r.doctor_calendar_id = s.doctor_calendar_id
--        AND s.analysis_run_id IS NULL;
--      Repeat analogously for appointments and visits.
-- If the source tables are empty, skip backfill and only SET NOT NULL later.
